# functions/orchestrator.py
"""
MVP Durable Functions Orchestrator
Handles multi-species ETL with retry, monitoring, and state management

ARCHITECTURAL DECISION AD-002:
Durable Functions for MVP (evaluate ADF for Final Product)
Volatility: LOW
Re-work Impact: LOW (ETL layer isolation)
"""

import azure.functions as func
import azure.durable_functions as df
from datetime import datetime, timedelta
from pytz import timezone
import json
import logging

app = df.DFApp(http_auth_level=func.AuthLevel.FUNCTION)

# Retry configuration
RETRY_OPTIONS = df.RetryOptions(
    first_retry_interval_in_milliseconds=5000,
    max_number_of_attempts=3,
    backoff_coefficient=2,
    max_retry_interval_in_milliseconds=60000,
    retry_timeout_in_milliseconds=300000
)

@app.timer_trigger(schedule="0 */15 * * * *", arg_name="timer")
@app.durable_client_input(client_name="client")
async def timer_orchestration_trigger(timer: func.TimerRequest, client):
    """
    Trigger orchestration every 15 minutes during business hours
    MVP: Supports multiple species routing
    """
    est = timezone('US/Eastern')
    now = datetime.now(est)
    
    # Business hours check
    is_business_hours = (
        now.weekday() < 5 and
        9 <= now.hour < 17 and
        not is_company_holiday(now.date())
    )
    
    if not is_business_hours:
        logging.info(f"Skipping sync - outside business hours: {now}")
        return {"status": "skipped", "reason": "outside_business_hours"}
    
    # Start orchestration for each species
    instance_ids = {}
    for species in ['poultry', 'swine']:  # Add more as needed
        instance_id = await client.start_new(
            "orchestrator_species_sync",
            client_input={'species': species, 'trigger_time': now.isoformat()}
        )
        instance_ids[species] = instance_id
        logging.info(f"Started orchestration for {species}: {instance_id}")
    
    return {
        "status": "started",
        "instance_ids": instance_ids,
        "timestamp": now.isoformat()
    }


@app.orchestration_trigger(context_name="context")
def orchestrator_species_sync(context: df.DurableOrchestrationContext):
    """
    Main orchestration workflow for single species
    Implements fan-out parallelization with checkpointing
    """
    
    input_data = context.get_input()
    species = input_data['species']
    
    logging.info(f"Starting orchestration for species: {species}")
    
    # Step 1: Get changed files from SharePoint (with retry)
    changed_files = yield context.call_activity_with_retry(
        "activity_get_changed_files",
        RETRY_OPTIONS,
        species
    )
    
    if not changed_files:
        logging.info(f"No changes detected for {species}")
        return {"species": species, "processed": 0, "status": "no_changes"}
    
    # Step 2: Fan-out document processing (max 100 parallel)
    processing_tasks = []
    for file_info in changed_files:
        task = context.call_activity_with_retry(
            "activity_process_document",
            RETRY_OPTIONS,
            {
                'file_info': file_info,
                'species': species
            }
        )
        processing_tasks.append(task)
    
    # Wait for all tasks (with automatic checkpointing)
    processing_results = yield context.task_all(processing_tasks)
    
    # Step 3: Collect successful chunks
    all_chunks = []
    failed_files = []
    
    for result in processing_results:
        if result['status'] == 'success':
            all_chunks.extend(result['chunks'])
        else:
            failed_files.append(result)
    
    # Step 4: Batch upload to Azure AI Search (100 docs per batch)
    upload_tasks = []
    for i in range(0, len(all_chunks), 100):
        batch = all_chunks[i:i+100]
        task = context.call_activity_with_retry(
            "activity_batch_upload_search",
            RETRY_OPTIONS,
            {
                'chunks': batch,
                'species': species,
                'index_name': f"{species}-nutrition-index"
            }
        )
        upload_tasks.append(task)
    
    upload_results = yield context.task_all(upload_tasks)
    
    # Step 5: Update sync state (delta token, checksums)
    yield context.call_activity(
        "activity_update_sync_state",
        {
            'species': species,
            'processed_files': len(changed_files),
            'successful_chunks': len(all_chunks),
            'failed_files': failed_files,
            'last_file': changed_files[-1] if changed_files else None
        }
    )
    
    # Step 6: Send failed files to dead letter queue
    if failed_files:
        yield context.call_activity(
            "activity_send_to_dlq",
            failed_files
        )
    
    return {
        "species": species,
        "processed_files": len(changed_files),
        "successful_chunks": len(all_chunks),
        "failed_files": len(failed_files),
        "status": "completed"
    }


def is_company_holiday(date):
    """Check if date is a company holiday"""
    # TODO: Integrate with company calendar system
    holidays = [
        # 2025 US Holidays
        '2025-01-01',  # New Year's
        '2025-05-26',  # Memorial Day
        '2025-07-04',  # Independence Day
        '2025-09-01',  # Labor Day
        '2025-11-27',  # Thanksgiving
        '2025-12-25',  # Christmas
    ]
    return date.isoformat() in holidays

# functions/activities.py
"""
Durable Functions Activities
Individual processing steps with error handling
"""

import azure.functions as func
import azure.durable_functions as df
from azure.storage.blob import BlobServiceClient
from azure.data.tables import TableServiceClient
from azure.identity import DefaultAzureCredential
from msgraph import GraphServiceClient
import io
import zipfile
import logging
from typing import List, Dict

app = df.DFApp()

@app.activity_trigger(input_name="species")
async def activity_get_changed_files(species: str) -> List[Dict]:
    """
    Get changed files from SharePoint using Microsoft Graph Delta Query
    
    ARCHITECTURAL DECISION: Microsoft Graph API over SharePoint REST
    - 1-2 resource units vs unpredictable REST costs
    - Delta queries for incremental sync
    - Managed Identity authentication
    """
    
    credential = DefaultAzureCredential()
    graph_client = GraphServiceClient(credential)
    
    # Get SharePoint site and drive for species
    site_config = get_species_sharepoint_config(species)
    site_id = site_config['site_id']
    drive_id = site_config['drive_id']
    
    # Load last delta token from Table Storage
    delta_token = load_delta_token(species)
    
    # Execute delta query
    delta_url = f"/sites/{site_id}/drives/{drive_id}/root/delta"
    
    if delta_token:
        # Incremental sync
        response = await graph_client.get(f"{delta_url}?token={delta_token}")
    else:
        # Initial sync
        response = await graph_client.get(delta_url)
    
    # Filter to actual files (not folders)
    changed_files = []
    for item in response.value:
        if 'file' in item and not item.get('deleted'):
            changed_files.append({
                'id': item['id'],
                'name': item['name'],
                'url': item['@microsoft.graph.downloadUrl'],
                'modified': item['lastModifiedDateTime'],
                'size': item['size'],
                'species': species,
                'sharepoint_url': item['webUrl']
            })
    
    # Save new delta token
    if hasattr(response, 'odata_delta_link'):
        new_token = response.odata_delta_link.split('token=')[1]
        save_delta_token(species, new_token)
    
    logging.info(f"Found {len(changed_files)} changed files for {species}")
    return changed_files


@app.activity_trigger(input_name="input_data")
async def activity_process_document(input_data: Dict) -> Dict:
    """
    Complete document processing pipeline:
    1. Download from SharePoint
    2. Extract nested zips
    3. Process multi-format documents
    4. Chunk text
    5. Generate embeddings
    6. Store in blob storage (intermediate layer)
    """
    
    file_info = input_data['file_info']
    species = input_data['species']
    
    try:
        # Download file
        file_data = await download_file(file_info['url'])
        
        # Save to intermediate blob storage
        blob_service = BlobServiceClient(
            account_url=os.environ['STORAGE_ACCOUNT_URL'],
            credential=DefaultAzureCredential()
        )
        container_client = blob_service.get_container_client('intermediate-files')
        
        blob_name = f"{species}/{file_info['id']}/{file_info['name']}"
        container_client.upload_blob(blob_name, file_data, overwrite=True)
        
        # Handle ZIP files recursively
        if file_info['name'].lower().endswith('.zip'):
            extractor = NestedZipExtractor(max_depth=10)
            extracted_files = extractor.extract_nested_zip_memory(file_data)
        else:
            extracted_files = [{'name': file_info['name'], 'data': file_data}]
        
        # Process each extracted file
        all_chunks = []
        processor = UniversalDocumentProcessor()
        
        for extracted in extracted_files:
            # Extract text based on file type
            text = processor.process_document_from_bytes(
                extracted['data'],
                extracted['name']
            )
            
            # Chunk text (512 tokens, 50 overlap)
            chunks = chunk_text_with_metadata(
                text=text,
                chunk_size=512,
                overlap=50,
                metadata={
                    'source_file': file_info['name'],
                    'document_title': extract_title(text, file_info['name']),
                    'species': species,
                    'study_date': file_info['modified'],
                    'sharepoint_url': file_info['sharepoint_url']
                }
            )
            
            # Generate embeddings in batches of 16
            embeddings = await generate_embeddings_batch(
                [chunk['content'] for chunk in chunks],
                batch_size=16
            )
            
            # Combine chunks with embeddings
            for chunk, embedding in zip(chunks, embeddings):
                chunk['chunk_vector'] = embedding
                chunk['chunk_id'] = generate_chunk_id(file_info, chunk)
                all_chunks.append(chunk)
        
        logging.info(f"Processed {file_info['name']}: {len(all_chunks)} chunks")
        
        return {
            'status': 'success',
            'file_id': file_info['id'],
            'file_name': file_info['name'],
            'chunks': all_chunks
        }
        
    except Exception as e:
        logging.error(f"Failed to process {file_info['name']}: {str(e)}")
        return {
            'status': 'failed',
            'file_id': file_info['id'],
            'file_name': file_info['name'],
            'error': str(e),
            'error_type': type(e).__name__
        }


@app.activity_trigger(input_name="input_data")
async def activity_batch_upload_search(input_data: Dict) -> Dict:
    """
    Upload batch of chunks to Azure AI Search
    """
    from azure.search.documents import SearchClient
    
    chunks = input_data['chunks']
    species = input_data['species']
    index_name = input_data['index_name']
    
    search_client = SearchClient(
        endpoint=os.environ['SEARCH_ENDPOINT'],
        index_name=index_name,
        credential=DefaultAzureCredential()
    )
    
    # Upload batch (max 100 docs per request)
    result = search_client.upload_documents(documents=chunks)
    
    successful = sum(1 for r in result if r.succeeded)
    failed = len(result) - successful
    
    logging.info(f"Uploaded {successful}/{len(chunks)} chunks to {index_name}")
    
    return {
        'index_name': index_name,
        'total': len(chunks),
        'successful': successful,
        'failed': failed
    }


@app.activity_trigger(input_name="sync_state")
async def activity_update_sync_state(sync_state: Dict):
    """Update sync state in Table Storage"""
    
    table_service = TableServiceClient(
        endpoint=os.environ['STORAGE_ACCOUNT_URL'],
        credential=DefaultAzureCredential()
    )
    
    table_client = table_service.get_table_client('syncstate')
    
    entity = {
        'PartitionKey': sync_state['species'],
        'RowKey': datetime.utcnow().isoformat(),
        'processed_files': sync_state['processed_files'],
        'successful_chunks': sync_state['successful_chunks'],
        'failed_files_count': len(sync_state['failed_files']),
        'timestamp': datetime.utcnow()
    }
    
    table_client.upsert_entity(entity)
    logging.info(f"Updated sync state for {sync_state['species']}")


@app.activity_trigger(input_name="failed_files")
async def activity_send_to_dlq(failed_files: List[Dict]):
    """Send failed files to Dead Letter Queue"""
    from azure.servicebus import ServiceBusClient, ServiceBusMessage
    
    servicebus_client = ServiceBusClient(
        os.environ['SERVICEBUS_CONNECTION_STRING']
    )
    
    with servicebus_client:
        sender = servicebus_client.get_queue_sender(queue_name="document-dlq")
        with sender:
            messages = [
                ServiceBusMessage(json.dumps(failed_file))
                for failed_file in failed_files
            ]
            sender.send_messages(messages)
    
    logging.warning(f"Sent {len(failed_files)} failed files to DLQ")


# Helper functions

def get_species_sharepoint_config(species: str) -> Dict:
    """Get SharePoint configuration for species"""
    # TODO: Load from configuration service or Key Vault
    configs = {
        'poultry': {
            'site_id': os.environ['SHAREPOINT_POULTRY_SITE_ID'],
            'drive_id': os.environ['SHAREPOINT_POULTRY_DRIVE_ID']
        },
        'swine': {
            'site_id': os.environ['SHAREPOINT_SWINE_SITE_ID'],
            'drive_id': os.environ['SHAREPOINT_SWINE_DRIVE_ID']
        }
    }
    return configs.get(species, {})


def load_delta_token(species: str) -> str:
    """Load delta token from Table Storage"""
    table_service = TableServiceClient(
        endpoint=os.environ['STORAGE_ACCOUNT_URL'],
        credential=DefaultAzureCredential()
    )
    
    table_client = table_service.get_table_client('deltatokens')
    
    try:
        entity = table_client.get_entity(
            partition_key=species,
            row_key='current'
        )
        return entity.get('token', '')
    except:
        return ''


def save_delta_token(species: str, token: str):
    """Save delta token to Table Storage"""
    table_service = TableServiceClient(
        endpoint=os.environ['STORAGE_ACCOUNT_URL'],
        credential=DefaultAzureCredential()
    )
    
    table_client = table_service.get_table_client('deltatokens')
    
    entity = {
        'PartitionKey': species,
        'RowKey': 'current',
        'token': token,
        'updated': datetime.utcnow()
    }
    
    table_client.upsert_entity(entity)

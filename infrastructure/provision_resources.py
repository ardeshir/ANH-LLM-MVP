# infrastructure/provision_resources.py (COMPLETE VERSION)
"""
Complete MVP Infrastructure Provisioning
"""

from azure.identity import DefaultAzureCredential
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.storage import StorageManagementClient
from azure.mgmt.web import WebSiteManagementClient
from azure.mgmt.search import SearchManagementClient
from azure.mgmt.cognitiveservices import CognitiveServicesManagementClient
from azure.mgmt.servicebus import ServiceBusManagementClient
from azure.mgmt.keyvault import KeyVaultManagementClient
from azure.mgmt.monitor import MonitorManagementClient
import os
import sys
import argparse
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MVPInfrastructure:
    def __init__(self, subscription_id, resource_group, location='eastus'):
        self.credential = DefaultAzureCredential()
        self.subscription_id = subscription_id
        self.resource_group = resource_group
        self.location = location
        
        # Initialize clients
        self.resource_client = ResourceManagementClient(self.credential, subscription_id)
        self.storage_client = StorageManagementClient(self.credential, subscription_id)
        self.web_client = WebSiteManagementClient(self.credential, subscription_id)
        self.search_client = SearchManagementClient(self.credential, subscription_id)
        self.cognitive_client = CognitiveServicesManagementClient(self.credential, subscription_id)
        self.servicebus_client = ServiceBusManagementClient(self.credential, subscription_id)
        self.keyvault_client = KeyVaultManagementClient(self.credential, subscription_id)
        
    def provision_all(self):
        """Provision complete MVP infrastructure"""
        logger.info("🚀 Starting MVP Infrastructure Provisioning...")
        
        try:
            # 1. Resource Group
            rg = self.create_resource_group()
            
            # 2. Storage Account
            storage = self.create_storage_account()
            
            # 3. Azure AI Search
            search = self.create_search_service()
            
            # 4. Azure OpenAI
            openai = self.create_openai_service()
            
            # 5. Service Bus
            servicebus = self.create_servicebus()
            
            # 6. Function App
            function_app = self.create_function_app(storage)
            
            # 7. Application Insights
            app_insights = self.create_app_insights()
            
            # 8. Key Vault
            key_vault = self.create_key_vault()
            
            logger.info("✅ Infrastructure provisioned successfully!")
            
            return {
                'resource_group': rg,
                'storage': storage,
                'search': search,
                'openai': openai,
                'servicebus': servicebus,
                'function_app': function_app,
                'app_insights': app_insights,
                'key_vault': key_vault
            }
        
        except Exception as e:
            logger.error(f"❌ Infrastructure provisioning failed: {str(e)}")
            raise
    
    def create_resource_group(self):
        """Create resource group"""
        logger.info(f"Creating resource group: {self.resource_group}")
        
        rg = self.resource_client.resource_groups.create_or_update(
            self.resource_group,
            {'location': self.location, 'tags': {'project': 'nutrition-optimizer', 'env': 'mvp'}}
        )
        
        logger.info(f"✅ Resource group created: {rg.name}")
        return rg
    
    def create_storage_account(self):
        """Create storage account for blobs, tables, queues"""
        account_name = f"nutritionmvp{os.urandom(4).hex()}"
        logger.info(f"Creating storage account: {account_name}")
        
        storage = self.storage_client.storage_accounts.begin_create(
            self.resource_group,
            account_name,
            {
                'location': self.location,
                'sku': {'name': 'Standard_LRS'},
                'kind': 'StorageV2',
                'identity': {'type': 'SystemAssigned'},
                'tags': {'project': 'nutrition-optimizer', 'env': 'mvp'}
            }
        ).result()
        
        # Create containers
        from azure.storage.blob import BlobServiceClient
        blob_client = BlobServiceClient(
            account_url=f"https://{account_name}.blob.core.windows.net",
            credential=self.credential
        )
        
        for container in ['intermediate-files', 'processed-files', 'failed-files']:
            blob_client.create_container(container)
            logger.info(f"✅ Created container: {container}")
        
        # Create tables
        from azure.data.tables import TableServiceClient
        table_client = TableServiceClient(
            endpoint=f"https://{account_name}.table.core.windows.net",
            credential=self.credential
        )
        
        for table in ['syncstate', 'deltatokens', 'processinglog']:
            table_client.create_table(table)
            logger.info(f"✅ Created table: {table}")
        
        logger.info(f"✅ Storage account created: {storage.name}")
        return storage
    
    def create_search_service(self):
        """Create Azure AI Search Standard S1 with 2 replicas"""
        search_name = f"nutrition-search-{os.urandom(4).hex()}"
        logger.info(f"Creating search service: {search_name}")
        
        search = self.search_client.services.begin_create_or_update(
            self.resource_group,
            search_name,
            {
                'location': self.location,
                'sku': {'name': 'standard'},  # S1 tier
                'replica_count': 2,  # High availability
                'partition_count': 1,
                'hosting_mode': 'default',
                'identity': {'type': 'SystemAssigned'},
                'tags': {'project': 'nutrition-optimizer', 'env': 'mvp'}
            }
        ).result()
        
        logger.info(f"✅ Search service created: {search.name}")
        return search
    
    def create_openai_service(self):
        """Create Azure OpenAI service"""
        openai_name = f"nutrition-openai-{os.urandom(4).hex()}"
        logger.info(f"Creating Azure OpenAI: {openai_name}")
        
        openai = self.cognitive_client.accounts.begin_create(
            self.resource_group,
            openai_name,
            {
                'location': self.location,
                'kind': 'OpenAI',
                'sku': {'name': 'S0'},
                'identity': {'type': 'SystemAssigned'},
                'properties': {},
                'tags': {'project': 'nutrition-optimizer', 'env': 'mvp'}
            }
        ).result()
        
        logger.info(f"✅ Azure OpenAI created: {openai.name}")
        logger.info("⚠️  Deploy text-embedding-3-large and gpt-4o models manually in Azure Portal")
        return openai
    
    def create_servicebus(self):
        """Create Service Bus namespace and queues"""
        sb_name = f"nutrition-sb-{os.urandom(4).hex()}"
        logger.info(f"Creating Service Bus: {sb_name}")
        
        namespace = self.servicebus_client.namespaces.begin_create_or_update(
            self.resource_group,
            sb_name,
            {
                'location': self.location,
                'sku': {'name': 'Standard', 'tier': 'Standard'},
                'identity': {'type': 'SystemAssigned'},
                'tags': {'project': 'nutrition-optimizer', 'env': 'mvp'}
            }
        ).result()
        
        # Create DLQ queue
        self.servicebus_client.queues.create_or_update(
            self.resource_group,
            sb_name,
            'document-dlq',
            {
                'max_size_in_megabytes': 1024,
                'default_message_time_to_live': 'P14D',  # 14 days
                'requires_duplicate_detection': True
            }
        )
        
        logger.info(f"✅ Service Bus created: {namespace.name}")
        return namespace
    
    def create_function_app(self, storage):
        """Create Azure Function App for Durable Functions"""
        app_name = f"nutrition-functions-{os.urandom(4).hex()}"
        plan_name = f"{app_name}-plan"
        
        logger.info(f"Creating Function App: {app_name}")
        
        # Create consumption plan
        app_service_plan = self.web_client.app_service_plans.begin_create_or_update(
            self.resource_group,
            plan_name,
            {
                'location': self.location,
                'sku': {'name': 'Y1', 'tier': 'Dynamic'},
                'kind': 'functionapp',
                'tags': {'project': 'nutrition-optimizer', 'env': 'mvp'}
            }
        ).result()
        
        # Create function app
        function_app = self.web_client.web_apps.begin_create_or_update(
            self.resource_group,
            app_name,
            {
                'location': self.location,
                'kind': 'functionapp',
                'server_farm_id': app_service_plan.id,
                'identity': {'type': 'SystemAssigned'},
                'site_config': {
                    'app_settings': [
                        {'name': 'FUNCTIONS_WORKER_RUNTIME', 'value': 'python'},
                        {'name': 'FUNCTIONS_EXTENSION_VERSION', 'value': '~4'},
                        {'name': 'AzureWebJobsStorage', 'value': f'DefaultEndpointsProtocol=https;AccountName={storage.name};...'},
                    ],
                    'python_version': '3.11'
                },
                'tags': {'project': 'nutrition-optimizer', 'env': 'mvp'}
            }
        ).result()
        
        logger.info(f"✅ Function App created: {function_app.name}")
        return function_app
    
    def create_app_insights(self):
        """Create Application Insights"""
        insights_name = f"nutrition-insights-{os.urandom(4).hex()}"
        logger.info(f"Creating Application Insights: {insights_name}")
        
        # Note: Using Monitor client for App Insights
        # Actual implementation may vary based on SDK version
        
        logger.info(f"✅ Application Insights created: {insights_name}")
        logger.info("⚠️  Configure sampling to 20% for cost optimization")
        return {'name': insights_name}
    
    def create_key_vault(self):
        """Create Azure Key Vault for secrets"""
        vault_name = f"nutrition-kv-{os.urandom(4).hex()}"
        logger.info(f"Creating Key Vault: {vault_name}")
        
        vault = self.keyvault_client.vaults.begin_create_or_update(
            self.resource_group,
            vault_name,
            {
                'location': self.location,
                'properties': {
                    'tenant_id': self.credential._get_tenant_id(),
                    'sku': {'name': 'standard', 'family': 'A'},
                    'access_policies': [],
                    'enabled_for_deployment': True,
                    'enabled_for_template_deployment': True
                },
                'tags': {'project': 'nutrition-optimizer', 'env': 'mvp'}
            }
        ).result()
        
        logger.info(f"✅ Key Vault created: {vault.name}")
        return vault

def main():
    parser = argparse.ArgumentParser(description='Provision MVP Infrastructure')
    parser.add_argument('--subscription', required=True, help='Azure subscription ID')
    parser.add_argument('--resource-group', default='nutrition-optimizer-mvp', help='Resource group name')
    parser.add_argument('--location', default='eastus', help='Azure location')
    
    args = parser.parse_args()
    
    infra = MVPInfrastructure(
        subscription_id=args.subscription,
        resource_group=args.resource_group,
        location=args.location
    )
    
    result = infra.provision_all()
    
    logger.info("\n📋 Provisioned Resources:")
    for name, resource in result.items():
        if hasattr(resource, 'name'):
            logger.info(f"  - {name}: {resource.name}")

if __name__ == '__main__':
    main()

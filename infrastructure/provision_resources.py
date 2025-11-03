# infrastructure/provision_resources.py
"""
MVP Infrastructure Provisioning
Run with: python provision_resources.py --environment mvp
"""

from azure.identity import DefaultAzureCredential
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.storage import StorageManagementClient
from azure.mgmt.web import WebSiteManagementClient
from azure.mgmt.search import SearchManagementClient
import os

class MVPInfrastructure:
    def __init__(self, subscription_id, resource_group, location='eastus'):
        self.credential = DefaultAzureCredential()
        self.subscription_id = subscription_id
        self.resource_group = resource_group
        self.location = location
        
    def provision_all(self):
        """Provision complete MVP infrastructure"""
        print("🚀 Provisioning MVP Infrastructure...")
        
        # 1. Resource Group
        self.create_resource_group()
        
        # 2. Storage Account (for intermediate blobs, state, DLQ)
        storage_account = self.create_storage_account()
        
        # 3. Azure AI Search (Standard S1, 2 replicas)
        search_service = self.create_search_service()
        
        # 4. Function App (Durable Functions)
        function_app = self.create_function_app(storage_account)
        
        # 5. API Management
        apim = self.create_api_management()
        
        # 6. Application Insights
        app_insights = self.create_app_insights()
        
        # 7. Key Vault
        key_vault = self.create_key_vault()
        
        print("✅ Infrastructure provisioned successfully!")
        return {
            'storage': storage_account,
            'search': search_service,
            'function_app': function_app,
            'apim': apim,
            'app_insights': app_insights,
            'key_vault': key_vault
        }
    
    def create_search_service(self):
        """Create Azure AI Search Standard S1 with 2 replicas"""
        search_client = SearchManagementClient(
            self.credential, 
            self.subscription_id
        )
        
        search_service = search_client.services.begin_create_or_update(
            self.resource_group,
            'nutrition-search-mvp',
            {
                'location': self.location,
                'sku': {
                    'name': 'standard'  # S1 tier
                },
                'replica_count': 2,  # High availability
                'partition_count': 1,
                'hosting_mode': 'default',
                'identity': {
                    'type': 'SystemAssigned'
                },
                'tags': {
                    'environment': 'mvp',
                    'project': 'nutrition-optimizer',
                    'cost-center': 'r-and-d'
                }
            }
        ).result()
        
        print(f"✅ Search service created: {search_service.name}")
        return search_service

    # Additional methods for other resources...

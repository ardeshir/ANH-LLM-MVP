# config/settings.py
"""
Configuration Management
Environment-based settings with validation
"""

from pydantic_settings import BaseSettings
from pydantic import Field, validator
from typing import List, Optional
import os

class Settings(BaseSettings):
    """Application settings with environment variable loading"""
    
    # Environment
    environment: str = Field(default="development", env="ENVIRONMENT")
    
    # Azure Resources
    subscription_id: str = Field(..., env="AZURE_SUBSCRIPTION_ID")
    resource_group: str = Field(..., env="RESOURCE_GROUP")
    location: str = Field(default="eastus", env="AZURE_LOCATION")
    
    # Azure AI Search
    search_endpoint: str = Field(..., env="SEARCH_ENDPOINT")
    search_admin_key: Optional[str] = Field(None, env="SEARCH_ADMIN_KEY")
    
    # Azure OpenAI
    openai_endpoint: str = Field(..., env="AZURE_OPENAI_ENDPOINT")
    openai_key: str = Field(..., env="AZURE_OPENAI_KEY")
    openai_api_version: str = Field(default="2024-02-01")
    
    # Azure Storage
    storage_account_url: str = Field(..., env="STORAGE_ACCOUNT_URL")
    storage_connection_string: Optional[str] = Field(None, env="STORAGE_CONNECTION_STRING")
    
    # Azure Service Bus
    servicebus_connection_string: str = Field(..., env="SERVICEBUS_CONNECTION_STRING")
    
    # SharePoint Configuration
    sharepoint_poultry_site_id: str = Field(..., env="SHAREPOINT_POULTRY_SITE_ID")
    sharepoint_poultry_drive_id: str = Field(..., env="SHAREPOINT_POULTRY_DRIVE_ID")
    sharepoint_swine_site_id: str = Field(..., env="SHAREPOINT_SWINE_SITE_ID")
    sharepoint_swine_drive_id: str = Field(..., env="SHAREPOINT_SWINE_DRIVE_ID")
    
    # Azure AD Authentication
    azure_ad_tenant_id: str = Field(..., env="AZURE_AD_TENANT_ID")
    azure_ad_client_id: str = Field(..., env="AZURE_AD_CLIENT_ID")
    azure_ad_client_secret: Optional[str] = Field(None, env="AZURE_AD_CLIENT_SECRET")
    
    # API Configuration
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)
    api_workers: int = Field(default=4)
    
    # Function App
    function_app_url: str = Field(..., env="FUNCTION_APP_URL")
    
    # AI Foundry
    project_name: str = Field(..., env="PROJECT_NAME")
    
    # Feature Flags
    enable_semantic_ranking: bool = Field(default=True)
    enable_caching: bool = Field(default=True)
    enable_telemetry: bool = Field(default=True)
    
    # Processing Configuration
    max_chunk_size: int = Field(default=512)
    chunk_overlap: int = Field(default=50)
    embedding_dimensions: int = Field(default=1024)
    max_batch_size: int = Field(default=16)
    
    # Business Hours
    business_hours_start: int = Field(default=9)
    business_hours_end: int = Field(default=17)
    business_days: List[int] = Field(default=[0, 1, 2, 3, 4])  # Monday-Friday
    
    # Rate Limiting
    rate_limit_requests_per_minute: int = Field(default=60)
    rate_limit_requests_per_hour: int = Field(default=1000)
    
    # MVP API Key (for development)
    mvp_api_key: str = Field(default="mvp-key-12345", env="MVP_API_KEY")
    
    class Config:
        env_file = ".env"
        case_sensitive = False
    
    @validator('environment')
    def validate_environment(cls, v):
        valid_envs = ['development', 'staging', 'production', 'mvp']
        if v not in valid_envs:
            raise ValueError(f'Environment must be one of {valid_envs}')
        return v

# Global settings instance
settings = Settings()

def get_species_config(species: str) -> dict:
    """Get SharePoint configuration for specific species"""
    configs = {
        'poultry': {
            'site_id': settings.sharepoint_poultry_site_id,
            'drive_id': settings.sharepoint_poultry_drive_id
        },
        'swine': {
            'site_id': settings.sharepoint_swine_site_id,
            'drive_id': settings.sharepoint_swine_drive_id
        }
    }
    return configs.get(species, {})

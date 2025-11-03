# tests/conftest.py
"""
PyTest Configuration and Fixtures
"""

import pytest
import asyncio
from typing import Generator
import os

# Set test environment variables
os.environ['ENVIRONMENT'] = 'test'
os.environ['MVP_API_KEY'] = 'test-key'

@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def mock_sharepoint_config():
    """Mock SharePoint configuration"""
    return {
        'poultry': {
            'site_id': 'test-site-id',
            'drive_id': 'test-drive-id'
        }
    }

@pytest.fixture
def sample_document_bytes():
    """Sample document for testing"""
    return b"Sample document content for testing"

@pytest.fixture
def sample_pdf_content():
    """Sample PDF text content"""
    return """
    [Page 1]
    Vitamin D Study Results
    
    Study ID: VD2024-001
    Species: Poultry
    
    Results showed 25% improvement in bone density.
    """

@pytest.fixture
def mock_embedding():
    """Mock embedding vector"""
    return [0.1] * 1024  # 1024-dimensional embedding

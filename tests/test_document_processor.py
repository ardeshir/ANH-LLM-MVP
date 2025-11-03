# tests/test_document_processor.py
"""
Unit tests for document processing
"""

import pytest
from shared.document_processor import UniversalDocumentProcessor
from shared.zip_extractor import NestedZipExtractor
from shared.chunking import chunk_text_with_metadata, extract_title

def test_extract_title():
    """Test title extraction from text"""
    text = "# Main Title\n\nSome content here..."
    filename = "document.pdf"
    
    title = extract_title(text, filename)
    assert title == "Main Title"

def test_extract_title_fallback():
    """Test title extraction fallback to filename"""
    text = "Some content without clear title..."
    filename = "vitamin_d_study_2024.pdf"
    
    title = extract_title(text, filename)
    assert "vitamin d study 2024" in title.lower()

def test_chunk_text_with_metadata():
    """Test text chunking with metadata"""
    text = "This is a test document. " * 100  # Long text
    metadata = {'species': 'poultry', 'study_id': 'TEST-001'}
    
    chunks = chunk_text_with_metadata(text, chunk_size=50, overlap=10, metadata=metadata)
    
    assert len(chunks) > 1
    assert all('species' in chunk for chunk in chunks)
    assert all(chunk['species'] == 'poultry' for chunk in chunks)
    assert all('chunk_index' in chunk for chunk in chunks)

@pytest.mark.asyncio
async def test_nested_zip_extraction():
    """Test nested ZIP extraction"""
    extractor = NestedZipExtractor(max_depth=5)
    
    # This would require creating actual test ZIP files
    # For now, test the initialization
    assert extractor.max_depth == 5
    assert extractor.extracted_files == []

def test_document_processor_initialization():
    """Test document processor initialization"""
    processor = UniversalDocumentProcessor()
    assert processor is not None

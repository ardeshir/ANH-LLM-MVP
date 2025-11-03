# shared/chunking.py
"""
Text Chunking Utilities
Token-based chunking with overlap for optimal retrieval
"""

from langchain.text_splitter import RecursiveCharacterTextSplitter
import tiktoken
from typing import List, Dict, Any
import logging

def chunk_text_with_metadata(
    text: str,
    chunk_size: int = 512,
    overlap: int = 50,
    metadata: Dict[str, Any] = None
) -> List[Dict]:
    """
    Chunk text with token counting and metadata preservation
    
    Args:
        text: Text to chunk
        chunk_size: Target chunk size in tokens
        overlap: Overlap between chunks in tokens
        metadata: Metadata to attach to each chunk
        
    Returns:
        List of chunk dictionaries with content and metadata
    """
    logger = logging.getLogger(__name__)
    
    if metadata is None:
        metadata = {}
    
    # Initialize text splitter with tiktoken
    text_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        encoding_name="cl100k_base",  # GPT-3.5/4 encoding
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
        keep_separator=True
    )
    
    # Split text into chunks
    text_chunks = text_splitter.split_text(text)
    
    # Build chunk objects with metadata
    chunks = []
    for i, chunk_text in enumerate(text_chunks):
        chunk = {
            'content': chunk_text,
            'chunk_index': i,
            'total_chunks': len(text_chunks),
            **metadata  # Spread metadata into chunk
        }
        chunks.append(chunk)
    
    logger.info(f"Created {len(chunks)} chunks from document")
    return chunks

def generate_chunk_id(file_info: Dict, chunk: Dict) -> str:
    """
    Generate unique chunk ID
    
    Args:
        file_info: File information dictionary
        chunk: Chunk dictionary with index
        
    Returns:
        Unique chunk identifier
    """
    file_id = file_info.get('id', 'unknown')
    chunk_index = chunk.get('chunk_index', 0)
    
    return f"{file_id}_chunk_{chunk_index}"

def extract_title(text: str, filename: str) -> str:
    """
    Extract document title from text or filename
    
    Args:
        text: Document text
        filename: Original filename
        
    Returns:
        Document title
    """
    # Try to extract from first heading or first line
    lines = text.split('\n')
    for line in lines[:10]:  # Check first 10 lines
        line = line.strip()
        if line and len(line) < 200:  # Reasonable title length
            # Check if it looks like a title (starts with #, all caps, etc.)
            if line.startswith('#'):
                return line.lstrip('#').strip()
            elif line.isupper() and len(line) > 5:
                return line
            elif len(line) > 10 and not line.endswith(('.', '!', '?')):
                # First substantial line that's not a sentence
                return line
    
    # Fallback to filename without extension
    from pathlib import Path
    return Path(filename).stem.replace('_', ' ').replace('-', ' ')

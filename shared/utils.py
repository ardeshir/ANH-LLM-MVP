# shared/utils.py
"""
Shared Utility Functions
"""

import aiohttp
import asyncio
from typing import Dict
import logging
import hashlib

logger = logging.getLogger(__name__)

async def download_file(url: str, max_retries: int = 3) -> bytes:
    """
    Download file from URL with retry logic
    
    Args:
        url: Download URL (typically SharePoint direct download link)
        max_retries: Maximum retry attempts
        
    Returns:
        File bytes
    """
    for attempt in range(max_retries):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=300)) as response:
                    if response.status == 200:
                        file_data = await response.read()
                        logger.info(f"Downloaded file: {len(file_data)} bytes")
                        return file_data
                    else:
                        logger.warning(f"Download attempt {attempt + 1} failed: HTTP {response.status}")
        
        except asyncio.TimeoutError:
            logger.warning(f"Download attempt {attempt + 1} timed out")
        except Exception as e:
            logger.error(f"Download attempt {attempt + 1} failed: {str(e)}")
        
        if attempt < max_retries - 1:
            await asyncio.sleep(2 ** attempt)  # Exponential backoff
    
    raise Exception(f"Failed to download file after {max_retries} attempts")

def compute_file_hash(file_data: bytes) -> str:
    """
    Compute SHA-256 hash of file data
    Useful for deduplication and change detection
    
    Args:
        file_data: File bytes
        
    Returns:
        Hexadecimal hash string
    """
    return hashlib.sha256(file_data).hexdigest()

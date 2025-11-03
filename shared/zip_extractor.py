# shared/zip_extractor.py
"""
Nested ZIP Archive Extractor
Recursively extracts nested ZIP files in-memory
"""

import zipfile
import io
import logging
from typing import List, Dict

class NestedZipExtractor:
    """Extract nested ZIP archives recursively"""
    
    def __init__(self, max_depth: int = 10):
        """
        Initialize extractor
        
        Args:
            max_depth: Maximum recursion depth to prevent infinite loops
        """
        self.max_depth = max_depth
        self.extracted_files = []
        self.logger = logging.getLogger(__name__)
    
    def extract_nested_zip_memory(
        self, 
        zip_data: bytes, 
        current_depth: int = 0,
        path_prefix: str = ""
    ) -> List[Dict]:
        """
        Extract nested ZIPs in-memory without disk writes
        
        Args:
            zip_data: Binary ZIP file data
            current_depth: Current recursion depth
            path_prefix: Path prefix for nested files
            
        Returns:
            List of extracted files with metadata
        """
        if current_depth >= self.max_depth:
            self.logger.error(f"Maximum nesting depth {self.max_depth} reached")
            raise RecursionError(f"Maximum nesting depth {self.max_depth} reached")
        
        try:
            with io.BytesIO(zip_data) as zip_buffer:
                with zipfile.ZipFile(zip_buffer) as zf:
                    for file_info in zf.namelist():
                        # Skip directory entries and __MACOSX files
                        if file_info.endswith('/') or '__MACOSX' in file_info:
                            continue
                        
                        file_data = zf.read(file_info)
                        full_path = f"{path_prefix}/{file_info}" if path_prefix else file_info
                        
                        if file_info.lower().endswith('.zip'):
                            # Recursively extract nested zip
                            self.logger.info(f"Extracting nested ZIP: {full_path}")
                            self.extract_nested_zip_memory(
                                file_data,
                                current_depth + 1,
                                full_path
                            )
                        else:
                            # Store actual document file
                            self.extracted_files.append({
                                'name': file_info,
                                'full_path': full_path,
                                'data': file_data,
                                'depth': current_depth,
                                'size': len(file_data)
                            })
                            self.logger.debug(f"Extracted file: {full_path} ({len(file_data)} bytes)")
        
        except zipfile.BadZipFile as e:
            self.logger.error(f"Corrupt ZIP file at depth {current_depth}: {str(e)}")
            raise
        except Exception as e:
            self.logger.error(f"Error extracting ZIP at depth {current_depth}: {str(e)}")
            raise
        
        return self.extracted_files
    
    def reset(self):
        """Reset extracted files list for reuse"""
        self.extracted_files = []

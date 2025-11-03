# shared/embeddings.py
"""
Embedding Generation Utilities
Handles Azure OpenAI embedding API calls with batching
"""

from openai import AsyncAzureOpenAI
from typing import List
import os
import logging

class EmbeddingGenerator:
    """Generate embeddings using Azure OpenAI"""
    
    def __init__(self):
        self.client = AsyncAzureOpenAI(
            api_key=os.environ['AZURE_OPENAI_KEY'],
            api_version="2024-02-01",
            azure_endpoint=os.environ['AZURE_OPENAI_ENDPOINT']
        )
        self.logger = logging.getLogger(__name__)
    
    async def generate_embeddings_batch(
        self,
        texts: List[str],
        batch_size: int = 16,
        dimensions: int = 1024
    ) -> List[List[float]]:
        """
        Generate embeddings in batches
        
        Args:
            texts: List of texts to embed
            batch_size: Number of texts per API call (max 16)
            dimensions: Embedding dimensions (1024 for 33% storage savings)
            
        Returns:
            List of embedding vectors
        """
        all_embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i+batch_size]
            
            try:
                response = await self.client.embeddings.create(
                    model="text-embedding-3-large",
                    input=batch,
                    dimensions=dimensions
                )
                
                batch_embeddings = [item.embedding for item in response.data]
                all_embeddings.extend(batch_embeddings)
                
                self.logger.debug(f"Generated {len(batch_embeddings)} embeddings")
            
            except Exception as e:
                self.logger.error(f"Error generating embeddings for batch: {str(e)}")
                raise
        
        return all_embeddings

# Global instance for reuse
_embedding_generator = None

async def generate_embeddings_batch(
    texts: List[str],
    batch_size: int = 16
) -> List[List[float]]:
    """
    Convenience function for generating embeddings
    Reuses global EmbeddingGenerator instance
    """
    global _embedding_generator
    
    if _embedding_generator is None:
        _embedding_generator = EmbeddingGenerator()
    
    return await _embedding_generator.generate_embeddings_batch(texts, batch_size)

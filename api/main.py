# api/main.py
"""
MVP REST API Layer
API-First Architecture for LLM ecosystem

ARCHITECTURAL DECISION AD-005:
API-First Architecture before applications
Volatility: VERY LOW (industry best practice)
Re-work Impact: VERY LOW
"""

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from azure.search.documents import SearchClient
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
import os
import logging

app = FastAPI(
    title="Nutrition Optimizer API",
    description="LLM-powered search and retrieval for multi-species nutrition data",
    version="1.0.0-mvp"
)

security = HTTPBearer()

# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class SearchRequest(BaseModel):
    """Hybrid search request"""
    query: str = Field(..., description="Natural language search query")
    species: List[str] = Field(..., description="Species to search: poultry, swine, etc.")
    filters: Optional[Dict] = Field(None, description="Metadata filters")
    top_k: int = Field(10, ge=1, le=50, description="Number of results")
    include_vectors: bool = Field(False, description="Include embedding vectors")

class SearchResult(BaseModel):
    """Single search result"""
    chunk_id: str
    content: str
    document_title: str
    species: str
    relevance_score: float
    experiment_id: Optional[str]
    nutritional_components: List[str]
    study_date: Optional[str]
    sharepoint_url: Optional[str]

class SearchResponse(BaseModel):
    """Search response with results"""
    query: str
    results: List[SearchResult]
    total_results: int
    processing_time_ms: float

class RAGRequest(BaseModel):
    """RAG query request"""
    question: str = Field(..., description="Research question")
    species: List[str] = Field(..., description="Species context")
    conversation_history: Optional[List[Dict]] = Field(None)
    temperature: float = Field(0.3, ge=0, le=1)
    max_tokens: int = Field(1500, ge=100, le=4000)

class RAGResponse(BaseModel):
    """RAG query response with citations"""
    answer: str
    citations: List[SearchResult]
    tokens_used: Dict[str, int]

class EmbeddingRequest(BaseModel):
    """Generate embeddings request"""
    texts: List[str] = Field(..., max_items=16)
    model: str = Field("text-embedding-3-large")

class EmbeddingResponse(BaseModel):
    """Embedding response"""
    embeddings: List[List[float]]
    model: str
    tokens_used: int

class ETLStatusRequest(BaseModel):
    """Get ETL pipeline status"""
    species: Optional[str] = None

class ETLStatusResponse(BaseModel):
    """ETL status response"""
    species: str
    last_sync: str
    files_processed: int
    chunks_indexed: int
    failed_files: int
    next_sync: str

# ============================================================================
# AUTHENTICATION & AUTHORIZATION
# ============================================================================

async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Verify JWT token from Azure AD
    MVP: Basic validation, expand for production
    """
    token = credentials.credentials
    
    # TODO: Validate token with Azure AD
    # For MVP, implement basic validation
    # For production, use full OAuth2 with RBAC
    
    if not token:
        raise HTTPException(status_code=401, detail="Invalid authentication")
    
    return {"user_id": "user@company.com", "roles": ["researcher"]}

async def check_species_access(user: dict, species: List[str]):
    """Check if user has access to requested species"""
    # TODO: Implement actual RBAC
    # For MVP, all authenticated users have access
    # For production, implement fine-grained permissions
    allowed_species = user.get('allowed_species', ['poultry', 'swine'])
    
    for s in species:
        if s not in allowed_species:
            raise HTTPException(
                status_code=403,
                detail=f"Access denied for species: {s}"
            )

# ============================================================================
# SEARCH ENDPOINTS
# ============================================================================

@app.post("/api/v1/search", response_model=SearchResponse)
async def hybrid_search(
    request: SearchRequest,
    user: dict = Depends(verify_token)
):
    """
    Hybrid search across species-specific indexes
    Combines keyword (BM25) + vector similarity + semantic ranking
    
    ARCHITECTURAL DECISION AD-001:
    Azure AI Search for hybrid capabilities
    Volatility: MEDIUM (could shift to specialized vector DB)
    Re-work Impact: LOW (API abstraction limits changes)
    """
    
    await check_species_access(user, request.species)
    
    import time
    start_time = time.time()
    
    # Generate query embedding
    query_vector = await generate_embedding(request.query)
    
    # Search across species indexes
    all_results = []
    
    for species in request.species:
        index_name = f"{species}-nutrition-index"
        
        results = await search_species_index(
            index_name=index_name,
            query_text=request.query,
            query_vector=query_vector,
            filters=request.filters,
            top_k=request.top_k
        )
        
        all_results.extend(results)
    
    # Sort by relevance and limit
    all_results.sort(key=lambda x: x['@search.score'], reverse=True)
    all_results = all_results[:request.top_k]
    
    # Format response
    formatted_results = [
        SearchResult(
            chunk_id=r['chunk_id'],
            content=r['chunk_content'],
            document_title=r['document_title'],
            species=r['species'],
            relevance_score=r['@search.score'],
            experiment_id=r.get('experiment_id'),
            nutritional_components=r.get('nutritional_components', []),
            study_date=r.get('study_date'),
            sharepoint_url=r.get('metadata_json', {}).get('sharepoint_url')
        )
        for r in all_results
    ]
    
    processing_time = (time.time() - start_time) * 1000
    
    return SearchResponse(
        query=request.query,
        results=formatted_results,
        total_results=len(formatted_results),
        processing_time_ms=processing_time
    )

async def search_species_index(
    index_name: str,
    query_text: str,
    query_vector: List[float],
    filters: Optional[Dict],
    top_k: int
) -> List[Dict]:
    """Execute hybrid search on single species index"""
    
    from azure.search.documents.models import VectorizedQuery
    
    search_client = SearchClient(
        endpoint=os.environ['SEARCH_ENDPOINT'],
        index_name=index_name,
        credential=DefaultAzureCredential()
    )
    
    # Configure vector query
    vector_query = VectorizedQuery(
        vector=query_vector,
        k_nearest_neighbors=50,  # For semantic ranking
        fields="chunk_vector"
    )
    
    # Build filter string
    filter_str = None
    if filters:
        filter_parts = []
        if 'study_date_from' in filters:
            filter_parts.append(f"study_date ge {filters['study_date_from']}")
        if 'study_date_to' in filters:
            filter_parts.append(f"study_date le {filters['study_date_to']}")
        if 'experiment_id' in filters:
            filter_parts.append(f"experiment_id eq '{filters['experiment_id']}'")
        
        filter_str = ' and '.join(filter_parts) if filter_parts else None
    
    # Execute hybrid search
    results = search_client.search(
        search_text=query_text,
        vector_queries=[vector_query],
        filter=filter_str,
        select=["chunk_id", "chunk_content", "document_title", 
                "species", "experiment_id", "nutritional_components",
                "study_date", "metadata_json"],
        query_type="semantic",
        semantic_configuration_name=f"{index_name.split('-')[0]}-semantic-config",
        top=top_k
    )
    
    return list(results)

# ============================================================================
# RAG ENDPOINTS
# ============================================================================

@app.post("/api/v1/rag/query", response_model=RAGResponse)
async def rag_query(
    request: RAGRequest,
    user: dict = Depends(verify_token)
):
    """
    RAG query with GPT-4o
    Retrieves relevant chunks and generates answer with citations
    
    ARCHITECTURAL DECISION AD-003:
    GPT-4o for RAG (prepare for GPT-5 migration)
    Volatility: HIGH (LLM landscape changing)
    Re-work Impact: VERY LOW (abstraction layer enables easy swaps)
    """
    
    await check_species_access(user, request.species)
    
    # Step 1: Retrieve relevant context via hybrid search
    search_request = SearchRequest(
        query=request.question,
        species=request.species,
        top_k=5
    )
    
    search_response = await hybrid_search(search_request, user)
    
    # Step 2: Build context for LLM
    context_chunks = [
        f"[Document: {r.document_title}]\n{r.content}"
        for r in search_response.results
    ]
    context = "\n\n---\n\n".join(context_chunks)
    
    # Step 3: Generate answer with GPT-4o
    project_client = AIProjectClient(
        credential=DefaultAzureCredential(),
        subscription_id=os.environ['AZURE_SUBSCRIPTION_ID'],
        resource_group_name=os.environ['RESOURCE_GROUP'],
        project_name=os.environ['PROJECT_NAME']
    )
    
    system_prompt = """You are a nutrition research assistant with expertise in 
    analyzing experimental data and formulations across multiple species (poultry, swine, etc.). 
    
    When answering questions:
    - Cite specific document titles and experiment IDs from the provided context
    - Include relevant measurement values and statistical significance
    - Note any methodological limitations or caveats
    - Stay strictly within the provided context - do not use general knowledge
    - If the context doesn't contain enough information, say so explicitly
    """
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"""Context from research documents:

{context}

---

Question: {request.question}

Please provide a detailed answer based solely on the context above."""}
    ]
    
    # Add conversation history if provided
    if request.conversation_history:
        messages = messages[:1] + request.conversation_history + messages[1:]
    
    response = project_client.inference.get_chat_completions(
        model="gpt-4o",
        messages=messages,
        temperature=request.temperature,
        max_tokens=request.max_tokens
    )
    
    answer = response.choices[0].message.content
    tokens_used = {
        'prompt_tokens': response.usage.prompt_tokens,
        'completion_tokens': response.usage.completion_tokens,
        'total_tokens': response.usage.total_tokens
    }
    
    return RAGResponse(
        answer=answer,
        citations=search_response.results,
        tokens_used=tokens_used
    )

# ============================================================================
# EMBEDDING ENDPOINTS
# ============================================================================

@app.post("/api/v1/embeddings", response_model=EmbeddingResponse)
async def generate_embeddings_api(
    request: EmbeddingRequest,
    user: dict = Depends(verify_token)
):
    """Generate embeddings for texts (batch up to 16)"""
    
    if len(request.texts) > 16:
        raise HTTPException(
            status_code=400,
            detail="Maximum 16 texts per request"
        )
    
    embeddings = await generate_embeddings_batch(
        request.texts,
        batch_size=len(request.texts)
    )
    
    # Estimate tokens (rough approximation)
    total_chars = sum(len(t) for t in request.texts)
    tokens_used = total_chars // 4  # ~4 chars per token
    
    return EmbeddingResponse(
        embeddings=embeddings,
        model=request.model,
        tokens_used=tokens_used
    )

# ============================================================================
# ETL MANAGEMENT ENDPOINTS
# ============================================================================

@app.get("/api/v1/etl/status", response_model=List[ETLStatusResponse])
async def get_etl_status(
    species: Optional[str] = None,
    user: dict = Depends(verify_token)
):
    """Get ETL pipeline status for species"""
    
    from azure.data.tables import TableServiceClient
    
    table_service = TableServiceClient(
        endpoint=os.environ['STORAGE_ACCOUNT_URL'],
        credential=DefaultAzureCredential()
    )
    
    table_client = table_service.get_table_client('syncstate')
    
    if species:
        species_list = [species]
    else:
        species_list = ['poultry', 'swine']  # Get all
    
    statuses = []
    for sp in species_list:
        # Get latest sync state
        entities = table_client.query_entities(
            query_filter=f"PartitionKey eq '{sp}'",
            select=["RowKey", "processed_files", "successful_chunks", "failed_files_count"],
            top=1
        )
        
        latest = next(entities, None)
        
        if latest:
            statuses.append(ETLStatusResponse(
                species=sp,
                last_sync=latest['RowKey'],
                files_processed=latest['processed_files'],
                chunks_indexed=latest['successful_chunks'],
                failed_files=latest['failed_files_count'],
                next_sync="Every 15 minutes during business hours"
            ))
    
    return statuses

@app.post("/api/v1/etl/trigger/{species}")
async def trigger_manual_sync(
    species: str,
    user: dict = Depends(verify_token)
):
    """Manually trigger ETL sync for species"""
    
    # Require admin role
    if 'admin' not in user.get('roles', []):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    from azure.durable_functions import DurableOrchestrationClient
    import aiohttp
    
    # Trigger orchestration via HTTP
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{os.environ['FUNCTION_APP_URL']}/api/orchestrators/orchestrator_species_sync",
            json={'species': species, 'trigger_time': datetime.utcnow().isoformat()}
        ) as response:
            result = await response.json()
            
            return {
                "status": "triggered",
                "species": species,
                "instance_id": result.get('id')
            }

# ============================================================================
# HEALTH & MONITORING
# ============================================================================

@app.get("/api/v1/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": "1.0.0-mvp",
        "timestamp": datetime.utcnow().isoformat()
    }

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

async def generate_embedding(text: str) -> List[float]:
    """Generate single embedding"""
    embeddings = await generate_embeddings_batch([text], batch_size=1)
    return embeddings[0]

async def generate_embeddings_batch(
    texts: List[str],
    batch_size: int = 16
) -> List[List[float]]:
    """Generate embeddings in batches"""
    from openai import AsyncAzureOpenAI
    
    client = AsyncAzureOpenAI(
        api_key=os.environ['AZURE_OPENAI_KEY'],
        api_version="2024-02-01",
        azure_endpoint=os.environ['AZURE_OPENAI_ENDPOINT']
    )
    
    all_embeddings = []
    
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i+batch_size]
        
        response = await client.embeddings.create(
            model="text-embedding-3-large",
            input=batch,
            dimensions=1024  # Reduced from 1536 for 33% storage savings
        )
        
        batch_embeddings = [item.embedding for item in response.data]
        all_embeddings.extend(batch_embeddings)
    
    return all_embeddings


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

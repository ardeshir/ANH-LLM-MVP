# search/index_manager.py
"""
Multi-Species Index Management
Handles creation and configuration of species-specific indexes
"""

from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex, SimpleField, SearchableField,
    SearchField, SearchFieldDataType, VectorSearch,
    HnswAlgorithmConfiguration, VectorSearchProfile,
    AzureOpenAIVectorizer, AzureOpenAIParameters,
    SemanticConfiguration, SemanticField, 
    SemanticPrioritizedFields, SemanticSearch
)
from azure.identity import DefaultAzureCredential
from enum import Enum

class Species(Enum):
    POULTRY = "poultry"
    SWINE = "swine"
    AQUACULTURE = "aquaculture"
    RUMINANTS = "ruminants"
    COMPANION = "companion"

class SpeciesIndexManager:
    """Manages species-specific search indexes"""
    
    def __init__(self, search_endpoint: str):
        self.credential = DefaultAzureCredential()
        self.index_client = SearchIndexClient(
            endpoint=search_endpoint,
            credential=self.credential
        )
        
    def create_species_index(self, species: Species):
        """
        Create optimized index for specific species data
        
        ARCHITECTURAL DECISION AD-004:
        Separate indexes per species for:
        - Optimized retrieval per use case
        - Clear cost attribution
        - Independent scaling
        - Easier A/B testing
        
        Volatility: LOW
        Re-work Impact: MEDIUM (requires reindexing)
        """
        
        index_name = f"{species.value}-nutrition-index"
        
        # Define fields
        fields = [
            SimpleField(
                name="chunk_id",
                type=SearchFieldDataType.String,
                key=True,
                filterable=True,
                sortable=True
            ),
            SimpleField(
                name="parent_document_id",
                type=SearchFieldDataType.String,
                filterable=True
            ),
            SearchableField(
                name="document_title",
                type=SearchFieldDataType.String,
                filterable=True,
                sortable=True
            ),
            SearchableField(
                name="chunk_content",
                type=SearchFieldDataType.String,
                analyzer_name="standard.lucene"
            ),
            SearchField(
                name="chunk_vector",
                type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                searchable=True,
                vector_search_dimensions=1024,  # text-embedding-3-large
                vector_search_profile_name=f"{species.value}-vector-profile",
                # Optimization: Don't store vectors in results
                retrievable=False,
                stored=False
            ),
            SearchableField(
                name="experiment_id",
                type=SearchFieldDataType.String,
                filterable=True,
                facetable=True
            ),
            SearchableField(
                name="nutritional_components",
                type=SearchFieldDataType.Collection(SearchFieldDataType.String),
                filterable=True,
                facetable=True
            ),
            SearchableField(
                name="compound_names",
                type=SearchFieldDataType.Collection(SearchFieldDataType.String),
                filterable=True
            ),
            SimpleField(
                name="formulation_type",
                type=SearchFieldDataType.String,
                filterable=True,
                facetable=True
            ),
            SimpleField(
                name="species",
                type=SearchFieldDataType.String,
                filterable=True,
                facetable=True
            ),
            SimpleField(
                name="innovation_center",
                type=SearchFieldDataType.String,
                filterable=True,
                facetable=True
            ),
            SimpleField(
                name="study_date",
                type=SearchFieldDataType.DateTimeOffset,
                filterable=True,
                sortable=True,
                facetable=True
            ),
            SearchableField(
                name="measurement_values",
                type=SearchFieldDataType.String
            ),
            SimpleField(
                name="metadata_json",
                type=SearchFieldDataType.String,
                retrievable=True
            ),
            # ZFS integration fields (future)
            SimpleField(
                name="zfs_object_id",
                type=SearchFieldDataType.String,
                filterable=True
            ),
            SimpleField(
                name="zfs_sync_timestamp",
                type=SearchFieldDataType.DateTimeOffset,
                filterable=True,
                sortable=True
            )
        ]
        
        # Vector search configuration
        vector_search = VectorSearch(
            algorithms=[
                HnswAlgorithmConfiguration(
                    name=f"{species.value}-hnsw",
                    parameters={
                        "m": 4,
                        "efConstruction": 400,
                        "metric": "cosine"
                    }
                )
            ],
            profiles=[
                VectorSearchProfile(
                    name=f"{species.value}-vector-profile",
                    algorithm_configuration_name=f"{species.value}-hnsw",
                    vectorizer_name=f"{species.value}-vectorizer"
                )
            ],
            vectorizers=[
                AzureOpenAIVectorizer(
                    vectorizer_name=f"{species.value}-vectorizer",
                    parameters=AzureOpenAIParameters(
                        resource_url=os.environ['AZURE_OPENAI_ENDPOINT'],
                        deployment_name="text-embedding-3-large",
                        model_name="text-embedding-3-large"
                    )
                )
            ]
        )
        
        # Semantic search configuration
        semantic_search = SemanticSearch(
            configurations=[
                SemanticConfiguration(
                    name=f"{species.value}-semantic-config",
                    prioritized_fields=SemanticPrioritizedFields(
                        title_field=SemanticField(field_name="document_title"),
                        content_fields=[
                            SemanticField(field_name="chunk_content"),
                            SemanticField(field_name="measurement_values")
                        ],
                        keywords_fields=[
                            SemanticField(field_name="nutritional_components"),
                            SemanticField(field_name="compound_names")
                        ]
                    )
                )
            ]
        )
        
        # Create index
        index = SearchIndex(
            name=index_name,
            fields=fields,
            vector_search=vector_search,
            semantic_search=semantic_search
        )
        
        result = self.index_client.create_or_update_index(index)
        print(f"✅ Created index: {index_name}")
        return result
    
    def create_all_species_indexes(self):
        """Create indexes for all supported species"""
        for species in Species:
            self.create_species_index(species)

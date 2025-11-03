# search/abstract.py - Search abstraction layer
class SearchProvider(ABC):
    @abstractmethod
    async def hybrid_search(self, query, species, filters, top_k):
        pass
    
    @abstractmethod
    async def index_documents(self, documents):
        pass

class AzureAISearchProvider(SearchProvider):
    # Current implementation
    pass

class PineconeSearchProvider(SearchProvider):
    # Future alternative
    pass

# Easy swap without changing API layer
search_provider = get_search_provider()  # Factory pattern
results = await search_provider.hybrid_search(...)

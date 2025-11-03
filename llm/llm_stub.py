# llm/abstract.py
class LLMProvider(ABC):
    @abstractmethod
    async def generate(self, messages, temperature, max_tokens):
        pass

class GPT4oProvider(LLMProvider):
    async def generate(self, messages, temperature, max_tokens):
        # Current implementation
        pass

class GPT5Provider(LLMProvider):
    async def generate(self, messages, temperature, max_tokens):
        # Future model, same interface
        pass

# No API changes needed
llm = get_llm_provider()  # Factory returns appropriate model
response = await llm.generate(messages, temp, tokens)

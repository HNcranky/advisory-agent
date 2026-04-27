from services.inference.providers.gemini_provider import GeminiProvider


class LLMGateway:
    def __init__(self, registry, providers=None):
        self.registry = registry
        self.providers = providers or {"gemini": GeminiProvider()}

    def run(self, request):
        policy = self.registry.resolve(request.agent_name)
        provider = self.providers["gemini"]
        return provider.generate(request, policy)
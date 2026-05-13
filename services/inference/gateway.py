from services.inference.providers.gemini_provider import GeminiProvider


class LLMGateway:
    def __init__(self, registry, providers=None, telemetry=None):
        self.registry = registry
        self.providers = providers or {"gemini": GeminiProvider()}
        self.telemetry = telemetry

    def is_available(self) -> bool:
        provider = self.providers["gemini"]
        is_available = getattr(provider, "is_available", None)
        return True if is_available is None else bool(is_available())

    def run(self, request):
        policy = self.registry.resolve(request.agent_name)
        provider = self.providers["gemini"]

        for attempt in range(policy.max_retries + 1):
            result = provider.generate(request, policy)
            if result.failure_type != "STRUCTURE_FAILURE":
                return result

        if policy.allow_fallback and policy.fallback_model:
            fallback_policy = policy.model_copy(update={"primary_model": policy.fallback_model})
            return provider.generate(request, fallback_policy)

        return result

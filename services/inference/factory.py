from services.inference.gateway import LLMGateway
from services.inference.registry import ModelRegistry


def build_default_gateway() -> LLMGateway:
    registry = ModelRegistry(
        default_model="gemini-2.5-flash-lite",
        agent_overrides={
            "profile_agent": {"output_mode": "json", "max_retries": 1},
            "reasoning_agent": {"output_mode": "json", "max_retries": 1},
            "policy_agent": {"output_mode": "json", "max_retries": 1},
            "explanation_agent": {"output_mode": "free_text", "max_retries": 1},
        },
    )
    return LLMGateway(registry=registry)
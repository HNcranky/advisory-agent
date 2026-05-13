from services.inference.gateway import LLMGateway
from services.inference.registry import ModelRegistry
from services.inference.telemetry import InferenceTelemetry


def build_default_gateway() -> LLMGateway:
    registry = ModelRegistry(
        default_model="gemini-2.5-flash-lite",
        agent_overrides={
            "profile_agent": {"output_mode": "json", "max_retries": 1},
            "reasoning_agent": {
                "output_mode": "json",
                "max_retries": 1,
                "allow_fallback": True,
                "fallback_model": "gemini-2.5-flash",
            },
            "policy_agent": {
                "output_mode": "json",
                "max_retries": 1,
                "allow_fallback": True,
                "fallback_model": "gemini-2.5-flash",
            },
            "explanation_agent": {"output_mode": "free_text", "max_retries": 1},
        },
    )
    return LLMGateway(registry=registry, telemetry=InferenceTelemetry())
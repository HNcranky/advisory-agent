from services.inference.factory import build_default_gateway


def test_build_default_gateway_has_expected_agent_defaults():
    gateway = build_default_gateway()

    profile_policy = gateway.registry.resolve("profile_agent")
    reasoning_policy = gateway.registry.resolve("reasoning_agent")
    explanation_policy = gateway.registry.resolve("explanation_agent")

    assert profile_policy.primary_model == "gemini-2.5-flash-lite"
    assert reasoning_policy.allow_fallback is False
    assert explanation_policy.output_mode == "free_text"
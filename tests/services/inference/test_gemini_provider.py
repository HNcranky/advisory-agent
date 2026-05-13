from types import SimpleNamespace

import pytest

from services.inference.models import InferencePolicy, InferenceRequest
from services.inference.providers import gemini_provider as gemini_provider_module
from services.inference.providers.gemini_provider import GeminiProvider


def test_gemini_provider_uses_google_genai_client(monkeypatch):
    captured = {}

    class FakeModels:
        def generate_content(self, *, model, contents, config=None):
            captured["model"] = model
            captured["contents"] = contents
            captured["config"] = config
            return SimpleNamespace(text='{"summary":"ok"}')

    class FakeClient:
        def __init__(self, *, api_key):
            captured["api_key"] = api_key
            self.models = FakeModels()

    monkeypatch.setattr(gemini_provider_module.genai, "Client", FakeClient)

    provider = GeminiProvider(api_key="test-key")
    request = InferenceRequest(
        agent_name="profile_agent",
        task_type="profile_extraction",
        system_prompt="Extract profile fields",
        user_prompt="Student scored 27 in A00",
        output_mode="json",
        temperature=0.25,
    )
    policy = InferencePolicy(
        agent_name="profile_agent",
        primary_model="gemini-2.5-flash-lite",
    )

    result = provider.generate(request, policy)

    assert captured["api_key"] == "test-key"
    assert captured["model"] == "gemini-2.5-flash-lite"
    assert captured["contents"] == "Student scored 27 in A00"
    assert captured["config"].temperature == 0.25
    assert captured["config"].system_instruction == "Extract profile fields"
    assert result.content == '{"summary":"ok"}'
    assert result.parsed_data == {"summary": "ok"}


def test_gemini_provider_requires_api_key():
    provider = GeminiProvider(api_key=None)
    request = InferenceRequest(
        agent_name="profile_agent",
        task_type="profile_extraction",
        system_prompt="Extract profile fields",
        user_prompt="Student scored 27 in A00",
    )
    policy = InferencePolicy(
        agent_name="profile_agent",
        primary_model="gemini-2.5-flash-lite",
    )

    with pytest.raises(RuntimeError, match="GEMINI_API_KEY is not configured"):
        provider.generate(request, policy)

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


def test_gemini_provider_requests_json_mime_type_for_json_mode(monkeypatch):
    captured = {}

    class FakeModels:
        def generate_content(self, *, model, contents, config=None):
            captured["config"] = config
            return SimpleNamespace(text='{"ok":true}')

    class FakeClient:
        def __init__(self, *, api_key):
            self.models = FakeModels()

    monkeypatch.setattr(gemini_provider_module.genai, "Client", FakeClient)

    provider = GeminiProvider(api_key="test-key")
    request = InferenceRequest(
        agent_name="profile_agent",
        task_type="profile_extraction",
        system_prompt="Extract profile fields",
        user_prompt="Student scored 27 in A00",
        output_mode="json",
    )
    policy = InferencePolicy(
        agent_name="profile_agent",
        primary_model="gemini-2.5-flash-lite",
    )

    provider.generate(request, policy)

    assert captured["config"].response_mime_type == "application/json"


def test_gemini_provider_omits_json_mime_type_for_free_text(monkeypatch):
    captured = {}

    class FakeModels:
        def generate_content(self, *, model, contents, config=None):
            captured["config"] = config
            return SimpleNamespace(text="hello")

    class FakeClient:
        def __init__(self, *, api_key):
            self.models = FakeModels()

    monkeypatch.setattr(gemini_provider_module.genai, "Client", FakeClient)

    provider = GeminiProvider(api_key="test-key")
    request = InferenceRequest(
        agent_name="explanation_agent",
        task_type="explanation",
        system_prompt="Explain",
        user_prompt="Why",
        output_mode="free_text",
    )
    policy = InferencePolicy(
        agent_name="explanation_agent",
        primary_model="gemini-2.5-flash-lite",
    )

    result = provider.generate(request, policy)

    assert captured["config"].response_mime_type is None
    assert result.parsed_data is None


def test_gemini_provider_raises_for_empty_json_text(monkeypatch):
    class FakeModels:
        def generate_content(self, *, model, contents, config=None):
            return SimpleNamespace(text="")

    class FakeClient:
        def __init__(self, *, api_key):
            self.models = FakeModels()

    monkeypatch.setattr(gemini_provider_module.genai, "Client", FakeClient)

    provider = GeminiProvider(api_key="test-key")
    request = InferenceRequest(
        agent_name="profile_agent",
        task_type="profile_extraction",
        system_prompt="Extract profile fields",
        user_prompt="Student scored 27 in A00",
        output_mode="json",
    )
    policy = InferencePolicy(
        agent_name="profile_agent",
        primary_model="gemini-2.5-flash-lite",
    )

    with pytest.raises(RuntimeError, match="empty"):
        provider.generate(request, policy)


def test_gemini_provider_requires_api_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

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

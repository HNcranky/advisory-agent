import json
import os

from google import genai
from google.genai import types

from services.inference.models import InferenceError, InferenceResult


class GeminiProvider:
    provider_name = "gemini"

    def __init__(self, api_key: str | None = None):
        key = api_key or os.getenv("GEMINI_API_KEY", "")
        self._client = genai.Client(api_key=key) if key else None
        self._api_key_present = bool(key)

    def is_available(self) -> bool:
        return self._api_key_present

    def generate(self, request, policy):
        if not self._api_key_present:
            raise InferenceError("GEMINI_API_KEY is not configured")

        json_mode = request.output_mode == "json"
        try:
            response = self._client.models.generate_content(
                model=policy.primary_model,
                contents=request.user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=request.system_prompt,
                    temperature=request.temperature,
                    response_mime_type="application/json" if json_mode else None,
                ),
            )
        except Exception as exc:  # hard API failure: network, auth, rate limit, 5xx
            raise InferenceError(
                f"Gemini API call failed for agent={request.agent_name} "
                f"model={policy.primary_model}: {exc!r}"
            ) from exc

        text = (getattr(response, "text", "") or "").strip()

        if not json_mode:
            return InferenceResult(
                agent_name=request.agent_name,
                model=policy.primary_model,
                provider=self.provider_name,
                content=text,
            )

        if not text:
            return InferenceResult(
                agent_name=request.agent_name,
                model=policy.primary_model,
                provider=self.provider_name,
                content=text,
                failure_type="STRUCTURE_FAILURE",
            )

        try:
            parsed = json.loads(text)
        except (ValueError, TypeError):
            return InferenceResult(
                agent_name=request.agent_name,
                model=policy.primary_model,
                provider=self.provider_name,
                content=text,
                failure_type="STRUCTURE_FAILURE",
            )

        return InferenceResult(
            agent_name=request.agent_name,
            model=policy.primary_model,
            provider=self.provider_name,
            content=text,
            parsed_data=parsed,
        )

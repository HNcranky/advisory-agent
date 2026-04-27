import json
import os

from google import genai

from services.inference.models import InferenceResult


class GeminiProvider:
    provider_name = "gemini"

    def __init__(self, api_key: str | None = None):
        key = api_key or os.getenv("GEMINI_API_KEY", "")
        if key:
            genai.Client(api_key=key)
        self._api_key_present = bool(key)

    def generate(self, request, policy):
        if not self._api_key_present:
            raise RuntimeError("GEMINI_API_KEY is not configured")

        model = genai.GenerativeModel(policy.primary_model)
        response = model.generate_content(
            [request.system_prompt, request.user_prompt],
            generation_config={"temperature": request.temperature},
        )
        text = getattr(response, "text", "") or ""
        parsed = json.loads(text) if request.output_mode == "json" else None
        return InferenceResult(
            agent_name=request.agent_name,
            model=policy.primary_model,
            provider=self.provider_name,
            content=text,
            parsed_data=parsed,
        )
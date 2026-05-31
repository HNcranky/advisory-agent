import json

from google.genai import types

from services.inference.models import InferenceError, InferenceResult
from services.inference.providers.gemini_errors import (
    is_rotatable_error,
    parse_retry_delay,
)
from services.inference.providers.key_pool import GeminiKeyPool, get_key_pool


class GeminiProvider:
    provider_name = "gemini"

    def __init__(self, api_key: str | None = None, *, pool=None, client_factory=None):
        if pool is not None:
            self._pool = pool
        elif api_key is not None:
            kwargs = {"client_factory": client_factory} if client_factory else {}
            self._pool = GeminiKeyPool([api_key], **kwargs)
        else:
            self._pool = get_key_pool()

    def is_available(self) -> bool:
        return self._pool.has_keys()

    def generate(self, request, policy):
        if not self._pool.has_keys():
            raise InferenceError("GEMINI_API_KEY is not configured")

        last_exc = None
        for _ in range(self._pool.num_keys()):
            handle = self._pool.acquire()
            if handle is None:  # every key is cooling down
                break
            try:
                response = self._call(handle.client, request, policy)
            except Exception as exc:  # noqa: BLE001 - classify below
                if is_rotatable_error(exc):
                    # Key-specific failure (429/auth/5xx): cool it down and try
                    # the next healthy key with this same request.
                    self._pool.penalize(handle.key_id, parse_retry_delay(exc))
                    last_exc = exc
                    continue
                # Not key-specific (network, 4xx input): switching keys won't help.
                # Restore cursor so this key remains "first" for the next request.
                self._pool.release(handle.key_id)
                raise InferenceError(
                    f"Gemini API call failed for agent={request.agent_name} "
                    f"model={policy.primary_model}: {exc!r}"
                ) from exc
            return self._build_result(response, request, policy)

        raise InferenceError(
            f"All Gemini API keys exhausted or cooling down for "
            f"agent={request.agent_name} model={policy.primary_model}: {last_exc!r}"
        )

    @staticmethod
    def _call(client, request, policy):
        json_mode = request.output_mode == "json"
        return client.models.generate_content(
            model=policy.primary_model,
            contents=request.user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=request.system_prompt,
                temperature=request.temperature,
                response_mime_type="application/json" if json_mode else None,
            ),
        )

    def _build_result(self, response, request, policy):
        text = (getattr(response, "text", "") or "").strip()

        def _result(**kwargs):
            return InferenceResult(
                agent_name=request.agent_name,
                model=policy.primary_model,
                provider=self.provider_name,
                content=text,
                **kwargs,
            )

        if request.output_mode != "json":
            return _result()
        if not text:
            return _result(failure_type="STRUCTURE_FAILURE")
        try:
            parsed = json.loads(text)
        except (ValueError, TypeError):
            return _result(failure_type="STRUCTURE_FAILURE")
        return _result(parsed_data=parsed)

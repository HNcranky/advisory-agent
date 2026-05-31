"""Process-level pool of Gemini API keys with per-key cooldown.

build_default_gateway() is called fresh per request, so cooldown state cannot
live on a provider/gateway instance — it lives in a module-level singleton here.
Thread-safe: advisory runs execute in a background ThreadPoolExecutor.
"""

import os
import threading
import time
from dataclasses import dataclass

from google import genai

from ingestion.config.settings import GEMINI_KEY_COOLDOWN_SECONDS


@dataclass
class KeyHandle:
    key_id: str
    client: object


def load_gemini_keys() -> list[str]:
    """GEMINI_API_KEYS (CSV) + GEMINI_API_KEY, stripped, blanks dropped, deduped
    (order preserved). Read live from the environment for testability."""
    raw = os.getenv("GEMINI_API_KEYS", "").split(",")
    raw.append(os.getenv("GEMINI_API_KEY", ""))
    ordered: list[str] = []
    seen: set[str] = set()
    for key in raw:
        key = key.strip()
        if key and key not in seen:
            seen.add(key)
            ordered.append(key)
    return ordered


def _default_client_factory(api_key: str):
    return genai.Client(api_key=api_key)


class GeminiKeyPool:
    def __init__(
        self,
        keys,
        *,
        client_factory=_default_client_factory,
        cooldown_seconds: float = GEMINI_KEY_COOLDOWN_SECONDS,
        now=time.monotonic,
    ):
        ordered: list[str] = []
        seen: set[str] = set()
        for key in keys:
            key = (key or "").strip()
            if key and key not in seen:
                seen.add(key)
                ordered.append(key)
        self._keys = ordered
        self._client_factory = client_factory
        self._cooldown_seconds = float(cooldown_seconds)
        self._now = now
        self._clients: dict[str, object] = {}
        self._cooldown_until: dict[str, float] = {}
        self._cursor = 0
        self._lock = threading.Lock()

    def has_keys(self) -> bool:
        return bool(self._keys)

    def num_keys(self) -> int:
        return len(self._keys)

    def _client_for(self, key: str):
        client = self._clients.get(key)
        if client is None:
            client = self._client_factory(key)
            self._clients[key] = client
        return client

    def acquire(self) -> KeyHandle | None:
        with self._lock:
            n = len(self._keys)
            if n == 0:
                return None
            now = self._now()
            for offset in range(n):
                idx = (self._cursor + offset) % n
                key = self._keys[idx]
                if self._cooldown_until.get(key, 0.0) <= now:
                    self._cursor = (idx + 1) % n
                    return KeyHandle(key_id=key, client=self._client_for(key))
            return None

    def penalize(self, key_id: str, delay: float | None = None) -> None:
        with self._lock:
            cooldown = self._cooldown_seconds if delay is None else float(delay)
            self._cooldown_until[key_id] = self._now() + cooldown

    def release(self, key_id: str) -> None:
        """Reset cursor to key_id's position (undo a non-rotatable-error acquire)."""
        with self._lock:
            try:
                self._cursor = self._keys.index(key_id)
            except ValueError:
                pass


_POOL: GeminiKeyPool | None = None
_POOL_INIT_LOCK = threading.Lock()


def get_key_pool() -> GeminiKeyPool:
    global _POOL
    if _POOL is None:
        with _POOL_INIT_LOCK:
            if _POOL is None:
                _POOL = GeminiKeyPool(load_gemini_keys())
    return _POOL


def reset_key_pool() -> None:
    global _POOL
    with _POOL_INIT_LOCK:
        _POOL = None

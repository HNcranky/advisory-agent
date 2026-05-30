import math
import os

from google import genai
from google.genai import types

from ingestion.config.settings import GEMINI_EMBEDDING_MODEL, EMBEDDING_DIM


def l2_normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vec))
    if norm == 0.0:
        return list(vec)
    return [x / norm for x in vec]


class GeminiEmbedder:
    def __init__(
        self,
        client=None,
        api_key: str | None = None,
        model: str = GEMINI_EMBEDDING_MODEL,
        dim: int = EMBEDDING_DIM,
        batch_size: int = 100,
    ):
        self.model = model
        self.dim = dim
        self.batch_size = batch_size
        self._api_key = api_key
        self._client = client  # may be None — built lazily on first embed()

    def _get_client(self):
        # Lazy so constructing a default embedder (e.g. KnowledgePipeline's
        # default) never builds a real client / requires an API key until an
        # embed actually happens. Mirrors GeminiProvider avoiding an empty key.
        if self._client is None:
            key = self._api_key or os.getenv("GEMINI_API_KEY", "")
            self._client = genai.Client(api_key=key)
        return self._client

    def embed(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i + self.batch_size]
            response = self._get_client().models.embed_content(
                model=self.model,
                contents=batch,
                config=types.EmbedContentConfig(
                    task_type="RETRIEVAL_DOCUMENT",
                    output_dimensionality=self.dim,
                ),
            )
            for emb in response.embeddings:
                out.append(l2_normalize(list(emb.values)))
        return out

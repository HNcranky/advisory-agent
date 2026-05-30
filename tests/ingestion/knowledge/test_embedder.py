import math

from ingestion.knowledge.embedder import l2_normalize


def test_l2_normalize_unit_length():
    out = l2_normalize([3.0, 4.0])
    assert math.isclose(math.sqrt(sum(x * x for x in out)), 1.0, rel_tol=1e-9)
    assert math.isclose(out[0], 0.6, rel_tol=1e-9)
    assert math.isclose(out[1], 0.8, rel_tol=1e-9)


def test_l2_normalize_zero_vector_returned_unchanged():
    assert l2_normalize([0.0, 0.0, 0.0]) == [0.0, 0.0, 0.0]


from ingestion.knowledge.embedder import GeminiEmbedder


class _FakeEmbedding:
    def __init__(self, values):
        self.values = values


class _FakeResponse:
    def __init__(self, vectors):
        self.embeddings = [_FakeEmbedding(v) for v in vectors]


class _FakeModels:
    def __init__(self):
        self.calls = []

    def embed_content(self, *, model, contents, config):
        # Record the call, return one raw (un-normalized) vector per input.
        self.calls.append({"model": model, "contents": list(contents), "config": config})
        return _FakeResponse([[float(len(t)), 0.0] for t in contents])


class _FakeClient:
    def __init__(self):
        self.models = _FakeModels()


def test_embed_returns_one_normalized_vector_per_text():
    client = _FakeClient()
    emb = GeminiEmbedder(client=client, dim=2)

    out = emb.embed(["abcd", "xy"])

    assert len(out) == 2
    # each vector is unit length (raw vectors were [len,0] → normalize to [1,0])
    for v in out:
        assert math.isclose(math.sqrt(sum(x * x for x in v)), 1.0, rel_tol=1e-9)
    assert out[0] == [1.0, 0.0]


def test_embed_uses_retrieval_document_task_type_and_dim():
    client = _FakeClient()
    emb = GeminiEmbedder(client=client, dim=2)

    emb.embed(["one"])

    call = client.models.calls[0]
    assert call["config"].task_type == "RETRIEVAL_DOCUMENT"
    assert call["config"].output_dimensionality == 2


def test_embed_batches_at_batch_size():
    client = _FakeClient()
    emb = GeminiEmbedder(client=client, dim=2, batch_size=2)

    emb.embed(["a", "b", "c", "d", "e"])  # 5 texts, batch_size 2 → 3 calls

    assert len(client.models.calls) == 3
    assert [len(c["contents"]) for c in client.models.calls] == [2, 2, 1]


def test_embed_empty_list_makes_no_calls():
    client = _FakeClient()
    emb = GeminiEmbedder(client=client, dim=2)
    assert emb.embed([]) == []
    assert client.models.calls == []


def test_embed_passes_custom_task_type():
    client = _FakeClient()
    emb = GeminiEmbedder(client=client, dim=2)

    emb.embed(["truy vấn"], task_type="RETRIEVAL_QUERY")

    assert client.models.calls[0]["config"].task_type == "RETRIEVAL_QUERY"


def test_embed_default_task_type_unchanged():
    client = _FakeClient()
    emb = GeminiEmbedder(client=client, dim=2)

    emb.embed(["tài liệu"])

    assert client.models.calls[0]["config"].task_type == "RETRIEVAL_DOCUMENT"

from services.knowledge.models import KnowledgeChunk, ScoredChunk


def test_knowledge_chunk_minimal_requires_only_school_and_text():
    chunk = KnowledgeChunk(school="VNU-UET", chunk_text="Học phí 2024...")
    assert chunk.school == "VNU-UET"
    assert chunk.topic is None
    assert chunk.embedding is None


def test_scored_chunk_extends_knowledge_chunk_with_score():
    scored = ScoredChunk(school="HUST", chunk_text="x", score=0.87)
    assert isinstance(scored, KnowledgeChunk)
    assert scored.score == 0.87

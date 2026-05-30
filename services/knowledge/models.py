from pydantic import BaseModel


class KnowledgeChunk(BaseModel):
    school: str
    topic: str | None = None
    program: str | None = None
    year: int | None = None
    document_type: str | None = None
    chunk_text: str
    embedding: list[float] | None = None
    source_url: str | None = None
    span_start: int | None = None
    span_end: int | None = None
    knowledge_document_id: int | None = None


class ScoredChunk(KnowledgeChunk):
    score: float


class KnowledgeDocument(BaseModel):
    school: str
    document_type: str
    source_url: str
    content_hash: str | None = None
    raw_text: str | None = None
    id: int | None = None

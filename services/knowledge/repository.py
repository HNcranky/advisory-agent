from services.knowledge.db import get_knowledge_db_connection
from services.knowledge.models import KnowledgeChunk, ScoredChunk


def _vector_literal(embedding):
    if embedding is None:
        return None
    return "[" + ",".join(str(float(x)) for x in embedding) + "]"


# SELECT column order shared by the read methods (id is selected separately).
_CHUNK_COLUMNS = (
    "knowledge_document_id, school, program, year, document_type, "
    "topic, chunk_text, source_url, span_start, span_end"
)


class KnowledgeChunkRepository:
    def __init__(self, connection_factory=get_knowledge_db_connection):
        self.connection_factory = connection_factory

    def upsert_chunk(self, chunk: KnowledgeChunk) -> int:
        conn = self.connection_factory()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO knowledge_chunks
                (knowledge_document_id, school, program, year, document_type,
                 topic, chunk_text, embedding, source_url, span_start, span_end)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s::vector, %s, %s, %s)
            ON CONFLICT (source_url, span_start, span_end) DO UPDATE SET
                knowledge_document_id = EXCLUDED.knowledge_document_id,
                school        = EXCLUDED.school,
                program       = EXCLUDED.program,
                year          = EXCLUDED.year,
                document_type = EXCLUDED.document_type,
                topic         = EXCLUDED.topic,
                chunk_text    = EXCLUDED.chunk_text,
                embedding     = EXCLUDED.embedding,
                ingested_at   = NOW()
            RETURNING id
            """,
            (
                chunk.knowledge_document_id,
                chunk.school,
                chunk.program,
                chunk.year,
                chunk.document_type,
                chunk.topic,
                chunk.chunk_text,
                _vector_literal(chunk.embedding),
                chunk.source_url,
                chunk.span_start,
                chunk.span_end,
            ),
        )
        chunk_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        return chunk_id

    @staticmethod
    def _row_to_chunk(row) -> KnowledgeChunk:
        return KnowledgeChunk(
            knowledge_document_id=row[1],
            school=row[2],
            program=row[3],
            year=row[4],
            document_type=row[5],
            topic=row[6],
            chunk_text=row[7],
            source_url=row[8],
            span_start=row[9],
            span_end=row[10],
        )

    def search_by_metadata(self, school, topic=None, limit=20):
        conn = self.connection_factory()
        cur = conn.cursor()
        sql = f"SELECT id, {_CHUNK_COLUMNS} FROM knowledge_chunks WHERE school = %s"
        params = [school]
        if topic is not None:
            sql += " AND topic = %s"
            params.append(topic)
        sql += " ORDER BY id LIMIT %s"
        params.append(limit)
        cur.execute(sql, tuple(params))
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [self._row_to_chunk(row) for row in rows]

    @staticmethod
    def _row_to_scored(row) -> ScoredChunk:
        return ScoredChunk(
            knowledge_document_id=row[1],
            school=row[2],
            program=row[3],
            year=row[4],
            document_type=row[5],
            topic=row[6],
            chunk_text=row[7],
            source_url=row[8],
            span_start=row[9],
            span_end=row[10],
            score=row[11],
        )

    def vector_search(self, embedding, school=None, topic=None, limit=5):
        literal = _vector_literal(embedding)
        conn = self.connection_factory()
        cur = conn.cursor()
        sql = (
            f"SELECT id, {_CHUNK_COLUMNS}, "
            "1 - (embedding <=> %s::vector) AS score "
            "FROM knowledge_chunks WHERE embedding IS NOT NULL"
        )
        params = [literal]
        if school is not None:
            sql += " AND school = %s"
            params.append(school)
        if topic is not None:
            sql += " AND topic = %s"
            params.append(topic)
        sql += " ORDER BY embedding <=> %s::vector LIMIT %s"
        params.append(literal)
        params.append(limit)
        cur.execute(sql, tuple(params))
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [self._row_to_scored(row) for row in rows]

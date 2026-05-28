from fastapi.encoders import jsonable_encoder
from psycopg2.extras import Json

from services.chat.db import get_db_connection


class TraceRepository:
    def __init__(self, connection_factory=get_db_connection):
        self.connection_factory = connection_factory

    def start_event(self, run_id: int, stage: str, sequence: int) -> int:
        conn = self.connection_factory()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO advisory_trace_events
                (run_id, stage, status, sequence, started_at)
            VALUES (%s, %s, %s, %s, NOW())
            RETURNING id
            """,
            (run_id, stage, "running", sequence),
        )
        event_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        return event_id

    def complete_event(self, event_id: int, output_json: dict) -> None:
        conn = self.connection_factory()
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE advisory_trace_events
            SET status = 'completed',
                completed_at = NOW(),
                duration_ms = EXTRACT(MILLISECONDS FROM (NOW() - started_at))::INTEGER,
                output_json = %s
            WHERE id = %s
            """,
            (Json(jsonable_encoder(output_json)), event_id),
        )
        conn.commit()
        cur.close()
        conn.close()

    def fail_event(self, event_id: int, error_text: str) -> None:
        conn = self.connection_factory()
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE advisory_trace_events
            SET status = 'failed',
                completed_at = NOW(),
                duration_ms = EXTRACT(MILLISECONDS FROM (NOW() - started_at))::INTEGER,
                error_text = %s
            WHERE id = %s
            """,
            (error_text, event_id),
        )
        conn.commit()
        cur.close()
        conn.close()

    def list_events_for_run(self, run_id: int) -> list[dict]:
        conn = self.connection_factory()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, stage, status, sequence, started_at, completed_at,
                   duration_ms, output_json, error_text
            FROM advisory_trace_events
            WHERE run_id = %s
            ORDER BY sequence ASC
            """,
            (run_id,),
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [
            {
                "id": r[0],
                "stage": r[1],
                "status": r[2],
                "sequence": r[3],
                "started_at": r[4],
                "completed_at": r[5],
                "duration_ms": r[6],
                "output_json": r[7],
                "error_text": r[8],
            }
            for r in rows
        ]

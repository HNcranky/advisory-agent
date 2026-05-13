from fastapi.encoders import jsonable_encoder
from psycopg2.extras import Json

from services.chat.db import get_db_connection
from services.chat.models import ChatSessionRecord, ChatMessageRecord, ChatProfileState


class ChatSessionRepository:
    def __init__(self, connection_factory=get_db_connection):
        self.connection_factory = connection_factory

    def _jsonb(self, value):
        return Json(jsonable_encoder(value))

    def create_session(self, session_token: str) -> ChatSessionRecord:
        conn = self.connection_factory()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO chat_sessions (session_token)
            VALUES (%s)
            RETURNING id, session_token, status, profile_state_json, latest_run_id
            """,
            (session_token,),
        )
        row = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
        return ChatSessionRecord(
            id=row[0],
            session_token=row[1],
            status=row[2],
            profile_state_json=row[3] or {},
            latest_run_id=row[4],
        )

    def get_session_by_token(self, session_token: str):
        conn = self.connection_factory()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, session_token, status, profile_state_json, latest_run_id
            FROM chat_sessions
            WHERE session_token = %s
            """,
            (session_token,),
        )
        row = cur.fetchone()
        cur.close()
        conn.close()
        if not row:
            return None
        return ChatSessionRecord(
            id=row[0],
            session_token=row[1],
            status=row[2],
            profile_state_json=row[3] or {},
            latest_run_id=row[4],
        )
        
    def append_message(self, session_token: str, role: str, content: str, kind: str = "chat"):
        conn = self.connection_factory()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO chat_messages (session_id, role, kind, content)
            SELECT id, %s, %s, %s
            FROM chat_sessions
            WHERE session_token = %s
            RETURNING id
            """,
            (role, kind, content, session_token)
        )
        row = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
        return ChatMessageRecord(
            id = row[0],
            session_token=session_token,
            role = role,
            kind = kind,
            content=content
        )
    
    def list_message(self, session_token: str):
        conn = self.connection_factory()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT m.id, s.session_token, m.role, m.kind, m.content
            FROM chat_messages m
            JOIN chat_sessions s ON s.id = m.session_id
            WHERE s.session_token = %s
            ORDER BY m.created_at ASC, m.id ASC
            """,
            (session_token,),
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [
            ChatMessageRecord(
                id = row[0],
                session_token = row[1],
                role = row[2],
                kind = row[3],
                content = row[4],
            )
            for row in rows
        ]
    
    def get_profile_state(self, session_token: str):
        session = self.get_session_by_token(session_token)
        return ChatProfileState(**session.profile_state_json) if session else ChatProfileState()
    
    def update_profile_state(self, session_token: str, profile_state, status: str):
        conn = self.connection_factory()
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE chat_sessions
            SET profile_state_json = %s, status = %s, updated_at = NOW()
            WHERE session_token = %s
            """,
            (self._jsonb(profile_state), status, session_token),
        )
        conn.commit()
        cur.close()
        conn.close()
        return profile_state
    
    def create_run(self, session_token: str, profile_state):
        conn = self.connection_factory()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO chat_advisory_runs (session_id, profile_snapshot_json)
            SELECT id, %s
            FROM chat_sessions
            WHERE session_token = %s
            RETURNING id
            """,
            (self._jsonb(profile_state), session_token)
        )
        
        run_id = cur.fetchone()[0]
        cur.execute(
            """
            UPDATE chat_sessions
            SET latest_run_id = %s, status = 'running', updated_at = NOW()
            WHERE session_token = %s
            """,
            (run_id, session_token),
        )
        conn.commit()
        cur.close()
        conn.close()
        return run_id
    
    def mark_run_running(self, run_id: int):
        conn = self.connection_factory()
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE chat_advisory_runs
            SET status = 'running', started_at = NOW()
            WHERE id = %s
            """,
            (run_id,),
        )
        conn.commit()
        cur.close()
        conn.close()
        
    def complete_run(self, run_id: int, result_json, final_answer: str):
        conn = self.connection_factory()
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE chat_advisory_runs
            SET status = 'completed', result_json = %s, final_answer = %s, completed_at = NOW()
            WHERE id = %s
            """,
            (self._jsonb(result_json), final_answer, run_id)
        )
        conn.commit()
        cur.close()
        conn.close()
        
    def update_session_status(self, session_token: str, status: str):
        conn = self.connection_factory()
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE chat_sessions
            SET status = %s, updated_at = NOW()
            WHERE session_token = %s
            """,
            (status, session_token),
        )
        conn.commit()
        cur.close()
        conn.close()

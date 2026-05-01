from services.chat.db import get_db_connection
from services.chat.models import ChatSessionRecord


class ChatSessionRepository:
    def __init__(self, connection_factory=get_db_connection):
        self.connection_factory = connection_factory

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
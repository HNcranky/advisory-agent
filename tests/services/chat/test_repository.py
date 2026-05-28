from psycopg2.extras import Json

from services.chat.models import ChatProfileState
from services.chat.repository import ChatSessionRepository


class FakeCursor:
    def __init__(self):
        self.statements = []
        self._row = (
            1,
            "session-123",
            "collecting_profile",
            {},
            None,
        )
        self._rows = [
            (1, "session-123", "assistant", "assistant_welcome", "Chào bạn"),
            (2, "session-123", "user", "user_message", "Em muon hoc CNTT"),
        ]

    def execute(self, sql, params):
        self.statements.append((sql, params))

    def fetchone(self):
        return self._row
    
    def fetchall(self):
        return self._rows

    def close(self):
        return None


class FakeConnection:
    def __init__(self):
        self.cursor_obj = FakeCursor()
        self.committed = False

    def cursor(self):
        return self.cursor_obj

    def commit(self):
        self.committed = True

    def close(self):
        return None


def test_create_session_persists_token_and_returns_record():
    connection = FakeConnection()
    repo = ChatSessionRepository(connection_factory=lambda: connection)

    session = repo.create_session("session-123")

    assert session.session_token == "session-123"
    assert session.status == "collecting_profile"
    assert "INSERT INTO chat_sessions" in connection.cursor_obj.statements[0][0]
    assert connection.committed is True
    
    
def test_list_message_returns_transcript_in_order():
    connection = FakeConnection()
    repo = ChatSessionRepository(connection_factory=lambda: connection)

    messages = repo.list_message("session-123")

    assert [message.kind for message in messages] == [
        "assistant_welcome",
        "user_message",
    ]
    sql = connection.cursor_obj.statements[0][0]
    assert "JOIN chat_sessions s ON s.id = m.session_id" in sql
    assert "WHERE s.session_token = %s" in sql


def test_repository_wraps_jsonb_payloads_with_psycopg2_json_adapter():
    connection = FakeConnection()
    repo = ChatSessionRepository(connection_factory=lambda: connection)
    profile_state = ChatProfileState(
        admission_year=2026,
        preferred_majors=["computer_science"],
        missing_slots=["total_score"],
    )

    repo.update_profile_state("session-123", profile_state, "collecting_profile")
    repo.create_run("session-123", profile_state)
    repo.complete_run(7, {"final_answer": "ok", "profile_state": profile_state}, "ok")

    update_params = connection.cursor_obj.statements[0][1]
    create_run_params = connection.cursor_obj.statements[1][1]
    complete_run_params = connection.cursor_obj.statements[3][1]

    assert isinstance(update_params[0], Json)
    assert isinstance(create_run_params[0], Json)
    assert isinstance(complete_run_params[0], Json)
    assert complete_run_params[0].adapted["profile_state"]["admission_year"] == 2026


class FakeCursorRunStatus(FakeCursor):
    def __init__(self, status):
        super().__init__()
        self._row = (status,)


def test_get_run_status_returns_status_string():
    conn = FakeConnection()
    conn.cursor_obj = FakeCursorRunStatus("running")
    repo = ChatSessionRepository(connection_factory=lambda: conn)

    status = repo.get_run_status(run_id=42)

    sql, params = conn.cursor_obj.statements[0]
    assert status == "running"
    assert "SELECT status" in sql and "chat_advisory_runs" in sql
    assert params == (42,)


def test_get_run_status_returns_none_when_missing():
    class EmptyCursor(FakeCursor):
        def fetchone(self):
            return None
    conn = FakeConnection()
    conn.cursor_obj = EmptyCursor()
    repo = ChatSessionRepository(connection_factory=lambda: conn)

    assert repo.get_run_status(run_id=999) is None

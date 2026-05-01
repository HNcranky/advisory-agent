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

    def execute(self, sql, params):
        self.statements.append((sql, params))

    def fetchone(self):
        return self._row

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
from fastapi.testclient import TestClient

from services.chat.models import ChatProfileState, ConversationTurnResult, ChatMessageRecord, ChatSessionSnapshot
from web.app import build_app


def test_post_message_returns_follow_up_payload(monkeypatch):
    client = TestClient(build_app())

    class FakeService:
        def handle_user_message(self, session_token, content):
            assert session_token == "session-123"
            assert content == "Em muon hoc CNTT"
            return ConversationTurnResult(
                session_status="collecting_profile",
                assistant_message="Tong diem hoac muc diem uoc tinh cua ban la bao nhieu?",
                should_start_run=False,
                profile_state=ChatProfileState(
                    admission_year=2026,
                    preferred_majors=["computer_science"],
                    location_preference="Ha Noi",
                    missing_slots=["total_score"],
                ),
            )

    monkeypatch.setattr("web.routes.chat_api.get_conversation_service", lambda: FakeService())

    response = client.post(
        "/api/sessions/session-123/messages",
        json={"content": "Em muon hoc CNTT"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["session_status"] == "collecting_profile"
    assert body["should_start_run"] is False
    assert body["profile_state"]["missing_slots"] == ["total_score"]


def test_post_message_returns_ready_payload(monkeypatch):
    client = TestClient(build_app())

    class FakeService:
        def handle_user_message(self, session_token, content):
            return ConversationTurnResult(
                session_status="ready",
                assistant_message="Cam on ban. Minh da co du thong tin va se bat dau phan tich.",
                should_start_run=True,
                profile_state=ChatProfileState(
                    admission_year=2026,
                    total_score=27.0,
                    preferred_majors=["computer_science"],
                    location_preference="Ha Noi",
                    missing_slots=[],
                ),
            )

    monkeypatch.setattr("web.routes.chat_api.get_conversation_service", lambda: FakeService())

    response = client.post(
        "/api/sessions/session-123/messages",
        json={"content": "Em muon hoc CNTT tai Ha Noi nam 2026 va duoc 27 diem"},
    )

    assert response.status_code == 200
    assert response.json()["should_start_run"] is True
    
    
def test_create_session_endpoint_returns_snapshot(monkeypatch):
    client = TestClient(build_app())

    class FakeSessionService:
        def start_session(self):
            return ChatSessionSnapshot(
                session={
                    "id": 1,
                    "session_token": "session-123",
                    "status": "collecting_profile",
                    "profile_state_json": {},
                    "latest_run_id": None,
                },
                messages=[
                    ChatMessageRecord(
                        id=1,
                        session_token="session-123",
                        role="assistant",
                        kind="assistant_welcome",
                        content="Chao ban",
                    )
                ],
            )

    monkeypatch.setattr("web.routes.chat_api.get_session_service", lambda: FakeSessionService())

    response = client.post("/api/sessions")

    assert response.status_code == 201
    body = response.json()
    assert body["session"]["session_token"] == "session-123"
    assert body["messages"][0]["kind"] == "assistant_welcome"


def test_get_session_endpoint_returns_404_when_missing(monkeypatch):
    client = TestClient(build_app())

    class FakeSessionService:
        def get_session_snapshot(self, session_token):
            return ChatSessionSnapshot(session=None, messages=[])

    monkeypatch.setattr("web.routes.chat_api.get_session_service", lambda: FakeSessionService())

    response = client.get("/api/sessions/missing-token")

    assert response.status_code == 404
    assert response.json()["detail"] == "Session not found"
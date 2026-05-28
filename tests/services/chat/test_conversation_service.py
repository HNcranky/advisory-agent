from agents.models import StudentProfile
from services.chat.conversation_service import ConversationService
from services.chat.models import ChatProfileState


class FakeRepository:
    def __init__(self):
        self.profile_state = ChatProfileState()
        self.messages = []
        self.status = "collecting_profile"

    def append_message(self, session_token, role, content, kind="chat"):
        self.messages.append((role, kind, content))

    def get_profile_state(self, session_token):
        return self.profile_state

    def update_profile_state(self, session_token, profile_state, status):
        self.profile_state = profile_state
        self.status = status
        return profile_state


def test_handle_user_message_returns_follow_up_when_score_missing():
    repo = FakeRepository()
    service = ConversationService(
        repository=repo,
        extract_profile=lambda text: StudentProfile(
            preferred_majors=["computer_science"],
            location_preference="Ha Noi",
        ),
    )

    result = service.handle_user_message("session-123", "Em muon hoc CNTT tai Ha Noi nam 2026")

    assert result.session_status == "collecting_profile"
    assert result.should_start_run is False
    assert "bao nhiêu" in result.assistant_message.lower()

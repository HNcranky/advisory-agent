from services import build_default_gateway
from services.chat.models import ConversationTurnResult
from services.chat.profile_state_service import merge_profile_state, next_follow_up_question
from services.chat.repository import ChatSessionRepository
from services.profile_inference_service import build_profile_with_gateway

class ConversationService:
    def __init__(self, repository = None, extract_profile = None):
        self.repository = repository or ChatSessionRepository()
        self.extract_profile = extract_profile or self._extract_profile
        
    def _extract_profile(self, text: str):
        gateway = build_default_gateway()
        return build_profile_with_gateway(text, gateway)
    
    def handle_user_message(self, session_token: str, content: str) -> ConversationTurnResult:
        self.repository.append_message(session_token, "user", content, "user_message")
        current = self.repository.get_profile_state(session_token)
        extracted = self.extract_profile(content)
        merged = merge_profile_state(current, extracted, content)
        
        follow_up = next_follow_up_question(merged)
        if follow_up:
            self.repository.update_profile_state(session_token, merged, "collecting_profile")
            self.repository.append_message(session_token, "assistant", follow_up, "assistant_follow_up")
            return ConversationTurnResult(
                session_status="collecting_profile",
                assistant_message=follow_up,
                should_start_run=False,
                profile_state=merged,
            )
        
        ready_message = "Cam on ban. Minh da co du thong tin va se bat dau phan tich."
        self.repository.update_profile_state(session_token, merged, "ready")
        self.repository.append_message(session_token, "assistant", ready_message, "assistant_ready")
        return ConversationTurnResult(
            session_status="ready",
            assistant_message = ready_message,
            should_start_run=True,
            profile_state=merged,
        )
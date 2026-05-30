from services import build_default_gateway
from services.chat.intent_router import IntentRouter
from services.chat.models import ConversationTurnResult
from services.chat.profile_state_service import merge_profile_state, next_follow_up_question
from services.chat.repository import ChatSessionRepository
from services.profile_inference_service import build_profile_with_gateway


class ConversationService:
    def __init__(self, repository=None, extract_profile=None, intent_router=None):
        self.repository = repository or ChatSessionRepository()
        self.extract_profile = extract_profile or self._extract_profile
        self.intent_router = intent_router or IntentRouter()

    def _extract_profile(self, text: str):
        gateway = build_default_gateway()
        return build_profile_with_gateway(text, gateway)

    _TOPIC_LABELS = {
        "tuition": "học phí",
        "curriculum": "chương trình học",
        "scholarship": "học bổng",
        "dormitory": "ký túc xá",
        "career": "định hướng nghề nghiệp",
        "admission_policy": "chính sách tuyển sinh",
        "program_overview": "tổng quan chương trình",
    }

    def handle_user_message(self, session_token: str, content: str) -> ConversationTurnResult:
        self.repository.append_message(session_token, "user", content, "user_message")
        session = self.repository.get_session_by_token(session_token)
        profile_state = self.repository.get_profile_state(session_token)
        flow_state = self.repository.get_flow_state(session_token)
        intent = self.intent_router.classify(content, profile_state)
        session_status = session.status if session else "collecting_profile"

        if intent.route == "ADVISORY_FLOW":
            return self._handle_advisory(session_token, content, profile_state, flow_state)
        # HYBRID has no orchestration in Phase 1 → reuse the knowledge fallback
        # (the question is well-formed; "no data yet" beats asking to clarify).
        if intent.route in ("KNOWLEDGE_QA", "HYBRID"):
            return self._handle_knowledge_qa(session_token, intent, profile_state, flow_state, session_status)
        if intent.route == "OUT_OF_SCOPE":
            return self._handle_out_of_scope(session_token, profile_state, flow_state, session_status)
        return self._handle_clarification(session_token, profile_state, flow_state, session_status)

    def _handle_advisory(self, session_token, content, profile_state, flow_state):
        extracted = self.extract_profile(content)
        merged = merge_profile_state(profile_state, extracted, content)

        follow_up = next_follow_up_question(merged)
        if follow_up:
            self.repository.update_profile_state(session_token, merged, "collecting_profile")
            self.repository.update_flow_state(
                session_token,
                flow_state.model_copy(update={
                    "active_flow": "ADVISORY_FLOW",
                    "pending_question": follow_up,
                }),
            )
            self.repository.append_message(session_token, "assistant", follow_up, "assistant_follow_up")
            return ConversationTurnResult(
                session_status="collecting_profile",
                assistant_message=follow_up,
                should_start_run=False,
                profile_state=merged,
            )

        ready_message = "Cảm ơn bạn. Mình đã có đủ thông tin và sẽ bắt đầu phân tích."
        self.repository.update_profile_state(session_token, merged, "ready")
        self.repository.update_flow_state(
            session_token,
            flow_state.model_copy(update={
                "active_flow": "ADVISORY_FLOW",
                "pending_question": None,  # clear: no question is pending once we run
            }),
        )
        self.repository.append_message(session_token, "assistant", ready_message, "assistant_ready")
        return ConversationTurnResult(
            session_status="ready",
            assistant_message=ready_message,
            should_start_run=True,
            profile_state=merged,
        )

    def _handle_knowledge_qa(self, session_token, intent, profile_state, flow_state, session_status):
        # Phase 1: no RAG data yet → always fallback. Do NOT touch profile or flow_state.
        topic_label = self._TOPIC_LABELS.get(intent.topic or "", "thông tin này")
        school_label = intent.school or "trường bạn hỏi"
        fallback = (
            f"Hệ thống chưa có dữ liệu về {topic_label} của {school_label}. "
            f"Bạn có thể liên hệ trực tiếp nhà trường để biết thêm chi tiết."
        )
        response = self._append_return_prompt(fallback, flow_state)
        self.repository.append_message(session_token, "assistant", response, "assistant_result")
        return ConversationTurnResult(
            session_status=session_status,
            assistant_message=response,
            should_start_run=False,
            profile_state=profile_state,
        )

    def _handle_out_of_scope(self, session_token, profile_state, flow_state, session_status):
        msg = (
            "Xin lỗi, câu hỏi này nằm ngoài phạm vi tư vấn tuyển sinh của mình. "
            "Mình chỉ có thể hỗ trợ các vấn đề liên quan đến tuyển sinh đại học."
        )
        response = self._append_return_prompt(msg, flow_state)
        self.repository.append_message(session_token, "assistant", response, "assistant_result")
        return ConversationTurnResult(
            session_status=session_status,
            assistant_message=response,
            should_start_run=False,
            profile_state=profile_state,
        )

    def _handle_clarification(self, session_token, profile_state, flow_state, session_status):
        msg = "Bạn có thể nói rõ hơn câu hỏi của mình không? Mình muốn hiểu đúng để hỗ trợ tốt hơn."
        response = self._append_return_prompt(msg, flow_state)
        self.repository.append_message(session_token, "assistant", response, "assistant_result")
        return ConversationTurnResult(
            session_status=session_status,
            assistant_message=response,
            should_start_run=False,
            profile_state=profile_state,
        )

    def _append_return_prompt(self, message: str, flow_state) -> str:
        """Re-ask the pending advisory question iff the user is mid-advisory-flow.

        Keyed off active_flow + pending_question (both persisted during the prior
        advisory turn), so the re-ask fires on the FIRST off-topic turn — no flag
        that gets set only after the response is built.
        """
        if flow_state.active_flow == "ADVISORY_FLOW" and flow_state.pending_question:
            return f"{message}\n\nNhân tiện, {flow_state.pending_question}"
        return message

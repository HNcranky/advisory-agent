from types import SimpleNamespace

from agents.models import StudentProfile
from services.chat.conversation_service import ConversationService
from services.chat.models import ChatProfileState, FlowState
from services.chat.intent_router import IntentResult
from services.knowledge.models import Citation, KnowledgeQAResult


class FakeRepository:
    def __init__(self):
        self.profile_state = ChatProfileState()
        self.flow_state = FlowState()
        self.messages = []
        self.status = "collecting_profile"

    def append_message(self, session_token, role, content, kind="chat"):
        self.messages.append((role, kind, content))

    def get_session_by_token(self, session_token):
        # Only .status is read by ConversationService.
        return SimpleNamespace(session_token=session_token, status=self.status)

    def get_profile_state(self, session_token):
        return self.profile_state

    def update_profile_state(self, session_token, profile_state, status):
        self.profile_state = profile_state
        self.status = status
        return profile_state

    def get_flow_state(self, session_token):
        return self.flow_state

    def update_flow_state(self, session_token, flow_state):
        self.flow_state = flow_state


class FakeIntentRouter:
    def __init__(self, result: IntentResult):
        self._result = result

    def classify(self, message, profile_state):
        return self._result


class FakeKnowledgeQA:
    def __init__(self, result=None, raise_exc=False):
        self._result = result
        self._raise = raise_exc
        self.calls = []

    def answer(self, question, school, topic, conversation_context=""):
        self.calls.append({"question": question, "school": school, "topic": topic})
        if self._raise:
            raise RuntimeError("simulated knowledge-qa failure")
        if self._result is not None:
            return self._result
        return KnowledgeQAResult(has_data=False, confidence=0.0)


def _make_service(intent_result=None, profile=None, flow=None, status=None, extract=None, knowledge_qa=None):
    """Build a ConversationService backed by fakes. Returns (service, repo)."""
    repo = FakeRepository()
    if profile is not None:
        repo.profile_state = profile
    if flow is not None:
        repo.flow_state = flow
    if status is not None:
        repo.status = status
    router = FakeIntentRouter(intent_result or IntentResult(route="ADVISORY_FLOW"))
    service = ConversationService(
        repository=repo,
        extract_profile=extract or (lambda text: StudentProfile()),
        intent_router=router,
        knowledge_qa=knowledge_qa or FakeKnowledgeQA(),
    )
    return service, repo


# ─── existing test (unchanged) ───────────────────────────────────────────────

def test_handle_user_message_returns_follow_up_when_score_missing():
    repo = FakeRepository()
    service = ConversationService(
        repository=repo,
        extract_profile=lambda text: StudentProfile(
            preferred_majors=["computer_science"],
            location_preference="Ha Noi",
        ),
        intent_router=FakeIntentRouter(IntentResult(route="ADVISORY_FLOW")),
    )

    result = service.handle_user_message("session-123", "Em muon hoc CNTT tai Ha Noi nam 2026")

    assert result.session_status == "collecting_profile"
    assert result.should_start_run is False
    assert "bao nhiêu" in result.assistant_message.lower()


# ─── Task 2: injection test ───────────────────────────────────────────────────

def test_conversation_service_accepts_intent_router_injection():
    repo = FakeRepository()
    router = FakeIntentRouter(IntentResult(route="ADVISORY_FLOW"))
    service = ConversationService(
        repository=repo,
        extract_profile=lambda text: StudentProfile(),
        intent_router=router,
    )
    assert service.intent_router is router


# ─── Resume offer (natural, không lặp câu hỏi cũ) ─────────────────────────────

def test_maybe_offer_resume_adds_offer_when_in_advisory_flow():
    service, _ = _make_service()
    flow = FlowState(active_flow="ADVISORY_FLOW", pending_question="Bạn học khối gì?")
    result = service._maybe_offer_resume("Xin lỗi, ngoài phạm vi.", flow)
    assert "Xin lỗi, ngoài phạm vi." in result
    assert service.RESUME_OFFER in result
    assert "Bạn học khối gì?" not in result  # KHÔNG lặp lại câu hỏi cũ


def test_maybe_offer_resume_skips_when_no_active_flow():
    service, _ = _make_service()
    flow = FlowState(active_flow=None, pending_question="Bạn học khối gì?")
    result = service._maybe_offer_resume("Xin lỗi, ngoài phạm vi.", flow)
    assert result == "Xin lỗi, ngoài phạm vi."


def test_maybe_offer_resume_skips_when_no_pending_question():
    service, _ = _make_service()
    flow = FlowState(active_flow="ADVISORY_FLOW", pending_question=None)
    result = service._maybe_offer_resume("Xin lỗi, ngoài phạm vi.", flow)
    assert result == "Xin lỗi, ngoài phạm vi."


# ─── Task 4: branch handler tests ────────────────────────────────────────────

def test_handle_out_of_scope_returns_polite_decline():
    service, _ = _make_service(intent_result=IntentResult(route="OUT_OF_SCOPE"))
    result = service.handle_user_message("tok", "thời tiết hôm nay")
    assert result.should_start_run is False
    assert "ngoài phạm vi" in result.assistant_message


def test_handle_out_of_scope_preserves_session_status():
    service, _ = _make_service(intent_result=IntentResult(route="OUT_OF_SCOPE"), status="ready")
    result = service.handle_user_message("tok", "thời tiết hôm nay")
    assert result.session_status == "ready"


def test_handle_clarification_returns_clarification_request():
    service, _ = _make_service(intent_result=IntentResult(route="CLARIFICATION"))
    result = service.handle_user_message("tok", "ý bạn là gì")
    assert result.should_start_run is False
    assert "rõ hơn" in result.assistant_message


def test_no_reask_when_not_in_advisory_flow():
    service, _ = _make_service(
        intent_result=IntentResult(route="OUT_OF_SCOPE"),
        flow=FlowState(),  # active_flow=None
    )
    result = service.handle_user_message("tok", "thời tiết hôm nay")
    assert "Nhân tiện" not in result.assistant_message


# ─── Task 5: KNOWLEDGE_QA + HYBRID ───────────────────────────────────────────

def test_handle_knowledge_qa_returns_fallback_with_topic_and_school():
    service, _ = _make_service(
        intent_result=IntentResult(route="KNOWLEDGE_QA", topic="tuition", school="VNU-UET"),
    )
    result = service.handle_user_message("tok", "học phí UET bao nhiêu")
    assert result.should_start_run is False
    assert "học phí" in result.assistant_message
    assert "VNU-UET" in result.assistant_message


def test_handle_knowledge_qa_label_when_school_null():
    service, _ = _make_service(
        intent_result=IntentResult(route="KNOWLEDGE_QA", topic="tuition", school=None),
    )
    result = service.handle_user_message("tok", "học phí bao nhiêu")
    assert "trường bạn hỏi" in result.assistant_message


def test_handle_knowledge_qa_label_when_topic_null():
    service, _ = _make_service(
        intent_result=IntentResult(route="KNOWLEDGE_QA", topic=None, school="NEU"),
    )
    result = service.handle_user_message("tok", "cho mình hỏi về NEU")
    assert "thông tin này" in result.assistant_message


def test_handle_knowledge_qa_does_not_mutate_flow_state():
    flow = FlowState(active_flow="ADVISORY_FLOW", pending_question="Bạn học khối gì?")
    service, repo = _make_service(
        intent_result=IntentResult(route="KNOWLEDGE_QA", topic="tuition", school="NEU"),
        profile=ChatProfileState(total_score=25.0),
        flow=flow,
    )
    service.handle_user_message("tok", "học phí NEU bao nhiêu")
    assert repo.flow_state == flow  # untouched


def test_handle_knowledge_qa_does_not_reset_profile():
    original = ChatProfileState(
        total_score=25.5,
        preferred_majors=["computer_science"],
        preferred_schools=["VNU-UET"],
    )
    service, repo = _make_service(
        intent_result=IntentResult(route="KNOWLEDGE_QA", topic="tuition", school="VNU-UET"),
        profile=original,
    )
    result = service.handle_user_message("tok", "học phí UET bao nhiêu")
    assert result.profile_state.total_score == 25.5
    assert result.profile_state.preferred_majors == ["computer_science"]
    assert repo.profile_state.total_score == 25.5


def test_handle_hybrid_uses_knowledge_qa_fallback():
    service, _ = _make_service(intent_result=IntentResult(route="HYBRID"))
    result = service.handle_user_message("tok", "so sánh UET và HUST về điểm chuẩn lẫn học phí")
    assert result.should_start_run is False
    assert "chưa có dữ liệu" in result.assistant_message


# ─── Task 6: Advisory flow-state tracking ────────────────────────────────────

def test_handle_advisory_saves_pending_question():
    service, repo = _make_service(
        intent_result=IntentResult(route="ADVISORY_FLOW"),
        extract=lambda text: StudentProfile(
            preferred_majors=["computer_science"],
            location_preference="Ha Noi",
        ),
    )
    service.handle_user_message("tok", "Em muon hoc CNTT tai Ha Noi nam 2026")
    assert repo.flow_state.active_flow == "ADVISORY_FLOW"
    assert repo.flow_state.pending_question  # non-empty


def test_handle_advisory_clears_pending_question_when_complete():
    service, repo = _make_service(
        intent_result=IntentResult(route="ADVISORY_FLOW"),
        flow=FlowState(active_flow="ADVISORY_FLOW", pending_question="old question"),
        extract=lambda text: StudentProfile(
            total_score=25.0,
            subject_combination="A00",
            preferred_majors=["computer_science"],
            location_preference="Ha Noi",
        ),
    )
    result = service.handle_user_message("tok", "25 điểm A00 CNTT Hà Nội 2026")
    assert result.should_start_run is True
    assert repo.flow_state.active_flow == "ADVISORY_FLOW"
    assert repo.flow_state.pending_question is None


def test_handle_advisory_preserves_existing_profile_fields():
    service, repo = _make_service(
        intent_result=IntentResult(route="ADVISORY_FLOW"),
        profile=ChatProfileState(total_score=25.0, subject_combination="A00"),
        extract=lambda text: StudentProfile(
            preferred_majors=["computer_science"],
            location_preference="Ha Noi",
        ),
    )
    result = service.handle_user_message("tok", "Em muon hoc CNTT tai Ha Noi")
    assert result.profile_state.total_score == 25.0
    assert result.profile_state.subject_combination == "A00"
    assert "computer_science" in result.profile_state.preferred_majors


# ─── Acceptance Criteria ──────────────────────────────────────────────────────

def test_ac_knowledge_qa_does_not_trigger_run():
    service, _ = _make_service(
        intent_result=IntentResult(route="KNOWLEDGE_QA", topic="tuition", school="VNU-UET"),
    )
    result = service.handle_user_message("tok", "học phí UET bao nhiêu?")
    assert result.should_start_run is False


def test_ac_advisory_flow_unchanged():
    service, _ = _make_service(
        intent_result=IntentResult(route="ADVISORY_FLOW"),
        extract=lambda text: StudentProfile(
            preferred_majors=["computer_science"],
            location_preference="Ha Noi",
        ),
    )
    result = service.handle_user_message("tok", "Em 25 điểm A00 nên chọn ngành gì?")
    assert result.session_status == "collecting_profile"
    assert result.should_start_run is False


def test_ac_out_of_scope_polite():
    service, _ = _make_service(intent_result=IntentResult(route="OUT_OF_SCOPE"))
    result = service.handle_user_message("tok", "thời tiết hôm nay thế nào?")
    assert result.should_start_run is False
    assert "ngoài phạm vi" in result.assistant_message


def test_ac_knowledge_qa_fallback_format():
    service, _ = _make_service(
        intent_result=IntentResult(route="KNOWLEDGE_QA", topic="tuition", school="VNU-UET"),
    )
    result = service.handle_user_message("tok", "học phí UET bao nhiêu?")
    assert "chưa có dữ liệu" in result.assistant_message
    assert "học phí" in result.assistant_message
    assert "VNU-UET" in result.assistant_message
    assert "liên hệ" in result.assistant_message


def test_ac_resume_offer_appears_on_first_detour():
    """Rẽ ngang khỏi advisory flow → offer quay lại tự nhiên, KHÔNG lặp câu hỏi cũ."""
    flow = FlowState(
        active_flow="ADVISORY_FLOW",
        pending_question="Tổng điểm hoặc mức điểm ước tính của bạn là bao nhiêu?",
    )
    service, _ = _make_service(
        intent_result=IntentResult(route="OUT_OF_SCOPE"),
        profile=ChatProfileState(preferred_majors=["computer_science"]),
        flow=flow,
    )
    result = service.handle_user_message("tok", "thời tiết hôm nay thế nào?")
    assert service.RESUME_OFFER in result.assistant_message
    assert "Tổng điểm" not in result.assistant_message  # không lặp câu hỏi cũ


def test_ac_profile_not_reset_on_side_query():
    original = ChatProfileState(
        total_score=27.0,
        subject_combination="A00",
        preferred_majors=["computer_science"],
        preferred_schools=["VNU-UET"],
        location_preference="Ha Noi",
    )
    service, repo = _make_service(
        intent_result=IntentResult(route="KNOWLEDGE_QA", topic="tuition", school="VNU-UET"),
        profile=original,
    )
    result = service.handle_user_message("tok", "học phí UET bao nhiêu?")
    assert result.profile_state.total_score == 27.0
    assert result.profile_state.location_preference == "Ha Noi"
    assert repo.profile_state.total_score == 27.0


# ─── Phase 4: KnowledgeQA service wiring ─────────────────────────────────────

def test_knowledge_qa_data_answer_is_surfaced_with_sources():
    qa = FakeKnowledgeQA(result=KnowledgeQAResult(
        has_data=True,
        answer="Học phí khoảng 35 triệu/năm.",
        citations=[Citation(source_url="https://uet/hoc-phi", chunk_text="Học phí 35 triệu")],
        confidence=0.9,
    ))
    service, _ = _make_service(
        intent_result=IntentResult(route="KNOWLEDGE_QA", topic="tuition", school="VNU-UET"),
        knowledge_qa=qa,
    )
    result = service.handle_user_message("tok", "học phí UET bao nhiêu")
    assert "35 triệu" in result.assistant_message
    assert "Nguồn:" in result.assistant_message
    assert "https://uet/hoc-phi" in result.assistant_message
    assert len(result.citations) == 1
    assert result.citations[0].source_url == "https://uet/hoc-phi"
    assert result.should_start_run is False


def test_knowledge_qa_data_answer_does_not_reset_profile_or_flow():
    flow = FlowState(active_flow="ADVISORY_FLOW", pending_question="Bạn học khối gì?")
    qa = FakeKnowledgeQA(result=KnowledgeQAResult(
        has_data=True, answer="Học phí 35 triệu.", citations=[], confidence=0.9,
    ))
    service, repo = _make_service(
        intent_result=IntentResult(route="KNOWLEDGE_QA", topic="tuition", school="VNU-UET"),
        profile=ChatProfileState(total_score=25.0),
        flow=flow,
        knowledge_qa=qa,
    )
    result = service.handle_user_message("tok", "học phí UET bao nhiêu")
    assert repo.flow_state == flow          # untouched
    assert repo.profile_state.total_score == 25.0
    assert service.RESUME_OFFER in result.assistant_message  # mid-flow resume offer appended


def test_knowledge_qa_resolves_school_from_preferred_schools_when_intent_school_null():
    qa = FakeKnowledgeQA(result=KnowledgeQAResult(has_data=False))
    service, _ = _make_service(
        intent_result=IntentResult(route="KNOWLEDGE_QA", topic="tuition", school=None),
        profile=ChatProfileState(preferred_schools=["VNU-UET"]),
        knowledge_qa=qa,
    )
    service.handle_user_message("tok", "trường này học phí bao nhiêu")
    assert qa.calls[0]["school"] == "VNU-UET"
    assert qa.calls[0]["question"] == "trường này học phí bao nhiêu"


def test_knowledge_qa_service_error_degrades_to_fallback():
    qa = FakeKnowledgeQA(raise_exc=True)
    service, _ = _make_service(
        intent_result=IntentResult(route="KNOWLEDGE_QA", topic="tuition", school="VNU-UET"),
        knowledge_qa=qa,
    )
    result = service.handle_user_message("tok", "học phí UET bao nhiêu")
    assert "chưa có dữ liệu" in result.assistant_message
    assert result.citations == []


# ─── Phase 5d: HYBRID routing + profile gating ───────────────────────────────

def _complete_profile():
    return ChatProfileState(
        admission_year=2026,
        total_score=27.0,
        preferred_majors=["computer_science"],
        location_preference="Ha Noi",
        preferred_schools=["VNU-UET", "HUST"],
    )


def test_hybrid_complete_profile_dispatches_hybrid_run():
    service, repo = _make_service(
        intent_result=IntentResult(
            route="HYBRID", schools=["VNU-UET", "HUST"], topics=["tuition"], needs_advisory=True,
        ),
        profile=_complete_profile(),
    )
    result = service.handle_user_message("tok", "so sánh UET và HUST điểm chuẩn lẫn học phí")
    assert result.should_start_run is True
    assert result.run_kind == "hybrid"
    assert result.hybrid_intent["route"] == "HYBRID"
    assert result.hybrid_intent["schools"] == ["VNU-UET", "HUST"]
    # a pending placeholder message was posted
    assert repo.messages[-1][1] == "assistant_hybrid_pending"


def test_hybrid_incomplete_profile_answers_knowledge_and_asks_follow_up():
    qa = FakeKnowledgeQA(result=KnowledgeQAResult(
        has_data=True, answer="Học phí UET ~35 triệu/năm.",
        citations=[Citation(source_url="https://uet/hp", chunk_text="..")], confidence=0.9,
    ))
    service, repo = _make_service(
        intent_result=IntentResult(route="HYBRID", schools=["VNU-UET"], topics=["tuition"], needs_advisory=True),
        profile=ChatProfileState(preferred_majors=["computer_science"]),  # missing year/score/location
        knowledge_qa=qa,
    )
    result = service.handle_user_message("tok", "so sánh học phí và điểm chuẩn UET")
    assert result.should_start_run is False
    assert "35 triệu" in result.assistant_message
    assert "Nhân tiện" in result.assistant_message          # advisory follow-up appended
    assert repo.flow_state.active_flow == "ADVISORY_FLOW"
    assert repo.flow_state.pending_question                  # persisted for later re-ask


def test_hybrid_incomplete_profile_no_knowledge_data_still_asks_follow_up():
    service, repo = _make_service(
        intent_result=IntentResult(route="HYBRID", schools=["VNU-UET"], topics=["tuition"], needs_advisory=True),
        profile=ChatProfileState(),  # fully empty
        knowledge_qa=FakeKnowledgeQA(),  # no data
    )
    result = service.handle_user_message("tok", "so sánh UET và HUST")
    assert result.should_start_run is False
    assert "chưa có dữ liệu" in result.assistant_message.lower()
    assert "Nhân tiện" in result.assistant_message


def test_hybrid_does_not_reset_profile():
    profile = _complete_profile()
    service, repo = _make_service(
        intent_result=IntentResult(route="HYBRID", schools=["VNU-UET"], topics=["tuition"], needs_advisory=True),
        profile=profile,
    )
    result = service.handle_user_message("tok", "so sánh UET và HUST")
    assert result.profile_state.total_score == 27.0
    assert repo.profile_state.total_score == 27.0


# ─── Plan 03: CONVERSATIONAL route ───────────────────────────────────────────

def test_handle_conversational_greeting_returns_template_not_clarification():
    service, repo = _make_service(
        intent_result=IntentResult(route="CONVERSATIONAL", subtype="GREETING"),
    )
    result = service.handle_user_message("tok", "xin chào")

    assert result.should_start_run is False
    assert "nói rõ hơn câu hỏi" not in result.assistant_message
    # repo.messages entries are (role, kind, content)
    assistant_msgs = [m for m in repo.messages if m[0] == "assistant"]
    assert len(assistant_msgs) == 1


def test_handle_conversational_greeting_no_resume_when_no_active_flow():
    service, repo = _make_service(
        intent_result=IntentResult(route="CONVERSATIONAL", subtype="GREETING"),
        flow=FlowState(),  # active_flow=None
    )
    result = service.handle_user_message("tok", "xin chào")
    assert "Nhân tiện" not in result.assistant_message


def test_knowledge_route_not_handled_as_conversational():
    # FakeKnowledgeQA mặc định trả has_data=False → message no-data
    service, repo = _make_service(
        intent_result=IntentResult(route="KNOWLEDGE_QA", topic="tuition", school="VNU-UET"),
    )
    result = service.handle_user_message("tok", "Chào bạn, học phí UET?")

    assert "Chào bạn!" not in result.assistant_message          # không phải greeting template
    assert "chưa có dữ liệu" in result.assistant_message.lower()  # đi đúng nhánh knowledge


# ─── Plan 04: Slot-aware clarification ───────────────────────────────────────

def test_clarification_asks_for_missing_school():
    service, repo = _make_service(
        intent_result=IntentResult(route="CLARIFICATION", missing_fields=["school"]),
    )
    result = service.handle_user_message("tok", "học phí trường này thế nào?")
    assert "trường nào" in result.assistant_message.lower()
    assert "nói rõ hơn câu hỏi" not in result.assistant_message


def test_clarification_asks_for_missing_subject_combination():
    service, repo = _make_service(
        intent_result=IntentResult(route="CLARIFICATION", missing_fields=["subject_combination"]),
    )
    result = service.handle_user_message("tok", "25 điểm thì chọn đâu?")
    assert "tổ hợp" in result.assistant_message.lower()


def test_clarification_falls_back_to_generic_when_no_missing_fields():
    service, repo = _make_service(
        intent_result=IntentResult(route="CLARIFICATION"),  # missing_fields=[]
    )
    result = service.handle_user_message("tok", "ý bạn là gì")
    assert "rõ hơn" in result.assistant_message.lower()

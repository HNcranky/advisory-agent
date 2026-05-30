# Phase 1 — Plan 3: ConversationService Routing

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire `IntentRouter` into `ConversationService` — add routing dispatcher, extract each branch into a private method, and implement flow state tracking so the agent re-asks pending advisory questions after answering side-queries.

**Architecture:** `handle_user_message` is refactored into a thin dispatcher that reads `FlowState` from the repository, classifies intent, then delegates to one of four private handlers. `_handle_advisory` preserves all existing logic verbatim, adding only `update_flow_state` side-effects. `_append_return_prompt` is a pure helper with no I/O. `IntentRouter` is injected via constructor — no change to call sites that don't pass it.

**Tech Stack:** Python 3.11, Pydantic v2, pytest

**Depends on:** Plan 1 (FlowState + repository methods) and Plan 2 (IntentRouter + IntentResult) must be complete.

---

### Task 1: Extend FakeRepository and Add FakeIntentRouter

**Files:**
- Modify: `tests/services/chat/test_conversation_service.py`

- [ ] **Step 1: Update FakeRepository and add FakeIntentRouter**

Open `tests/services/chat/test_conversation_service.py`. Replace the entire file with the following (existing test is preserved at the bottom):

```python
from agents.models import StudentProfile
from services.chat.conversation_service import ConversationService
from services.chat.models import ChatProfileState, FlowState
from services.chat.intent_router import IntentResult


class FakeRepository:
    def __init__(self):
        self.profile_state = ChatProfileState()
        self.flow_state = FlowState()
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

    def get_flow_state(self, session_token):
        return self.flow_state

    def update_flow_state(self, session_token, flow_state):
        self.flow_state = flow_state


class FakeIntentRouter:
    def __init__(self, result: IntentResult):
        self._result = result

    def classify(self, message, profile_state):
        return self._result


# ─── existing test (unchanged) ───────────────────────────────────────────────

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
```

- [ ] **Step 2: Run existing test to make sure it still passes**

```
pytest tests/services/chat/test_conversation_service.py -v
```

Expected: 1 passed

- [ ] **Step 3: Commit**

```
git add tests/services/chat/test_conversation_service.py
git commit -m "test: extend FakeRepository with flow_state support and add FakeIntentRouter"
```

---

### Task 2: Wire IntentRouter into ConversationService Constructor

**Files:**
- Modify: `services/chat/conversation_service.py`
- Modify: `tests/services/chat/test_conversation_service.py` (extend)

- [ ] **Step 1: Add failing test**

Append to `tests/services/chat/test_conversation_service.py`:

```python
def test_conversation_service_accepts_intent_router_injection():
    """IntentRouter must be injectable — default constructor should also work without passing one."""
    repo = FakeRepository()
    router = FakeIntentRouter(IntentResult(route="ADVISORY_FLOW"))
    service = ConversationService(
        repository=repo,
        extract_profile=lambda text: StudentProfile(),
        intent_router=router,
    )
    assert service.intent_router is router
```

- [ ] **Step 2: Run test to verify it fails**

```
pytest tests/services/chat/test_conversation_service.py::test_conversation_service_accepts_intent_router_injection -v
```

Expected: `TypeError: ConversationService.__init__() got an unexpected keyword argument 'intent_router'`

- [ ] **Step 3: Add intent_router to constructor**

Open `services/chat/conversation_service.py`. Replace the constructor and imports:

```python
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
```

Leave `handle_user_message` untouched for now.

- [ ] **Step 4: Run test to verify it passes**

```
pytest tests/services/chat/test_conversation_service.py -v
```

Expected: 2 passed

- [ ] **Step 5: Commit**

```
git add services/chat/conversation_service.py tests/services/chat/test_conversation_service.py
git commit -m "feat: add intent_router injection to ConversationService constructor"
```

---

### Task 3: _append_return_prompt Helper

**Files:**
- Modify: `services/chat/conversation_service.py`
- Modify: `tests/services/chat/test_conversation_service.py` (extend)

- [ ] **Step 1: Add failing tests**

Append to `tests/services/chat/test_conversation_service.py`:

```python
from services.chat.models import FlowState


def _make_service(intent_result=None, profile=None, flow=None, extract=None):
    repo = FakeRepository()
    if profile:
        repo.profile_state = profile
    if flow:
        repo.flow_state = flow
    router = FakeIntentRouter(intent_result or IntentResult(route="ADVISORY_FLOW"))
    return ConversationService(
        repository=repo,
        extract_profile=extract or (lambda text: StudentProfile()),
        intent_router=router,
    ), repo


def test_append_return_prompt_adds_pending_question_when_return_to_flow():
    service, _ = _make_service()
    flow = FlowState(return_to_flow=True, pending_question="Bạn học khối gì?")
    result = service._append_return_prompt("Xin lỗi, ngoài phạm vi.", flow)
    assert "Bạn học khối gì?" in result
    assert "Xin lỗi, ngoài phạm vi." in result


def test_append_return_prompt_does_not_add_when_return_to_flow_false():
    service, _ = _make_service()
    flow = FlowState(return_to_flow=False, pending_question="Bạn học khối gì?")
    result = service._append_return_prompt("Xin lỗi, ngoài phạm vi.", flow)
    assert "Bạn học khối gì?" not in result
    assert result == "Xin lỗi, ngoài phạm vi."


def test_append_return_prompt_does_not_add_when_no_pending_question():
    service, _ = _make_service()
    flow = FlowState(return_to_flow=True, pending_question=None)
    result = service._append_return_prompt("Xin lỗi, ngoài phạm vi.", flow)
    assert result == "Xin lỗi, ngoài phạm vi."
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/services/chat/test_conversation_service.py -k "append_return_prompt" -v
```

Expected: `AttributeError: 'ConversationService' object has no attribute '_append_return_prompt'`

- [ ] **Step 3: Add _append_return_prompt to ConversationService**

Append to the `ConversationService` class in `services/chat/conversation_service.py`:

```python
    def _append_return_prompt(self, message: str, flow_state) -> str:
        if flow_state.return_to_flow and flow_state.pending_question:
            return f"{message}\n\nNhân tiện, {flow_state.pending_question}"
        return message
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/services/chat/test_conversation_service.py -k "append_return_prompt" -v
```

Expected: 3 passed

- [ ] **Step 5: Commit**

```
git add services/chat/conversation_service.py tests/services/chat/test_conversation_service.py
git commit -m "feat: add _append_return_prompt helper to ConversationService"
```

---

### Task 4: _handle_out_of_scope and _handle_clarification

**Files:**
- Modify: `services/chat/conversation_service.py`
- Modify: `tests/services/chat/test_conversation_service.py` (extend)

- [ ] **Step 1: Add failing tests**

Append to `tests/services/chat/test_conversation_service.py`:

```python
def test_handle_out_of_scope_returns_polite_decline():
    service, repo = _make_service(
        intent_result=IntentResult(route="OUT_OF_SCOPE"),
        profile=ChatProfileState(),
    )
    result = service.handle_user_message("tok", "thời tiết hôm nay")
    assert result.should_start_run is False
    assert any(
        phrase in result.assistant_message
        for phrase in ["ngoài phạm vi", "không thể hỗ trợ", "xin lỗi"]
    )


def test_handle_out_of_scope_appends_pending_question_when_return_to_flow():
    service, repo = _make_service(
        intent_result=IntentResult(route="OUT_OF_SCOPE"),
        profile=ChatProfileState(total_score=25.0),
        flow=FlowState(
            active_flow="ADVISORY_FLOW",
            return_to_flow=True,
            pending_question="Bạn học khối gì?",
        ),
    )
    result = service.handle_user_message("tok", "thời tiết hôm nay")
    assert "Bạn học khối gì?" in result.assistant_message


def test_handle_clarification_returns_clarification_request():
    service, repo = _make_service(
        intent_result=IntentResult(route="CLARIFICATION"),
        profile=ChatProfileState(),
    )
    result = service.handle_user_message("tok", "ý bạn là gì")
    assert result.should_start_run is False
    assert any(
        phrase in result.assistant_message
        for phrase in ["rõ hơn", "không hiểu", "câu hỏi"]
    )


def test_handle_hybrid_falls_back_to_clarification():
    """HYBRID is not implemented in Phase 1 — falls back to clarification."""
    service, repo = _make_service(
        intent_result=IntentResult(route="HYBRID"),
        profile=ChatProfileState(),
    )
    result = service.handle_user_message("tok", "so sánh UET và HUST")
    assert result.should_start_run is False
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/services/chat/test_conversation_service.py -k "out_of_scope or clarification or hybrid" -v
```

Expected: 4 failed (methods not yet defined)

- [ ] **Step 3: Add handlers and routing dispatcher to ConversationService**

Replace the entire `handle_user_message` method and add the new private methods. Open `services/chat/conversation_service.py` and replace from `handle_user_message` onwards with:

```python
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
        profile_state = self.repository.get_profile_state(session_token)
        flow_state = self.repository.get_flow_state(session_token)
        intent = self.intent_router.classify(content, profile_state)

        if intent.route == "ADVISORY_FLOW":
            return self._handle_advisory(session_token, content, profile_state, flow_state)
        elif intent.route == "KNOWLEDGE_QA":
            return self._handle_knowledge_qa(session_token, intent, profile_state, flow_state)
        elif intent.route == "OUT_OF_SCOPE":
            return self._handle_out_of_scope(session_token, profile_state, flow_state)
        else:
            # CLARIFICATION + HYBRID (Phase 1 fallback)
            return self._handle_clarification(session_token, profile_state, flow_state)

    def _handle_advisory(self, session_token, content, profile_state, flow_state):
        extracted = self.extract_profile(content)
        merged = merge_profile_state(profile_state, extracted, content)

        follow_up = next_follow_up_question(merged)
        if follow_up:
            new_flow = flow_state.model_copy(update={
                "active_flow": "ADVISORY_FLOW",
                "pending_question": follow_up,
            })
            self.repository.update_profile_state(session_token, merged, "collecting_profile")
            self.repository.update_flow_state(session_token, new_flow)
            self.repository.append_message(session_token, "assistant", follow_up, "assistant_follow_up")
            return ConversationTurnResult(
                session_status="collecting_profile",
                assistant_message=follow_up,
                should_start_run=False,
                profile_state=merged,
            )

        ready_message = "Cảm ơn bạn. Mình đã có đủ thông tin và sẽ bắt đầu phân tích."
        new_flow = flow_state.model_copy(update={
            "active_flow": "ADVISORY_FLOW",
            "return_to_flow": False,
            "pending_question": None,
        })
        self.repository.update_profile_state(session_token, merged, "ready")
        self.repository.update_flow_state(session_token, new_flow)
        self.repository.append_message(session_token, "assistant", ready_message, "assistant_ready")
        return ConversationTurnResult(
            session_status="ready",
            assistant_message=ready_message,
            should_start_run=True,
            profile_state=merged,
        )

    def _handle_knowledge_qa(self, session_token, intent, profile_state, flow_state):
        topic_label = self._TOPIC_LABELS.get(intent.topic or "", "thông tin này")
        school_label = intent.school or "trường bạn hỏi"
        fallback = (
            f"Hệ thống chưa có dữ liệu về {topic_label} của {school_label}. "
            f"Bạn có thể liên hệ trực tiếp nhà trường để biết thêm chi tiết."
        )
        response = self._append_return_prompt(fallback, flow_state)

        if flow_state.active_flow == "ADVISORY_FLOW":
            self.repository.update_flow_state(
                session_token,
                flow_state.model_copy(update={"return_to_flow": True}),
            )

        self.repository.append_message(session_token, "assistant", response, "assistant_result")
        status = "collecting_profile" if profile_state.missing_slots else "ready"
        return ConversationTurnResult(
            session_status=status,
            assistant_message=response,
            should_start_run=False,
            profile_state=profile_state,
        )

    def _handle_out_of_scope(self, session_token, profile_state, flow_state):
        msg = (
            "Xin lỗi, câu hỏi này nằm ngoài phạm vi tư vấn tuyển sinh của mình. "
            "Mình chỉ có thể hỗ trợ các vấn đề liên quan đến tuyển sinh đại học."
        )
        response = self._append_return_prompt(msg, flow_state)
        self.repository.append_message(session_token, "assistant", response, "assistant_result")
        status = "collecting_profile" if profile_state.missing_slots else "ready"
        return ConversationTurnResult(
            session_status=status,
            assistant_message=response,
            should_start_run=False,
            profile_state=profile_state,
        )

    def _handle_clarification(self, session_token, profile_state, flow_state):
        msg = "Bạn có thể nói rõ hơn câu hỏi của mình không? Mình muốn hiểu đúng để hỗ trợ tốt hơn."
        response = self._append_return_prompt(msg, flow_state)
        self.repository.append_message(session_token, "assistant", response, "assistant_result")
        status = "collecting_profile" if profile_state.missing_slots else "ready"
        return ConversationTurnResult(
            session_status=status,
            assistant_message=response,
            should_start_run=False,
            profile_state=profile_state,
        )

    def _append_return_prompt(self, message: str, flow_state) -> str:
        if flow_state.return_to_flow and flow_state.pending_question:
            return f"{message}\n\nNhân tiện, {flow_state.pending_question}"
        return message
```

- [ ] **Step 4: Run all conversation service tests**

```
pytest tests/services/chat/test_conversation_service.py -v
```

Expected: all passed (including the original test)

- [ ] **Step 5: Commit**

```
git add services/chat/conversation_service.py tests/services/chat/test_conversation_service.py
git commit -m "feat: add routing dispatcher and branch handlers to ConversationService"
```

---

### Task 5: _handle_knowledge_qa

**Files:**
- Modify: `tests/services/chat/test_conversation_service.py` (extend)

- [ ] **Step 1: Add KNOWLEDGE_QA specific tests**

Append to `tests/services/chat/test_conversation_service.py`:

```python
def test_handle_knowledge_qa_returns_fallback_message():
    service, repo = _make_service(
        intent_result=IntentResult(route="KNOWLEDGE_QA", topic="tuition", school="VNU-UET"),
        profile=ChatProfileState(),
    )
    result = service.handle_user_message("tok", "học phí UET bao nhiêu")
    assert result.should_start_run is False
    assert "học phí" in result.assistant_message
    assert "VNU-UET" in result.assistant_message


def test_handle_knowledge_qa_uses_fallback_label_when_school_null():
    service, repo = _make_service(
        intent_result=IntentResult(route="KNOWLEDGE_QA", topic="tuition", school=None),
        profile=ChatProfileState(),
    )
    result = service.handle_user_message("tok", "học phí bao nhiêu")
    assert "trường bạn hỏi" in result.assistant_message


def test_handle_knowledge_qa_uses_fallback_label_when_topic_null():
    service, repo = _make_service(
        intent_result=IntentResult(route="KNOWLEDGE_QA", topic=None, school="NEU"),
        profile=ChatProfileState(),
    )
    result = service.handle_user_message("tok", "cho mình hỏi về NEU")
    assert "thông tin này" in result.assistant_message


def test_handle_knowledge_qa_sets_return_to_flow_when_advisory_active():
    flow = FlowState(active_flow="ADVISORY_FLOW", pending_question="Bạn học khối gì?")
    service, repo = _make_service(
        intent_result=IntentResult(route="KNOWLEDGE_QA", topic="tuition", school="NEU"),
        profile=ChatProfileState(total_score=25.0),
        flow=flow,
    )
    service.handle_user_message("tok", "học phí NEU bao nhiêu")
    assert repo.flow_state.return_to_flow is True


def test_handle_knowledge_qa_appends_pending_question_in_response():
    flow = FlowState(
        active_flow="ADVISORY_FLOW",
        return_to_flow=True,
        pending_question="Bạn học khối gì?",
    )
    service, repo = _make_service(
        intent_result=IntentResult(route="KNOWLEDGE_QA", topic="tuition", school="NEU"),
        profile=ChatProfileState(total_score=25.0),
        flow=flow,
    )
    result = service.handle_user_message("tok", "học phí NEU bao nhiêu")
    assert "Bạn học khối gì?" in result.assistant_message


def test_handle_knowledge_qa_does_not_reset_profile_state():
    original_profile = ChatProfileState(
        total_score=25.5,
        preferred_majors=["computer_science"],
        preferred_schools=["VNU-UET"],
    )
    service, repo = _make_service(
        intent_result=IntentResult(route="KNOWLEDGE_QA", topic="tuition", school="VNU-UET"),
        profile=original_profile,
    )
    result = service.handle_user_message("tok", "học phí UET bao nhiêu")
    assert result.profile_state.total_score == 25.5
    assert result.profile_state.preferred_majors == ["computer_science"]
    assert result.profile_state.preferred_schools == ["VNU-UET"]
```

- [ ] **Step 2: Run tests**

```
pytest tests/services/chat/test_conversation_service.py -k "knowledge_qa" -v
```

Expected: 6 passed

- [ ] **Step 3: Commit**

```
git add tests/services/chat/test_conversation_service.py
git commit -m "test: add KNOWLEDGE_QA branch tests to ConversationService"
```

---

### Task 6: _handle_advisory — Flow State Tracking

**Files:**
- Modify: `tests/services/chat/test_conversation_service.py` (extend)

- [ ] **Step 1: Add advisory flow state tracking tests**

Append to `tests/services/chat/test_conversation_service.py`:

```python
def test_handle_advisory_saves_pending_question_in_flow_state():
    """When advisory handler returns a follow-up, it must save it as pending_question."""
    service, repo = _make_service(
        intent_result=IntentResult(route="ADVISORY_FLOW"),
        profile=ChatProfileState(),  # missing_slots will be populated by merge
        extract=lambda text: StudentProfile(
            preferred_majors=["computer_science"],
            location_preference="Ha Noi",
        ),
    )
    service.handle_user_message("tok", "Em muon hoc CNTT tai Ha Noi nam 2026")

    assert repo.flow_state.active_flow == "ADVISORY_FLOW"
    assert repo.flow_state.pending_question is not None
    assert len(repo.flow_state.pending_question) > 0


def test_handle_advisory_clears_flow_state_when_profile_complete():
    """When profile is complete, pending_question and return_to_flow must be cleared."""
    service, repo = _make_service(
        intent_result=IntentResult(route="ADVISORY_FLOW"),
        profile=ChatProfileState(),
        extract=lambda text: StudentProfile(
            total_score=25.0,
            subject_combination="A00",
            preferred_majors=["computer_science"],
            location_preference="Ha Noi",
        ),
    )
    # Pre-load a pending question in flow state
    repo.flow_state = FlowState(
        active_flow="ADVISORY_FLOW",
        return_to_flow=True,
        pending_question="old question",
    )

    result = service.handle_user_message("tok", "25 điểm A00 CNTT Hà Nội")

    assert result.should_start_run is True
    assert repo.flow_state.return_to_flow is False
    assert repo.flow_state.pending_question is None


def test_handle_advisory_preserves_existing_profile_fields():
    """Profile merge must not lose previously collected fields."""
    service, repo = _make_service(
        intent_result=IntentResult(route="ADVISORY_FLOW"),
        profile=ChatProfileState(
            total_score=25.0,
            subject_combination="A00",
        ),
        extract=lambda text: StudentProfile(
            preferred_majors=["computer_science"],
            location_preference="Ha Noi",
        ),
    )
    result = service.handle_user_message("tok", "Em muon hoc CNTT tai Ha Noi")

    assert result.profile_state.total_score == 25.0
    assert result.profile_state.subject_combination == "A00"
    assert "computer_science" in result.profile_state.preferred_majors
```

- [ ] **Step 2: Run tests**

```
pytest tests/services/chat/test_conversation_service.py -k "advisory" -v
```

Expected: 4 passed (including the original test from Task 1)

- [ ] **Step 3: Commit**

```
git add tests/services/chat/test_conversation_service.py
git commit -m "test: add advisory flow state tracking tests"
```

---

### Task 7: Acceptance Criteria Verification

**Files:**
- Modify: `tests/services/chat/test_conversation_service.py` (extend)

These tests map 1:1 to the acceptance criteria in the spec.

- [ ] **Step 1: Add acceptance criteria tests**

Append to `tests/services/chat/test_conversation_service.py`:

```python
# ─── Acceptance Criteria ──────────────────────────────────────────────────────

def test_ac_knowledge_qa_does_not_trigger_advisory_run():
    """AC: 'học phí UET bao nhiêu?' → KNOWLEDGE_QA, NOT advisory graph."""
    service, repo = _make_service(
        intent_result=IntentResult(route="KNOWLEDGE_QA", topic="tuition", school="VNU-UET"),
        profile=ChatProfileState(),
    )
    result = service.handle_user_message("tok", "học phí UET bao nhiêu?")
    assert result.should_start_run is False


def test_ac_advisory_flow_unchanged():
    """AC: advisory question → ADVISORY_FLOW, existing behavior unchanged."""
    service, repo = _make_service(
        intent_result=IntentResult(route="ADVISORY_FLOW"),
        profile=ChatProfileState(),
        extract=lambda text: StudentProfile(
            preferred_majors=["computer_science"],
            location_preference="Ha Noi",
        ),
    )
    result = service.handle_user_message("tok", "Em 25 điểm A00 nên chọn ngành gì?")
    assert result.session_status == "collecting_profile"
    assert result.should_start_run is False


def test_ac_out_of_scope_polite_response():
    """AC: out-of-scope question → polite decline."""
    service, repo = _make_service(
        intent_result=IntentResult(route="OUT_OF_SCOPE"),
        profile=ChatProfileState(),
    )
    result = service.handle_user_message("tok", "thời tiết hôm nay thế nào?")
    assert result.should_start_run is False
    assert len(result.assistant_message) > 0


def test_ac_knowledge_qa_fallback_message_format():
    """AC: KNOWLEDGE_QA with no data → structured fallback mentioning topic and school."""
    service, repo = _make_service(
        intent_result=IntentResult(route="KNOWLEDGE_QA", topic="tuition", school="VNU-UET"),
        profile=ChatProfileState(),
    )
    result = service.handle_user_message("tok", "học phí UET bao nhiêu?")
    assert "học phí" in result.assistant_message
    assert "VNU-UET" in result.assistant_message
    assert "liên hệ" in result.assistant_message


def test_ac_return_to_flow_appends_pending_question():
    """AC: after side-query, return_to_flow=True → pending question appended."""
    flow = FlowState(
        active_flow="ADVISORY_FLOW",
        return_to_flow=True,
        pending_question="Tổng điểm hoặc mức điểm ước tính của bạn là bao nhiêu?",
    )
    service, repo = _make_service(
        intent_result=IntentResult(route="OUT_OF_SCOPE"),
        profile=ChatProfileState(preferred_majors=["computer_science"]),
        flow=flow,
    )
    result = service.handle_user_message("tok", "thời tiết hôm nay thế nào?")
    assert "Tổng điểm" in result.assistant_message


def test_ac_profile_state_not_reset_on_side_query():
    """AC: profile state must not be reset when routing to non-advisory branch."""
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
    assert result.profile_state.subject_combination == "A00"
    assert result.profile_state.preferred_majors == ["computer_science"]
    assert result.profile_state.preferred_schools == ["VNU-UET"]
    assert result.profile_state.location_preference == "Ha Noi"
    # profile_state in repo must also be unchanged
    assert repo.profile_state.total_score == 27.0
```

- [ ] **Step 2: Run acceptance criteria tests**

```
pytest tests/services/chat/test_conversation_service.py -k "test_ac_" -v
```

Expected: 6 passed

- [ ] **Step 3: Run full test suite**

```
pytest --tb=short -q
```

Expected: all tests pass, no regressions

- [ ] **Step 4: Commit**

```
git add tests/services/chat/test_conversation_service.py
git commit -m "test: add acceptance criteria tests for Phase 1 routing"
```

---

### Task 8: Final Smoke Check

- [ ] **Step 1: Run all Phase 1 tests together**

```
pytest tests/services/chat/ -v --tb=short
```

Expected output (minimum):
```
tests/services/chat/test_flow_state_model.py          5 passed
tests/services/chat/test_repository.py                7 passed
tests/services/chat/test_intent_router.py            30+ passed
tests/services/chat/test_conversation_service.py     20+ passed
```

- [ ] **Step 2: Verify no import errors across the service layer**

```
python -c "
from services.chat.models import FlowState, ChatProfileState
from services.chat.intent_router import IntentRouter, IntentResult
from services.chat.conversation_service import ConversationService
from services.chat.repository import ChatSessionRepository
print('All imports OK')
"
```

Expected: `All imports OK`

- [ ] **Step 3: Commit final tag**

```
git add .
git commit -m "feat: Phase 1 complete — IntentRouter + flow state routing in ConversationService"
```

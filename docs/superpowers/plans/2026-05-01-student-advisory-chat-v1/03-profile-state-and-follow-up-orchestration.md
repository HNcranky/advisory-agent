# Student Advisory Chat V1 - Phase 3: Profile State And Follow-Up Orchestration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn raw user messages into progressively richer structured profile state and respond with one focused follow-up question at a time.

**Architecture:** Reuse the existing `build_profile_with_gateway()` service for per-turn extraction, then merge its output into a chat-specific profile state model that also tracks admission year and missing critical slots. Keep the orchestration inside a new conversation service so the HTTP routes stay thin and the advisory graph remains untouched in this phase.

**Tech Stack:** Python, Pydantic, existing Gemini gateway, `pytest`, `monkeypatch`

---

## Planned File Structure

- `services/chat/models.py`
  - Add `ChatProfileState` and `ConversationTurnResult`.
- `services/chat/profile_state_service.py`
  - Merge extracted fields, compute missing slots, and choose the next follow-up question.
- `services/chat/conversation_service.py`
  - Persist messages, update profile state, and decide whether the session is still collecting or ready.
- `web/routes/chat_api.py`
  - Upgrade message POST handling to call the conversation service.

### Task 1: Add Profile-State Merge And Missing-Slot Logic

**Files:**
- Modify: `services/chat/models.py`
- Create: `services/chat/profile_state_service.py`
- Test: `tests/services/chat/test_profile_state_service.py`

- [ ] **Step 1: Write the failing test**

```python
from agents.models import StudentProfile
from services.chat.models import ChatProfileState
from services.chat.profile_state_service import (
    merge_profile_state,
    next_follow_up_question,
)


def test_merge_profile_state_updates_fields_and_computes_missing_slots():
    current = ChatProfileState()
    extracted = StudentProfile(
        total_score=27.0,
        preferred_majors=["computer_science"],
        location_preference="Ha Noi",
    )

    merged = merge_profile_state(current, extracted, "Em xet tuyen nam 2026")

    assert merged.admission_year == 2026
    assert merged.total_score == 27.0
    assert merged.preferred_majors == ["computer_science"]
    assert merged.location_preference == "Ha Noi"
    assert merged.missing_slots == []
    assert next_follow_up_question(merged) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/services/chat/test_profile_state_service.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'services.chat.profile_state_service'`

- [ ] **Step 3: Write minimal implementation**

```python
# services/chat/models.py
from typing import List, Optional

from pydantic import BaseModel, Field


class ChatProfileState(BaseModel):
    admission_year: Optional[int] = None
    total_score: Optional[float] = None
    subject_combination: Optional[str] = None
    preferred_majors: List[str] = Field(default_factory=list)
    preferred_schools: List[str] = Field(default_factory=list)
    location_preference: Optional[str] = None
    tuition_budget: Optional[str] = None
    constraints: List[str] = Field(default_factory=list)
    missing_slots: List[str] = Field(default_factory=list)
```

```python
# services/chat/profile_state_service.py
import re

from agents.models import StudentProfile
from services.chat.models import ChatProfileState


CRITICAL_SLOT_ORDER = [
    "admission_year",
    "total_score",
    "preferred_majors",
    "location_preference",
]


def _extract_admission_year(raw_message: str):
    match = re.search(r"\b20\d{2}\b", raw_message)
    return int(match.group(0)) if match else None


def merge_profile_state(current: ChatProfileState, extracted: StudentProfile, raw_message: str) -> ChatProfileState:
    merged = ChatProfileState(
        admission_year=_extract_admission_year(raw_message) or current.admission_year,
        total_score=extracted.total_score or current.total_score,
        subject_combination=extracted.subject_combination or current.subject_combination,
        preferred_majors=extracted.preferred_majors or current.preferred_majors,
        preferred_schools=extracted.preferred_schools or current.preferred_schools,
        location_preference=extracted.location_preference or current.location_preference,
        tuition_budget=extracted.tuition_budget or current.tuition_budget,
        constraints=extracted.constraints or current.constraints,
    )
    merged.missing_slots = [
        slot
        for slot in CRITICAL_SLOT_ORDER
        if not getattr(merged, slot)
    ]
    return merged


def next_follow_up_question(state: ChatProfileState):
    prompts = {
        "admission_year": "Ban dang xet tuyen cho nam nao?",
        "total_score": "Tong diem hoac muc diem uoc tinh cua ban la bao nhieu?",
        "preferred_majors": "Ban quan tam nhat den nganh nao?",
        "location_preference": "Ban muon hoc o khu vuc hay thanh pho nao?",
    }
    return prompts.get(state.missing_slots[0]) if state.missing_slots else None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/services/chat/test_profile_state_service.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add services/chat/models.py services/chat/profile_state_service.py tests/services/chat/test_profile_state_service.py
git commit -m "feat: add chat profile-state merge logic"
```

### Task 2: Add Conversation Service And Follow-Up Message Endpoint

**Files:**
- Modify: `services/chat/repository.py`
- Create: `services/chat/conversation_service.py`
- Modify: `web/routes/chat_api.py`
- Test: `tests/services/chat/test_conversation_service.py`
- Test: `tests/web/test_chat_session_api.py`

- [ ] **Step 1: Write the failing test**

```python
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
    assert "bao nhieu" in result.assistant_message.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/services/chat/test_conversation_service.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'services.chat.conversation_service'`

- [ ] **Step 3: Write minimal implementation**

```python
# services/chat/models.py
class ConversationTurnResult(BaseModel):
    session_status: str
    assistant_message: str
    should_start_run: bool = False
    profile_state: ChatProfileState
```

```python
# services/chat/repository.py
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
            (profile_state.model_dump(mode="json"), status, session_token),
        )
        conn.commit()
        cur.close()
        conn.close()
        return profile_state
```

```python
# services/chat/conversation_service.py
from services import build_default_gateway
from services.chat.models import ConversationTurnResult
from services.chat.profile_state_service import merge_profile_state, next_follow_up_question
from services.chat.repository import ChatSessionRepository
from services.profile_inference_service import build_profile_with_gateway


class ConversationService:
    def __init__(self, repository=None, extract_profile=None):
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
            assistant_message=ready_message,
            should_start_run=True,
            profile_state=merged,
        )
```

```python
# web/routes/chat_api.py
from pydantic import BaseModel

from services.chat.conversation_service import ConversationService


class ChatMessageCreate(BaseModel):
    content: str


def get_conversation_service():
    return ConversationService()


@router.post("/{session_token}/messages")
def post_message(session_token: str, payload: ChatMessageCreate):
    service = get_conversation_service()
    result = service.handle_user_message(session_token, payload.content)
    return result.model_dump()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/services/chat/test_conversation_service.py tests/web/test_chat_session_api.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add services/chat/repository.py services/chat/conversation_service.py web/routes/chat_api.py tests/services/chat/test_conversation_service.py tests/web/test_chat_session_api.py
git commit -m "feat: add chat follow-up orchestration"
```

## Self-Review

Spec coverage in this plan:
- Progressive profile capture: covered by Task 1.
- One-question-at-a-time follow-up flow: covered by Task 2.
- Session layer decision boundary before full runs: covered by Task 2.

Intentional exclusions from this plan:
- No advisory graph execution yet.
- No background run persistence yet.
- No public HTML UI yet.

Plan complete and saved to `docs/superpowers/plans/2026-05-01-student-advisory-chat-v1/03-profile-state-and-follow-up-orchestration.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**

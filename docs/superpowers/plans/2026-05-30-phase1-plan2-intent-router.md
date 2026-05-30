# Phase 1 — Plan 2: IntentRouter Service

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `IntentRouter` — a self-contained service that classifies user messages into one of 5 routes (`ADVISORY_FLOW`, `KNOWLEDGE_QA`, `CLARIFICATION`, `OUT_OF_SCOPE`, `HYBRID`) using a single LLM call, with guaranteed safe fallback on any failure.

**Architecture:** `IntentResult` and `IntentRouter` live in `services/chat/intent_router.py`. `IntentRouter` follows the same gateway-injection pattern as `build_profile_with_gateway` in `profile_inference_service.py`: gateway is injected in constructor, enabling unit tests without any real LLM calls. All exceptions are caught internally — `classify()` never raises.

**Tech Stack:** Python 3.11, Pydantic v2, `InferenceRequest`/`InferenceResult` from `services.inference.models`, pytest

**Depends on:** Plan 1 must be complete (`FlowState` and `ChatProfileState` available in `services/chat/models.py`)

---

### Task 1: IntentResult Model

**Files:**
- Create: `services/chat/intent_router.py`
- Test: `tests/services/chat/test_intent_router.py`

- [ ] **Step 1: Create test file with failing tests**

Create `tests/services/chat/test_intent_router.py`:

```python
import pytest
from services.chat.intent_router import IntentResult


def test_intent_result_defaults():
    result = IntentResult(route="ADVISORY_FLOW")
    assert result.route == "ADVISORY_FLOW"
    assert result.topic is None
    assert result.school is None
    assert result.return_to_flow is False


def test_intent_result_full():
    result = IntentResult(
        route="KNOWLEDGE_QA",
        topic="tuition",
        school="VNU-UET",
        return_to_flow=True,
    )
    assert result.route == "KNOWLEDGE_QA"
    assert result.topic == "tuition"
    assert result.school == "VNU-UET"
    assert result.return_to_flow is True


def test_intent_result_rejects_invalid_route():
    with pytest.raises(Exception):
        IntentResult(route="INVALID_ROUTE")


def test_intent_result_rejects_invalid_topic():
    with pytest.raises(Exception):
        IntentResult(route="KNOWLEDGE_QA", topic="invalid_topic")


def test_intent_result_model_validate_from_dict():
    data = {"route": "OUT_OF_SCOPE"}
    result = IntentResult.model_validate(data)
    assert result.route == "OUT_OF_SCOPE"
    assert result.topic is None
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/services/chat/test_intent_router.py -v
```

Expected: `ModuleNotFoundError: No module named 'services.chat.intent_router'`

- [ ] **Step 3: Create intent_router.py with IntentResult**

Create `services/chat/intent_router.py`:

```python
from typing import Literal, Optional

from pydantic import BaseModel

from services import build_default_gateway
from services.chat.models import ChatProfileState
from services.inference.models import InferenceRequest

INTENT_SYSTEM_PROMPT = """
Bạn là bộ phân loại intent cho hệ thống tư vấn tuyển sinh đại học Việt Nam.

Phân loại tin nhắn của user vào đúng 1 trong 5 route:

ADVISORY_FLOW — câu hỏi tư vấn chọn ngành/trường dựa trên điểm số, nguyện vọng, khả năng đậu
  Ví dụ: "25 điểm A00 nên chọn trường nào", "em có đậu NEU không", "tư vấn ngành CNTT"

KNOWLEDGE_QA — câu hỏi thực tế về thông tin cụ thể của trường/ngành
  Ví dụ: "học phí UET bao nhiêu", "chương trình CNTT gồm gì", "có học bổng không", "ký túc xá thế nào"

CLARIFICATION — câu quá mơ hồ, thiếu context để phân loại chính xác
  Ví dụ: "thế còn cái đó thì sao" (không rõ đối tượng), "ý bạn là gì"

OUT_OF_SCOPE — hoàn toàn ngoài lĩnh vực tuyển sinh đại học
  Ví dụ: "thời tiết hôm nay", "kể chuyện cười", "1+1 bằng mấy", "giúp tôi viết code"

HYBRID — cần cả dữ liệu tư vấn (điểm chuẩn, xác suất đậu) lẫn thông tin thực tế (học phí, chương trình)
  Ví dụ: "so sánh UET và HUST về điểm chuẩn lẫn học phí"
  Chỉ dùng HYBRID khi câu hỏi thực sự cần cả hai loại dữ liệu.

Quy tắc resolve đại từ:
- "trường này", "ở đó", "trường đó" → dùng preferred_schools trong profile (nếu có)
- "ngành này", "chuyên ngành đó" → dùng preferred_majors trong profile (nếu có)
- Không thể resolve → để school/topic là null, route về CLARIFICATION

Chuẩn hóa tên trường thành viết tắt phổ biến nếu nhận ra: VNU-UET, HUST, NEU, VNU-HCMUS, UEH, FTU, ...

return_to_flow: true nếu profile có bất kỳ dữ liệu nào (user đang trong luồng tư vấn dở chừng).

Trả về JSON hợp lệ, không giải thích thêm:
{"route": "...", "topic": "...", "school": "...", "return_to_flow": true/false}
""".strip()


class IntentResult(BaseModel):
    route: Literal[
        "ADVISORY_FLOW", "KNOWLEDGE_QA", "HYBRID", "CLARIFICATION", "OUT_OF_SCOPE"
    ]
    topic: Optional[
        Literal[
            "tuition",
            "curriculum",
            "scholarship",
            "dormitory",
            "career",
            "admission_policy",
            "program_overview",
        ]
    ] = None
    school: Optional[str] = None
    return_to_flow: bool = False


_FALLBACK = IntentResult(route="ADVISORY_FLOW")


class IntentRouter:
    def __init__(self, gateway=None):
        self._gateway = gateway or build_default_gateway()

    def classify(self, message: str, profile_state: ChatProfileState) -> IntentResult:
        try:
            result = self._gateway.run(
                InferenceRequest(
                    agent_name="intent_router",
                    task_type="intent_classification",
                    system_prompt=INTENT_SYSTEM_PROMPT,
                    user_prompt=self._build_user_prompt(message, profile_state),
                    output_mode="json",
                    temperature=0.0,
                )
            )
            if not result.parsed_data:
                return _FALLBACK
            return IntentResult.model_validate(result.parsed_data)
        except Exception:
            return _FALLBACK

    def _build_user_prompt(self, message: str, profile_state: ChatProfileState) -> str:
        has_data = any([
            profile_state.total_score,
            profile_state.preferred_majors,
            profile_state.preferred_schools,
            profile_state.subject_combination,
            profile_state.location_preference,
        ])
        schools = (
            ", ".join(profile_state.preferred_schools)
            if profile_state.preferred_schools
            else "chưa có"
        )
        majors = (
            ", ".join(profile_state.preferred_majors)
            if profile_state.preferred_majors
            else "chưa có"
        )
        return (
            f'Tin nhắn: "{message}"\n\n'
            f"Trường quan tâm: {schools}\n"
            f"Ngành quan tâm: {majors}\n"
            f"Điểm số: {profile_state.total_score or 'chưa có'}\n"
            f"Khối thi: {profile_state.subject_combination or 'chưa có'}\n"
            f"return_to_flow: {'true' if has_data else 'false'}"
        )
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/services/chat/test_intent_router.py::test_intent_result_defaults \
       tests/services/chat/test_intent_router.py::test_intent_result_full \
       tests/services/chat/test_intent_router.py::test_intent_result_rejects_invalid_route \
       tests/services/chat/test_intent_router.py::test_intent_result_rejects_invalid_topic \
       tests/services/chat/test_intent_router.py::test_intent_result_model_validate_from_dict \
       -v
```

Expected: 5 passed

- [ ] **Step 5: Commit**

```
git add services/chat/intent_router.py tests/services/chat/test_intent_router.py
git commit -m "feat: add IntentResult model and IntentRouter skeleton"
```

---

### Task 2: User Prompt Builder

**Files:**
- Modify: `tests/services/chat/test_intent_router.py` (extend)
- No changes to `services/chat/intent_router.py` — already written above

- [ ] **Step 1: Add failing tests for _build_user_prompt**

Append to `tests/services/chat/test_intent_router.py`:

```python
from services.chat.models import ChatProfileState
from services.chat.intent_router import IntentRouter


def _make_router():
    """Router with a no-op gateway — only used for prompt building tests."""
    return IntentRouter(gateway=None.__class__)  # gateway unused in these tests


def test_build_user_prompt_includes_message():
    router = IntentRouter.__new__(IntentRouter)
    profile = ChatProfileState()
    prompt = router._build_user_prompt("học phí UET bao nhiêu", profile)
    assert "học phí UET bao nhiêu" in prompt


def test_build_user_prompt_includes_preferred_schools():
    router = IntentRouter.__new__(IntentRouter)
    profile = ChatProfileState(preferred_schools=["VNU-UET", "HUST"])
    prompt = router._build_user_prompt("msg", profile)
    assert "VNU-UET" in prompt
    assert "HUST" in prompt


def test_build_user_prompt_shows_chua_co_when_no_schools():
    router = IntentRouter.__new__(IntentRouter)
    profile = ChatProfileState()
    prompt = router._build_user_prompt("msg", profile)
    assert "chưa có" in prompt


def test_build_user_prompt_return_to_flow_true_when_profile_has_data():
    router = IntentRouter.__new__(IntentRouter)
    profile = ChatProfileState(total_score=25.0)
    prompt = router._build_user_prompt("msg", profile)
    assert "return_to_flow: true" in prompt


def test_build_user_prompt_return_to_flow_false_when_profile_empty():
    router = IntentRouter.__new__(IntentRouter)
    profile = ChatProfileState()
    prompt = router._build_user_prompt("msg", profile)
    assert "return_to_flow: false" in prompt
```

- [ ] **Step 2: Run tests**

```
pytest tests/services/chat/test_intent_router.py -k "prompt" -v
```

Expected: 5 passed (prompt builder already implemented in Task 1)

- [ ] **Step 3: Commit**

```
git add tests/services/chat/test_intent_router.py
git commit -m "test: add user prompt builder tests for IntentRouter"
```

---

### Task 3: classify() — Full 20 Test Cases

**Files:**
- Modify: `tests/services/chat/test_intent_router.py` (extend)

The gateway mock pattern used throughout:

```python
# FakeGateway helper — defined once at top of the test additions
```

- [ ] **Step 1: Add FakeGateway helper and all 20 classify tests**

Append to `tests/services/chat/test_intent_router.py`:

```python
from services.inference.models import InferenceError, InferenceResult


class FakeGateway:
    def __init__(self, parsed_data=None, should_raise=False):
        self._parsed_data = parsed_data
        self._should_raise = should_raise

    def run(self, request):
        if self._should_raise:
            raise InferenceError("simulated failure")
        return InferenceResult(
            agent_name=request.agent_name,
            model="test-model",
            provider="test",
            content="{}",
            parsed_data=self._parsed_data,
        )


# --- ADVISORY_FLOW ---

def test_classify_advisory_basic():
    gw = FakeGateway({"route": "ADVISORY_FLOW", "return_to_flow": False})
    router = IntentRouter(gateway=gw)
    result = router.classify("25 điểm A00 nên chọn trường nào", ChatProfileState())
    assert result.route == "ADVISORY_FLOW"


def test_classify_advisory_eligibility_question():
    gw = FakeGateway({"route": "ADVISORY_FLOW", "return_to_flow": False})
    router = IntentRouter(gateway=gw)
    result = router.classify("em có đậu NEU không", ChatProfileState())
    assert result.route == "ADVISORY_FLOW"


def test_classify_advisory_major_advice():
    gw = FakeGateway({"route": "ADVISORY_FLOW", "return_to_flow": False})
    router = IntentRouter(gateway=gw)
    result = router.classify("tư vấn ngành CNTT cho mình", ChatProfileState())
    assert result.route == "ADVISORY_FLOW"


def test_classify_advisory_score_combination():
    gw = FakeGateway({"route": "ADVISORY_FLOW", "return_to_flow": False})
    router = IntentRouter(gateway=gw)
    result = router.classify("điểm 28 khối B00 nên nộp đâu", ChatProfileState())
    assert result.route == "ADVISORY_FLOW"


def test_classify_advisory_chance_question():
    gw = FakeGateway({"route": "ADVISORY_FLOW", "return_to_flow": False})
    router = IntentRouter(gateway=gw)
    result = router.classify("cơ hội đậu Bách Khoa của em là bao nhiêu", ChatProfileState())
    assert result.route == "ADVISORY_FLOW"


# --- KNOWLEDGE_QA ---

def test_classify_knowledge_tuition_with_school():
    gw = FakeGateway({"route": "KNOWLEDGE_QA", "topic": "tuition", "school": "VNU-UET", "return_to_flow": False})
    router = IntentRouter(gateway=gw)
    result = router.classify("học phí UET bao nhiêu", ChatProfileState())
    assert result.route == "KNOWLEDGE_QA"
    assert result.topic == "tuition"
    assert result.school == "VNU-UET"


def test_classify_knowledge_curriculum():
    gw = FakeGateway({"route": "KNOWLEDGE_QA", "topic": "curriculum", "school": None, "return_to_flow": False})
    router = IntentRouter(gateway=gw)
    result = router.classify("chương trình CNTT gồm gì", ChatProfileState())
    assert result.route == "KNOWLEDGE_QA"
    assert result.topic == "curriculum"


def test_classify_knowledge_scholarship():
    gw = FakeGateway({"route": "KNOWLEDGE_QA", "topic": "scholarship", "return_to_flow": False})
    router = IntentRouter(gateway=gw)
    result = router.classify("có học bổng không", ChatProfileState())
    assert result.route == "KNOWLEDGE_QA"
    assert result.topic == "scholarship"


def test_classify_knowledge_dormitory():
    gw = FakeGateway({"route": "KNOWLEDGE_QA", "topic": "dormitory", "return_to_flow": False})
    router = IntentRouter(gateway=gw)
    result = router.classify("ký túc xá thế nào", ChatProfileState())
    assert result.route == "KNOWLEDGE_QA"
    assert result.topic == "dormitory"


def test_classify_knowledge_pronoun_resolved_from_profile():
    """'trường này' should be resolved using preferred_schools from profile."""
    gw = FakeGateway({"route": "KNOWLEDGE_QA", "topic": "tuition", "school": "VNU-UET", "return_to_flow": True})
    profile = ChatProfileState(preferred_schools=["VNU-UET"])
    router = IntentRouter(gateway=gw)
    result = router.classify("trường này học phí bao nhiêu", profile)
    assert result.route == "KNOWLEDGE_QA"
    assert result.school == "VNU-UET"


def test_classify_knowledge_return_to_flow_true_when_profile_has_data():
    gw = FakeGateway({"route": "KNOWLEDGE_QA", "topic": "tuition", "school": "HUST", "return_to_flow": True})
    profile = ChatProfileState(total_score=27.0, preferred_schools=["HUST"])
    router = IntentRouter(gateway=gw)
    result = router.classify("học phí HUST bao nhiêu", profile)
    assert result.return_to_flow is True


# --- OUT_OF_SCOPE ---

def test_classify_out_of_scope_weather():
    gw = FakeGateway({"route": "OUT_OF_SCOPE", "return_to_flow": False})
    router = IntentRouter(gateway=gw)
    result = router.classify("thời tiết hôm nay thế nào", ChatProfileState())
    assert result.route == "OUT_OF_SCOPE"


def test_classify_out_of_scope_joke():
    gw = FakeGateway({"route": "OUT_OF_SCOPE", "return_to_flow": False})
    router = IntentRouter(gateway=gw)
    result = router.classify("kể cho tôi nghe một câu chuyện cười", ChatProfileState())
    assert result.route == "OUT_OF_SCOPE"


def test_classify_out_of_scope_coding_help():
    gw = FakeGateway({"route": "OUT_OF_SCOPE", "return_to_flow": False})
    router = IntentRouter(gateway=gw)
    result = router.classify("giúp tôi viết code Python", ChatProfileState())
    assert result.route == "OUT_OF_SCOPE"


def test_classify_out_of_scope_food():
    gw = FakeGateway({"route": "OUT_OF_SCOPE", "return_to_flow": False})
    router = IntentRouter(gateway=gw)
    result = router.classify("hôm nay ăn gì ngon", ChatProfileState())
    assert result.route == "OUT_OF_SCOPE"


# --- CLARIFICATION ---

def test_classify_clarification_ambiguous_pronoun():
    gw = FakeGateway({"route": "CLARIFICATION", "return_to_flow": False})
    router = IntentRouter(gateway=gw)
    result = router.classify("thế còn cái đó thì sao", ChatProfileState())
    assert result.route == "CLARIFICATION"


def test_classify_clarification_vague():
    gw = FakeGateway({"route": "CLARIFICATION", "return_to_flow": False})
    router = IntentRouter(gateway=gw)
    result = router.classify("ý bạn là gì", ChatProfileState())
    assert result.route == "CLARIFICATION"


# --- ERROR FALLBACKS ---

def test_classify_returns_advisory_fallback_on_inference_error():
    gw = FakeGateway(should_raise=True)
    router = IntentRouter(gateway=gw)
    result = router.classify("bất kỳ câu gì", ChatProfileState())
    assert result.route == "ADVISORY_FLOW"
    assert result.topic is None
    assert result.school is None


def test_classify_returns_advisory_fallback_when_parsed_data_is_none():
    gw = FakeGateway(parsed_data=None)
    router = IntentRouter(gateway=gw)
    result = router.classify("bất kỳ câu gì", ChatProfileState())
    assert result.route == "ADVISORY_FLOW"


def test_classify_returns_advisory_fallback_on_invalid_route_in_response():
    """LLM returns a route not in the Literal — Pydantic validation error → fallback."""
    gw = FakeGateway({"route": "MADE_UP_ROUTE", "return_to_flow": False})
    router = IntentRouter(gateway=gw)
    result = router.classify("bất kỳ câu gì", ChatProfileState())
    assert result.route == "ADVISORY_FLOW"
```

- [ ] **Step 2: Run all tests to verify they pass**

```
pytest tests/services/chat/test_intent_router.py -v
```

Expected: ≥ 30 passed (5 model + 5 prompt + 20 classify)

- [ ] **Step 3: Run full test suite for regressions**

```
pytest --tb=short -q
```

Expected: all existing tests still pass

- [ ] **Step 4: Commit**

```
git add tests/services/chat/test_intent_router.py
git commit -m "test: add 20 classify test cases for IntentRouter"
```

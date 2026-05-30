# Phase 1 — Intent Router & Flow State Preservation

**Date:** 2026-05-30
**Status:** Draft
**Parent spec:** `2026-05-30-intent-router-and-knowledge-qa-design.md`

---

## Problem

Hệ thống hiện tại chỉ có một luồng xử lý tuyến tính (`profile → retrieve → conflict → reason → policy → explain`). Mọi tin nhắn của user đều bị đẩy vào luồng tư vấn tuyển sinh bất kể nội dung.

Hệ quả:
- *"Học phí trường UET bao nhiêu?"* → hệ thống cố extract profile từ câu này → trả về câu hỏi tư vấn không liên quan
- *"Thời tiết hôm nay thế nào?"* → chạy toàn bộ advisory graph → lãng phí tài nguyên, trả lời sai
- Profile state bị reset hoặc nhiễu khi user hỏi câu bên lề giữa chừng

**Nguyên nhân gốc rễ:** Không có bước phân loại intent. `ConversationService` không biết phân biệt câu hỏi tư vấn với câu hỏi thực tế hoặc câu ngoài phạm vi.

---

## Mục đích Phase 1

Ngăn hệ thống ép câu hỏi bên lề vào luồng tư vấn. User nhận được hành vi đúng ngay lập tức **dù chưa có data RAG** (Phase 2–4 chưa hoàn thiện).

Sau Phase 1:
- Câu hỏi knowledge → trả fallback rõ ràng, không chạy advisory graph
- Câu ngoài phạm vi → từ chối lịch sự
- Profile state của user không bị ảnh hưởng khi rẽ nhánh
- Sau câu bên lề, agent tự động nhắc lại câu hỏi advisory đang chờ

---

## Phạm vi

**Trong scope:**
- `IntentRouter` service (LLM call riêng)
- `FlowState` model + DB migration
- Routing logic trong `ConversationService`
- Fallback responses cho KNOWLEDGE_QA và OUT_OF_SCOPE
- Re-ask mechanism sau khi trả lời câu bên lề
- Unit tests ≥ 20 cases

**Ngoài scope (Phase sau):**
- RAG pipeline thực sự cho KNOWLEDGE_QA (Phase 4)
- HYBRID orchestration (Phase 5)
- Corpus infrastructure (Phase 2–3)

---

## Files thay đổi

| File | Loại thay đổi |
|---|---|
| `services/chat/intent_router.py` | Tạo mới |
| `services/chat/models.py` | Thêm `FlowState`, `IntentResult` |
| `services/chat/conversation_service.py` | Sửa — thêm routing logic |
| `services/chat/repository.py` | Thêm `get_flow_state`, `update_flow_state` |
| `db/migrations/012_flow_state.sql` | Tạo mới |
| `tests/services/chat/test_intent_router.py` | Tạo mới |
| `tests/services/chat/test_conversation_service.py` | Mở rộng |
| `tests/services/chat/test_repository.py` | Mở rộng |

**Không thay đổi:** `graph.py`, `state.py`, toàn bộ agents, admission ingestion pipeline, structured data schema.

---

## Luồng xử lý mới

```
handle_user_message(session_token, content)
│
├── 1. save_message(content)
├── 2. profile_state = get_profile_state()       # đã có sẵn
│   flow_state    = get_flow_state()             # column mới
│
├── 3. intent = IntentRouter.classify(content, profile_state)
│             └── LLM call riêng, JSON output, ~200ms
│
├── 4a. route == ADVISORY_FLOW
│       → profile extraction → merge → check missing_slots
│       → update flow_state.pending_question nếu có follow-up
│       → IF profile đủ: should_start_run=True (graph.invoke() như cũ)
│
├── 4b. route == KNOWLEDGE_QA
│       → update flow_state { return_to_flow=True }
│       → return fallback message
│       → IF return_to_flow AND missing_slots: append pending_question
│
├── 4c. route == OUT_OF_SCOPE
│       → return polite decline
│       → IF return_to_flow AND missing_slots: append pending_question
│
└── 4d. route == CLARIFICATION (+ HYBRID fallback Phase 1)
        → return generic clarification request
        → IF return_to_flow AND missing_slots: append pending_question
```

Advisory graph (`graph.invoke()`) **không thay đổi** — chỉ được gọi khi `ADVISORY_FLOW` + profile đủ.

---

## 1. IntentRouter Service

**File:** `services/chat/intent_router.py`

### Output schema

```python
class IntentResult(BaseModel):
    route: Literal["ADVISORY_FLOW", "KNOWLEDGE_QA", "HYBRID", "CLARIFICATION", "OUT_OF_SCOPE"]
    topic: Optional[Literal[
        "tuition",          # học phí
        "curriculum",       # chương trình học
        "scholarship",      # học bổng
        "dormitory",        # ký túc xá
        "career",           # định hướng nghề nghiệp
        "admission_policy", # chính sách tuyển sinh
        "program_overview", # tổng quan chương trình
    ]] = None
    school: Optional[str] = None   # resolved từ message hoặc profile_state.preferred_schools
    return_to_flow: bool = False    # True nếu profile_state có dữ liệu (user đang mid-advisory-flow)
```

### Class

```python
class IntentRouter:
    def __init__(self, llm_call=None):
        self._llm_call = llm_call or call_llm_json   # injectable để test

    def classify(self, message: str, profile_state: ChatProfileState) -> IntentResult:
        try:
            prompt = self._build_prompt(message, profile_state)
            raw = self._llm_call(prompt)
            return IntentResult.model_validate(raw)
        except Exception:
            return IntentResult(route="ADVISORY_FLOW")  # safe fallback

    def _build_prompt(self, message: str, profile_state: ChatProfileState) -> dict:
        ...
```

### System prompt

```
Bạn là bộ phân loại intent cho hệ thống tư vấn tuyển sinh đại học Việt Nam.

Phân loại tin nhắn của user vào đúng 1 trong 5 route:

ADVISORY_FLOW — câu hỏi tư vấn chọn ngành/trường dựa trên điểm số, nguyện vọng, khả năng đậu
  Ví dụ: "25 điểm A00 nên chọn trường nào", "em có đậu NEU không", "tư vấn ngành CNTT"

KNOWLEDGE_QA — câu hỏi thực tế về thông tin cụ thể của trường/ngành
  Ví dụ: "học phí UET bao nhiêu", "chương trình CNTT gồm gì", "có học bổng không", "ký túc xá thế nào"

CLARIFICATION — câu quá mơ hồ, thiếu context để phân loại chính xác
  Ví dụ: "thế còn cái đó thì sao" (không rõ "cái đó" là gì), "ý bạn là gì"

OUT_OF_SCOPE — hoàn toàn ngoài lĩnh vực tuyển sinh đại học
  Ví dụ: "thời tiết hôm nay", "kể chuyện cười", "1+1 bằng mấy", "giúp tôi viết code"

HYBRID — cần cả dữ liệu tư vấn (điểm chuẩn, xác suất đậu) lẫn thông tin thực tế (học phí, chương trình)
  Ví dụ: "so sánh UET và HUST về điểm chuẩn lẫn học phí"
  Lưu ý: chỉ dùng HYBRID khi thực sự cần cả hai loại dữ liệu, không dùng cho câu hỏi thuần advisory

Quy tắc resolve đại từ:
- Nếu user dùng "trường này", "ở đó", "trường đó" → resolve từ preferred_schools trong profile
- Nếu user dùng "ngành này", "chuyên ngành đó" → resolve từ preferred_majors trong profile
- Nếu không thể resolve → để school/topic là null, route về CLARIFICATION

Trường (school): chuẩn hóa thành tên viết tắt phổ biến (VNU-UET, HUST, NEU, ...) nếu nhận ra.

return_to_flow: true nếu profile có bất kỳ dữ liệu nào (user đang trong luồng tư vấn dở chừng).

Trả về JSON hợp lệ theo schema sau, không giải thích thêm:
{"route": "...", "topic": "...", "school": "...", "return_to_flow": true/false}
```

### User turn

```
Tin nhắn: "{message}"

Profile hiện tại:
- Trường quan tâm: {preferred_schools or "chưa có"}
- Ngành quan tâm: {preferred_majors or "chưa có"}
- Điểm số: {total_score or "chưa có"}
- Khối thi: {subject_combination or "chưa có"}
- return_to_flow: {true nếu bất kỳ field nào trong profile có giá trị, ngược lại false}
```

### Error handling

| Tình huống | Hành vi |
|---|---|
| LLM call throw | Trả `IntentResult(route="ADVISORY_FLOW")` |
| Response không parse được thành JSON | Trả `IntentResult(route="ADVISORY_FLOW")` |
| `route` không hợp lệ | Trả `IntentResult(route="ADVISORY_FLOW")` |
| `school=null` trong KNOWLEDGE_QA | Service dùng label *"trường bạn hỏi"* |
| `topic=null` trong KNOWLEDGE_QA | Service dùng label *"thông tin này"* |

Không propagate exception ra ngoài `classify()`.

---

## 2. FlowState Model

**Thêm vào** `services/chat/models.py`:

```python
class FlowState(BaseModel):
    active_flow:      Optional[str] = None   # "ADVISORY_FLOW" khi đang trong luồng tư vấn
    return_to_flow:   bool = False           # có advisory flow đang dở không
    pending_question: Optional[str] = None  # follow-up question cuối cùng đã hỏi user
```

### Lifecycle

| Sự kiện | Thay đổi FlowState |
|---|---|
| Session mới | `{}` — default (tất cả None/False) |
| ADVISORY turn, trả follow-up question | `active_flow="ADVISORY_FLOW"`, `pending_question=<câu hỏi>` |
| ADVISORY turn, profile đủ (run bắt đầu) | `active_flow="ADVISORY_FLOW"`, `return_to_flow=False`, `pending_question=None` |
| KNOWLEDGE_QA hoặc OUT_OF_SCOPE turn | `return_to_flow=True` nếu `active_flow` đã set; giữ nguyên `pending_question` |
| Trả lời xong câu bên lề, user quay lại advisory | Handled bình thường bởi ADVISORY_FLOW branch |

---

## 3. DB Migration

**File:** `db/migrations/012_flow_state.sql`

```sql
-- Thêm column lưu flow control state, tách biệt với profile data
ALTER TABLE chat_sessions
    ADD COLUMN IF NOT EXISTS flow_state_json JSONB NOT NULL DEFAULT '{}';
```

Idempotent (`ADD COLUMN IF NOT EXISTS`). Không đụng đến column hiện có. Default `'{}'` tương thích với `FlowState()` default.

---

## 4. Repository Changes

**Thêm vào** `services/chat/repository.py`:

```python
def get_flow_state(self, session_token: str) -> FlowState:
    row = self._execute_one(
        "SELECT flow_state_json FROM chat_sessions WHERE session_token = %s",
        (session_token,)
    )
    return FlowState.model_validate(row["flow_state_json"] or {})

def update_flow_state(self, session_token: str, flow_state: FlowState) -> None:
    self._execute(
        "UPDATE chat_sessions SET flow_state_json = %s WHERE session_token = %s",
        (flow_state.model_dump_json(), session_token)
    )
```

Không swallow exception — DB failure propagate lên caller.

---

## 5. ConversationService Changes

`handle_user_message()` tách thành private methods. `IntentRouter` injectable qua constructor để test.

```python
class ConversationService:
    def __init__(self, repository=None, extract_profile=None, intent_router=None):
        self.repository   = repository    or ChatSessionRepository()
        self.extract_profile = extract_profile or self._extract_profile
        self.intent_router = intent_router or IntentRouter()

    # ------------------------------------------------------------------ public

    def handle_user_message(self, session_token: str, content: str) -> ConversationTurnResult:
        self.repository.append_message(session_token, "user", content, kind="user_message")
        profile_state = self.repository.get_profile_state(session_token)
        flow_state    = self.repository.get_flow_state(session_token)
        intent        = self.intent_router.classify(content, profile_state)

        if intent.route == "ADVISORY_FLOW":
            return self._handle_advisory(session_token, content, profile_state, flow_state)
        elif intent.route == "KNOWLEDGE_QA":
            return self._handle_knowledge_qa(session_token, intent, flow_state)
        elif intent.route == "OUT_OF_SCOPE":
            return self._handle_out_of_scope(session_token, flow_state)
        else:
            # CLARIFICATION + HYBRID (Phase 1 fallback)
            return self._handle_clarification(session_token, flow_state)

    # ----------------------------------------------------------------- private

    def _handle_advisory(self, session_token, content, profile_state, flow_state):
        # Logic hiện tại giữ nguyên:
        # extract_profile → merge → check missing_slots → follow-up or should_start_run

        extracted = self.extract_profile(content)
        merged    = merge_profile_state(profile_state, extracted, content)
        self.repository.update_profile_state(session_token, merged)

        if merged.missing_slots:
            follow_up = build_follow_up_question(merged)
            new_flow = flow_state.model_copy(update={
                "active_flow": "ADVISORY_FLOW",
                "pending_question": follow_up,
            })
            self.repository.update_flow_state(session_token, new_flow)
            self.repository.append_message(session_token, "assistant", follow_up, kind="assistant_follow_up")
            return ConversationTurnResult(
                assistant_message=follow_up,
                should_start_run=False,
                profile_state=merged,
            )
        else:
            new_flow = flow_state.model_copy(update={
                "active_flow": "ADVISORY_FLOW",
                "return_to_flow": False,
                "pending_question": None,
            })
            self.repository.update_flow_state(session_token, new_flow)
            self.repository.update_session_status(session_token, "ready")
            return ConversationTurnResult(
                should_start_run=True,
                profile_state=merged,
            )

    def _handle_knowledge_qa(self, session_token, intent, flow_state):
        # Phase 1: chưa có RAG data → luôn trả fallback
        TOPIC_LABELS = {
            "tuition": "học phí", "curriculum": "chương trình học",
            "scholarship": "học bổng", "dormitory": "ký túc xá",
            "career": "định hướng nghề nghiệp", "admission_policy": "chính sách tuyển sinh",
            "program_overview": "tổng quan chương trình",
        }
        topic_label  = TOPIC_LABELS.get(intent.topic, "thông tin này")
        school_label = intent.school or "trường bạn hỏi"

        fallback = (
            f"Hệ thống chưa có dữ liệu về {topic_label} của {school_label}. "
            f"Bạn có thể liên hệ trực tiếp nhà trường để biết thêm chi tiết."
        )
        response = self._append_return_prompt(fallback, flow_state)

        if flow_state.active_flow == "ADVISORY_FLOW":
            self.repository.update_flow_state(
                session_token,
                flow_state.model_copy(update={"return_to_flow": True})
            )

        self.repository.append_message(session_token, "assistant", response, kind="assistant_result")
        return ConversationTurnResult(assistant_message=response, should_start_run=False)

    def _handle_out_of_scope(self, session_token, flow_state):
        msg = (
            "Xin lỗi, câu hỏi này nằm ngoài phạm vi tư vấn tuyển sinh của mình. "
            "Mình chỉ có thể hỗ trợ các vấn đề liên quan đến tuyển sinh đại học."
        )
        response = self._append_return_prompt(msg, flow_state)
        self.repository.append_message(session_token, "assistant", response, kind="assistant_result")
        return ConversationTurnResult(assistant_message=response, should_start_run=False)

    def _handle_clarification(self, session_token, flow_state):
        msg = "Bạn có thể nói rõ hơn câu hỏi của mình không? Mình muốn hiểu đúng để hỗ trợ tốt hơn."
        response = self._append_return_prompt(msg, flow_state)
        self.repository.append_message(session_token, "assistant", response, kind="assistant_result")
        return ConversationTurnResult(assistant_message=response, should_start_run=False)

    def _append_return_prompt(self, message: str, flow_state: FlowState) -> str:
        """Nếu user đang dở advisory flow và có pending question → nhắc lại cuối response."""
        if flow_state.return_to_flow and flow_state.pending_question:
            return f"{message}\n\nNhân tiện, {flow_state.pending_question}"
        return message
```

---

## 6. Error Handling

| Tình huống | Hành vi |
|---|---|
| `IntentRouter.classify()` throw | Đã tự catch bên trong, trả `ADVISORY_FLOW` |
| `route="HYBRID"` (chưa implement) | Fallback `_handle_clarification()` |
| `get_flow_state()` DB lỗi | Propagate — không swallow |
| `update_flow_state()` DB lỗi | Propagate — không swallow |
| `school=null` trong KNOWLEDGE_QA | Label *"trường bạn hỏi"* |
| `topic=null` trong KNOWLEDGE_QA | Label *"thông tin này"* |

---

## 7. Testing Strategy

### `tests/services/chat/test_intent_router.py` — unit tests (mock LLM)

≥ 20 cases bao phủ 5 routes:

**ADVISORY_FLOW (≥ 5 cases):**
- `"25 điểm A00 nên chọn trường nào"` → ADVISORY_FLOW
- `"em có đậu NEU không"` → ADVISORY_FLOW
- `"tư vấn ngành CNTT cho mình"` → ADVISORY_FLOW
- `"điểm 28 khối B00 nên nộp đâu"` → ADVISORY_FLOW
- `"cơ hội đậu Bách Khoa của em là bao nhiêu"` → ADVISORY_FLOW

**KNOWLEDGE_QA (≥ 5 cases):**
- `"học phí UET bao nhiêu"` → KNOWLEDGE_QA, topic=tuition, school=VNU-UET
- `"chương trình học CNTT gồm gì"` → KNOWLEDGE_QA, topic=curriculum
- `"có học bổng không"` → KNOWLEDGE_QA, topic=scholarship
- `"ký túc xá thế nào"` → KNOWLEDGE_QA, topic=dormitory
- `"trường này học phí bao nhiêu"` + `preferred_schools=["VNU-UET"]` → school=VNU-UET

**OUT_OF_SCOPE (≥ 4 cases):**
- `"thời tiết hôm nay thế nào"` → OUT_OF_SCOPE
- `"kể cho tôi nghe một câu chuyện cười"` → OUT_OF_SCOPE
- `"giúp tôi viết code Python"` → OUT_OF_SCOPE
- `"hôm nay ăn gì ngon"` → OUT_OF_SCOPE

**CLARIFICATION (≥ 3 cases):**
- `"thế còn cái đó thì sao"` (no profile) → CLARIFICATION
- `"ý bạn là gì"` → CLARIFICATION
- `"còn nữa không"` (no context) → CLARIFICATION

**LLM failure (≥ 3 cases):**
- LLM throw exception → fallback ADVISORY_FLOW
- LLM trả về non-JSON → fallback ADVISORY_FLOW
- LLM trả về route không hợp lệ → fallback ADVISORY_FLOW

### `tests/services/chat/test_conversation_service.py` — mở rộng file hiện có

Dùng `FakeIntentRouter` inject vào constructor:

```python
class FakeIntentRouter:
    def __init__(self, result: IntentResult):
        self._result = result
    def classify(self, message, profile_state):
        return self._result
```

Cases:
- Route ADVISORY_FLOW → `_handle_advisory` chạy, profile được update
- Route KNOWLEDGE_QA → trả fallback message, profile **không bị reset**
- Route OUT_OF_SCOPE → trả polite decline, profile **không bị reset**
- Route CLARIFICATION → trả generic clarification
- `return_to_flow=True` + `pending_question="Bạn học khối gì?"` → câu nhắc xuất hiện cuối response
- `return_to_flow=True` + `pending_question=None` → không append gì thêm
- `flow_state.pending_question` được lưu khi ADVISORY follow-up
- `flow_state.pending_question` giữ nguyên khi rẽ KNOWLEDGE_QA
- `flow_state` cleared (`return_to_flow=False`, `pending_question=None`) khi profile đủ

### `tests/services/chat/test_repository.py` — mở rộng

- `get_flow_state()` trả `FlowState()` default khi column là `{}`
- `update_flow_state()` + `get_flow_state()` round-trip đúng (persist và đọc lại)

---

## Acceptance Criteria

- [ ] `"học phí UET bao nhiêu?"` → route `KNOWLEDGE_QA`, **KHÔNG** chạy advisory graph
- [ ] `"Em 25 điểm A00 nên chọn ngành gì?"` → route `ADVISORY_FLOW`, flow hiện tại không thay đổi
- [ ] `"thời tiết hôm nay thế nào?"` → route `OUT_OF_SCOPE`, trả lời lịch sự
- [ ] `KNOWLEDGE_QA` chưa có data → *"Hệ thống chưa có dữ liệu về [topic] của [trường], bạn có thể liên hệ trực tiếp nhà trường..."*
- [ ] Sau trả lời câu bên lề, `return_to_flow=true` + `missing_slots` không rỗng → response kết thúc bằng pending follow-up question
- [ ] Profile state của user **KHÔNG bị reset** khi route sang nhánh khác
- [ ] Unit test router ≥ 20 cases bao phủ 5 intent types
- [ ] Migration idempotent — chạy lại không lỗi, không duplicate column

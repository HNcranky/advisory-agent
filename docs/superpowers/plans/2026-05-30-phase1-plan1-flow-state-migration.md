# Phase 1 — Plan 1: FlowState Model + DB Migration + Repository

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `FlowState` Pydantic model, DB migration for `flow_state_json` column, and two repository methods (`get_flow_state`, `update_flow_state`) — the storage foundation for Phase 1 routing.

**Architecture:** `FlowState` lives in `services/chat/models.py` alongside `ChatProfileState`. A new JSONB column `flow_state_json` is added to `chat_sessions` via an idempotent migration. Two methods are added to `ChatSessionRepository` following the exact same psycopg2 pattern used by `get_profile_state` / `update_profile_state`.

**Tech Stack:** Python 3.11, Pydantic v2, psycopg2, PostgreSQL, pytest, unittest.mock

---

### Task 1: FlowState Pydantic Model

**Files:**
- Modify: `services/chat/models.py`
- Test: `tests/services/chat/test_flow_state_model.py`

- [ ] **Step 1: Create test file and write failing tests**

Create `tests/services/chat/test_flow_state_model.py`:

```python
import pytest
from services.chat.models import FlowState


def test_flow_state_defaults():
    state = FlowState()
    assert state.active_flow is None
    assert state.return_to_flow is False
    assert state.pending_question is None


def test_flow_state_model_validate_from_empty_dict():
    state = FlowState.model_validate({})
    assert state == FlowState()


def test_flow_state_model_validate_from_full_dict():
    state = FlowState.model_validate({
        "active_flow": "ADVISORY_FLOW",
        "return_to_flow": True,
        "pending_question": "Bạn học khối gì?",
    })
    assert state.active_flow == "ADVISORY_FLOW"
    assert state.return_to_flow is True
    assert state.pending_question == "Bạn học khối gì?"


def test_flow_state_model_copy_update():
    original = FlowState(active_flow="ADVISORY_FLOW")
    updated = original.model_copy(update={"return_to_flow": True, "pending_question": "Q?"})
    assert updated.active_flow == "ADVISORY_FLOW"
    assert updated.return_to_flow is True
    assert updated.pending_question == "Q?"
    # original unchanged
    assert original.return_to_flow is False
    assert original.pending_question is None


def test_flow_state_equality():
    a = FlowState(active_flow="ADVISORY_FLOW", return_to_flow=True)
    b = FlowState(active_flow="ADVISORY_FLOW", return_to_flow=True)
    assert a == b
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/services/chat/test_flow_state_model.py -v
```

Expected: `ImportError: cannot import name 'FlowState' from 'services.chat.models'`

- [ ] **Step 3: Add FlowState to models.py**

Open `services/chat/models.py`. After the `ChatProfileState` class (line 33), add:

```python
class FlowState(BaseModel):
    active_flow: Optional[str] = None
    return_to_flow: bool = False
    pending_question: Optional[str] = None
```

The top of `models.py` already imports `Optional` — no new imports needed.

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/services/chat/test_flow_state_model.py -v
```

Expected: 5 passed

- [ ] **Step 5: Commit**

```
git add services/chat/models.py tests/services/chat/test_flow_state_model.py
git commit -m "feat: add FlowState model to services/chat/models"
```

---

### Task 2: DB Migration

**Files:**
- Create: `db/migrations/012_flow_state.sql`

- [ ] **Step 1: Create migration file**

Create `db/migrations/012_flow_state.sql`:

```sql
-- Add flow control state column to chat_sessions.
-- Kept separate from profile_state_json: profile data vs. routing state are different concerns.
ALTER TABLE chat_sessions
    ADD COLUMN IF NOT EXISTS flow_state_json JSONB NOT NULL DEFAULT '{}';
```

- [ ] **Step 2: Verify migration is idempotent**

Run against your local DB twice:

```
psql $DATABASE_URL -f db/migrations/012_flow_state.sql
psql $DATABASE_URL -f db/migrations/012_flow_state.sql
```

Expected: No error on second run (`ADD COLUMN IF NOT EXISTS` is idempotent).

- [ ] **Step 3: Verify column exists**

```
psql $DATABASE_URL -c "\d chat_sessions"
```

Expected: `flow_state_json` column appears with type `jsonb` and default `'{}'`.

- [ ] **Step 4: Commit**

```
git add db/migrations/012_flow_state.sql
git commit -m "feat: add flow_state_json column to chat_sessions"
```

---

### Task 3: Repository — get_flow_state

**Files:**
- Modify: `services/chat/repository.py`
- Test: `tests/services/chat/test_repository.py`

- [ ] **Step 1: Create test file and write failing test**

Create `tests/services/chat/test_repository.py`:

```python
from unittest.mock import MagicMock
import pytest
from services.chat.repository import ChatSessionRepository
from services.chat.models import FlowState


def _make_conn(fetchone_return=None):
    """Returns (conn, cursor) mocks wired together."""
    cursor = MagicMock()
    cursor.fetchone.return_value = fetchone_return
    conn = MagicMock()
    conn.cursor.return_value = cursor
    return conn, cursor


def test_get_flow_state_returns_default_when_column_is_null():
    conn, cursor = _make_conn(fetchone_return=(None,))
    repo = ChatSessionRepository(connection_factory=lambda: conn)

    result = repo.get_flow_state("tok-1")

    assert result == FlowState()
    assert result.active_flow is None
    assert result.return_to_flow is False
    assert result.pending_question is None


def test_get_flow_state_returns_default_when_row_missing():
    conn, cursor = _make_conn(fetchone_return=None)
    repo = ChatSessionRepository(connection_factory=lambda: conn)

    result = repo.get_flow_state("tok-1")

    assert result == FlowState()


def test_get_flow_state_returns_persisted_state():
    saved = {
        "active_flow": "ADVISORY_FLOW",
        "return_to_flow": True,
        "pending_question": "Bạn học khối gì?",
    }
    conn, cursor = _make_conn(fetchone_return=(saved,))
    repo = ChatSessionRepository(connection_factory=lambda: conn)

    result = repo.get_flow_state("tok-1")

    assert result.active_flow == "ADVISORY_FLOW"
    assert result.return_to_flow is True
    assert result.pending_question == "Bạn học khối gì?"


def test_get_flow_state_queries_correct_table_and_token():
    conn, cursor = _make_conn(fetchone_return=(None,))
    repo = ChatSessionRepository(connection_factory=lambda: conn)

    repo.get_flow_state("my-token")

    sql = cursor.execute.call_args[0][0]
    params = cursor.execute.call_args[0][1]
    assert "flow_state_json" in sql
    assert "chat_sessions" in sql
    assert params == ("my-token",)
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/services/chat/test_repository.py -v
```

Expected: `AttributeError: 'ChatSessionRepository' object has no attribute 'get_flow_state'`

- [ ] **Step 3: Add get_flow_state to repository.py**

Open `services/chat/repository.py`. Add this import at the top (after existing imports):

```python
from services.chat.models import ChatSessionRecord, ChatMessageRecord, ChatProfileState, FlowState
```

Then add `get_flow_state` after the `get_profile_state` method (after line 116):

```python
def get_flow_state(self, session_token: str) -> FlowState:
    conn = self.connection_factory()
    cur = conn.cursor()
    cur.execute(
        "SELECT flow_state_json FROM chat_sessions WHERE session_token = %s",
        (session_token,),
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    return FlowState.model_validate(row[0] or {} if row else {})
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/services/chat/test_repository.py -v
```

Expected: 4 passed

- [ ] **Step 5: Commit**

```
git add services/chat/repository.py tests/services/chat/test_repository.py
git commit -m "feat: add get_flow_state to ChatSessionRepository"
```

---

### Task 4: Repository — update_flow_state

**Files:**
- Modify: `services/chat/repository.py`
- Test: `tests/services/chat/test_repository.py` (extend)

- [ ] **Step 1: Add failing tests**

Append to `tests/services/chat/test_repository.py`:

```python
def test_update_flow_state_executes_update_sql():
    conn, cursor = _make_conn()
    repo = ChatSessionRepository(connection_factory=lambda: conn)
    flow = FlowState(active_flow="ADVISORY_FLOW", return_to_flow=True, pending_question="Q?")

    repo.update_flow_state("tok-1", flow)

    cursor.execute.assert_called_once()
    sql = cursor.execute.call_args[0][0]
    assert "flow_state_json" in sql
    assert "chat_sessions" in sql
    conn.commit.assert_called_once()


def test_update_flow_state_passes_correct_session_token():
    conn, cursor = _make_conn()
    repo = ChatSessionRepository(connection_factory=lambda: conn)
    flow = FlowState()

    repo.update_flow_state("specific-token", flow)

    params = cursor.execute.call_args[0][1]
    assert "specific-token" in params


def test_update_flow_state_closes_connection():
    conn, cursor = _make_conn()
    repo = ChatSessionRepository(connection_factory=lambda: conn)

    repo.update_flow_state("tok-1", FlowState())

    cur_close_called = cursor.close.called
    conn_close_called = conn.close.called
    assert cur_close_called
    assert conn_close_called
```

- [ ] **Step 2: Run new tests to verify they fail**

```
pytest tests/services/chat/test_repository.py::test_update_flow_state_executes_update_sql -v
```

Expected: `AttributeError: 'ChatSessionRepository' object has no attribute 'update_flow_state'`

- [ ] **Step 3: Add update_flow_state to repository.py**

Add this method after `get_flow_state`:

```python
def update_flow_state(self, session_token: str, flow_state: FlowState) -> None:
    conn = self.connection_factory()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE chat_sessions
        SET flow_state_json = %s, updated_at = NOW()
        WHERE session_token = %s
        """,
        (self._jsonb(flow_state), session_token),
    )
    conn.commit()
    cur.close()
    conn.close()
```

- [ ] **Step 4: Run all repository tests**

```
pytest tests/services/chat/test_repository.py -v
```

Expected: 7 passed

- [ ] **Step 5: Run full test suite to check for regressions**

```
pytest --tb=short -q
```

Expected: all existing tests still pass

- [ ] **Step 6: Commit**

```
git add services/chat/repository.py tests/services/chat/test_repository.py
git commit -m "feat: add update_flow_state to ChatSessionRepository"
```

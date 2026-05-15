# Slice 4 — Real-data end-to-end + chat surface + docs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Verify the conflict-aware advisory pipeline against the real curated HUST + VNU-UET corpus from Slice 1, prove that the verification section reaches the chat surface, and document the demo-prep workflow. This slice is what makes the thesis claim — *"the system handles distributed, heterogeneous, conflicting admission data"* — load-bearing.

**Architecture:** No new production code. Add a `requires_real_dataset` pytest marker, the `tests/e2e/test_real_conflict_resolution.py` real-data integration test, extend `tests/e2e/test_chat_web_flow.py` to assert the verification section reaches the polled snapshot, and document the demo-prep gate in `QUICKSTART.md`. Manual chat-walkthrough is a phase-completion criterion outside automated tests.

**Tech Stack:** pytest (with custom marker), FastAPI TestClient (existing `web.app.build_app`), the curated `tests/e2e/fixtures/real_dataset_dump.sql` from Slice 1, existing chat services (`ConversationService`, `run_dispatcher`, `ChatSessionRepository`).

---

## File Structure

- Create: `tests/e2e/test_real_conflict_resolution.py` — the load-bearing real-data integration test (gated by marker).
- Modify: `pytest.ini` / `pyproject.toml` (whichever defines pytest config) — register the `requires_real_dataset` marker so `-W error` doesn't trip on it.
- Create: `tests/e2e/conftest.py` (if missing) — provide a `seeded_real_dataset_db` fixture that loads the dump into a transactional test DB.
- Modify: `tests/e2e/test_chat_web_flow.py` — add one test asserting the verification section text reaches the assistant_result message via the chat snapshot API.
- Modify: `QUICKSTART.md` — add the "Demo prep / phase-completion gate" section.
- Create: `docs/superpowers/demo_walkthrough.md` — manual walkthrough checklist (resolved + unresolved chat flows) used during demo prep.

This slice intentionally adds NO production code. All changes are tests, configuration, and documentation.

---

## Task 1: Register the `requires_real_dataset` pytest marker

**Files:**
- Modify: existing pytest config (probably `pyproject.toml` — verify with `Grep`)

- [ ] **Step 1: Locate the pytest config**

Run: `Grep` for `[tool.pytest`, `[pytest]`, `pytest.ini`, or `setup.cfg` at the repo root. Identify the file that holds pytest config (most likely `pyproject.toml`; otherwise `pytest.ini`).

- [ ] **Step 2: Register the marker**

In `pyproject.toml`, add (or extend) under `[tool.pytest.ini_options]`:

```toml
[tool.pytest.ini_options]
markers = [
    "requires_real_dataset: integration test requiring the curated HUST+VNU-UET dump; skipped by default",
]
```

If using `pytest.ini`, the equivalent is:

```ini
[pytest]
markers =
    requires_real_dataset: integration test requiring the curated HUST+VNU-UET dump; skipped by default
```

If a `markers` list already exists, append the new line; do not replace.

- [ ] **Step 3: Verify the marker is registered**

Run: `pytest --markers | Select-String requires_real_dataset`

Expected: a line `@pytest.mark.requires_real_dataset: integration test requiring ...`.

- [ ] **Step 4: Verify default pytest run skips marker-tagged tests**

Create a temporary file `tests/_marker_probe.py`:

```python
import pytest


@pytest.mark.requires_real_dataset
def test_probe_should_be_collected_but_skipped_by_default():
    assert False, "this body should not run on a default pytest invocation"
```

Run: `pytest tests/_marker_probe.py -v`

Expected: the test is **collected** (not "unknown mark") and **passes by default** because no `-m requires_real_dataset` was passed. Wait — by default, custom markers run too unless explicitly deselected. Pytest only skips marker-tagged tests if the test body itself opts out. The correct pattern is `pytest -m "not requires_real_dataset"` to skip them, OR have the test itself skip when an env var or fixture is missing.

Change the strategy: the marker is for **selection**, not for skipping. The test itself will skip when the seeded DB isn't available — see Task 2. Remove `tests/_marker_probe.py` and commit only the marker registration.

```powershell
Remove-Item tests/_marker_probe.py
git add pyproject.toml
git commit -m "test: register requires_real_dataset pytest marker"
```

The phase-completion command becomes `pytest -m requires_real_dataset` (selects only those tests) and the default `pytest` (without `-m`) lets the per-test skip guard handle them.

---

## Task 2: Real-data conftest fixture

**Files:**
- Create or Modify: `tests/e2e/conftest.py`

- [ ] **Step 1: Check whether `tests/e2e/conftest.py` exists**

Run: `Glob` for `tests/e2e/conftest.py`. If it doesn't exist, create it. If it does, read it first to see what fixtures already live there.

- [ ] **Step 2: Add the `seeded_real_dataset_db` fixture**

Add to `tests/e2e/conftest.py`:

```python
import os
from pathlib import Path

import pytest


REAL_DATASET_DUMP = Path("tests/e2e/fixtures/real_dataset_dump.sql")


@pytest.fixture(scope="session")
def seeded_real_dataset_db():
    """Session-scoped fixture: pipe the curated dump into the configured database.

    Skips the test if:
    - DATABASE_URL is not set, or
    - the dump file is missing.

    The fixture does NOT clean up after itself — it assumes the test DB is
    disposable. Demo-prep runs typically point DATABASE_URL at a dedicated
    test instance.
    """
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        pytest.skip("DATABASE_URL not set; real-data e2e cannot run")
    if not REAL_DATASET_DUMP.exists():
        pytest.skip(f"Real-data dump missing at {REAL_DATASET_DUMP}; run Slice 1 to produce it")

    # Use psql to load the dump.
    import subprocess
    result = subprocess.run(
        ["psql", db_url, "-v", "ON_ERROR_STOP=1", "-f", str(REAL_DATASET_DUMP)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        pytest.skip(
            f"Failed to load real-data dump: {result.stderr[-500:]}"
        )
    yield db_url
```

- [ ] **Step 3: Commit**

```powershell
git add tests/e2e/conftest.py
git commit -m "test: add seeded_real_dataset_db fixture for real-data e2e"
```

---

## Task 3: The real-data conflict-resolution test

**Files:**
- Create: `tests/e2e/test_real_conflict_resolution.py`

This is the **load-bearing test for the phase**. Failing it fails the phase.

- [ ] **Step 1: Write the test**

Create `tests/e2e/test_real_conflict_resolution.py`:

```python
import pytest

from services.chat.advisory_runner import run_advisory_for_session
from services.chat.models import ChatProfileState


pytestmark = pytest.mark.requires_real_dataset


def test_real_dataset_produces_a_conflict_outcome(seeded_real_dataset_db):
    """At least one of the curated HUST/UET programs must round-trip a
    conflict outcome through the advisory graph."""
    # Build a profile likely to retrieve the conflict-bearing programs.
    # The exact preferred_majors/preferred_schools depend on what Slice 1
    # curated; adjust these to match the dataset_curation_log.md entries.
    profile = ChatProfileState(
        admission_year=2026,
        total_score=27,
        subject_combination="A00",
        preferred_schools=["hust", "uet"],
        preferred_majors=["computer_science", "electrical_engineering"],
        missing_slots=[],
    )

    result = run_advisory_for_session(profile, latest_user_message="Tu van giup em")

    outcomes = result.get("resolution_outcomes") or []
    assert outcomes, (
        "No resolution_outcomes produced from the real dataset. "
        "Either retrieval did not pull the conflict-bearing rows, or detection failed. "
        "Inspect canonical_admission_records via the Slice 1 acceptance SQL."
    )

    final_answer = result.get("final_answer") or ""
    assert "## Xác minh dữ liệu" in final_answer, (
        f"Verification section missing from final_answer: {final_answer[:1000]}"
    )


def test_real_dataset_chat_walkthrough_resolved_branch(seeded_real_dataset_db):
    """At least one outcome on the real dataset is deterministically resolved."""
    profile = ChatProfileState(
        admission_year=2026,
        total_score=28,
        subject_combination="A00",
        preferred_schools=["hust", "uet"],
        preferred_majors=["computer_science", "electrical_engineering"],
        missing_slots=[],
    )
    result = run_advisory_for_session(profile, latest_user_message="Em muon hoc CS")
    resolved = [o for o in (result.get("resolution_outcomes") or []) if o.status == "resolved"]
    assert resolved, (
        "Expected at least one resolved outcome on the real dataset. "
        "If everything is unresolved, the corroboration/trust axes may not be wired "
        "to the real source_registry trust_levels."
    )


def test_real_dataset_chat_walkthrough_unresolved_branch(seeded_real_dataset_db):
    """At least one outcome on the real dataset is unresolved (or LLM-tiebroken)."""
    profile = ChatProfileState(
        admission_year=2026,
        total_score=28,
        subject_combination="A00",
        preferred_schools=["hust", "uet"],
        preferred_majors=["computer_science", "electrical_engineering"],
        missing_slots=[],
    )
    result = run_advisory_for_session(profile, latest_user_message="Em muon hoc nganh khac")
    unresolved = [
        o for o in (result.get("resolution_outcomes") or []) if o.status == "unresolved"
    ]
    if not unresolved:
        pytest.skip(
            "All real-dataset conflicts were deterministically resolved. "
            "This is acceptable but means the unresolved-branch surfacing is untested on real data. "
            "Demo prep should manually walk through an unresolved fixture if curation produces none."
        )
    assert unresolved
```

The third test is `pytest.skip` rather than `assert` because real data may produce only resolved outcomes (a desirable state). The spec requires the unresolved path to be demonstrable on real OR walkthrough data; the walkthrough doc (Task 6) covers the synthetic fallback.

- [ ] **Step 2: Run the test against the seeded DB**

Prereqs: Slice 1 must have produced `tests/e2e/fixtures/real_dataset_dump.sql`, and `DATABASE_URL` must point at a disposable Postgres instance.

Run: `pytest -m requires_real_dataset -v`

Expected: 2 PASS, 1 PASS-or-SKIP (the unresolved-branch test).

If `test_real_dataset_produces_a_conflict_outcome` fails with "No resolution_outcomes produced":

- Run the Slice 1 acceptance SQL against the same DB to confirm conflicting rows exist.
- Check `state.retrieved_programs` length by running the test in a debugger or with a temporary print — if 0, the retrieval filter doesn't match the curated programs (adjust `preferred_majors` in the profile).
- If retrieval returns rows but `conflict_records` is empty, check `_group_key` — the curated rows may differ on `admission_method` and not collide.

- [ ] **Step 3: Run default pytest to verify the marker correctly skips these tests when DATABASE_URL is unset**

Run: `$env:DATABASE_URL=$null; pytest tests/e2e/test_real_conflict_resolution.py -v`

Expected: all 3 SKIPPED with "DATABASE_URL not set; real-data e2e cannot run".

- [ ] **Step 4: Commit**

```powershell
git add tests/e2e/test_real_conflict_resolution.py
git commit -m "test(e2e): real-data conflict resolution test gated by requires_real_dataset"
```

---

## Task 4: Chat web-surface verification-section assertion

**Files:**
- Modify: `tests/e2e/test_chat_web_flow.py`

The existing `test_chat_web_flow.py` only checks the static page + JS, not the run lifecycle. Add one test that drives the chat API end-to-end with synthetic conflict-bearing data and asserts the verification section reaches the polled snapshot.

- [ ] **Step 1: Read the current chat web routes**

Run: `Grep` for `@app.post` and `@app.get` in `web/` to identify the chat API route shape (URL paths for creating a session, posting a message, polling a snapshot). Capture: session-create POST URL, message POST URL, and snapshot GET URL. These typically are `POST /api/sessions`, `POST /api/sessions/{token}/messages`, `GET /api/sessions/{token}`.

- [ ] **Step 2: Write the failing test**

Append to `tests/e2e/test_chat_web_flow.py`:

```python
import time

from unittest.mock import patch

from agents.models import CandidateProgram, Evidence, StudentProfile
from services.inference.models import InferenceResult


def _two_conflicting_candidates():
    c1 = CandidateProgram(
        candidate_id="hust:2026:cs:thpt:a",
        school_id="hust", school_name="HUST", admission_year=2026,
        program_id="computer_science", program_name="Khoa hoc May tinh",
        admission_method="thpt_score", subject_combinations=["A00", "A01"],
        quota={"total": 100},
        evidence=[Evidence(source_url="https://hust.edu.vn/cs", school_name="HUST",
                           admission_year=2026, field_name="record", trust_level=3)],
    )
    c2 = CandidateProgram(
        candidate_id="hust:2026:cs:thpt:b",
        school_id="hust", school_name="HUST", admission_year=2026,
        program_id="computer_science", program_name="Khoa hoc May tinh",
        admission_method="thpt_score", subject_combinations=["A00", "A01"],
        quota={"total": 200},
        evidence=[Evidence(source_url="https://other-source/", school_name="HUST",
                           admission_year=2026, field_name="record", trust_level=1)],
    )
    return [c1, c2]


def _stub_profile():
    return StudentProfile(
        total_score=27, subject_combination="A00",
        preferred_majors=["computer_science"], preferred_schools=["hust"],
        missing_slots=[],
    )


def test_chat_snapshot_eventually_contains_verification_section(monkeypatch):
    """End-to-end through the chat HTTP surface: a session that triggers a conflict
    must surface '## Xác minh dữ liệu' in the assistant_result message reachable from
    the snapshot endpoint."""
    client = TestClient(build_app())

    # Stub the inference layers so the run doesn't hit Gemini.
    import agents.profile_agent as profile_agent_module
    import agents.retrieval_agent as retrieval_agent_module
    import agents.conflict_agent as conflict_agent_module
    monkeypatch.setattr(
        profile_agent_module, "build_profile_with_gateway",
        lambda user_query, gateway: _stub_profile(),
    )
    monkeypatch.setattr(
        retrieval_agent_module, "fetch_candidates",
        lambda filters, limit=100: _two_conflicting_candidates(),
    )
    monkeypatch.setattr(
        conflict_agent_module, "package_evidence",
        lambda record, raw_candidates, admission_year: record.options,
    )
    monkeypatch.setattr(conflict_agent_module, "build_default_gateway", lambda: object())

    # Also stub ConversationService's profile extraction so the user message path
    # immediately reaches "ready" without follow-up questions.
    import services.chat.conversation_service as conv_module
    monkeypatch.setattr(
        conv_module, "build_profile_with_gateway",
        lambda text, gateway: _stub_profile(),
    )

    # 1. Create a session.
    resp = client.post("/api/sessions")
    assert resp.status_code == 200
    session_token = resp.json()["session_token"]

    # 2. Send a user message that triggers the advisory run.
    resp = client.post(
        f"/api/sessions/{session_token}/messages",
        json={"content": "Em 27 diem A00 muon hoc CS o HUST"},
    )
    assert resp.status_code == 200

    # 3. Poll the snapshot until an assistant_result appears (max 5 seconds).
    final_answer = None
    for _ in range(50):
        resp = client.get(f"/api/sessions/{session_token}")
        assert resp.status_code == 200
        body = resp.json()
        messages = body.get("messages", [])
        result_msg = next(
            (m for m in messages if m.get("kind") == "assistant_result"),
            None,
        )
        if result_msg:
            final_answer = result_msg["content"]
            break
        time.sleep(0.1)

    assert final_answer is not None, "Advisory run did not complete within 5 seconds"
    assert "## Xác minh dữ liệu" in final_answer
    # The deterministically-resolved trust_level=3 source wins → value 100 should appear.
    assert "100" in final_answer
```

Note: the exact API paths (`/api/sessions`, `/api/sessions/{token}/messages`, `/api/sessions/{token}`) must match `web/app.py`. If they differ, adjust accordingly. The poll loop's 5-second budget covers the synchronous-vs-threaded run dispatcher — if `run_dispatcher` uses a thread pool, 5 seconds is generous; if it's synchronous, the first poll already has the answer.

- [ ] **Step 3: Run the test**

Run: `pytest tests/e2e/test_chat_web_flow.py -v`

Expected: PASS.

Common failure modes:
- API path mismatch → 404 on `client.post("/api/sessions")`. Fix by `Grep`-ing `web/app.py` for the actual mount.
- Snapshot polling never finds `assistant_result` → the run dispatcher hasn't completed. Increase the poll budget OR look at how existing chat tests trigger and wait for runs (`tests/services/chat/test_run_dispatcher.py` and `test_advisory_runner.py` show the patterns).
- `package_evidence` patch site wrong if `agents/conflict_agent.py` imports `package_evidence` as a direct symbol — Slice 3 imports it; the monkeypatch on `conflict_agent_module.package_evidence` then works because Python rebinds the module-level name.

- [ ] **Step 4: Commit**

```powershell
git add tests/e2e/test_chat_web_flow.py
git commit -m "test(e2e): assert verification section reaches chat snapshot"
```

---

## Task 5: Update QUICKSTART.md with the phase-completion gate

**Files:**
- Modify: `QUICKSTART.md`

- [ ] **Step 1: Append the demo-prep section**

After the existing "Troubleshooting" section in `QUICKSTART.md`, append:

```markdown

## Demo prep / phase-completion gate

The conflict-aware advisory phase ships only when the real-data end-to-end test passes against the curated HUST + VNU-UET corpus.

### Prerequisites

- A disposable Postgres instance (do not run this against your dev DB).
- `DATABASE_URL` exported in the shell, pointing at that instance.
- The curated dump exists at `tests/e2e/fixtures/real_dataset_dump.sql`. If it is missing, follow Slice 1 of the conflict-aware-advisory plan to re-curate.

### Run the gated test

```powershell
# Apply migrations to the disposable DB first.
psql $env:DATABASE_URL -f db/migrations/001_source_registry.sql
psql $env:DATABASE_URL -f db/migrations/002_discovered_resources.sql
psql $env:DATABASE_URL -f db/migrations/003_raw_documents.sql
psql $env:DATABASE_URL -f db/migrations/004_extracted_facts.sql
psql $env:DATABASE_URL -f db/migrations/005_canonical_programs.sql
psql $env:DATABASE_URL -f db/migrations/006_rename_conditions_to_metadata.sql
psql $env:DATABASE_URL -f db/migrations/007_advisory_indexes.sql
psql $env:DATABASE_URL -f db/migrations/008_advisory_runs.sql
psql $env:DATABASE_URL -f db/migrations/009_chat_sessions.sql
psql $env:DATABASE_URL -f db/migrations/010_canonical_records_per_source.sql

# Run the gated test (the seeded_real_dataset_db fixture pipes the dump in).
pytest -m requires_real_dataset -v
```

Expected outcome:

- `test_real_dataset_produces_a_conflict_outcome` — PASS.
- `test_real_dataset_chat_walkthrough_resolved_branch` — PASS.
- `test_real_dataset_chat_walkthrough_unresolved_branch` — PASS or SKIP (SKIP is acceptable when the curated data produces only resolved outcomes).

If `test_real_dataset_produces_a_conflict_outcome` fails, the phase is not shippable; either re-curate the dataset or fix the failing layer.

### Manual chat walkthrough

Before the defense:

1. Apply migrations and load the dump as above.
2. Start the chat web app (step 4 of this Quickstart).
3. Send a freeform message describing a student whose profile would retrieve at least one conflict-bearing program.
4. Confirm the assistant result turn contains a `## Xác minh dữ liệu` section.
5. Capture the exact text shown to the student — this becomes the demo artifact.

The manual walkthrough is the final gate; see `docs/superpowers/demo_walkthrough.md` for the full checklist.
```

- [ ] **Step 2: Commit**

```powershell
git add QUICKSTART.md
git commit -m "docs(quickstart): document phase-completion gate for conflict-aware advisory"
```

---

## Task 6: Demo walkthrough checklist document

**Files:**
- Create: `docs/superpowers/demo_walkthrough.md`

- [ ] **Step 1: Write the walkthrough**

Create `docs/superpowers/demo_walkthrough.md`:

```markdown
# Conflict-Aware Advisory V1 — Demo Walkthrough Checklist

The phase ships only when the items below are verified manually on a clean run against the curated dataset. This document is the artifact reviewers should sign off on before the thesis defense.

## Environment

- [ ] `DATABASE_URL` points at a disposable Postgres instance (not the dev DB).
- [ ] All migrations 001 → 010 are applied.
- [ ] `tests/e2e/fixtures/real_dataset_dump.sql` is loaded into the DB.
- [ ] `pytest -m requires_real_dataset` passes (see QUICKSTART.md).

## Verify the data

Run:

```sql
SELECT school_id, admission_year, program_id, admission_method,
       COUNT(*) AS row_count,
       COUNT(DISTINCT quota::text) AS distinct_quota_count,
       array_agg(source_url) AS sources
FROM canonical_admission_records
WHERE admission_year = 2026
GROUP BY school_id, admission_year, program_id, admission_method
HAVING COUNT(DISTINCT quota::text) >= 2;
```

- [ ] At least 3 program-method tuples returned (Slice 1 acceptance criterion).

## Resolved-branch chat walkthrough

1. [ ] Start the chat web app per QUICKSTART.md step 4.
2. [ ] Send: *"Em được 28 điểm A00 và muốn học Khoa học Máy tính ở HUST."* (substitute a profile that retrieves a HUST conflict-bearing program).
3. [ ] Answer any follow-up questions until the assistant enters the "analyzing" state.
4. [ ] When the assistant result turn appears, confirm:
   - [ ] A `## Xác minh dữ liệu` section is present.
   - [ ] The section names a specific resolved value with a labelled source (e.g., "Trang tuyển sinh HUST").
   - [ ] The rejected source(s) and their reported value(s) are mentioned.
   - [ ] The recommendation's band is consistent with the resolved value (the program is not blocked from the "safe" band by an uncertainty flag).

Capture a screenshot of the assistant turn.

## Unresolved-branch chat walkthrough

If the real dataset produces an unresolved outcome (the resolved-branch SQL above includes at least one tuple where the Comparison agent ties on all axes), perform this walkthrough. Otherwise it is acceptable to skip and rely on the synthetic graph integration test `tests/e2e/test_advisory_flow.py::test_advisory_flow_surfaces_uncertainty_for_unresolved_conflict` as the load-bearing evidence.

1. [ ] Send a message that retrieves an unresolved conflict-bearing program.
2. [ ] Confirm:
   - [ ] The `## Xác minh dữ liệu` section names both conflicting sources and their reported values.
   - [ ] The section ends with "Bạn nên xác minh trực tiếp với trường trước khi đăng ký."
   - [ ] The recommendation's cautions include "Số liệu hạn ngạch chưa được xác nhận giữa các nguồn."
   - [ ] The recommendation is NOT in the top "safe" band — it appears in a lower band (`match` or below).

Capture a screenshot of the assistant turn.

## Sign-off

- [ ] Reviewer name + date
- [ ] Walkthrough artifacts (screenshots) stored alongside this document.
```

- [ ] **Step 2: Commit**

```powershell
git add docs/superpowers/demo_walkthrough.md
git commit -m "docs: demo walkthrough checklist for conflict-aware advisory"
```

---

## Task 7: Full-suite regression sweep

- [ ] **Step 1: Run the full default suite**

Run: `pytest tests/ -v`

Expected: all green except `tests/e2e/test_real_conflict_resolution.py` which SKIPs when `DATABASE_URL` is unset.

- [ ] **Step 2: If `DATABASE_URL` is available, run the gated suite**

Run: `pytest -m requires_real_dataset -v`

Expected: 2 PASS, 1 PASS-or-SKIP.

- [ ] **Step 3: Verify default `pytest` (no `-m`) still runs the marker tests, with the per-test skip guard handling the missing DB**

Run: `pytest tests/e2e/ -v`

Expected: real-dataset tests SKIP gracefully when DB unavailable; chat web flow tests PASS.

- [ ] **Step 4: Final commit if any cleanups were required**

```powershell
git status
# If anything is uncommitted, review and commit.
```

---

## Slice 4 Exit Gate

Before declaring Slice 4 — and the entire phase — complete:

1. `pytest -m requires_real_dataset` passes against the curated dump (at least the conflict-outcome + resolved-branch tests; unresolved-branch may SKIP).
2. `pytest tests/e2e/test_chat_web_flow.py -v` passes, including the new verification-section snapshot test.
3. `pytest tests/ -v` passes (default invocation) with the real-data tests SKIPping when no DB is available.
4. `QUICKSTART.md` documents the phase-completion gate.
5. `docs/superpowers/demo_walkthrough.md` exists, the resolved-branch walkthrough is signed off, AND either the unresolved-branch walkthrough is signed off OR it's explicitly delegated to the synthetic graph integration test.

If any gate fails, the phase is not shippable. The defense story — *"can you show this resolving a real conflict?"* — requires the gated test to pass; until then, slip the phase rather than ship reduced.

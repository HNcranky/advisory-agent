# Advisory Flow Reliability-First Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a policy-safe, citation-grounded advisory flow for A00/A01 CNTT-Kỹ thuật within a fixed top-10 Northern university boundary.

**Architecture:** Keep existing graph order (`profile -> retrieve -> reason -> policy -> explain`) and strengthen node contracts instead of changing orchestration. Add deterministic data contracts (top-10 boundary, evidence threshold, staleness and warning behavior) and minimal observability for audit/debug. Implement through TDD-first tasks with small commits.

**Tech Stack:** Python, Pydantic, LangGraph, pytest, PostgreSQL access layer (`ingestion.storage.db_connection`)

---

## File Structure Map

### Existing files to modify

- `agents/models.py`  
  Extend core payload models (`StudentProfile`, `Evidence`, `CandidateProgram`, `PolicyDecision`) with deterministic fields needed by spec contracts.
- `state.py`  
  Add state fields for completeness scoring, retrieval coverage, structured errors, and trace logs.
- `services/profile_service.py`  
  Extend profile extraction and completeness scoring.
- `services/retrieval_service.py`  
  Enforce top-10 + major boundary filtering and deterministic conflict markers.
- `services/reasoning_service.py`  
  Add reliability penalty rule with bounded scoring.
- `services/policy_service.py`  
  Enforce evidence threshold, warning priority/merge behavior, and policy snapshot fallback logic.
- `services/explanation_service.py`  
  Render structured warnings, follow-up prompts, and citation details.
- `ingestion/config/settings.py` (if needed by current config style)  
  Wire constants for staleness thresholds and fallback behavior.

### New files to create

- `ingestion/config/top10_northern_schools.json`  
  Source-of-truth allowlist (exactly 10 school IDs).
- `ingestion/config/policy_rules.py`  
  Central constants and helpers for staleness, warning severity, evidence threshold.
- `services/policy_snapshot_service.py`  
  Policy snapshot lookup contract (`school_id + year + version`) with unavailable/stale flags.
- `services/trace_service.py`  
  Minimal helper to append consistent per-step decision traces.

### Tests to create/modify

- Modify: `tests/agents/test_profile_agent.py`
- Modify: `tests/agents/test_reasoning_agent.py`
- Modify: `tests/agents/test_policy_agent.py`
- Modify: `tests/agents/test_explanation_agent.py`
- Modify: `tests/services/test_retrieval_service.py`
- Modify: `tests/e2e/test_advisory_flow.py`
- Create: `tests/services/test_policy_snapshot_service.py`
- Create: `tests/services/test_trace_service.py`

## Chunk 1: Contracts and Config Foundations

### Task 1: Add failing tests for model/state/config contracts

**Files:**
- Test: `tests/services/test_retrieval_service.py`
- Test: `tests/agents/test_policy_agent.py`
- Test: `tests/e2e/test_advisory_flow.py`

- [ ] **Step 1: Write failing tests for top-10 config + evidence contract**

```python
def test_retrieval_filters_out_non_top10_candidates():
    ...
    assert all(c.school_id in TOP10 for c in candidates)

def test_policy_requires_valid_citation_contract():
    ...
    assert "all_recommendations_blocked" in decision.policy_flags
```

- [ ] **Step 2: Run tests to verify failures**

Run: `pytest tests/services/test_retrieval_service.py tests/agents/test_policy_agent.py -v`  
Expected: FAIL with missing fields/rules/config assumptions.

- [ ] **Step 3: Add minimal config + model field implementation**

Implement:
- `ingestion/config/top10_northern_schools.json` with exactly 10 IDs
- `agents/models.py` fields:
  - `StudentProfile.profile_completeness_score: float | None`
  - `StudentProfile.career_orientation: Optional[str]`
  - `Evidence.source_type: Optional[str]`
  - `Evidence.record_freshness_days: Optional[int]`
  - `CandidateProgram.conflict_markers: List[str]`
  - `PolicyDecision.warnings` can carry structured warning payload (or add `warning_details`)

- [ ] **Step 4: Add state plumbing**

Update `state.py`:
- `profile_completeness_score`
- `retrieval_coverage`
- `structured_errors`
- `trace_log`

- [ ] **Step 5: Re-run focused tests**

Run: `pytest tests/services/test_retrieval_service.py tests/agents/test_policy_agent.py -v`  
Expected: PASS for new contract tests.

- [ ] **Step 6: Commit**

```bash
git add agents/models.py state.py ingestion/config/top10_northern_schools.json tests/services/test_retrieval_service.py tests/agents/test_policy_agent.py
git commit -m "feat: add advisory contract models and top10 config"
```

### Task 2: Add central policy constants and snapshot lookup service

**Files:**
- Create: `ingestion/config/policy_rules.py`
- Create: `services/policy_snapshot_service.py`
- Test: `tests/services/test_policy_snapshot_service.py`

- [ ] **Step 1: Write failing tests for snapshot unavailable/stale behavior**

```python
def test_policy_snapshot_service_marks_unavailable():
    snap = get_policy_snapshot("hust", 2026)
    assert snap.status == "unavailable"

def test_policy_snapshot_service_marks_stale_when_over_threshold():
    assert snap.policy_snapshot_age_days > MAX_POLICY_AGE_DAYS
```

- [ ] **Step 2: Run tests to verify failures**

Run: `pytest tests/services/test_policy_snapshot_service.py -v`  
Expected: FAIL (module/function not found).

- [ ] **Step 3: Implement minimal constants and service**

Implement in `ingestion/config/policy_rules.py`:
- `MAX_POLICY_AGE_DAYS = 45`
- `MAX_RECORD_AGE_DAYS = 45`
- warning severity ordering and dedupe helpers

Implement in `services/policy_snapshot_service.py`:
- `get_policy_snapshot(school_id: str, admission_year: int) -> PolicySnapshotResult`
- deterministic statuses: `ok | stale | unavailable`

- [ ] **Step 4: Re-run tests**

Run: `pytest tests/services/test_policy_snapshot_service.py -v`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ingestion/config/policy_rules.py services/policy_snapshot_service.py tests/services/test_policy_snapshot_service.py
git commit -m "feat: add policy snapshot contract service"
```

## Chunk 2: Service/Agent Behavior Upgrades

### Task 3: Upgrade profile extraction with completeness scoring

**Files:**
- Modify: `services/profile_service.py`
- Modify: `agents/profile_agent.py`
- Test: `tests/agents/test_profile_agent.py`

- [ ] **Step 1: Write failing tests for completeness score and critical slots**

```python
def test_profile_agent_sets_completeness_score():
    out = profile_agent(state)
    assert 0 <= out.student_profile.profile_completeness_score <= 1
    assert "career_orientation" in out.student_profile.missing_slots
```

- [ ] **Step 2: Run test to verify failure**

Run: `pytest tests/agents/test_profile_agent.py -v`  
Expected: FAIL for missing score/field.

- [ ] **Step 3: Implement minimal profile scoring**

Rules:
- critical slots = `total_score`, `subject_combination`, `preferred_majors`, `career_orientation`
- completeness = `filled_critical / 4` rounded to 2 decimals

- [ ] **Step 4: Re-run test**

Run: `pytest tests/agents/test_profile_agent.py -v`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add services/profile_service.py agents/profile_agent.py tests/agents/test_profile_agent.py
git commit -m "feat: add profile completeness scoring"
```

### Task 4: Enforce retrieval boundary and conflict marker schema

**Files:**
- Modify: `services/retrieval_service.py`
- Test: `tests/services/test_retrieval_service.py`

- [ ] **Step 1: Write failing tests for top10 and major allowlist filtering**

```python
def test_fetch_candidates_applies_major_allowlist():
    ...
    assert all(c.program_id in MAJOR_ALLOWLIST for c in candidates)
```

- [ ] **Step 2: Write failing test for conflict marker enum**

```python
def test_detect_conflicts_returns_enum_markers():
    markers = detect_conflicts(candidates)
    assert "quota_conflict" in markers_by_candidate["..."]
```

- [ ] **Step 3: Run tests to verify failures**

Run: `pytest tests/services/test_retrieval_service.py -v`  
Expected: FAIL on missing filters/marker structure.

- [ ] **Step 4: Implement minimal retrieval changes**

Implement:
- top10 allowlist loading + startup validation helper
- deterministic major allowlist filter for sprint IDs
- `detect_conflicts` returns enum markers (`quota_conflict`, `subject_combination_conflict`, etc.)

- [ ] **Step 5: Re-run tests**

Run: `pytest tests/services/test_retrieval_service.py -v`  
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add services/retrieval_service.py tests/services/test_retrieval_service.py
git commit -m "feat: enforce retrieval boundaries and conflict markers"
```

### Task 5: Apply reasoning penalty formula and bounded score

**Files:**
- Modify: `services/reasoning_service.py`
- Test: `tests/agents/test_reasoning_agent.py`

- [ ] **Step 1: Write failing tests for reliability penalties**

```python
def test_reasoning_applies_conflict_and_staleness_penalties():
    rec = reasoning_agent(state).ranked_recommendations[0]
    assert rec.score == 0.75
```

- [ ] **Step 2: Run test to verify failure**

Run: `pytest tests/agents/test_reasoning_agent.py -v`  
Expected: FAIL.

- [ ] **Step 3: Implement penalty formula**

Rules:
- `-0.10` conflict marker present
- `-0.05` best citation trust_level == 3
- `-0.10` best citation record_freshness_days > 45
- clamp `[0, 1]`

- [ ] **Step 4: Re-run test**

Run: `pytest tests/agents/test_reasoning_agent.py -v`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add services/reasoning_service.py tests/agents/test_reasoning_agent.py
git commit -m "feat: add reliability-aware reasoning penalties"
```

### Task 6: Enforce policy decision contract and warning precedence

**Files:**
- Modify: `services/policy_service.py`
- Modify: `agents/policy_agent.py`
- Test: `tests/agents/test_policy_agent.py`

- [ ] **Step 1: Write failing tests for warning merge/priority and fail-closed cases**

```python
def test_policy_warning_priority_high_to_low():
    assert [w["severity"] for w in decision.warning_details] == ["high", "medium", "low"]

def test_policy_fails_closed_when_top10_config_invalid():
    assert decision.policy_flags == ["top10_config_invalid"]
```

- [ ] **Step 2: Run test to verify failure**

Run: `pytest tests/agents/test_policy_agent.py -v`  
Expected: FAIL.

- [ ] **Step 3: Implement policy rules**

Implement:
- valid citation gate (source_url + source_type + trust_level>=3)
- policy snapshot unavailable/stale warnings
- deterministic warning dedupe/sort by severity
- `requires_follow_up=True` whenever critical slots missing

- [ ] **Step 4: Re-run tests**

Run: `pytest tests/agents/test_policy_agent.py -v`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add services/policy_service.py agents/policy_agent.py tests/agents/test_policy_agent.py
git commit -m "feat: harden policy guardrails and warning contracts"
```

## Chunk 3: Output, Observability, and End-to-End Verification

### Task 7: Improve explanation rendering and structured error output

**Files:**
- Modify: `services/explanation_service.py`
- Modify: `agents/explanation_agent.py`
- Test: `tests/agents/test_explanation_agent.py`

- [ ] **Step 1: Write failing tests for structured warning + follow-up sections**

```python
def test_explanation_renders_structured_warnings_and_followups():
    answer = explanation_agent(state).final_answer
    assert "Canh bao" in answer
    assert "Thong tin can bo sung" in answer
```

- [ ] **Step 2: Run test to verify failure**

Run: `pytest tests/agents/test_explanation_agent.py -v`  
Expected: FAIL.

- [ ] **Step 3: Implement minimal explanation changes**

Implement:
- warning block from structured warning payload
- citation list including source type/trust level when available
- explicit follow-up prompts tied to `missing_critical_slots`
- structured error rendering when `structured_errors` present

- [ ] **Step 4: Re-run test**

Run: `pytest tests/agents/test_explanation_agent.py -v`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add services/explanation_service.py agents/explanation_agent.py tests/agents/test_explanation_agent.py
git commit -m "feat: improve advisory explanation clarity and safety messaging"
```

### Task 8: Add minimal trace logging helper and integration wiring

**Files:**
- Create: `services/trace_service.py`
- Modify: `agents/profile_agent.py`
- Modify: `agents/retrieval_agent.py`
- Modify: `agents/reasoning_agent.py`
- Modify: `agents/policy_agent.py`
- Modify: `agents/explanation_agent.py`
- Test: `tests/services/test_trace_service.py`

- [ ] **Step 1: Write failing test for trace append behavior**

```python
def test_append_trace_step_adds_timestamped_entry():
    state = append_trace_step(state, "policy", {"flags": ["missing_critical_profile"]})
    assert state.trace_log[-1]["step"] == "policy"
```

- [ ] **Step 2: Run test to verify failure**

Run: `pytest tests/services/test_trace_service.py -v`  
Expected: FAIL.

- [ ] **Step 3: Implement trace helper and wire each agent**

Implement:
- one append helper with stable event shape
- each agent appends one concise step summary

- [ ] **Step 4: Re-run test**

Run: `pytest tests/services/test_trace_service.py -v`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add services/trace_service.py agents/profile_agent.py agents/retrieval_agent.py agents/reasoning_agent.py agents/policy_agent.py agents/explanation_agent.py tests/services/test_trace_service.py
git commit -m "feat: add minimal advisory decision trace logging"
```

### Task 9: End-to-end regression and final verification

**Files:**
- Modify: `tests/e2e/test_advisory_flow.py`
- Modify (if needed): `tests/fixtures/advisory_queries.json`

- [ ] **Step 1: Add failing e2e tests for new acceptance criteria**

```python
def test_e2e_always_returns_warning_when_profile_critical_missing():
    ...

def test_e2e_never_recommends_outside_top10():
    ...
```

- [ ] **Step 2: Run e2e tests to verify failure**

Run: `pytest tests/e2e/test_advisory_flow.py -v`  
Expected: FAIL before implementation wiring is complete.

- [ ] **Step 3: Make minimal fixes to pass e2e**

Only patch behavior gaps found by e2e failures; avoid scope creep.

- [ ] **Step 4: Run full test suite**

Run: `pytest -v`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/e2e/test_advisory_flow.py tests/fixtures/advisory_queries.json
git commit -m "test: add reliability-first advisory e2e coverage"
```

### Task 10: Final docs sync

**Files:**
- Modify: `README.md` (only sections that describe advisory behavior/contracts)

- [ ] **Step 1: Add failing docs-check expectation (manual)**

Checklist:
- top10 boundary documented
- citation validity rule documented
- warning precedence documented

- [ ] **Step 2: Update README minimally**

Add concise “Reliability-first advisory constraints” section.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: document advisory reliability contracts"
```


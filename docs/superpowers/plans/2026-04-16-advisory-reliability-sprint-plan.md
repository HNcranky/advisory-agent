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
- Modify: `agents/models.py`
- Modify: `state.py`
- Create: `ingestion/config/top10_northern_schools.json`
- Modify: `agents/profile_agent.py`
- Modify: `agents/retrieval_agent.py`
- Modify: `agents/policy_agent.py`
- Modify: `agents/explanation_agent.py`
- Test: `tests/services/test_retrieval_service.py`
- Test: `tests/agents/test_policy_agent.py`

- [ ] **Step 1: Write failing tests for top-10 config + evidence contract**

```python
def test_retrieval_filters_out_non_top10_candidates():
    filters = {"admission_year": 2026, "preferred_majors": [], "preferred_schools": []}
    candidates = fetch_candidates(filters)
    assert all(c.school_id in TOP10 for c in candidates)

def test_policy_requires_valid_citation_contract():
    state = AgentState(user_query="Tu van")
    state.ranked_recommendations = [RankedRecommendation(candidate_id="x", band="match", score=0.7, summary="x")]
    state.retrieved_programs = [CandidateProgram(candidate_id="x", school_id="hust", school_name="HUST", admission_year=2026, program_name="CS", evidence=[])]
    decision, kept = evaluate_policy_guardrails(state.user_query, state.student_profile, state.retrieved_programs, state.ranked_recommendations, [])
    assert "all_recommendations_blocked" in decision.policy_flags
    assert kept == []

def test_policy_rejects_citation_when_source_type_missing_or_trust_low():
    bad_evidence = Evidence(source_url="https://x", source_type=None, trust_level=2)
    candidate = CandidateProgram(candidate_id="x", school_id="hust", school_name="HUST", admission_year=2026, program_name="CS", evidence=[bad_evidence])
    rec = RankedRecommendation(candidate_id="x", band="match", score=0.6, summary="x")
    decision, kept = evaluate_policy_guardrails("Tu van", StudentProfile(), [candidate], [rec], [])
    assert "all_recommendations_blocked" in decision.policy_flags
    assert kept == []

def test_policy_rejects_citation_when_source_url_empty():
    bad_evidence = Evidence(source_url="", source_type="official_school_site", trust_level=5)
    candidate = CandidateProgram(candidate_id="x", school_id="hust", school_name="HUST", admission_year=2026, program_name="CS", evidence=[bad_evidence])
    rec = RankedRecommendation(candidate_id="x", band="match", score=0.6, summary="x")
    decision, kept = evaluate_policy_guardrails("Tu van", StudentProfile(), [candidate], [rec], [])
    assert "all_recommendations_blocked" in decision.policy_flags
    assert kept == []

def test_retrieval_emits_top10_config_invalid_when_allowlist_broken():
    with pytest.raises(ValueError, match="top10_config_invalid"):
        load_top10_school_ids(config_path="tests/fixtures/bad_top10.json")

def test_top10_allowlist_requires_exactly_10_unique_school_ids():
    with pytest.raises(ValueError, match="top10_config_invalid"):
        load_top10_school_ids(config_path="tests/fixtures/top10_duplicate_ids.json")

def test_policy_warnings_follow_structured_schema():
    decision, _ = evaluate_policy_guardrails(
        user_query="Tu van",
        profile=StudentProfile(missing_slots=["total_score"]),
        candidates=[],
        recommendations=[],
        conflicts=[]
    )
    first = decision.warnings[0]
    assert set(first.keys()) >= {"code", "severity", "message"}

def test_conflict_markers_follow_enum_contract():
    markers = detect_conflicts([...])
    allowed = {"quota_conflict", "subject_combination_conflict", "method_conflict", "program_name_conflict", "policy_snapshot_conflict"}
    assert set(markers).issubset(allowed)
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
  - `Evidence.published_at: Optional[str]`
  - `Evidence.record_freshness_days: Optional[int]`
  - `CandidateProgram.conflict_markers: List[str]`
  - `PolicyDecision.warnings: List[Dict[str, str]]` (single canonical structured warning payload)

- [ ] **Step 4: Add state plumbing**

Update `state.py`:
- `profile_completeness_score: Optional[float] = None`
- `retrieval_coverage: Dict[str, int] = Field(default_factory=dict)`
- `structured_errors: List[Dict[str, Any]] = Field(default_factory=list)`
- `trace_log: List[Dict[str, Any]] = Field(default_factory=list)`

Update agent nodes:
- `agents/profile_agent.py` writes `profile_completeness_score`
- `agents/retrieval_agent.py` writes `retrieval_coverage`
- `agents/retrieval_agent.py` writes `retrieval_missing_data` reasons for empty/no-match cases
- `agents/policy_agent.py` writes structured policy warnings/errors
- `agents/explanation_agent.py` reads `structured_errors` for final rendering path

- [ ] **Step 5: Re-run focused tests**

Run: `pytest tests/services/test_retrieval_service.py tests/agents/test_policy_agent.py -v`  
Expected: PASS for new contract tests.

- [ ] **Step 6: Add explicit startup fail-closed coverage test**

```python
def test_service_enters_fail_closed_mode_when_top10_invalid():
    state = AgentState(user_query="Tu van")
    out = retrieval_agent(state)
    assert out.structured_errors[0]["error_code"] == "top10_config_invalid"
    assert out.structured_errors[0]["retryable"] is False
```

Run: `pytest tests/services/test_retrieval_service.py::test_service_enters_fail_closed_mode_when_top10_invalid -v`  
Expected: PASS.

- [ ] **Step 7: Add version-bump invariant test for top10 edits**

```python
def test_top10_config_change_requires_policy_version_bump():
    assert validate_top10_change_requires_policy_bump(old_config, new_config, old_policy_version, new_policy_version) is True
```

Run: `pytest tests/services/test_retrieval_service.py::test_top10_config_change_requires_policy_version_bump -v`  
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add agents/models.py state.py ingestion/config/top10_northern_schools.json agents/profile_agent.py agents/retrieval_agent.py agents/policy_agent.py agents/explanation_agent.py tests/services/test_retrieval_service.py tests/agents/test_policy_agent.py
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
    snap = get_policy_snapshot("hust", 2026, policy_version="2026.v1")
    assert snap.status == "unavailable"

def test_policy_snapshot_service_marks_stale_when_over_threshold():
    snap = get_policy_snapshot("hust", 2026, policy_version="2026.v1")
    assert snap.status == "stale"
    assert snap.policy_snapshot_age_days > MAX_POLICY_AGE_DAYS

def test_policy_snapshot_service_keys_by_policy_version():
    snap_v1 = get_policy_snapshot("hust", 2026, policy_version="2026.v1")
    snap_v2 = get_policy_snapshot("hust", 2026, policy_version="2026.v2")
    assert snap_v1.policy_version != snap_v2.policy_version

def test_warning_dedupe_and_severity_ordering():
    warnings = sort_and_dedupe_warnings([
        {"code": "w1", "severity": "low", "message": "a"},
        {"code": "w1", "severity": "low", "message": "a"},
        {"code": "w2", "severity": "high", "message": "b"},
    ])
    assert [w["code"] for w in warnings] == ["w2", "w1"]
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
- `get_policy_snapshot(school_id: str, admission_year: int, policy_version: str | None = None) -> PolicySnapshotResult`
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
- Modify: `agents/models.py`
- Modify: `state.py`
- Modify: `services/profile_service.py`
- Modify: `agents/profile_agent.py`
- Test: `tests/agents/test_profile_agent.py`

- [ ] **Step 1: Write failing tests for completeness score and critical slots**

```python
def test_profile_agent_sets_completeness_score():
    out = profile_agent(state)
    assert 0 <= out.student_profile.profile_completeness_score <= 1
    assert "career_orientation" in out.student_profile.missing_critical_slots
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
- Modify: `agents/retrieval_agent.py`
- Modify: `state.py`
- Test: `tests/services/test_retrieval_service.py`

- [ ] **Step 1: Write failing tests for top10 and major allowlist filtering**

```python
def test_fetch_candidates_applies_major_allowlist():
    filters = {"admission_year": 2026, "preferred_majors": ["computer_science"], "preferred_schools": []}
    candidates = fetch_candidates(filters)
    assert all(c.program_id in MAJOR_ALLOWLIST for c in candidates)

def test_fetch_candidates_applies_admission_year_filter():
    filters = {"admission_year": 2026, "preferred_majors": [], "preferred_schools": []}
    candidates = fetch_candidates(filters)
    assert all(c.admission_year == 2026 for c in candidates)

def test_fetch_candidates_applies_top10_boundary():
    filters = {"admission_year": 2026, "preferred_majors": [], "preferred_schools": []}
    candidates = fetch_candidates(filters)
    assert all(c.school_id in TOP10_SCHOOL_IDS for c in candidates)

def test_retrieval_agent_sets_coverage_and_missing_data_on_empty_result(monkeypatch):
    state = AgentState(user_query="A00 CNTT", admission_year=2026)
    with monkeypatch.context() as m:
        m.setattr("agents.retrieval_agent.fetch_candidates", lambda filters, limit=100: [])
        out = retrieval_agent(state)
    assert out.retrieval_coverage.get("matched_candidates", -1) == 0
    assert len(out.retrieval_missing_data) > 0

def test_retrieval_returns_invalid_admission_year_error_schema():
    state = AgentState(user_query="A00 CNTT", admission_year=1900)
    out = retrieval_agent(state)
    err = out.structured_errors[0]
    assert err["error_code"] == "invalid_admission_year"
    assert set(err.keys()) >= {"error_code", "severity", "message", "action_required", "retryable"}
```

- [ ] **Step 2: Write failing test for conflict marker enum**

```python
def test_detect_conflicts_returns_enum_markers():
    markers = detect_conflicts([
        make_candidate(candidate_id="hust:2026:cs:thpt", quota={"total": 300}, subject_combinations=["A00"]),
        make_candidate(candidate_id="hust:2026:cs:thpt", quota={"total": 250}, subject_combinations=["A00"]),
    ])
    assert "quota_conflict" in markers
```

- [ ] **Step 3: Run tests to verify failures**

Run: `pytest tests/services/test_retrieval_service.py -v`  
Expected: FAIL on missing filters/marker structure.

- [ ] **Step 4: Implement minimal retrieval changes**

Implement:
- deterministic major allowlist filter for sprint IDs
- strict admission_year filter assertion path
- enforce exact CNTT-Kỹ thuật IDs:
  - `computer_science`
  - `software_engineering`
  - `information_systems`
  - `computer_engineering`
  - `artificial_intelligence`
  - `data_science`
  - `cyber_security`
- ensure retrieval owns normalized `candidate.evidence[]` population from canonical records
- `detect_conflicts` returns enum markers:
  - `quota_conflict`
  - `subject_combination_conflict`
  - `method_conflict`
  - `program_name_conflict`
  - `policy_snapshot_conflict`

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
    state = build_reasoning_state(base_score_profile=True, with_conflict=True, trust_level=3, freshness_days=50)
    rec = reasoning_agent(state).ranked_recommendations[0]
    assert 0 <= rec.score <= 1
    assert rec.score < 1.0
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
    decision, _ = evaluate_policy_guardrails("Tu van", StudentProfile(), [], [], [])
    assert [w["severity"] for w in decision.warnings] == ["high", "medium", "low"]

def test_policy_fails_closed_when_top10_config_invalid():
    decision, _ = evaluate_policy_guardrails("Tu van", StudentProfile(), [], [], ["top10_config_invalid"])
    assert decision.policy_flags == ["top10_config_invalid"]

def test_policy_payload_contains_blocked_claims_and_allowed_candidate_ids():
    decision, kept = evaluate_policy_guardrails(
        user_query="Em co chac do khong",
        profile=StudentProfile(total_score=27, subject_combination="A00", preferred_majors=["computer_science"]),
        candidates=[candidate_with_valid_evidence],
        recommendations=[recommendation_for_candidate],
        conflicts=[]
    )
    assert isinstance(decision.blocked_claims, list)
    assert isinstance(decision.allowed_candidate_ids, list)
    assert all(rec.candidate_id in decision.allowed_candidate_ids for rec in kept)

def test_policy_blocks_definitive_claim_prompt():
    decision, _ = evaluate_policy_guardrails(
        user_query="Em co chac chan do khong?",
        profile=StudentProfile(total_score=27, subject_combination="A00", preferred_majors=["computer_science"]),
        candidates=[candidate_with_valid_evidence],
        recommendations=[recommendation_for_candidate],
        conflicts=[]
    )
    assert "no_definitive_admission_answer" in decision.blocked_claims

def test_policy_payload_schema_and_snapshot_warnings():
    decision, _ = evaluate_policy_guardrails(
        user_query="Tu van",
        profile=StudentProfile(total_score=27, subject_combination="A00", preferred_majors=["computer_science"]),
        candidates=[candidate_with_stale_evidence],
        recommendations=[recommendation_for_candidate],
        conflicts=[]
    )
    assert isinstance(decision.allow_answer, bool)
    assert any(w["code"] == "policy_snapshot_unavailable" for w in decision.warnings) or any(
        w["code"] == "stale_policy_snapshot" for w in decision.warnings
    )
    assert any("stale" in flag for flag in decision.policy_flags)
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
- keep `PolicyDecision.warnings` as structured objects (`code`, `severity`, `message`) per spec payload

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
    state = AgentState(user_query="Tu van")
    state.policy_decision = PolicyDecision(
        warnings=[{"code": "missing_critical_profile", "severity": "high", "message": "Need more profile data"}],
        requires_follow_up=True,
    )
    answer = explanation_agent(state).final_answer
    assert "Canh bao" in answer
    assert "Thong tin can bo sung" in answer

def test_explanation_renders_structured_errors_and_citation_fields():
    state = AgentState(user_query="Tu van", admission_year=1900)
    state.structured_errors = [{
        "error_code": "invalid_admission_year",
        "severity": "high",
        "message": "Admission year is missing or invalid.",
        "action_required": "Provide a valid admission year.",
        "retryable": True,
    }]
    state.policy_decision = PolicyDecision(warnings=[], requires_follow_up=False)
    answer = explanation_agent(state).final_answer
    assert "invalid_admission_year" in answer
    assert "Provide a valid admission year." in answer
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
    state = AgentState(user_query="Tu van")
    state = append_trace_step(state, "policy", {"flags": ["missing_critical_profile"]})
    assert state.trace_log[-1]["step"] == "policy"
    assert "timestamp" in state.trace_log[-1]
    assert "payload" in state.trace_log[-1]

def test_all_agents_emit_required_trace_payload_fields():
    state = AgentState(user_query="Em duoc 27 diem A00 muon hoc CNTT", admission_year=2026)
    result = graph.invoke(state)
    steps = {entry["step"]: entry["payload"] for entry in result["trace_log"]}
    assert {"profile", "retrieve", "reason", "policy", "explain"}.issubset(set(steps.keys()))
```

- [ ] **Step 2: Run test to verify failure**

Run: `pytest tests/services/test_trace_service.py -v`  
Expected: FAIL.

- [ ] **Step 3: Implement trace helper and wire each agent**

Implement:
- one append helper with stable event shape:
  - `timestamp`
  - `step` (`profile|retrieve|reason|policy|explain`)
  - `summary`
  - `payload`
- required payloads by step:
  - `profile`: extracted slots + `profile_completeness_score`
  - `retrieve`: filters + `retrieval_coverage` + `retrieval_missing_data`
  - `reason`: eligibility summary + score band distribution
  - `policy`: `policy_flags` + kept/blocked candidate IDs
  - `explain`: citation count + warning count + follow-up-required flag
- store in `state.trace_log` as audit/debug source of truth for this sprint

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
    state = AgentState(user_query="Tu van nganh CNTT", admission_year=2026)
    result = graph.invoke(state)
    assert result["policy_decision"].requires_follow_up is True
    assert "Thong tin can bo sung" in result["final_answer"]

def test_e2e_never_recommends_outside_top10():
    result = graph.invoke(AgentState(user_query="Em duoc 27 diem A00 muon hoc CNTT", admission_year=2026))
    assert all(c.school_id in TOP10_SCHOOL_IDS for c in result["retrieved_programs"])

def test_e2e_adds_warning_for_stale_or_conflicting_data():
    result = graph.invoke(AgentState(user_query="Em duoc 27 diem A00 muon hoc CNTT", admission_year=2026))
    assert any(
        "stale" in w.get("code", "") or "conflict" in w.get("code", "")
        for w in result["policy_decision"].warnings
    )

def test_e2e_blocks_definitive_claims():
    result = graph.invoke(AgentState(user_query="Em co chac chan do khong?", admission_year=2026))
    assert "no_definitive_admission_answer" in result["policy_decision"].blocked_claims

def test_e2e_policy_snapshot_unavailable_keeps_conservative_output():
    result = graph.invoke(AgentState(user_query="Tu van CNTT", admission_year=2026))
    assert any(w.get("code") == "policy_snapshot_unavailable" for w in result["policy_decision"].warnings)
    assert result["final_answer"]

def test_e2e_kept_recommendations_have_valid_citations():
    result = graph.invoke(AgentState(user_query="Em duoc 27 diem A00 muon hoc CNTT", admission_year=2026))
    allowed = set(result["policy_decision"].allowed_candidate_ids)
    candidate_map = {c.candidate_id: c for c in result["retrieved_programs"]}
    for candidate_id in allowed:
        evs = candidate_map[candidate_id].evidence
        assert any(
            ev.source_url and ev.source_type and (ev.trust_level or 0) >= 3
            for ev in evs
        )

def test_e2e_warnings_are_deduped_and_sorted_by_severity():
    result = graph.invoke(AgentState(user_query="Tu van", admission_year=2026))
    severities = [w.get("severity") for w in result["policy_decision"].warnings]
    order = {"high": 0, "medium": 1, "low": 2}
    assert severities == sorted(severities, key=lambda s: order.get(s, 99))
    codes = [w.get("code") for w in result["policy_decision"].warnings]
    assert len(codes) == len(set(codes))

def test_e2e_invalid_admission_year_returns_structured_error():
    result = graph.invoke(AgentState(user_query="Tu van CNTT", admission_year=1900))
    err = result["structured_errors"][0]
    assert err["error_code"] == "invalid_admission_year"
    assert set(err.keys()) >= {"error_code", "severity", "message", "action_required", "retryable"}
```

- [ ] **Step 2: Run e2e tests to verify failure**

Run: `pytest tests/e2e/test_advisory_flow.py -v`  
Expected: FAIL before implementation wiring is complete.

- [ ] **Step 3: Make minimal fixes to pass e2e**

Patch only these targets:
- `services/policy_service.py` for warning/guardrail contract failures
- `services/retrieval_service.py` for top10 and stale/conflict propagation failures
- `services/explanation_service.py` for follow-up/warning rendering failures

Expected after patch:
- each new e2e test has deterministic pass/fail condition matching spec acceptance criteria
- no change to graph topology or unrelated ingestion pipeline behavior

- [ ] **Step 4: Run full test suite**

Run: `pytest -v`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/e2e/test_advisory_flow.py tests/fixtures/advisory_queries.json services/policy_service.py services/retrieval_service.py services/explanation_service.py
git commit -m "test: add reliability-first advisory e2e coverage"
```

### Task 10: Final docs sync

**Files:**
- Modify: `README.md` (only sections that describe advisory behavior/contracts)

- [ ] **Step 1: Add deterministic docs checklist gate**

Create a checklist block in PR/commit notes and verify README contains all 3 exact headings:
- `Reliability-first advisory constraints`
- `Citation validity rule`
- `Warning precedence`

Run: `python -c "from pathlib import Path; t=Path('README.md').read_text(encoding='utf-8'); req=['Reliability-first advisory constraints','Citation validity rule','Warning precedence']; print('PASS' if all(x in t for x in req) else 'FAIL')"`  
Expected: FAIL (before Step 2 updates README)

- [ ] **Step 2: Update README minimally**

Add concise “Reliability-first advisory constraints” section.

Run: `python -c "from pathlib import Path; t=Path('README.md').read_text(encoding='utf-8'); req=['Reliability-first advisory constraints','Citation validity rule','Warning precedence']; print('PASS' if all(x in t for x in req) else 'FAIL')"`  
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: document advisory reliability contracts"
```


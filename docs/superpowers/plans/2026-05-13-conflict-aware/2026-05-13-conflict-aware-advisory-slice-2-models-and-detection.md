# Slice 2 — Conflict data model + detection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce the structured conflict data model (`ConflictRecord`, `EvidenceOption`, `ComparisonReport`, `ResolutionOutcome`), the new state fields, and the deterministic detection function that promotes flat-string conflicts to structured records — without yet wiring anything into the advisory graph.

**Architecture:** Add a new package `services/conflict/` with `models.py` (pydantic types) and `detection.py` (`detect_quota_conflicts(candidates) -> List[ConflictRecord]`). Extend `state.AgentState` with `conflict_records` and `resolution_outcomes` fields, and `agents.models.CandidateProgram` with `data_uncertain_fields`. Remove the call to `detect_conflicts` from `retrieval_agent` — in this slice, conflicts simply aren't surfaced. The existing `services/retrieval_service.detect_conflicts` function stays in the file (the conflict_agent stub still imports it) but becomes unused by the graph; it will die in Slice 3.

**Tech Stack:** Python 3.11+, pydantic v1/v2 (match existing usage in `agents/models.py`), pytest.

---

## File Structure

- Create: `services/conflict/__init__.py` — empty package marker.
- Create: `services/conflict/models.py` — pydantic models for the conflict layer.
- Create: `services/conflict/detection.py` — `detect_quota_conflicts` and `_normalize_quota_value`.
- Modify: `state.py` — add `conflict_records`, `resolution_outcomes` fields.
- Modify: `agents/models.py` — add `data_uncertain_fields` to `CandidateProgram`.
- Modify: `agents/retrieval_agent.py` — stop calling `detect_conflicts`; leave the import behind for now (Slice 3 will remove it cleanly when the function is repurposed).
- Modify: `agents/conflict_agent.py` — leave as a stub for this slice. It currently imports `detect_conflicts` from `services.retrieval_service`; the stub is not in the graph and need not be touched until Slice 3.
- Create: `tests/services/conflict/__init__.py`
- Create: `tests/services/conflict/test_models.py`
- Create: `tests/services/conflict/test_detection.py`
- Modify: `tests/e2e/test_advisory_flow.py` — the existing fixture patches `retrieval_agent.detect_conflicts`; verify the patch still applies (it should, since the import stays).

Single responsibility per file: models are pure data; detection is one function with one helper; nothing else gets touched.

---

## Task 1: Pydantic models for the conflict layer

**Files:**
- Create: `services/conflict/__init__.py`
- Create: `services/conflict/models.py`
- Create: `tests/services/conflict/__init__.py`
- Create: `tests/services/conflict/test_models.py`

- [ ] **Step 1: Confirm pydantic version**

Run: `Grep` for `from pydantic` in `agents/models.py` and `state.py`. Confirm whether the codebase uses pydantic v1 syntax (`Field(default_factory=...)`) or pydantic v2. The plan code below uses syntax compatible with both for the most part; if v2-specific changes are needed (e.g., `model_config`), apply the existing project's pattern.

- [ ] **Step 2: Write the failing test for model shape**

Create `tests/services/conflict/__init__.py` as an empty file.

Create `tests/services/conflict/test_models.py`:

```python
from datetime import datetime

from services.conflict.models import (
    ComparisonReport,
    ConflictRecord,
    EvidenceOption,
    ResolutionOutcome,
)


def _option(value=100, trust=2, url="https://a.example/"):
    return EvidenceOption(
        evidence_id=f"{url}|quota",
        source_url=url,
        trust_level=trust,
        fetched_at=datetime(2026, 1, 1),
        confidence_score=0.9,
        value=value,
    )


def test_evidence_option_minimal_construction():
    opt = EvidenceOption(evidence_id="x|quota", source_url="https://x/", value=100)
    assert opt.trust_level is None
    assert opt.fetched_at is None
    assert opt.confidence_score is None


def test_conflict_record_carries_options():
    record = ConflictRecord(
        conflict_key="hust:2026:cs:thpt_score",
        field_name="quota",
        school_id="hust",
        school_name="HUST",
        program_name="CS",
        admission_method="thpt_score",
        options=[_option(100), _option(200, url="https://b.example/")],
    )
    assert len(record.options) == 2
    assert record.field_name == "quota"


def test_comparison_report_defaults():
    options = [_option(100), _option(200)]
    report = ComparisonReport(
        ranked_options=options, is_decisive=True, decision_axes=["trust_level"]
    )
    assert report.is_decisive is True
    assert report.decision_axes == ["trust_level"]


def test_resolution_outcome_resolved_shape():
    chosen = _option(100)
    outcome = ResolutionOutcome(
        status="resolved",
        resolved_value=100,
        chosen_evidence=chosen,
        rejected_evidence=[_option(200, url="https://b.example/")],
        rationale="trust_level dominated",
    )
    assert outcome.status == "resolved"
    assert outcome.resolved_value == 100
    assert outcome.uncertainty_reason is None


def test_resolution_outcome_unresolved_shape():
    outcome = ResolutionOutcome(
        status="unresolved",
        resolved_value=None,
        chosen_evidence=None,
        rejected_evidence=[],
        rationale="indecisive",
        uncertainty_reason="conflict_unresolved_quota",
    )
    assert outcome.status == "unresolved"
    assert outcome.chosen_evidence is None
    assert outcome.uncertainty_reason == "conflict_unresolved_quota"
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `pytest tests/services/conflict/test_models.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'services.conflict'`.

- [ ] **Step 4: Implement the models**

Create `services/conflict/__init__.py` as an empty file.

Create `services/conflict/models.py`:

```python
from datetime import datetime
from typing import Any, List, Literal, Optional

from pydantic import BaseModel, Field


class EvidenceOption(BaseModel):
    evidence_id: str
    source_url: str
    trust_level: Optional[int] = None
    fetched_at: Optional[datetime] = None
    confidence_score: Optional[float] = None
    value: Any = None
    # Provenance enrichment added by the Evidence agent (Slice 3); optional here.
    is_official: Optional[bool] = None
    parser_profile: Optional[str] = None


class ConflictRecord(BaseModel):
    conflict_key: str
    field_name: str
    school_id: str
    school_name: str
    program_name: str
    admission_method: Optional[str] = None
    options: List[EvidenceOption] = Field(default_factory=list)


class ComparisonReport(BaseModel):
    ranked_options: List[EvidenceOption] = Field(default_factory=list)
    is_decisive: bool = False
    decision_axes: List[str] = Field(default_factory=list)


class ResolutionOutcome(BaseModel):
    status: Literal["resolved", "unresolved"]
    resolved_value: Optional[Any] = None
    chosen_evidence: Optional[EvidenceOption] = None
    rejected_evidence: List[EvidenceOption] = Field(default_factory=list)
    rationale: str = ""
    uncertainty_reason: Optional[str] = None
    # Carries the originating conflict_key so downstream agents can correlate
    # an outcome back to candidates without re-deriving the key.
    conflict_key: Optional[str] = None
    field_name: Optional[str] = None
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `pytest tests/services/conflict/test_models.py -v`

Expected: all 5 tests PASS.

- [ ] **Step 6: Commit**

```powershell
git add services/conflict/__init__.py services/conflict/models.py tests/services/conflict/__init__.py tests/services/conflict/test_models.py
git commit -m "feat(conflict): add structured conflict data models"
```

---

## Task 2: State and CandidateProgram fields

**Files:**
- Modify: `state.py` (add `conflict_records` and `resolution_outcomes` fields).
- Modify: `agents/models.py` (add `data_uncertain_fields` to `CandidateProgram`).
- Create: `tests/test_state_extensions.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_state_extensions.py`:

```python
from agents.models import CandidateProgram
from services.conflict.models import ConflictRecord, EvidenceOption, ResolutionOutcome
from state import AgentState


def test_agent_state_has_conflict_fields_default_empty():
    state = AgentState(user_query="test")
    assert state.conflict_records == []
    assert state.resolution_outcomes == []


def test_agent_state_accepts_conflict_records():
    record = ConflictRecord(
        conflict_key="k", field_name="quota",
        school_id="s", school_name="S", program_name="P",
        options=[EvidenceOption(evidence_id="e", source_url="u", value=1)],
    )
    state = AgentState(user_query="test", conflict_records=[record])
    assert state.conflict_records[0].conflict_key == "k"


def test_agent_state_accepts_resolution_outcomes():
    outcome = ResolutionOutcome(status="unresolved", rationale="r")
    state = AgentState(user_query="test", resolution_outcomes=[outcome])
    assert state.resolution_outcomes[0].status == "unresolved"


def test_candidate_program_has_data_uncertain_fields_default_empty():
    candidate = CandidateProgram(
        candidate_id="c", school_id="s", school_name="S",
        admission_year=2026, program_name="P",
    )
    assert candidate.data_uncertain_fields == []


def test_candidate_program_accepts_data_uncertain_fields():
    candidate = CandidateProgram(
        candidate_id="c", school_id="s", school_name="S",
        admission_year=2026, program_name="P",
        data_uncertain_fields=["quota"],
    )
    assert candidate.data_uncertain_fields == ["quota"]
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_state_extensions.py -v`

Expected: FAIL — attribute errors on `conflict_records`, `resolution_outcomes`, `data_uncertain_fields`.

- [ ] **Step 3: Add `data_uncertain_fields` to `CandidateProgram`**

In `agents/models.py`, locate the `CandidateProgram` class. Append one field after `evidence`:

```python
    data_uncertain_fields: List[str] = Field(default_factory=list)
```

- [ ] **Step 4: Add conflict-layer fields to `AgentState`**

In `state.py`, add an import at the top:

```python
from services.conflict.models import ConflictRecord, ResolutionOutcome
```

Then inside `class AgentState`, after the existing `conflicts: List[str] = Field(default_factory=list)` line, add:

```python
    conflict_records: List[ConflictRecord] = Field(default_factory=list)
    resolution_outcomes: List[ResolutionOutcome] = Field(default_factory=list)
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `pytest tests/test_state_extensions.py -v`

Expected: all 5 PASS.

- [ ] **Step 6: Run the full test suite to confirm no regression from the schema additions**

Run: `pytest tests/ -v --ignore=tests/ingestion/test_db_writer_per_source_upsert.py`

Expected: green except for any test that depended on `AgentState` not having these fields (none expected — both are additive and default to `[]`).

- [ ] **Step 7: Commit**

```powershell
git add state.py agents/models.py tests/test_state_extensions.py
git commit -m "feat(state): add conflict_records, resolution_outcomes, data_uncertain_fields"
```

---

## Task 3: Quota normalization helper

**Files:**
- Create: `services/conflict/detection.py` (initial — just the helper)
- Create: `tests/services/conflict/test_detection.py` (initial — helper tests)

- [ ] **Step 1: Write the failing tests for `_normalize_quota_value`**

Create `tests/services/conflict/test_detection.py` with initial content:

```python
from services.conflict.detection import _normalize_quota_value


def test_normalize_quota_int_total():
    assert _normalize_quota_value({"total": 100}) == 100


def test_normalize_quota_str_numeric_total():
    assert _normalize_quota_value({"total": "100"}) == 100


def test_normalize_quota_dict_with_nested_total():
    # Sub-keys (e.g., per-method breakdown) collapse to None — heterogeneous shape
    # is treated as a distinct value via its serialized form.
    assert _normalize_quota_value({"per_method": {"thpt_score": 50}}) is not None


def test_normalize_quota_none():
    assert _normalize_quota_value(None) is None


def test_normalize_quota_empty_dict():
    assert _normalize_quota_value({}) is None


def test_normalize_quota_non_numeric_total():
    # "khoảng 100" — non-numeric, must still produce a comparable scalar
    result = _normalize_quota_value({"total": "khoảng 100"})
    assert result is not None
    assert isinstance(result, str)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/services/conflict/test_detection.py -v`

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement the helper**

Create `services/conflict/detection.py`:

```python
import json
from typing import Any, Optional


def _normalize_quota_value(quota: Any) -> Optional[Any]:
    """Reduce a quota dict to a comparable scalar.

    Rules:
    - None or empty dict -> None.
    - dict with a numeric "total" -> int(total).
    - dict with a non-numeric "total" string -> the raw string.
    - any other dict shape -> a deterministic JSON dump (sorted keys), so two
      identical heterogeneous shapes compare equal but a heterogeneous shape
      and a flat `{"total": N}` do not.
    - any non-dict primitive -> itself.
    """
    if quota is None:
        return None
    if isinstance(quota, dict):
        if not quota:
            return None
        if "total" in quota and len(quota) == 1:
            value = quota["total"]
            if isinstance(value, int):
                return value
            if isinstance(value, str):
                stripped = value.strip()
                try:
                    return int(stripped)
                except ValueError:
                    return stripped
            return value
        return json.dumps(quota, sort_keys=True, ensure_ascii=False)
    return quota
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/services/conflict/test_detection.py -v`

Expected: 6 PASS.

- [ ] **Step 5: Commit**

```powershell
git add services/conflict/detection.py tests/services/conflict/test_detection.py
git commit -m "feat(conflict): add quota normalization helper"
```

---

## Task 4: `detect_quota_conflicts` — single-group case

**Files:**
- Modify: `services/conflict/detection.py` (add `detect_quota_conflicts`)
- Modify: `tests/services/conflict/test_detection.py` (add new test)

- [ ] **Step 1: Write the failing test for the single-group case**

Append to `tests/services/conflict/test_detection.py`:

```python
from agents.models import CandidateProgram, Evidence
from services.conflict.detection import detect_quota_conflicts


def _candidate(school_id, program_id, admission_method, quota, source_url, trust_level=2):
    return CandidateProgram(
        candidate_id=f"{school_id}:{program_id}:{admission_method}:{source_url}",
        school_id=school_id,
        school_name=school_id.upper(),
        admission_year=2026,
        program_id=program_id,
        program_name=program_id,
        admission_method=admission_method,
        quota=quota,
        evidence=[
            Evidence(
                source_url=source_url, school_name=school_id.upper(),
                admission_year=2026, field_name="record",
                trust_level=trust_level,
            )
        ],
    )


def test_detect_two_candidates_distinct_quotas_produces_one_record():
    candidates = [
        _candidate("hust", "cs", "thpt_score", {"total": 100}, "https://a/"),
        _candidate("hust", "cs", "thpt_score", {"total": 200}, "https://b/"),
    ]
    records = detect_quota_conflicts(candidates)
    assert len(records) == 1
    rec = records[0]
    assert rec.field_name == "quota"
    assert rec.conflict_key == "hust:2026:cs:thpt_score"
    assert rec.school_id == "hust"
    assert len(rec.options) == 2
    values = sorted(opt.value for opt in rec.options)
    assert values == [100, 200]
    sources = sorted(opt.source_url for opt in rec.options)
    assert sources == ["https://a/", "https://b/"]


def test_detect_identical_quotas_produces_no_record():
    candidates = [
        _candidate("hust", "cs", "thpt_score", {"total": 100}, "https://a/"),
        _candidate("hust", "cs", "thpt_score", {"total": 100}, "https://b/"),
    ]
    assert detect_quota_conflicts(candidates) == []


def test_detect_single_candidate_produces_no_record():
    candidates = [_candidate("hust", "cs", "thpt_score", {"total": 100}, "https://a/")]
    assert detect_quota_conflicts(candidates) == []
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/services/conflict/test_detection.py -v`

Expected: 3 new tests FAIL with `ImportError: cannot import name 'detect_quota_conflicts'`.

- [ ] **Step 3: Implement `detect_quota_conflicts`**

Append to `services/conflict/detection.py`:

```python
from typing import Dict, List, Tuple

from agents.models import CandidateProgram
from services.conflict.models import ConflictRecord, EvidenceOption


def _group_key(c: CandidateProgram) -> Tuple[str, int, str, str]:
    return (
        c.school_id,
        c.admission_year,
        c.program_id or c.program_name,
        c.admission_method or "unknown_method",
    )


def _conflict_key_str(key: Tuple[str, int, str, str]) -> str:
    school_id, year, program, method = key
    return f"{school_id}:{year}:{program}:{method}"


def _option_from_candidate(c: CandidateProgram) -> EvidenceOption:
    evidence = c.evidence[0] if c.evidence else None
    source_url = evidence.source_url if evidence else ""
    return EvidenceOption(
        evidence_id=f"{source_url}|quota",
        source_url=source_url,
        trust_level=evidence.trust_level if evidence else None,
        fetched_at=None,
        confidence_score=evidence.confidence_score if evidence else None,
        value=_normalize_quota_value(c.quota),
    )


def detect_quota_conflicts(candidates: List[CandidateProgram]) -> List[ConflictRecord]:
    """Group candidates by (school_id, year, program, method) and emit one
    ConflictRecord per group that contains >= 2 candidates AND >= 2 distinct
    normalized quota values.
    """
    groups: Dict[Tuple[str, int, str, str], List[CandidateProgram]] = {}
    for c in candidates:
        groups.setdefault(_group_key(c), []).append(c)

    records: List[ConflictRecord] = []
    for key, group in groups.items():
        if len(group) < 2:
            continue
        normalized = {_normalize_quota_value(c.quota) for c in group}
        if len(normalized) < 2:
            continue

        options = [_option_from_candidate(c) for c in group]
        first = group[0]
        records.append(
            ConflictRecord(
                conflict_key=_conflict_key_str(key),
                field_name="quota",
                school_id=first.school_id,
                school_name=first.school_name,
                program_name=first.program_name,
                admission_method=first.admission_method,
                options=options,
            )
        )
    return records
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/services/conflict/test_detection.py -v`

Expected: all detection tests PASS.

- [ ] **Step 5: Commit**

```powershell
git add services/conflict/detection.py tests/services/conflict/test_detection.py
git commit -m "feat(conflict): detect quota conflicts as structured records"
```

---

## Task 5: `detect_quota_conflicts` — corroboration, multiple groups, heterogeneous shapes

**Files:**
- Modify: `tests/services/conflict/test_detection.py` (more tests)
- Modify: `services/conflict/detection.py` only if new tests reveal a gap.

- [ ] **Step 1: Write the failing tests**

Append to `tests/services/conflict/test_detection.py`:

```python
def test_detect_three_candidates_two_agree_one_record_three_options():
    candidates = [
        _candidate("hust", "cs", "thpt_score", {"total": 100}, "https://a/"),
        _candidate("hust", "cs", "thpt_score", {"total": 100}, "https://b/"),
        _candidate("hust", "cs", "thpt_score", {"total": 200}, "https://c/"),
    ]
    records = detect_quota_conflicts(candidates)
    assert len(records) == 1
    assert len(records[0].options) == 3, "All 3 source rows preserved for corroboration"


def test_detect_multiple_groups_emit_multiple_records():
    candidates = [
        _candidate("hust", "cs", "thpt_score", {"total": 100}, "https://a/"),
        _candidate("hust", "cs", "thpt_score", {"total": 200}, "https://b/"),
        _candidate("uet", "ee", "thpt_score", {"total": 50}, "https://c/"),
        _candidate("uet", "ee", "thpt_score", {"total": 60}, "https://d/"),
    ]
    records = detect_quota_conflicts(candidates)
    keys = sorted(r.conflict_key for r in records)
    assert keys == ["hust:2026:cs:thpt_score", "uet:2026:ee:thpt_score"]
    for r in records:
        assert len(r.options) == 2


def test_detect_heterogeneous_quota_shapes_treated_as_conflict():
    candidates = [
        _candidate("hust", "cs", "thpt_score", {"total": 100}, "https://a/"),
        _candidate("hust", "cs", "thpt_score", {"per_method": {"thpt_score": 50}}, "https://b/"),
    ]
    records = detect_quota_conflicts(candidates)
    assert len(records) == 1
    assert len(records[0].options) == 2


def test_detect_distinct_methods_do_not_collide():
    candidates = [
        _candidate("hust", "cs", "thpt_score", {"total": 100}, "https://a/"),
        _candidate("hust", "cs", "talent",     {"total": 200}, "https://b/"),
    ]
    records = detect_quota_conflicts(candidates)
    assert records == []
```

- [ ] **Step 2: Run the tests**

Run: `pytest tests/services/conflict/test_detection.py -v`

Expected: PASS — the implementation from Task 4 already handles these cases. If any test fails, fix `detect_quota_conflicts` (likely the heterogeneous-shape case — confirm the normalization produces two distinct serialized values).

- [ ] **Step 3: Commit**

```powershell
git add tests/services/conflict/test_detection.py
git commit -m "test(conflict): cover corroboration, multi-group, heterogeneous shapes"
```

---

## Task 6: Stop calling old `detect_conflicts` from `retrieval_agent`

**Files:**
- Modify: `agents/retrieval_agent.py`
- Modify: `tests/e2e/test_advisory_flow.py` (only if it breaks; otherwise leave alone)

- [ ] **Step 1: Read the current retrieval_agent**

The current `agents/retrieval_agent.py` ends with:

```python
    state.retrieved_programs = candidates
    state.conflicts = detect_conflicts(candidates)
    return state
```

- [ ] **Step 2: Write a regression test asserting `state.conflicts` is empty after retrieval**

Create `tests/agents/test_retrieval_agent_no_legacy_conflicts.py`:

```python
import agents.retrieval_agent as retrieval_agent_module
from agents.models import CandidateProgram, Evidence
from state import AgentState


def _two_conflicting_candidates():
    return [
        CandidateProgram(
            candidate_id="hust:cs:a",
            school_id="hust", school_name="HUST", admission_year=2026,
            program_id="cs", program_name="CS", admission_method="thpt_score",
            quota={"total": 100},
            evidence=[Evidence(source_url="https://a/", school_name="HUST",
                               admission_year=2026, field_name="record")],
        ),
        CandidateProgram(
            candidate_id="hust:cs:b",
            school_id="hust", school_name="HUST", admission_year=2026,
            program_id="cs", program_name="CS", admission_method="thpt_score",
            quota={"total": 200},
            evidence=[Evidence(source_url="https://b/", school_name="HUST",
                               admission_year=2026, field_name="record")],
        ),
    ]


def test_retrieval_agent_no_longer_emits_legacy_string_conflicts(monkeypatch):
    monkeypatch.setattr(
        retrieval_agent_module, "fetch_candidates",
        lambda filters, limit=100: _two_conflicting_candidates(),
    )
    state = AgentState(user_query="test")
    out = retrieval_agent_module.retrieval_agent(state)
    assert out.conflicts == [], "Slice 2: retrieval_agent no longer surfaces conflicts"
    assert len(out.retrieved_programs) == 2
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `pytest tests/agents/test_retrieval_agent_no_legacy_conflicts.py -v`

Expected: FAIL — `out.conflicts` contains a `"Quota conflict for ..."` string.

- [ ] **Step 4: Update `retrieval_agent` to stop calling `detect_conflicts`**

In `agents/retrieval_agent.py`:

1. Remove `detect_conflicts` from the `from services.retrieval_service import (...)` import. The remaining imports are `build_retrieval_filters` and `fetch_candidates`.
2. Remove the `state.conflicts = detect_conflicts(candidates)` line at the end of `retrieval_agent`. Do **not** assign anything else to `state.conflicts` — it defaults to `[]`.
3. The error-path assignment `state.conflicts = [f"Retrieval error: {exc}"]` stays. The legacy shim is still used for genuine error reporting.

Final state of the function body:

```python
def retrieval_agent(state: AgentState):
    filters = build_retrieval_filters(state.student_profile, state.admission_year)
    state.retrieval_filters = filters

    try:
        candidates = fetch_candidates(filters=filters)
    except Exception as exc:
        state.retrieved_programs = []
        state.conflicts = [f"Retrieval error: {exc}"]
        return state

    subject_combination = state.student_profile.subject_combination
    if subject_combination:
        candidates = [
            candidate
            for candidate in candidates
            if not candidate.subject_combinations
            or subject_combination in candidate.subject_combinations
        ]

    state.retrieved_programs = candidates
    return state
```

- [ ] **Step 5: Run the regression test**

Run: `pytest tests/agents/test_retrieval_agent_no_legacy_conflicts.py -v`

Expected: PASS.

- [ ] **Step 6: Run the existing advisory flow test**

Run: `pytest tests/e2e/test_advisory_flow.py -v`

Expected: green. The existing test already does `monkeypatch.setattr(retrieval_agent, "detect_conflicts", lambda candidates: [])`, which becomes a no-op patch on a now-unused name. If pytest raises `AttributeError: module 'agents.retrieval_agent' has no attribute 'detect_conflicts'` because the import was removed, leave the patch line alone but ensure the test passes by either:

- Keeping `detect_conflicts` imported in `retrieval_agent` (just unused), or
- Removing the now-obsolete `monkeypatch.setattr(retrieval_agent, "detect_conflicts", ...)` line from the test.

Prefer the second (cleaner) option: edit `tests/e2e/test_advisory_flow.py` to delete the line `monkeypatch.setattr(retrieval_agent, "detect_conflicts", lambda candidates: [])`.

- [ ] **Step 7: Run the full test suite**

Run: `pytest tests/ -v --ignore=tests/ingestion/test_db_writer_per_source_upsert.py`

Expected: green. The existing `tests/services/test_retrieval_service.py` may still test the old `detect_conflicts` function directly — that's fine, the function still exists in `services/retrieval_service.py`; it's only no longer called from the graph. Slice 3 will replace its callers entirely and the function dies then.

- [ ] **Step 8: Commit**

```powershell
git add agents/retrieval_agent.py tests/agents/test_retrieval_agent_no_legacy_conflicts.py tests/e2e/test_advisory_flow.py
git commit -m "refactor(retrieval): stop emitting legacy string conflicts"
```

---

## Slice 2 Exit Gate

Before declaring Slice 2 complete:

1. `pytest tests/services/conflict/ -v` — all green.
2. `pytest tests/test_state_extensions.py -v` — green.
3. `pytest tests/agents/test_retrieval_agent_no_legacy_conflicts.py -v` — green.
4. `pytest tests/ -v --ignore=tests/ingestion/test_db_writer_per_source_upsert.py` — green overall.
5. `AgentState.conflict_records` and `AgentState.resolution_outcomes` both default to `[]` and accept their respective types.
6. `CandidateProgram.data_uncertain_fields` defaults to `[]`.

Slice 2 is intentionally **invisible to users**: the graph still runs, the chat output is unchanged, conflicts are silently dropped in this slice. That is the safe-merge intent — Slice 3 wires the new layer into the graph.

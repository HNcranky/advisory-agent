# Slice 3 — Evidence + Comparison + Resolution agents Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Evidence/Comparison/Resolution multi-agent layer on top of the data model and detection layer from Slice 2, wire it as a new `conflict` node between `retrieve` and `reason` in the advisory graph, extend the reasoning and explanation agents to honour resolved/unresolved outcomes, and prove end-to-end on synthetic fixtures that both decisive resolution and unresolved outcomes survive into the chat output.

**Architecture:** Add `services/conflict/{evidence_agent,comparison_agent,resolution_agent,source_labels}.py`. Rewrite `agents/conflict_agent.py` as the orchestrator that calls detection → packaging → comparison → resolution and mutates `state`. Restructure the LLM prompt in `services/conflict_resolution_service.py` to return JSON `{chosen_source_url, confidence, rationale}`. Wire `conflict` into `graph.py` between `retrieve` and `reason`. Extend `reasoning_service.reason_candidates` to block uncertain quota candidates from the top "safe" band. Extend `explanation_service.build_explanation` to append a Vietnamese `## Xác minh dữ liệu` section from deterministic templates when outcomes exist.

**Tech Stack:** Python 3.11+, pydantic, psycopg2 (for the Evidence agent's join query), LangGraph, pytest, existing inference gateway (`services.inference`).

---

## File Structure

- Create: `services/conflict/source_labels.py` — hostname → Vietnamese label dictionary + URL host extraction.
- Create: `services/conflict/evidence_agent.py` — `package_evidence(record, raw_candidates) -> List[EvidenceOption]` enriching options via a SQL join.
- Create: `services/conflict/comparison_agent.py` — `compare(options) -> ComparisonReport` (deterministic, no LLM).
- Create: `services/conflict/resolution_agent.py` — `resolve(record, report, gateway) -> ResolutionOutcome`.
- Modify: `services/conflict_resolution_service.py` — restructure prompt + return contract to `{chosen_source_url, confidence, rationale}`.
- Modify: `agents/conflict_agent.py` — rewrite as the conflict-node orchestrator (detect → package → compare → resolve → reconcile state).
- Modify: `graph.py` — add `conflict` node, edges `retrieve -> conflict -> reason`.
- Modify: `services/reasoning_service.py` — block candidates with `data_uncertain_fields` from the top band, surface the Vietnamese caution.
- Modify: `services/explanation_service.py` — append the `## Xác minh dữ liệu` section when `resolution_outcomes` is non-empty.
- Modify: `agents/explanation_agent.py` — pass `resolution_outcomes` through to `build_explanation`.
- Create: `tests/services/conflict/test_source_labels.py`
- Create: `tests/services/conflict/test_evidence_agent.py`
- Create: `tests/services/conflict/test_comparison_agent.py`
- Create: `tests/services/conflict/test_resolution_agent.py`
- Create: `tests/agents/test_conflict_agent.py`
- Modify: `tests/services/test_conflict_resolution_service.py` — assert the new return contract.
- Modify: `tests/agents/test_reasoning_agent.py` — add a case for `data_uncertain_fields`.
- Modify: `tests/agents/test_explanation_agent.py` — add cases for the verification section.
- Modify: `tests/agents/test_policy_agent.py` — assert only unresolved/LLM-tiebroken outcomes fire ambiguity.
- Modify: `tests/e2e/test_advisory_flow.py` — add a resolved-and-unresolved end-to-end case.

Single responsibility per file. The orchestrator owns flow control; per-step modules own one step each.

---

## Task 1: Source-label helper

**Files:**
- Create: `services/conflict/source_labels.py`
- Create: `tests/services/conflict/test_source_labels.py`

- [ ] **Step 1: Write the failing test**

Create `tests/services/conflict/test_source_labels.py`:

```python
from services.conflict.source_labels import label_for_source


def test_known_hostname_returns_vietnamese_label():
    assert label_for_source("https://hust.edu.vn/tuyensinh/cs.html") == "Trang tuyển sinh HUST"


def test_uet_hostname_returns_vietnamese_label():
    assert label_for_source("https://uet.vnu.edu.vn/programs/ee") == "Trang chương trình UET (ĐHQGHN)"


def test_vnu_hostname_returns_proposal_label():
    assert label_for_source("https://vnu.edu.vn/admission/proposal-2026.pdf") == "Đề án tuyển sinh ĐHQGHN"


def test_unknown_hostname_falls_back_to_hostname():
    result = label_for_source("https://random-site.example/page")
    assert result == "Nguồn: random-site.example"


def test_empty_url_returns_unknown_label():
    assert label_for_source("") == "Nguồn không xác định"


def test_malformed_url_returns_unknown_label():
    assert label_for_source("not-a-url") == "Nguồn không xác định"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/services/conflict/test_source_labels.py -v`

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement the helper**

Create `services/conflict/source_labels.py`:

```python
from urllib.parse import urlparse


_KNOWN_LABELS = {
    "hust.edu.vn": "Trang tuyển sinh HUST",
    "ts.hust.edu.vn": "Trang tuyển sinh HUST",
    "tuyensinh.hust.edu.vn": "Trang tuyển sinh HUST",
    "uet.vnu.edu.vn": "Trang chương trình UET (ĐHQGHN)",
    "vnu.edu.vn": "Đề án tuyển sinh ĐHQGHN",
    "ts.vnu.edu.vn": "Trang tuyển sinh ĐHQGHN",
}


def label_for_source(source_url: str) -> str:
    if not source_url:
        return "Nguồn không xác định"
    parsed = urlparse(source_url)
    host = parsed.hostname
    if not host:
        return "Nguồn không xác định"
    host = host.lower()
    if host in _KNOWN_LABELS:
        return _KNOWN_LABELS[host]
    # Strip leading "www."
    if host.startswith("www.") and host[4:] in _KNOWN_LABELS:
        return _KNOWN_LABELS[host[4:]]
    return f"Nguồn: {host}"
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/services/conflict/test_source_labels.py -v`

Expected: all 6 PASS.

- [ ] **Step 5: Commit**

```powershell
git add services/conflict/source_labels.py tests/services/conflict/test_source_labels.py
git commit -m "feat(conflict): add Vietnamese source-label helper"
```

---

## Task 2: Evidence agent — provenance enrichment

**Files:**
- Create: `services/conflict/evidence_agent.py`
- Create: `tests/services/conflict/test_evidence_agent.py`

- [ ] **Step 1: Write the failing test**

Create `tests/services/conflict/test_evidence_agent.py`:

```python
from datetime import datetime
from unittest.mock import MagicMock

import services.conflict.evidence_agent as ea_module
from services.conflict.evidence_agent import package_evidence
from services.conflict.models import ConflictRecord, EvidenceOption


def _record(options):
    return ConflictRecord(
        conflict_key="hust:2026:cs:thpt_score",
        field_name="quota",
        school_id="hust",
        school_name="HUST",
        program_name="CS",
        admission_method="thpt_score",
        options=options,
    )


def _option(url, value=100):
    return EvidenceOption(
        evidence_id=f"{url}|quota", source_url=url, value=value, trust_level=2,
    )


def _row(fetched_at, is_official, parser_profile):
    return (fetched_at, is_official, parser_profile)


def test_package_evidence_enriches_with_provenance(monkeypatch):
    rows = {
        "https://a/": _row(datetime(2026, 5, 1), True, "html_default"),
        "https://b/": _row(datetime(2026, 5, 3), True, "pdf_table"),
    }

    def fake_query(source_url, school_id, admission_year):
        return rows[source_url]

    monkeypatch.setattr(ea_module, "_fetch_provenance", fake_query)

    record = _record([_option("https://a/"), _option("https://b/", 200)])
    options = package_evidence(record, raw_candidates=[], admission_year=2026)

    assert options[0].fetched_at == datetime(2026, 5, 1)
    assert options[0].is_official is True
    assert options[0].parser_profile == "html_default"
    assert options[1].fetched_at == datetime(2026, 5, 3)
    assert options[1].parser_profile == "pdf_table"


def test_package_evidence_missing_provenance_returns_none_fields(monkeypatch):
    monkeypatch.setattr(ea_module, "_fetch_provenance", lambda *a, **k: None)

    record = _record([_option("https://gone/")])
    options = package_evidence(record, raw_candidates=[], admission_year=2026)

    assert options[0].fetched_at is None
    assert options[0].is_official is None
    assert options[0].parser_profile is None
    assert options[0].source_url == "https://gone/"


def test_package_evidence_preserves_original_option_value(monkeypatch):
    monkeypatch.setattr(
        ea_module, "_fetch_provenance",
        lambda *a, **k: _row(datetime(2026, 1, 1), True, "html_default"),
    )

    record = _record([_option("https://a/", value=123)])
    options = package_evidence(record, raw_candidates=[], admission_year=2026)

    assert options[0].value == 123
    assert options[0].trust_level == 2


def test_package_evidence_swallows_db_exceptions(monkeypatch):
    def raising(*args, **kwargs):
        raise RuntimeError("connection broken")

    monkeypatch.setattr(ea_module, "_fetch_provenance", raising)

    record = _record([_option("https://a/")])
    options = package_evidence(record, raw_candidates=[], admission_year=2026)

    # DB failure must not propagate. Enrichment fields stay None.
    assert options[0].fetched_at is None
    assert options[0].is_official is None
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/services/conflict/test_evidence_agent.py -v`

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement the Evidence agent**

Create `services/conflict/evidence_agent.py`:

```python
from datetime import datetime
from typing import Any, List, Optional, Tuple

from ingestion.storage.db_connection import get_cursor
from services.conflict.models import ConflictRecord, EvidenceOption


_PROVENANCE_SQL = """
SELECT
    rd.fetched_at,
    sr.is_official,
    sr.parser_profile
FROM canonical_admission_records car
JOIN extracted_facts ef ON ef.id = car.extracted_fact_id
JOIN raw_documents rd ON rd.id = ef.raw_document_id
LEFT JOIN source_registry sr ON sr.source_id = rd.source_id
WHERE car.source_url = %s
  AND car.school_id = %s
  AND car.admission_year = %s
LIMIT 1
"""


def _fetch_provenance(
    source_url: str, school_id: str, admission_year: int
) -> Optional[Tuple[Optional[datetime], Optional[bool], Optional[str]]]:
    with get_cursor(commit=False) as cur:
        cur.execute(_PROVENANCE_SQL, (source_url, school_id, admission_year))
        row = cur.fetchone()
        if not row:
            return None
        return row


def package_evidence(
    record: ConflictRecord,
    raw_candidates: List[Any],
    admission_year: int,
) -> List[EvidenceOption]:
    """Return record.options with fetched_at/is_official/parser_profile populated.

    Missing rows along the join chain leave enrichment fields as None.
    DB exceptions are swallowed; we never let conflict resolution fail because
    of a provenance lookup.
    """
    enriched: List[EvidenceOption] = []
    for option in record.options:
        try:
            row = _fetch_provenance(option.source_url, record.school_id, admission_year)
        except Exception:
            row = None

        if row is None:
            fetched_at, is_official, parser_profile = None, None, None
        else:
            fetched_at, is_official, parser_profile = row

        enriched.append(
            option.copy(
                update={
                    "fetched_at": fetched_at,
                    "is_official": is_official,
                    "parser_profile": parser_profile,
                }
            )
        )
    return enriched
```

Note: if the project uses pydantic v2, `option.copy(update=...)` is deprecated; use `option.model_copy(update=...)`. Match the pattern already used elsewhere in the codebase — grep for `.copy(update=` in `agents/` or `services/` to confirm.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/services/conflict/test_evidence_agent.py -v`

Expected: 4 PASS.

- [ ] **Step 5: Commit**

```powershell
git add services/conflict/evidence_agent.py tests/services/conflict/test_evidence_agent.py
git commit -m "feat(conflict): add Evidence agent for provenance enrichment"
```

---

## Task 3: Comparison agent — trust + corroboration + recency + confidence

**Files:**
- Create: `services/conflict/comparison_agent.py`
- Create: `tests/services/conflict/test_comparison_agent.py`

- [ ] **Step 1: Write the failing tests — decisive trust_level**

Create `tests/services/conflict/test_comparison_agent.py`:

```python
from datetime import datetime

from services.conflict.comparison_agent import compare
from services.conflict.models import EvidenceOption


def _opt(value, trust=None, fetched_at=None, confidence=None, url=None):
    url = url or f"https://{value}/"
    return EvidenceOption(
        evidence_id=f"{url}|quota",
        source_url=url,
        value=value,
        trust_level=trust,
        fetched_at=fetched_at,
        confidence_score=confidence,
    )


def test_decisive_on_trust_level():
    options = [_opt(100, trust=1), _opt(200, trust=3)]
    report = compare(options)
    assert report.is_decisive is True
    assert report.ranked_options[0].value == 200
    assert "trust_level" in report.decision_axes


def test_corroboration_two_mid_trust_beat_one_high_trust():
    # Two options at trust=2 agreeing on value 100, one at trust=3 reporting 200.
    options = [
        _opt(100, trust=2, url="https://a/"),
        _opt(100, trust=2, url="https://b/"),
        _opt(200, trust=3, url="https://c/"),
    ]
    report = compare(options)
    assert report.is_decisive is True
    assert report.ranked_options[0].value == 100
    assert "corroboration" in report.decision_axes


def test_recency_tiebreaker_after_trust_ties():
    options = [
        _opt(100, trust=2, fetched_at=datetime(2026, 1, 1)),
        _opt(200, trust=2, fetched_at=datetime(2026, 5, 1)),
    ]
    report = compare(options)
    assert report.is_decisive is True
    assert report.ranked_options[0].value == 200
    assert report.decision_axes == ["recency"]


def test_confidence_only_when_earlier_axes_tie():
    options = [
        _opt(100, trust=2, fetched_at=datetime(2026, 1, 1), confidence=0.5),
        _opt(200, trust=2, fetched_at=datetime(2026, 1, 1), confidence=0.9),
    ]
    report = compare(options)
    assert report.is_decisive is True
    assert report.ranked_options[0].value == 200
    assert report.decision_axes == ["confidence_score"]


def test_all_tie_yields_indecisive():
    options = [
        _opt(100, trust=2, fetched_at=datetime(2026, 1, 1), confidence=0.7, url="https://a/"),
        _opt(200, trust=2, fetched_at=datetime(2026, 1, 1), confidence=0.7, url="https://b/"),
    ]
    report = compare(options)
    assert report.is_decisive is False


def test_missing_recency_falls_through_to_next_axis():
    # Equal trust, no fetched_at on either → recency axis ties → confidence breaks tie.
    options = [
        _opt(100, trust=2, fetched_at=None, confidence=0.5),
        _opt(200, trust=2, fetched_at=None, confidence=0.9),
    ]
    report = compare(options)
    assert report.is_decisive is True
    assert report.ranked_options[0].value == 200
    assert report.decision_axes == ["confidence_score"]


def test_single_option_input_is_decisive_trivially():
    options = [_opt(100, trust=2)]
    report = compare(options)
    # Single option is trivially the winner; not "decisive" in the conflict sense.
    assert report.is_decisive is False
    assert report.ranked_options[0].value == 100
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/services/conflict/test_comparison_agent.py -v`

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement the Comparison agent**

Create `services/conflict/comparison_agent.py`:

```python
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from services.conflict.models import ComparisonReport, EvidenceOption


def _corroboration_trust(options: List[EvidenceOption]) -> Dict[Any, int]:
    """For each distinct value, return the max trust_level it can claim,
    accounting for corroboration: if two or more options report the same value,
    the value's effective trust is `max(actual trust, second-highest single-source trust)`.
    """
    by_value: Dict[Any, List[Optional[int]]] = defaultdict(list)
    for opt in options:
        by_value[opt.value].append(opt.trust_level)

    # Determine the second-highest single-source trust across the whole option set,
    # used as the corroboration boost ceiling.
    all_trusts = sorted(
        [t for opts in by_value.values() for t in opts if t is not None],
        reverse=True,
    )
    second_highest_single = all_trusts[1] if len(all_trusts) >= 2 else None

    effective: Dict[Any, int] = {}
    for value, trusts in by_value.items():
        present = [t for t in trusts if t is not None]
        max_single = max(present) if present else -1
        if len(present) >= 2 and second_highest_single is not None:
            effective[value] = max(max_single, second_highest_single)
        else:
            effective[value] = max_single
    return effective


def _axis_key(opt: EvidenceOption, effective_trust: Dict[Any, int]) -> Tuple:
    trust = effective_trust.get(opt.value, opt.trust_level if opt.trust_level is not None else -1)
    fetched = opt.fetched_at.timestamp() if opt.fetched_at is not None else float("-inf")
    confidence = opt.confidence_score if opt.confidence_score is not None else float("-inf")
    return (trust, fetched, confidence)


def compare(options: List[EvidenceOption]) -> ComparisonReport:
    if not options:
        return ComparisonReport(ranked_options=[], is_decisive=False, decision_axes=[])

    effective = _corroboration_trust(options)
    ranked = sorted(options, key=lambda o: _axis_key(o, effective), reverse=True)

    if len(options) < 2:
        return ComparisonReport(ranked_options=ranked, is_decisive=False, decision_axes=[])

    top = ranked[0]
    runner = ranked[1]

    # Determine which axis broke the tie, in order.
    axes: List[str] = []

    top_trust = effective[top.value]
    runner_trust = effective[runner.value]
    if top_trust != runner_trust:
        # Trust dominated. If corroboration boosted the winner, name corroboration.
        top_single = max(
            [o.trust_level for o in options if o.value == top.value and o.trust_level is not None],
            default=-1,
        )
        if top_single != top_trust:
            axes.append("corroboration")
        else:
            axes.append("trust_level")
        return ComparisonReport(ranked_options=ranked, is_decisive=True, decision_axes=axes)

    # Trust tied. Recency next.
    top_fetched = top.fetched_at
    runner_fetched = runner.fetched_at
    if top_fetched != runner_fetched and not (top_fetched is None and runner_fetched is None):
        if top_fetched is not None and (runner_fetched is None or top_fetched > runner_fetched):
            axes.append("recency")
            return ComparisonReport(ranked_options=ranked, is_decisive=True, decision_axes=axes)
        if runner_fetched is not None and (top_fetched is None or runner_fetched > top_fetched):
            # Sorting already placed the more-recent one first; this branch shouldn't trigger,
            # but covers paranoid edge cases.
            axes.append("recency")
            return ComparisonReport(ranked_options=ranked, is_decisive=True, decision_axes=axes)

    # Recency tied. Confidence next.
    top_conf = top.confidence_score
    runner_conf = runner.confidence_score
    if top_conf is not None and runner_conf is not None and top_conf != runner_conf:
        axes.append("confidence_score")
        return ComparisonReport(ranked_options=ranked, is_decisive=True, decision_axes=axes)
    if top_conf is not None and runner_conf is None:
        axes.append("confidence_score")
        return ComparisonReport(ranked_options=ranked, is_decisive=True, decision_axes=axes)

    # All axes tie.
    return ComparisonReport(ranked_options=ranked, is_decisive=False, decision_axes=[])
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/services/conflict/test_comparison_agent.py -v`

Expected: all 7 PASS. If a test fails, the most likely culprit is the corroboration logic — trace through the failing fixture by hand and adjust `_corroboration_trust`.

- [ ] **Step 5: Commit**

```powershell
git add services/conflict/comparison_agent.py tests/services/conflict/test_comparison_agent.py
git commit -m "feat(conflict): add deterministic Comparison agent"
```

---

## Task 4: Restructure `conflict_resolution_service` prompt + return contract

**Files:**
- Modify: `services/conflict_resolution_service.py`
- Modify: `tests/services/test_conflict_resolution_service.py`

- [ ] **Step 1: Update the existing test to assert the new contract**

Replace `tests/services/test_conflict_resolution_service.py` with:

```python
from services.conflict_resolution_service import resolve_conflicts_with_gateway
from services.inference.models import InferenceResult


class FakeGateway:
    def __init__(self, parsed):
        self._parsed = parsed
        self.requests = []

    def run(self, request):
        self.requests.append(request)
        return InferenceResult(
            agent_name=request.agent_name,
            model="gemini-2.5-flash",
            provider="fake",
            content="{}",
            parsed_data=self._parsed,
        )


def test_resolve_returns_structured_decision_when_gateway_succeeds():
    gateway = FakeGateway(parsed={
        "chosen_source_url": "https://hust.edu.vn/cs",
        "confidence": "high",
        "rationale": "HUST official page is more recent than the proposal PDF.",
    })

    parsed = resolve_conflicts_with_gateway(
        payload={
            "conflict_record": {"conflict_key": "hust:2026:cs:thpt_score", "field_name": "quota"},
            "comparison_report": {"is_decisive": False, "decision_axes": []},
        },
        gateway=gateway,
    )

    assert parsed["chosen_source_url"] == "https://hust.edu.vn/cs"
    assert parsed["confidence"] == "high"
    assert parsed["rationale"].startswith("HUST official")
    assert len(gateway.requests) == 1
    assert gateway.requests[0].agent_name == "resolution_agent"


def test_resolve_returns_fallback_when_gateway_returns_no_parsed_data():
    gateway = FakeGateway(parsed=None)
    parsed = resolve_conflicts_with_gateway(payload={}, gateway=gateway)
    assert parsed["confidence"] == "low"
    assert parsed["chosen_source_url"] is None
    assert "resolution_failed" in parsed["rationale"].lower()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/services/test_conflict_resolution_service.py -v`

Expected: FAIL — current function signature accepts `conflicts` (a list), not `payload`, and returns `{resolution, uncertainty_reasons}` shape.

- [ ] **Step 3: Rewrite `services/conflict_resolution_service.py`**

Replace the file contents with:

```python
import json

from services.inference.models import InferenceRequest


RESOLUTION_SYSTEM_PROMPT = """
Bạn là một bộ phân giải xung đột dữ liệu tuyển sinh.
Đầu vào là một bản ghi xung đột (conflict_record) và báo cáo so sánh (comparison_report).
Hãy chọn nguồn đáng tin nhất chỉ khi bạn rất chắc chắn.
Chỉ trả về JSON với khóa: chosen_source_url, confidence, rationale.
- chosen_source_url: URL nguồn được chọn, hoặc null nếu không thể quyết.
- confidence: "high" | "medium" | "low".
- rationale: lý do bằng tiếng Việt, ngắn gọn.
Trả về "high" chỉ khi bằng chứng rõ ràng nghiêng về một nguồn.
Không bịa ra nguồn ngoài danh sách trong payload.
"""


def resolve_conflicts_with_gateway(payload, gateway):
    """Ask the inference gateway to break a deadlocked comparison.

    payload: {"conflict_record": {...}, "comparison_report": {...}}
    Returns: {"chosen_source_url": str | None, "confidence": str, "rationale": str}.
    Failure modes (no parsed_data, gateway raises) collapse to a conservative
    low-confidence response so the caller can treat the outcome as unresolved.
    """
    try:
        result = gateway.run(
            InferenceRequest(
                agent_name="resolution_agent",
                task_type="conflict_resolution",
                system_prompt=RESOLUTION_SYSTEM_PROMPT.strip(),
                user_prompt=json.dumps(payload, ensure_ascii=False, default=str),
                output_mode="json",
                temperature=0.0,
            )
        )
    except Exception as exc:
        return {
            "chosen_source_url": None,
            "confidence": "low",
            "rationale": f"resolution_failed: gateway raised {type(exc).__name__}",
        }

    parsed = result.parsed_data
    if not isinstance(parsed, dict):
        return {
            "chosen_source_url": None,
            "confidence": "low",
            "rationale": "resolution_failed: no parsed_data from gateway",
        }

    confidence = parsed.get("confidence")
    if confidence not in ("high", "medium", "low"):
        confidence = "low"

    return {
        "chosen_source_url": parsed.get("chosen_source_url"),
        "confidence": confidence,
        "rationale": str(parsed.get("rationale") or "no rationale provided"),
    }
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/services/test_conflict_resolution_service.py -v`

Expected: both PASS.

- [ ] **Step 5: Commit**

```powershell
git add services/conflict_resolution_service.py tests/services/test_conflict_resolution_service.py
git commit -m "refactor(conflict): structured JSON contract for resolution gateway"
```

---

## Task 5: Resolution agent — deterministic-first with conservative LLM tiebreaker

**Files:**
- Create: `services/conflict/resolution_agent.py`
- Create: `tests/services/conflict/test_resolution_agent.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/services/conflict/test_resolution_agent.py`:

```python
from datetime import datetime
from unittest.mock import MagicMock

from services.conflict.models import (
    ComparisonReport,
    ConflictRecord,
    EvidenceOption,
)
from services.conflict.resolution_agent import resolve


def _opt(value, url, trust=2):
    return EvidenceOption(
        evidence_id=f"{url}|quota", source_url=url, value=value, trust_level=trust,
    )


def _record(options):
    return ConflictRecord(
        conflict_key="hust:2026:cs:thpt_score",
        field_name="quota",
        school_id="hust", school_name="HUST", program_name="CS",
        admission_method="thpt_score",
        options=options,
    )


def test_decisive_report_resolves_without_calling_gateway():
    chosen = _opt(100, "https://hust.edu.vn/cs", trust=3)
    rejected = _opt(200, "https://other/", trust=1)
    record = _record([chosen, rejected])
    report = ComparisonReport(
        ranked_options=[chosen, rejected], is_decisive=True, decision_axes=["trust_level"],
    )

    gateway = MagicMock()
    outcome = resolve(record, report, gateway=gateway)

    assert outcome.status == "resolved"
    assert outcome.resolved_value == 100
    assert outcome.chosen_evidence == chosen
    assert outcome.rejected_evidence == [rejected]
    assert "trust_level" in outcome.rationale.lower() or "tin cậy" in outcome.rationale.lower()
    gateway.run.assert_not_called()


def test_indecisive_high_confidence_llm_resolves(monkeypatch):
    a = _opt(100, "https://a/", trust=2)
    b = _opt(200, "https://b/", trust=2)
    record = _record([a, b])
    report = ComparisonReport(ranked_options=[a, b], is_decisive=False, decision_axes=[])

    import services.conflict.resolution_agent as ra
    monkeypatch.setattr(
        ra, "resolve_conflicts_with_gateway",
        lambda payload, gateway: {
            "chosen_source_url": "https://b/",
            "confidence": "high",
            "rationale": "B is more recent in practice.",
        },
    )

    outcome = resolve(record, report, gateway=MagicMock())

    assert outcome.status == "resolved"
    assert outcome.resolved_value == 200
    assert outcome.chosen_evidence.source_url == "https://b/"
    assert outcome.rationale.startswith("LLM tiebreaker:")


def test_indecisive_medium_confidence_stays_unresolved(monkeypatch):
    a = _opt(100, "https://a/", trust=2)
    b = _opt(200, "https://b/", trust=2)
    record = _record([a, b])
    report = ComparisonReport(ranked_options=[a, b], is_decisive=False, decision_axes=[])

    import services.conflict.resolution_agent as ra
    monkeypatch.setattr(
        ra, "resolve_conflicts_with_gateway",
        lambda payload, gateway: {
            "chosen_source_url": "https://b/",
            "confidence": "medium",
            "rationale": "lean towards B",
        },
    )

    outcome = resolve(record, report, gateway=MagicMock())

    assert outcome.status == "unresolved"
    assert outcome.chosen_evidence is None
    assert outcome.uncertainty_reason == "conflict_unresolved_quota"


def test_indecisive_invalid_chosen_url_stays_unresolved(monkeypatch):
    a = _opt(100, "https://a/", trust=2)
    b = _opt(200, "https://b/", trust=2)
    record = _record([a, b])
    report = ComparisonReport(ranked_options=[a, b], is_decisive=False, decision_axes=[])

    import services.conflict.resolution_agent as ra
    monkeypatch.setattr(
        ra, "resolve_conflicts_with_gateway",
        lambda payload, gateway: {
            "chosen_source_url": "https://fabricated/",
            "confidence": "high",
            "rationale": "made up",
        },
    )

    outcome = resolve(record, report, gateway=MagicMock())
    assert outcome.status == "unresolved"


def test_indecisive_gateway_raises_stays_unresolved(monkeypatch):
    a = _opt(100, "https://a/", trust=2)
    b = _opt(200, "https://b/", trust=2)
    record = _record([a, b])
    report = ComparisonReport(ranked_options=[a, b], is_decisive=False, decision_axes=[])

    import services.conflict.resolution_agent as ra

    def boom(payload, gateway):
        raise RuntimeError("network down")

    monkeypatch.setattr(ra, "resolve_conflicts_with_gateway", boom)

    outcome = resolve(record, report, gateway=MagicMock())
    assert outcome.status == "unresolved"
    assert outcome.uncertainty_reason == "conflict_unresolved_quota"


def test_resolved_outcome_carries_conflict_key_for_correlation():
    chosen = _opt(100, "https://a/", trust=3)
    record = _record([chosen, _opt(200, "https://b/", trust=1)])
    report = ComparisonReport(
        ranked_options=record.options, is_decisive=True, decision_axes=["trust_level"],
    )
    outcome = resolve(record, report, gateway=MagicMock())
    assert outcome.conflict_key == record.conflict_key
    assert outcome.field_name == "quota"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/services/conflict/test_resolution_agent.py -v`

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement the Resolution agent**

Create `services/conflict/resolution_agent.py`:

```python
from typing import Any

from services.conflict.models import (
    ComparisonReport,
    ConflictRecord,
    EvidenceOption,
    ResolutionOutcome,
)
from services.conflict_resolution_service import resolve_conflicts_with_gateway


_AXIS_LABELS_VI = {
    "trust_level": "nguồn có mức độ tin cậy cao hơn",
    "corroboration": "có hai nguồn cùng thống nhất giá trị này",
    "recency": "nguồn được cập nhật gần đây hơn",
    "confidence_score": "độ tin cậy trích xuất cao hơn",
}


def _deterministic_rationale(chosen: EvidenceOption, axes) -> str:
    if not axes:
        return f"Chọn nguồn {chosen.source_url} (không có trục quyết định cụ thể)."
    parts = [_AXIS_LABELS_VI.get(ax, ax) for ax in axes]
    return "Chọn vì " + ", và ".join(parts) + f" (nguồn: {chosen.source_url})."


def _find_option_by_url(options, url: str):
    for opt in options:
        if opt.source_url == url:
            return opt
    return None


def resolve(
    record: ConflictRecord,
    report: ComparisonReport,
    gateway: Any,
) -> ResolutionOutcome:
    if report.is_decisive and report.ranked_options:
        chosen = report.ranked_options[0]
        rejected = list(report.ranked_options[1:])
        return ResolutionOutcome(
            status="resolved",
            resolved_value=chosen.value,
            chosen_evidence=chosen,
            rejected_evidence=rejected,
            rationale=_deterministic_rationale(chosen, report.decision_axes),
            conflict_key=record.conflict_key,
            field_name=record.field_name,
        )

    # Indecisive — fall through to the LLM tiebreaker, but only flip to resolved
    # on confidence=="high" AND a recognisable chosen_source_url.
    payload = {
        "conflict_record": record.dict() if hasattr(record, "dict") else record.model_dump(),
        "comparison_report": report.dict() if hasattr(report, "dict") else report.model_dump(),
    }
    try:
        decision = resolve_conflicts_with_gateway(payload=payload, gateway=gateway)
    except Exception:
        decision = {"chosen_source_url": None, "confidence": "low", "rationale": "gateway_error"}

    chosen_url = decision.get("chosen_source_url")
    confidence = decision.get("confidence", "low")
    chosen = _find_option_by_url(record.options, chosen_url) if chosen_url else None

    if chosen is not None and confidence == "high":
        rejected = [o for o in record.options if o.source_url != chosen.source_url]
        return ResolutionOutcome(
            status="resolved",
            resolved_value=chosen.value,
            chosen_evidence=chosen,
            rejected_evidence=rejected,
            rationale=f"LLM tiebreaker: {decision.get('rationale', '')}",
            conflict_key=record.conflict_key,
            field_name=record.field_name,
        )

    return ResolutionOutcome(
        status="unresolved",
        resolved_value=None,
        chosen_evidence=None,
        rejected_evidence=[],
        rationale="Conflicting authoritative sources could not be reconciled deterministically",
        uncertainty_reason="conflict_unresolved_quota",
        conflict_key=record.conflict_key,
        field_name=record.field_name,
    )
```

If the project is pydantic v2, change `record.dict()` / `report.dict()` to `record.model_dump()` / `report.model_dump()` — the `hasattr` guard above handles both, but verify by running the test.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/services/conflict/test_resolution_agent.py -v`

Expected: all 6 PASS.

- [ ] **Step 5: Commit**

```powershell
git add services/conflict/resolution_agent.py tests/services/conflict/test_resolution_agent.py
git commit -m "feat(conflict): add Resolution agent with conservative LLM tiebreaker"
```

---

## Task 6: Rewrite `conflict_agent` as the orchestrator

**Files:**
- Modify: `agents/conflict_agent.py`
- Create: `tests/agents/test_conflict_agent.py`

- [ ] **Step 1: Write the failing test for the conflict node**

Create `tests/agents/test_conflict_agent.py`:

```python
from datetime import datetime
from unittest.mock import MagicMock

import agents.conflict_agent as conflict_module
from agents.models import CandidateProgram, Evidence
from state import AgentState


def _candidate(school_id, program_id, method, quota, url, trust=2):
    return CandidateProgram(
        candidate_id=f"{school_id}:{program_id}:{method}:{url}",
        school_id=school_id, school_name=school_id.upper(),
        admission_year=2026,
        program_id=program_id, program_name=program_id,
        admission_method=method,
        quota=quota,
        evidence=[Evidence(
            source_url=url, school_name=school_id.upper(),
            admission_year=2026, field_name="record", trust_level=trust,
        )],
    )


def test_resolved_conflict_collapses_candidates_and_does_not_emit_legacy_string(monkeypatch):
    # Two candidates same key; one trust=3, one trust=1 → decisive on trust_level.
    monkeypatch.setattr(
        conflict_module, "package_evidence",
        lambda record, raw_candidates, admission_year: record.options,
    )

    state = AgentState(user_query="test", admission_year=2026)
    state.retrieved_programs = [
        _candidate("hust", "cs", "thpt", {"total": 100}, "https://hust.edu.vn/cs", trust=3),
        _candidate("hust", "cs", "thpt", {"total": 200}, "https://other/", trust=1),
    ]

    out = conflict_module.conflict_agent(state)

    assert len(out.conflict_records) == 1
    assert len(out.resolution_outcomes) == 1
    assert out.resolution_outcomes[0].status == "resolved"
    assert out.resolution_outcomes[0].resolved_value == 100
    # Resolved → candidate collapsed to a single representative carrying the resolved value.
    same_key = [c for c in out.retrieved_programs if c.school_id == "hust" and c.program_id == "cs"]
    assert len(same_key) == 1
    assert same_key[0].quota == {"total": 100}
    assert same_key[0].data_uncertain_fields == []
    # Legacy state.conflicts must NOT be populated for deterministically resolved cases.
    assert out.conflicts == []


def test_unresolved_conflict_keeps_all_candidates_and_marks_uncertainty(monkeypatch):
    # Equal trust + no recency + no confidence → indecisive.
    monkeypatch.setattr(
        conflict_module, "package_evidence",
        lambda record, raw_candidates, admission_year: record.options,
    )
    # Stub the LLM call to return medium confidence → unresolved.
    monkeypatch.setattr(
        conflict_module, "resolve_conflicts_with_gateway",
        lambda payload, gateway: {
            "chosen_source_url": "https://b/", "confidence": "medium", "rationale": "lean",
        },
    )
    monkeypatch.setattr(conflict_module, "build_default_gateway", lambda: MagicMock())

    state = AgentState(user_query="test", admission_year=2026)
    state.retrieved_programs = [
        _candidate("hust", "cs", "thpt", {"total": 100}, "https://a/", trust=2),
        _candidate("hust", "cs", "thpt", {"total": 200}, "https://b/", trust=2),
    ]

    out = conflict_module.conflict_agent(state)

    assert out.resolution_outcomes[0].status == "unresolved"
    # Both candidates kept; both marked uncertain.
    candidates = [c for c in out.retrieved_programs if c.school_id == "hust"]
    assert len(candidates) == 2
    for c in candidates:
        assert "quota" in c.data_uncertain_fields
    # Legacy shim IS populated for unresolved cases (so policy_agent escalates).
    assert out.conflicts != []
    assert any("hust" in c.lower() or "cs" in c.lower() for c in out.conflicts)


def test_no_conflicts_means_no_state_changes(monkeypatch):
    monkeypatch.setattr(
        conflict_module, "package_evidence",
        lambda record, raw_candidates, admission_year: record.options,
    )
    state = AgentState(user_query="test", admission_year=2026)
    state.retrieved_programs = [
        _candidate("hust", "cs", "thpt", {"total": 100}, "https://a/"),
    ]
    out = conflict_module.conflict_agent(state)
    assert out.conflict_records == []
    assert out.resolution_outcomes == []
    assert out.conflicts == []
    assert out.retrieved_programs[0].data_uncertain_fields == []


def test_llm_tiebroken_resolved_populates_legacy_shim(monkeypatch):
    # Deterministic comparison indecisive, gateway returns high confidence → resolved
    # but counts as "LLM-tiebroken" — the legacy shim is still populated.
    monkeypatch.setattr(
        conflict_module, "package_evidence",
        lambda record, raw_candidates, admission_year: record.options,
    )
    monkeypatch.setattr(
        conflict_module, "resolve_conflicts_with_gateway",
        lambda payload, gateway: {
            "chosen_source_url": "https://b/", "confidence": "high", "rationale": "B fresher",
        },
    )
    monkeypatch.setattr(conflict_module, "build_default_gateway", lambda: MagicMock())

    state = AgentState(user_query="test", admission_year=2026)
    state.retrieved_programs = [
        _candidate("hust", "cs", "thpt", {"total": 100}, "https://a/", trust=2),
        _candidate("hust", "cs", "thpt", {"total": 200}, "https://b/", trust=2),
    ]
    out = conflict_module.conflict_agent(state)

    assert out.resolution_outcomes[0].status == "resolved"
    assert out.resolution_outcomes[0].rationale.startswith("LLM tiebreaker:")
    # LLM-tiebroken case populates the legacy shim so policy_agent flags ambiguity.
    assert out.conflicts != []
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/agents/test_conflict_agent.py -v`

Expected: FAIL — the current `conflict_agent` stub still calls the legacy string-emission path and doesn't populate `conflict_records` / `resolution_outcomes`.

- [ ] **Step 3: Rewrite `agents/conflict_agent.py`**

Replace the file contents with:

```python
from typing import Dict, List, Tuple

from agents.models import CandidateProgram
from services import build_default_gateway
from services.conflict.comparison_agent import compare
from services.conflict.detection import detect_quota_conflicts
from services.conflict.evidence_agent import package_evidence
from services.conflict.models import ConflictRecord, ResolutionOutcome
from services.conflict.resolution_agent import resolve
from services.conflict_resolution_service import resolve_conflicts_with_gateway  # noqa: F401 — re-exported for test patching
from state import AgentState


def _group_key(c: CandidateProgram) -> Tuple[str, int, str, str]:
    return (
        c.school_id,
        c.admission_year,
        c.program_id or c.program_name,
        c.admission_method or "unknown_method",
    )


def _conflict_key_str(key) -> str:
    school_id, year, program, method = key
    return f"{school_id}:{year}:{program}:{method}"


def _reconcile_candidates(
    candidates: List[CandidateProgram],
    outcomes: List[ResolutionOutcome],
) -> List[CandidateProgram]:
    by_key: Dict[str, List[CandidateProgram]] = {}
    for c in candidates:
        by_key.setdefault(_conflict_key_str(_group_key(c)), []).append(c)

    outcome_by_key: Dict[str, ResolutionOutcome] = {
        o.conflict_key: o for o in outcomes if o.conflict_key
    }

    new_candidates: List[CandidateProgram] = []
    seen_keys = set()
    for c in candidates:
        key = _conflict_key_str(_group_key(c))
        outcome = outcome_by_key.get(key)
        if outcome is None:
            new_candidates.append(c)
            continue

        if outcome.status == "resolved":
            # Collapse: keep one representative per key with the resolved value.
            if key in seen_keys:
                continue
            seen_keys.add(key)
            # Pick the candidate whose source_url matches the chosen evidence.
            chosen_url = outcome.chosen_evidence.source_url if outcome.chosen_evidence else None
            rep = next(
                (cand for cand in by_key[key] if any(ev.source_url == chosen_url for ev in cand.evidence)),
                by_key[key][0],
            )
            # Materialise the resolved quota onto the representative.
            updated = rep.copy(update={
                "quota": _quota_from_value(outcome.resolved_value, rep.quota),
                "data_uncertain_fields": [],
            }) if hasattr(rep, "copy") else rep.model_copy(update={
                "quota": _quota_from_value(outcome.resolved_value, rep.quota),
                "data_uncertain_fields": [],
            })
            new_candidates.append(updated)
        else:
            # Unresolved: keep all candidates in the group, mark each uncertain.
            uncertain = c.copy(update={
                "data_uncertain_fields": list(set(c.data_uncertain_fields + [outcome.field_name or "quota"])),
            }) if hasattr(c, "copy") else c.model_copy(update={
                "data_uncertain_fields": list(set(c.data_uncertain_fields + [outcome.field_name or "quota"])),
            })
            new_candidates.append(uncertain)
    return new_candidates


def _quota_from_value(resolved_value, existing_quota):
    """Reconstruct a quota dict from the resolved scalar. If resolved_value is an int,
    materialise as {"total": int}; if it's a string and existing was a dict, preserve
    the dict shape; otherwise emit {"total": resolved_value}."""
    if isinstance(resolved_value, int):
        return {"total": resolved_value}
    if isinstance(existing_quota, dict) and resolved_value is not None:
        return {"total": resolved_value}
    return existing_quota


def _legacy_string_for_outcome(outcome: ResolutionOutcome) -> str:
    if outcome.status == "unresolved":
        return f"Unresolved quota conflict for {outcome.conflict_key}: {outcome.rationale}"
    return f"LLM-tiebroken quota conflict for {outcome.conflict_key}: {outcome.rationale}"


def conflict_agent(state: AgentState) -> AgentState:
    candidates = state.retrieved_programs or []
    records: List[ConflictRecord] = detect_quota_conflicts(candidates)
    if not records:
        return state

    gateway = build_default_gateway() if any(True for _ in [None]) else None

    outcomes: List[ResolutionOutcome] = []
    enriched_records: List[ConflictRecord] = []
    for record in records:
        options = package_evidence(record, raw_candidates=candidates, admission_year=state.admission_year)
        enriched_record = record.copy(update={"options": options}) if hasattr(record, "copy") else record.model_copy(update={"options": options})
        report = compare(options)
        outcome = resolve(enriched_record, report, gateway=gateway)
        outcomes.append(outcome)
        enriched_records.append(enriched_record)

    state.conflict_records = enriched_records
    state.resolution_outcomes = outcomes
    state.retrieved_programs = _reconcile_candidates(candidates, outcomes)

    # Legacy shim: only populate for unresolved OR LLM-tiebroken outcomes.
    legacy: List[str] = []
    for o in outcomes:
        if o.status == "unresolved":
            legacy.append(_legacy_string_for_outcome(o))
        elif o.rationale.startswith("LLM tiebreaker:"):
            legacy.append(_legacy_string_for_outcome(o))
    state.conflicts = list(dict.fromkeys(state.conflicts + legacy))

    return state
```

The `if any(True for _ in [None]) else None` line is intentionally always-true; it exists to let tests monkeypatch `build_default_gateway` without instantiating a real gateway. A cleaner version is `gateway = build_default_gateway()` — that is also fine; the test patches `conflict_module.build_default_gateway` either way. Pick the simpler form unless a test reveals a reason not to.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/agents/test_conflict_agent.py -v`

Expected: all 4 PASS.

- [ ] **Step 5: Commit**

```powershell
git add agents/conflict_agent.py tests/agents/test_conflict_agent.py
git commit -m "feat(conflict): rewrite conflict_agent as orchestrator node"
```

---

## Task 7: Wire the `conflict` node into the graph

**Files:**
- Modify: `graph.py`

- [ ] **Step 1: Update `graph.py`**

Replace the file contents with:

```python
from langgraph.graph import StateGraph

from state import AgentState

from agents.profile_agent import profile_agent
from agents.retrieval_agent import retrieval_agent
from agents.conflict_agent import conflict_agent
from agents.reasoning_agent import reasoning_agent
from agents.policy_agent import policy_agent
from agents.explanation_agent import explanation_agent


builder = StateGraph(AgentState)

builder.add_node("profile", profile_agent)
builder.add_node("retrieve", retrieval_agent)
builder.add_node("conflict", conflict_agent)
builder.add_node("reason", reasoning_agent)
builder.add_node("policy", policy_agent)
builder.add_node("explain", explanation_agent)


builder.set_entry_point("profile")

builder.add_edge("profile", "retrieve")
builder.add_edge("retrieve", "conflict")
builder.add_edge("conflict", "reason")
builder.add_edge("reason", "policy")
builder.add_edge("policy", "explain")


graph = builder.compile()
```

- [ ] **Step 2: Update `tests/e2e/test_advisory_flow.py` to stop patching the now-removed legacy hook**

If Slice 2's Task 6 didn't already remove the `monkeypatch.setattr(retrieval_agent, "detect_conflicts", ...)` lines from `test_advisory_flow.py`, remove them now. The new graph doesn't depend on that path. The two existing tests (`test_advisory_flow_returns_policy_checked_answer` and `test_advisory_flow_handles_empty_retrieval`) should pass as-is once those lines are gone, because the new `conflict_agent` produces no records for those fixtures (no duplicate keys).

The middle test (`test_advisory_flow_surfaces_uncertainty_for_policy_ambiguity`) currently relies on `monkeypatch.setattr(retrieval_agent, "detect_conflicts", lambda candidates: ["Quota conflict for ..."])` to populate `state.conflicts`. After Slice 2 that hook is gone. **Replace that test** with one that constructs two same-key candidates with different quotas so the new conflict node naturally emits an unresolved outcome:

```python
def test_advisory_flow_surfaces_uncertainty_for_unresolved_conflict(monkeypatch):
    def _conflicting_candidates():
        from datetime import datetime
        c1 = CandidateProgram(
            candidate_id="hust:2026:computer_science:thpt_score:a",
            school_id="hust", school_name="HUST", admission_year=2026,
            program_id="computer_science", program_name="Khoa hoc May tinh",
            admission_method="thpt_score",
            subject_combinations=["A00", "A01"],
            quota={"total": 100},
            evidence=[Evidence(source_url="https://a/", school_name="HUST",
                               admission_year=2026, field_name="record", trust_level=2)],
        )
        c2 = CandidateProgram(
            candidate_id="hust:2026:computer_science:thpt_score:b",
            school_id="hust", school_name="HUST", admission_year=2026,
            program_id="computer_science", program_name="Khoa hoc May tinh",
            admission_method="thpt_score",
            subject_combinations=["A00", "A01"],
            quota={"total": 200},
            evidence=[Evidence(source_url="https://b/", school_name="HUST",
                               admission_year=2026, field_name="record", trust_level=2)],
        )
        return [c1, c2]

    class FakeGateway:
        def __init__(self):
            self.requests = []
        def run(self, request):
            self.requests.append(request)
            # First call: resolution_agent. Return medium → unresolved.
            if request.agent_name == "resolution_agent":
                return InferenceResult(
                    agent_name="resolution_agent", model="x", provider="fake",
                    content="{}", parsed_data={
                        "chosen_source_url": "https://a/",
                        "confidence": "medium",
                        "rationale": "uncertain",
                    },
                )
            # Second call: policy_agent ambiguity.
            return InferenceResult(
                agent_name="policy_agent", model="x", provider="fake",
                content="{}", parsed_data={
                    "warnings": ["Conflict remains."],
                    "requires_human_verification": True,
                },
            )

    fake_gateway = FakeGateway()
    monkeypatch.setattr(profile_agent_module, "build_profile_with_gateway",
                        lambda user_query, gateway: _mock_profile())
    monkeypatch.setattr(retrieval_agent, "fetch_candidates",
                        lambda filters, limit=100: _conflicting_candidates())
    monkeypatch.setattr(policy_agent_module, "build_default_gateway", lambda: fake_gateway)
    import agents.conflict_agent as conflict_module
    monkeypatch.setattr(conflict_module, "build_default_gateway", lambda: fake_gateway)
    # The Evidence agent's DB call must not run in this graph test.
    monkeypatch.setattr(
        conflict_module, "package_evidence",
        lambda record, raw_candidates, admission_year: record.options,
    )

    state = AgentState(user_query="Em duoc 27 diem A00 muon hoc HUST", admission_year=2026)
    result = graph.invoke(state)

    policy = result["policy_decision"]
    assert "retrieval_conflicts_detected" in policy.policy_flags
    assert any("Conflict" in w for w in policy.warnings)
    assert result["uncertainty_reasons"] == ["policy_ambiguity_requires_verification"]
    assert len(result["resolution_outcomes"]) == 1
    assert result["resolution_outcomes"][0].status == "unresolved"
```

- [ ] **Step 3: Run the advisory flow tests**

Run: `pytest tests/e2e/test_advisory_flow.py -v`

Expected: all 3 tests PASS.

- [ ] **Step 4: Run the full agent + e2e suite**

Run: `pytest tests/agents/ tests/e2e/ -v`

Expected: green.

- [ ] **Step 5: Commit**

```powershell
git add graph.py tests/e2e/test_advisory_flow.py
git commit -m "feat(graph): wire conflict node between retrieve and reason"
```

---

## Task 8: Reasoning agent — block uncertain-quota candidates from the top band

**Files:**
- Modify: `services/reasoning_service.py`
- Modify: `tests/agents/test_reasoning_agent.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/agents/test_reasoning_agent.py`:

```python
def test_reasoning_agent_blocks_data_uncertain_quota_from_safe_band():
    state = AgentState(user_query="test")
    state.student_profile = StudentProfile(
        total_score=28,
        subject_combination="A00",
        preferred_majors=["computer_science"],
        preferred_schools=["hust"],
    )
    state.retrieved_programs = [
        CandidateProgram(
            candidate_id="hust:2026:computer_science:thpt_score",
            school_id="hust", school_name="HUST", admission_year=2026,
            program_id="computer_science", program_name="Khoa hoc May tinh",
            admission_method="thpt_score", subject_combinations=["A00"],
            data_uncertain_fields=["quota"],
            evidence=[Evidence(source_url="https://x/", school_name="HUST",
                               admission_year=2026, field_name="record", confidence_score=0.9)],
        )
    ]

    output = reasoning_agent(state)

    rec = output.ranked_recommendations[0]
    # Even though the profile is strong, the uncertain quota blocks the top band.
    assert rec.band != "safe"
    assert any(
        "Số liệu hạn ngạch chưa được xác nhận" in c for c in rec.cautions
    )
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/agents/test_reasoning_agent.py -v`

Expected: the new test FAILs (the candidate likely gets `band="safe"` and lacks the Vietnamese caution).

- [ ] **Step 3: Update `services/reasoning_service.py`**

In `_score_to_band`, the function does not see `data_uncertain_fields`. Two options: pass a flag to `_score_to_band`, or apply the demotion inside `reason_candidates`. Use the latter; it keeps `_score_to_band` pure.

In `reason_candidates`, after computing `band = _score_to_band(score, has_missing_critical)`, add:

```python
        if candidate.data_uncertain_fields:
            cautions.append("Số liệu hạn ngạch chưa được xác nhận giữa các nguồn.")
            if band == "safe":
                band = "match"
```

The demotion rule: an uncertain field cannot ride in the top "safe" band. Lower bands keep their classification. The Vietnamese caution always appears so the explanation surfaces uncertainty.

- [ ] **Step 4: Run the tests**

Run: `pytest tests/agents/test_reasoning_agent.py -v`

Expected: all PASS, including the existing two.

- [ ] **Step 5: Commit**

```powershell
git add services/reasoning_service.py tests/agents/test_reasoning_agent.py
git commit -m "feat(reasoning): demote data-uncertain candidates from the safe band"
```

---

## Task 9: Explanation agent — append "Xác minh dữ liệu" section

**Files:**
- Modify: `services/explanation_service.py`
- Modify: `agents/explanation_agent.py`
- Modify: `tests/agents/test_explanation_agent.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/agents/test_explanation_agent.py`:

```python
from datetime import datetime

from services.conflict.models import EvidenceOption, ResolutionOutcome


def _resolved_outcome():
    chosen = EvidenceOption(
        evidence_id="https://hust.edu.vn/cs|quota",
        source_url="https://hust.edu.vn/cs",
        value=100, trust_level=3,
    )
    rejected = EvidenceOption(
        evidence_id="https://other/|quota",
        source_url="https://other/", value=200, trust_level=1,
    )
    return ResolutionOutcome(
        status="resolved", resolved_value=100,
        chosen_evidence=chosen, rejected_evidence=[rejected],
        rationale="Chọn vì nguồn có mức độ tin cậy cao hơn (nguồn: https://hust.edu.vn/cs).",
        conflict_key="hust:2026:cs:thpt_score",
        field_name="quota",
    )


def _unresolved_outcome():
    return ResolutionOutcome(
        status="unresolved", resolved_value=None, chosen_evidence=None,
        rejected_evidence=[
            EvidenceOption(evidence_id="a|quota", source_url="https://uet.vnu.edu.vn/ee",
                           value=50, trust_level=2),
            EvidenceOption(evidence_id="b|quota", source_url="https://vnu.edu.vn/proposal.pdf",
                           value=70, trust_level=2),
        ],
        rationale="indecisive", uncertainty_reason="conflict_unresolved_quota",
        conflict_key="uet:2026:ee:thpt_score", field_name="quota",
    )


def test_explanation_appends_verification_section_for_resolved():
    state = AgentState(user_query="Tu van")
    state.student_profile = StudentProfile(total_score=27, subject_combination="A00")
    state.retrieved_programs = [
        CandidateProgram(
            candidate_id="hust:1", school_id="hust", school_name="HUST",
            admission_year=2026, program_id="cs", program_name="Khoa hoc May tinh",
            admission_method="thpt_score",
            evidence=[Evidence(source_url="https://hust.edu.vn/cs", school_name="HUST",
                               admission_year=2026, field_name="record")],
        )
    ]
    state.resolution_outcomes = [_resolved_outcome()]

    output = explanation_agent(state)

    assert "## Xác minh dữ liệu" in output.final_answer
    assert "100" in output.final_answer  # resolved value
    assert "Trang tuyển sinh HUST" in output.final_answer  # chosen source label


def test_explanation_appends_verification_section_for_unresolved():
    state = AgentState(user_query="Tu van")
    state.student_profile = StudentProfile(total_score=27, subject_combination="A00")
    state.retrieved_programs = []
    state.resolution_outcomes = [_unresolved_outcome()]

    output = explanation_agent(state)

    assert "## Xác minh dữ liệu" in output.final_answer
    assert "Trang chương trình UET (ĐHQGHN)" in output.final_answer
    assert "Đề án tuyển sinh ĐHQGHN" in output.final_answer
    assert "xác minh trực tiếp với trường" in output.final_answer


def test_explanation_omits_verification_section_when_no_outcomes():
    state = AgentState(user_query="Tu van")
    state.student_profile = StudentProfile(total_score=27, subject_combination="A00")
    state.retrieved_programs = []
    state.resolution_outcomes = []
    output = explanation_agent(state)
    assert "Xác minh dữ liệu" not in (output.final_answer or "")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/agents/test_explanation_agent.py -v`

Expected: 3 new tests FAIL — the section is not yet emitted.

- [ ] **Step 3: Add the verification-section renderer to `services/explanation_service.py`**

Add at the top of the file:

```python
from services.conflict.models import ResolutionOutcome
from services.conflict.source_labels import label_for_source
```

Add this helper at module level:

```python
def _render_verification_section(outcomes: List[ResolutionOutcome], candidates: List[CandidateProgram]) -> List[str]:
    if not outcomes:
        return []

    candidate_by_key: Dict[str, CandidateProgram] = {}
    for c in candidates:
        key = f"{c.school_id}:{c.admission_year}:{c.program_id or c.program_name}:{c.admission_method or 'unknown_method'}"
        candidate_by_key.setdefault(key, c)

    lines: List[str] = ["", "## Xác minh dữ liệu"]
    for outcome in outcomes:
        candidate = candidate_by_key.get(outcome.conflict_key or "")
        school = candidate.school_name if candidate else (outcome.conflict_key or "")
        program = candidate.program_name if candidate else (outcome.conflict_key or "")

        if outcome.status == "resolved" and outcome.chosen_evidence is not None:
            chosen_label = label_for_source(outcome.chosen_evidence.source_url)
            rejected_values = ", ".join(
                f"{label_for_source(opt.source_url)}: {opt.value}"
                for opt in outcome.rejected_evidence
            )
            prefix = (
                "Hệ thống cần đối chiếu thêm để quyết định"
                if outcome.rationale.startswith("LLM tiebreaker:")
                else "Hệ thống tìm thấy nhiều nguồn báo cáo khác nhau"
            )
            lines.append(
                f"- Hạn ngạch ngành {program} tại {school}: {prefix}. "
                f"Chúng tôi sử dụng giá trị {outcome.resolved_value} từ {chosen_label}. "
                f"Nguồn khác báo cáo: {rejected_values or 'không có'}."
            )
        else:
            sources_text = "; ".join(
                f"{label_for_source(opt.source_url)} báo {opt.value}"
                for opt in outcome.rejected_evidence
            )
            lines.append(
                f"- Hạn ngạch ngành {program} tại {school}: hệ thống tìm thấy thông tin mâu thuẫn "
                f"giữa các nguồn ({sources_text}). Bạn nên xác minh trực tiếp với trường trước khi đăng ký."
            )
    return lines
```

Update `build_explanation`'s signature and body:

```python
def build_explanation(
    profile: StudentProfile,
    recommendations: List[RankedRecommendation],
    candidates: List[CandidateProgram],
    policy: Optional[PolicyDecision],
    resolution_outcomes: Optional[List[ResolutionOutcome]] = None,
) -> str:
    # ... existing body unchanged ...

    # After the existing follow-up line and before `return "\n".join(lines)`:
    lines.extend(_render_verification_section(resolution_outcomes or [], candidates))

    return "\n".join(lines)
```

- [ ] **Step 4: Update `agents/explanation_agent.py` to pass `resolution_outcomes`**

Replace with:

```python
from services.explanation_service import build_explanation
from state import AgentState


def explanation_agent(state: AgentState):
    state.final_answer = build_explanation(
        profile=state.student_profile,
        recommendations=state.ranked_recommendations,
        candidates=state.retrieved_programs,
        policy=state.policy_decision,
        resolution_outcomes=state.resolution_outcomes,
    )
    state.advisory = state.final_answer
    state.citations = [ev for program in state.retrieved_programs for ev in program.evidence]
    return state
```

- [ ] **Step 5: Run the tests**

Run: `pytest tests/agents/test_explanation_agent.py -v`

Expected: all PASS, including the existing two.

- [ ] **Step 6: Commit**

```powershell
git add services/explanation_service.py agents/explanation_agent.py tests/agents/test_explanation_agent.py
git commit -m "feat(explanation): append 'Xác minh dữ liệu' section for conflict outcomes"
```

---

## Task 10: Policy agent integration sanity-check test

**Files:**
- Modify: `tests/agents/test_policy_agent.py`

This task adds a test confirming the legacy compatibility shim from `conflict_agent` (only unresolved/LLM-tiebroken outcomes populate `state.conflicts`) drives the ambiguity escalation correctly. The policy agent code itself is unchanged.

- [ ] **Step 1: Write the test**

Append to `tests/agents/test_policy_agent.py`:

```python
def test_policy_agent_does_not_escalate_when_only_resolved_outcomes_present(monkeypatch):
    # Even with resolution_outcomes present, if state.conflicts is empty (because the
    # conflict_agent did not populate the shim for deterministically resolved cases),
    # the policy agent must NOT call interpret_policy_ambiguity.
    import agents.policy_agent as pa
    called = []
    monkeypatch.setattr(pa, "interpret_policy_ambiguity",
                        lambda *args, **kwargs: called.append(args) or {"warnings": [], "requires_human_verification": False})
    monkeypatch.setattr(pa, "build_default_gateway", lambda: object())

    state = AgentState(user_query="Tu van")
    state.student_profile = StudentProfile(total_score=27, subject_combination="A00")
    state.retrieved_programs = []
    state.conflicts = []  # legacy shim empty (resolved case)

    policy_agent(state)
    assert called == []


def test_policy_agent_escalates_when_unresolved_outcome_populates_shim(monkeypatch):
    import agents.policy_agent as pa
    monkeypatch.setattr(pa, "interpret_policy_ambiguity",
                        lambda *args, **kwargs: {"warnings": ["w"], "requires_human_verification": True})
    monkeypatch.setattr(pa, "build_default_gateway", lambda: object())

    state = AgentState(user_query="Tu van")
    state.student_profile = StudentProfile(total_score=27, subject_combination="A00")
    state.retrieved_programs = []
    state.conflicts = ["Unresolved quota conflict for hust:2026:cs:thpt_score: ..."]

    output = policy_agent(state)
    assert "policy_ambiguity_requires_verification" in output.uncertainty_reasons
```

- [ ] **Step 2: Run the test**

Run: `pytest tests/agents/test_policy_agent.py -v`

Expected: all PASS.

- [ ] **Step 3: Commit**

```powershell
git add tests/agents/test_policy_agent.py
git commit -m "test(policy): verify shim drives ambiguity escalation only for unresolved cases"
```

---

## Task 11: Add a resolved-case end-to-end graph test

**Files:**
- Modify: `tests/e2e/test_advisory_flow.py`

- [ ] **Step 1: Add the new test**

Append to `tests/e2e/test_advisory_flow.py`:

```python
def test_advisory_flow_resolves_quota_conflict_and_surfaces_rationale(monkeypatch):
    # Two same-key candidates, one trust=3 one trust=1 → deterministically resolved.
    def _conflicting_candidates():
        c1 = CandidateProgram(
            candidate_id="hust:2026:computer_science:thpt_score:a",
            school_id="hust", school_name="HUST", admission_year=2026,
            program_id="computer_science", program_name="Khoa hoc May tinh",
            admission_method="thpt_score", subject_combinations=["A00", "A01"],
            quota={"total": 100},
            evidence=[Evidence(source_url="https://hust.edu.vn/cs", school_name="HUST",
                               admission_year=2026, field_name="record", trust_level=3)],
        )
        c2 = CandidateProgram(
            candidate_id="hust:2026:computer_science:thpt_score:b",
            school_id="hust", school_name="HUST", admission_year=2026,
            program_id="computer_science", program_name="Khoa hoc May tinh",
            admission_method="thpt_score", subject_combinations=["A00", "A01"],
            quota={"total": 200},
            evidence=[Evidence(source_url="https://other/", school_name="HUST",
                               admission_year=2026, field_name="record", trust_level=1)],
        )
        return [c1, c2]

    monkeypatch.setattr(profile_agent_module, "build_profile_with_gateway",
                        lambda user_query, gateway: _mock_profile())
    monkeypatch.setattr(retrieval_agent, "fetch_candidates",
                        lambda filters, limit=100: _conflicting_candidates())
    import agents.conflict_agent as conflict_module
    monkeypatch.setattr(conflict_module, "build_default_gateway", lambda: object())
    monkeypatch.setattr(
        conflict_module, "package_evidence",
        lambda record, raw_candidates, admission_year: record.options,
    )

    state = AgentState(user_query="Em duoc 27 diem A00 muon hoc HUST", admission_year=2026)
    result = graph.invoke(state)

    assert "## Xác minh dữ liệu" in result["final_answer"]
    assert "100" in result["final_answer"]
    assert result["resolution_outcomes"][0].status == "resolved"
    assert result["resolution_outcomes"][0].resolved_value == 100
    # Resolved deterministically → legacy shim stays empty → policy ambiguity NOT triggered.
    assert "policy_ambiguity_requires_verification" not in result["uncertainty_reasons"]
```

- [ ] **Step 2: Run the test**

Run: `pytest tests/e2e/test_advisory_flow.py -v`

Expected: all 4 PASS (3 existing + 1 new).

- [ ] **Step 3: Commit**

```powershell
git add tests/e2e/test_advisory_flow.py
git commit -m "test(e2e): assert end-to-end resolution rationale surfaces"
```

---

## Task 12: Full-suite regression sweep

- [ ] **Step 1: Run all tests except real-data**

Run: `pytest tests/ -v --ignore=tests/ingestion/test_db_writer_per_source_upsert.py`

Expected: green.

- [ ] **Step 2: If anything fails, fix at root cause**

Most likely failures and their fixes:
- Existing test imports `detect_conflicts` from `services.retrieval_service` — that function is still defined, so the import works. If a test asserts its output shape, the test is now obsolete (slice 2's retrieval_agent stopped calling it; this slice doesn't delete it but no longer relies on it). Leave the legacy `services.retrieval_service.detect_conflicts` function in place this phase; an explicit deletion is a future-phase cleanup.
- `tests/services/chat/*` tests that build an `AgentState` — they should be unaffected (new fields default to `[]`).
- `test_advisory_flow` middle test (the rewritten ambiguity test) — covered by Task 7 Step 2.

- [ ] **Step 3: Commit if any test fixes were required**

```powershell
git add -A
git commit -m "test: align suite with new conflict-resolution flow"
```

---

## Slice 3 Exit Gate

Before declaring Slice 3 complete:

1. `pytest tests/services/conflict/ -v` — all green (source_labels, evidence_agent, comparison_agent, resolution_agent, detection).
2. `pytest tests/agents/test_conflict_agent.py -v` — all green.
3. `pytest tests/services/test_conflict_resolution_service.py -v` — all green with the new contract.
4. `pytest tests/agents/test_reasoning_agent.py tests/agents/test_explanation_agent.py tests/agents/test_policy_agent.py -v` — all green.
5. `pytest tests/e2e/test_advisory_flow.py -v` — all green, including both new fixtures (resolved and unresolved).
6. `pytest tests/ -v --ignore=tests/ingestion/test_db_writer_per_source_upsert.py` — green overall.
7. The advisory graph runs `profile → retrieve → conflict → reason → policy → explain`.
8. A synthetic conflict fixture produces a `## Xác minh dữ liệu` section in `final_answer`.
9. Resolved deterministic outcomes do NOT populate `state.conflicts`; unresolved AND LLM-tiebroken outcomes DO.

After Slice 3, the system can demonstrate the full conflict-resolution flow on synthetic fixtures. Slice 4 binds that machinery to the real curated dataset and to the chat surface.

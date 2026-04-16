# Design Spec: Advisory Flow Reliability-First (Sprint Next)

## 1. Problem Statement

Current project already has a basic multi-agent advisory skeleton and simple use cases.  
For next sprint, the goal is to make advisory output reliable and policy-safe for high-school students by:

- Focusing on advisory flow: `user -> profile -> retrieval -> policy -> explanation`
- Scope-limiting to A00/A01 and CNTT-Kỹ thuật group
- Restricting recommendations strictly to configured top-10 Northern Vietnam universities
- Prioritizing citation quality and policy warnings over advanced ranking complexity

## 2. Scope and Non-Goals

### In Scope

1. Profile quality upgrades for better advisory inputs
2. Retrieval constraints and coverage diagnostics
3. Policy guardrails tied to MoET + university policy snapshots
4. Evidence/citation contract enforcement
5. Explainability improvements with mandatory warning/follow-up behavior
6. Minimal observability for auditing advisory decisions

### Out of Scope (This Sprint)

1. Full ingestion multi-agent orchestration redesign
2. Full conflict resolution multi-agent pipeline automation
3. Heavy ML/LLM ranking model redesign
4. UI/web chat productization

## 3. Recommended Approach

Choose **Reliability-first**:

- Keep existing heuristic ranking structure
- Strengthen correctness boundaries and policy safety
- Ensure every retained recommendation is evidence-backed
- Make every limitation explicit in final advisory text

Rationale: This aligns with sprint success criteria (trusted citations + clear policy warnings) and reduces risk of unsafe/overconfident admissions advice.

## 4. Architecture (Target Within Existing Codebase)

## 4.1 Advisory Orchestration

Continue using current graph node order:

`profile -> retrieve -> reason -> policy -> explain`

No graph topology change in this sprint; only node responsibilities are expanded with stricter contracts.

## 4.2 Component Responsibilities

### Profile Agent v2

- Expand `StudentProfile` enrichment for:
  - Academic strength indicators (existing score + optional normalized bands)
  - Capability/interest/career preference slots
- Add:
  - `profile_completeness_score`
  - `missing_critical_slots`

Critical profile slots for this sprint (fixed):

1. `total_score`
2. `subject_combination`
3. `preferred_majors`
4. `career_orientation`

### Retrieval Agent v2

- Enforce hard filter by:
  - `admission_year`
  - configured top-10 school allowlist
  - target major group (CNTT-Kỹ thuật)
- Return diagnostics:
  - `retrieval_coverage` (how many schools/programs matched)
  - `retrieval_missing_data` reasons when empty
- Owns population of `candidate.evidence[]` as authoritative source payload from canonical records

Deterministic CNTT-Kỹ thuật filter for this sprint:

- Include `program_id` in:
  - `computer_science`
  - `software_engineering`
  - `information_systems`
  - `computer_engineering`
  - `artificial_intelligence`
  - `data_science`
  - `cyber_security`

### Reasoning Agent v2

- Keep safe/match/reach heuristic bands
- Add reliability-aware penalties from evidence quality and conflict markers
- Preserve transparent reason/caution strings
- Does not mutate `candidate.evidence[]`; consumes read-only evidence from retrieval output

Penalty rule (deterministic):

- Base score remains existing heuristic output in range `[0, 1]`
- Apply penalties:
  - `-0.10` if any conflict marker exists for candidate
  - `-0.05` if best citation `trust_level == 3`
  - `-0.10` if best citation has `record_freshness_days > 45`
- Clamp final score to `[0, 1]`

### Policy Agent v2

- Evaluate using versioned policy snapshots (`school_id + year + version`)
- Guardrail rules:
  - Block definitive admission claims
  - Require warnings for missing critical profile
  - Require warnings for stale/conflicting data
- Filter out recommendations without minimum evidence quality
- Is the final gate for evidence threshold enforcement using retrieval-owned `candidate.evidence[]`

### Explanation Agent v2

- Produce structured advisory output:
  - Profile summary
  - Ranked recommendations
  - Evidence citations
  - Policy warnings
  - Explicit follow-up questions when critical slots are missing

### Observability Layer (Minimal)

- Add per-step decision trace for:
  - profile extraction summary
  - retrieval filters/results
  - policy flags and filtered recommendations
- Store logs for audit/debug; avoid introducing unrelated telemetry stack complexity.

## 4.3 Node Interface Contracts (Explicit)

| Node | Required Input | Required Output | Failure/Degrade Behavior |
|------|----------------|-----------------|---------------------------|
| profile | `user_query`, `admission_year` | `student_profile`, `missing_critical_slots`, `profile_completeness_score` | If extraction partial, keep flow running and mark missing slots |
| retrieve | `student_profile`, `admission_year`, `top10_school_ids` | `retrieved_programs`, `retrieval_filters`, `retrieval_coverage`, `retrieval_missing_data` | If no match, return empty list + reasons; no fabricated candidates |
| reason | `student_profile`, `retrieved_programs` | `eligibility_checks`, `ranked_recommendations` | If profile missing criticals, band can be `unknown` with cautions |
| policy | `student_profile`, `ranked_recommendations`, `retrieved_programs`, `policy_snapshot` | `policy_decision`, filtered `ranked_recommendations` | If policy snapshot missing/stale, must attach warning; still allow conservative answer |
| explain | `student_profile`, filtered recommendations, `policy_decision` | `final_answer`, `citations` | Must include warning/follow-up blocks when triggered |

## 5. Data Contracts

## 5.1 School Boundary Contract

- Central config: fixed list of top-10 Northern universities
- Any candidate outside list is discarded before recommendation stage
- Source of truth in codebase: `ingestion/config/top10_northern_schools.json`
- Ownership/update rule: edits must include policy snapshot version bump for affected schools
- Retrieval input `top10_school_ids` is loaded from this file at startup and cached in memory.
- Startup validation is mandatory: config must contain exactly 10 unique `school_id` values.
- Validation failure behavior: service starts in fail-closed mode for recommendations and emits `top10_config_invalid`.

## 5.2 Evidence Contract

Each recommendation candidate should carry normalized evidence fields:

- `source_url`
- `source_type`
- `published_at` (optional if unavailable)
- `trust_level`
- `record_freshness_days`
- `confidence_score`

Normative evidence threshold for this sprint (single source of truth):

1. `source_url` non-empty
2. `source_type` present
3. `trust_level >= 3` (scale 1-5)

Only candidates with at least one evidence entry meeting all 3 rules remain in final recommendations.  
`confidence_score` is advisory (ranking confidence adjustment only, not validity gate).

## 5.3 Policy Snapshot Contract

Policy records keyed by:

- `school_id`
- `admission_year`
- `policy_version`

Policy lookup failure or stale snapshots produce mandatory warnings.

Staleness definitions and criteria:

- `policy_snapshot_age_days`: days since policy snapshot was last synced.
- `record_freshness_days`: days since admission record source was published/updated.
- `policy_snapshot_age_days > 45` => mark stale and force warning in final advisory.
- `record_freshness_days > 45` => reduce confidence and force warning.

## 5.4 Policy Decision Payload Schema

Canonical policy payload:

```json
{
  "allow_answer": true,
  "blocked_claims": ["no_definitive_admission_answer"],
  "policy_flags": ["missing_critical_profile", "stale_policy_snapshot"],
  "warnings": [
    {
      "code": "policy_snapshot_unavailable",
      "severity": "high",
      "message": "Policy snapshot unavailable; verify official source."
    }
  ],
  "requires_follow_up": true,
  "allowed_candidate_ids": ["hust:2026:computer_science:thpt_score"]
}
```

## 5.5 Candidate Payload Contract (retrieve -> reason -> policy)

```json
{
  "candidate_id": "school:year:program:method",
  "school_id": "hust",
  "program_id": "computer_science",
  "admission_year": 2026,
  "admission_method": "thpt_score",
  "subject_combinations": ["A00", "A01"],
  "evidence": [
    {
      "source_url": "https://...",
      "source_type": "official_school_site",
      "trust_level": 5,
      "record_freshness_days": 12,
      "confidence_score": 0.88
    }
  ],
  "conflict_markers": ["quota_conflict"]
}
```

## 5.6 Conflict Marker Enum

Allowed `conflict_markers` values this sprint:

1. `quota_conflict`
2. `subject_combination_conflict`
3. `method_conflict`
4. `program_name_conflict`
5. `policy_snapshot_conflict`

## 6. Data Flow

1. User query enters profile stage.
2. Profile extraction computes values + missing critical slots.
3. Retrieval applies strict scope filters (year/top-10/major group).
4. Reasoning computes fit bands and explanation artifacts.
5. Policy checks safety, freshness, evidence sufficiency, and legal wording constraints.
6. Explanation emits final advisory with citations and warnings.

## 7. Error Handling and Safety Behavior

1. **Empty retrieval**: no fabricated recommendations; return explicit “no matching programs” + what to refine.
2. **Missing critical profile**: allow advisory but force follow-up prompts and lower certainty language.
3. **Conflicting records**: keep conservative output; attach conflict warning and lower confidence.
4. **Stale data**: require source re-verification warning in output.
5. **Insufficient evidence**: candidate removed before final recommendation list.
6. **Invalid or missing admission_year**: stop retrieval, return structured error and follow-up prompt for target admission year.
7. **Missing top-10 allowlist config**: fail closed (no recommendation output), return explicit system warning.
8. **Missing policy snapshot config**: allow conservative output, force warning `"policy_snapshot_unavailable"`.

Failure precedence (deterministic):

1. Config failures (`top10_config_invalid`) take highest precedence and force empty recommendations.
2. Retrieval emptiness handled next (`empty_retrieval`) with refinement guidance.
3. Policy/data freshness and conflict warnings are merged next.
4. Missing profile critical slots always set `requires_follow_up=true` regardless of other warnings.
5. Final output includes de-duplicated warnings sorted by severity: `high -> medium -> low`.

Structured error schema (for validation/fail-closed paths):

```json
{
  "error_code": "invalid_admission_year",
  "severity": "high",
  "message": "Admission year is missing or invalid.",
  "action_required": "Provide a valid admission year.",
  "retryable": true
}
```

## 8. Testing Strategy

## 8.1 Unit Tests

- Profile extraction completeness and missing slot detection
- Retrieval boundary enforcement (top-10 + year + major group)
- Policy filtering and warning behavior
- Explanation output sections and citation rendering

## 8.2 Integration Tests

End-to-end advisory flow cases:

1. Complete profile + valid evidence
2. Missing profile slots
3. Conflicting candidate facts
4. Stale policy/data conditions
5. Definitive-claim user prompt (must be guarded)

## 8.3 Regression Fixtures

- A00/A01 CNTT-Kỹ thuật fixture set as sprint baseline for deterministic checks.

## 9. Sprint Feature Stack (Basic -> Complex)

1. **Basic**
   - Top-10 school boundary in retrieval
   - Profile completeness scoring and missing critical slots
2. **Basic+**
   - Standardized citation object and evidence threshold enforcement
   - Mandatory warning/follow-up generation
3. **Intermediate**
   - Versioned policy snapshot lookup
   - Freshness and conflict-aware policy warnings
4. **Intermediate+**
   - Minimal advisory trace/audit logging
   - Reliability-aware adjustment in ranking confidence

## 10. Success Criteria (Sprint Done)

1. Every kept recommendation includes at least one valid citation.
2. Advisory always includes policy warning for missing critical profile or stale/conflicting data.
3. No recommendation outside configured top-10 school list.
4. Follow-up questions are generated whenever critical profile slots are missing.
5. If policy snapshot config is missing/unavailable, output must still be generated in conservative mode with warning `policy_snapshot_unavailable`.


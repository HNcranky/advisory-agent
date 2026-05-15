# Slice 1 — Schema fix + dataset curation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the per-logical-program UNIQUE constraint on `canonical_admission_records` with a per-source one so distinct sources for the same program coexist as separate rows, then curate a real HUST + VNU-UET corpus producing at least 3 organic quota conflicts.

**Architecture:** Add migration `010_canonical_records_per_source.sql` that drops `UNIQUE(school_id, admission_year, program_id, admission_method)` and adds `UNIQUE(school_id, admission_year, program_id, admission_method, source_url)`. Update `ingestion/storage/db_writer.py:save_canonical_records` to use the new conflict target. Then curate real sources for HUST + VNU-UET and export the resulting DB rows to `tests/e2e/fixtures/real_dataset_dump.sql`. This slice is the hard prerequisite for the entire phase: without it, the writer silently de-duplicates the conflict signal.

**Tech Stack:** PostgreSQL, psycopg2, existing ingestion pipeline (`ingestion/fetchers/`, `ingestion/parsers/`, `ingestion/storage/`), pytest.

---

## File Structure

- Create: `db/migrations/010_canonical_records_per_source.sql` — schema migration.
- Modify: `ingestion/storage/db_writer.py` (function `save_canonical_records`, the `ON CONFLICT (...)` clause around lines 181–194).
- Create: `tests/ingestion/test_db_writer_per_source_upsert.py` — integration test against a local Postgres or a transactional rollback test that exercises the new conflict target.
- Create: `docs/superpowers/dataset_curation_log.md` — running log of pre-flight findings (URLs visited, programs aligned, quota values observed). Not test code; an artifact for the thesis appendix.
- Create: `tests/e2e/fixtures/real_dataset_dump.sql` — one-time `pg_dump --data-only --inserts` of curated rows. Gating artifact for Slice 4.

---

## Task 1: Schema migration

**Files:**
- Create: `db/migrations/010_canonical_records_per_source.sql`

- [ ] **Step 1: Write the migration SQL**

Create `db/migrations/010_canonical_records_per_source.sql` with this exact content:

```sql
-- 010_canonical_records_per_source.sql
-- Replace per-logical-program uniqueness with per-source uniqueness so that
-- distinct sources for the same (school, year, program, method) coexist as
-- separate rows. This is the precondition for cross-source conflict detection.

BEGIN;

-- Drop the old per-logical-program uniqueness.
-- The constraint name follows the default convention used by CREATE TABLE ... UNIQUE(...);
-- if your environment renamed it, adjust before running.
ALTER TABLE canonical_admission_records
    DROP CONSTRAINT IF EXISTS canonical_admission_records_school_id_admission_year_program_id_admission_method_key;

-- Belt-and-suspenders: drop any other unique index on the same tuple.
DROP INDEX IF EXISTS canonical_admission_records_school_id_admission_year_program_id_admission_method_key;

-- Add the new per-source uniqueness.
ALTER TABLE canonical_admission_records
    ADD CONSTRAINT canonical_admission_records_per_source_unique
    UNIQUE (school_id, admission_year, program_id, admission_method, source_url);

COMMIT;
```

- [ ] **Step 2: Verify migration applies cleanly against an empty DB**

Run (from repo root, in a PowerShell shell with PG env vars set per `QUICKSTART.md`):

```powershell
psql $env:DATABASE_URL -f db/migrations/005_canonical_programs.sql
psql $env:DATABASE_URL -f db/migrations/010_canonical_records_per_source.sql
psql $env:DATABASE_URL -c "\d canonical_admission_records" | Select-String "UNIQUE"
```

Expected: output mentions `canonical_admission_records_per_source_unique` and includes `source_url`. The old 4-tuple constraint is not listed.

- [ ] **Step 3: Verify migration applies cleanly against a DB that already had old data**

Run:

```powershell
psql $env:DATABASE_URL -f db/migrations/005_canonical_programs.sql
psql $env:DATABASE_URL -c "INSERT INTO canonical_admission_records (school_id, school_name_canonical, admission_year, program_id, admission_method, source_url) VALUES ('hust',  'HUST', 2026, 'cs', 'thpt_score', 'https://a.example/');"
psql $env:DATABASE_URL -f db/migrations/010_canonical_records_per_source.sql
psql $env:DATABASE_URL -c "INSERT INTO canonical_admission_records (school_id, school_name_canonical, admission_year, program_id, admission_method, source_url) VALUES ('hust', 'HUST', 2026, 'cs', 'thpt_score', 'https://b.example/');"
psql $env:DATABASE_URL -c "SELECT COUNT(*) FROM canonical_admission_records WHERE school_id='hust';"
```

Expected: the second insert succeeds (different `source_url`) and final count is 2. The old constraint would have made the second insert collide.

- [ ] **Step 4: Commit**

```powershell
git add db/migrations/010_canonical_records_per_source.sql
git commit -m "feat(db): per-source uniqueness on canonical_admission_records"
```

---

## Task 2: Writer-side conflict target update

**Files:**
- Modify: `ingestion/storage/db_writer.py` (lines 172–214 inside `save_canonical_records`)
- Create: `tests/ingestion/__init__.py` (if missing)
- Create: `tests/ingestion/test_db_writer_per_source_upsert.py`

- [ ] **Step 1: Write the failing integration test**

Create `tests/ingestion/test_db_writer_per_source_upsert.py`:

```python
import os
import pytest

from ingestion.models.pipeline_models import NormalizedAdmissionRecord
from ingestion.storage.db_writer import save_canonical_records
from ingestion.storage.db_connection import get_cursor


pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="Requires DATABASE_URL pointing at a postgres test instance",
)


def _record(source_url: str, quota_value: int) -> NormalizedAdmissionRecord:
    return NormalizedAdmissionRecord(
        school_id="test_school",
        school_name_canonical="Test School",
        admission_year=2026,
        program_id="test_program",
        program_name_canonical="Test Program",
        program_name_raw="Test Program",
        admission_method="thpt_score",
        admission_method_raw="thpt_score",
        subject_combinations=[],
        quota={"total": quota_value},
        deadline=None,
        metadata={},
        tuition=None,
        source_url=source_url,
        source_trust_level=2,
        confidence_score=0.9,
    )


def test_distinct_sources_coexist():
    # Clean state
    with get_cursor() as cur:
        cur.execute("DELETE FROM canonical_admission_records WHERE school_id='test_school'")

    save_canonical_records([_record("https://a.example/", 100)])
    save_canonical_records([_record("https://b.example/", 200)])

    with get_cursor(commit=False) as cur:
        cur.execute(
            "SELECT source_url, quota FROM canonical_admission_records "
            "WHERE school_id='test_school' ORDER BY source_url"
        )
        rows = cur.fetchall()

    assert len(rows) == 2
    assert rows[0][0] == "https://a.example/"
    assert rows[1][0] == "https://b.example/"


def test_same_source_upserts():
    with get_cursor() as cur:
        cur.execute("DELETE FROM canonical_admission_records WHERE school_id='test_school'")

    save_canonical_records([_record("https://a.example/", 100)])
    save_canonical_records([_record("https://a.example/", 150)])

    with get_cursor(commit=False) as cur:
        cur.execute(
            "SELECT quota FROM canonical_admission_records "
            "WHERE school_id='test_school' AND source_url='https://a.example/'"
        )
        rows = cur.fetchall()

    assert len(rows) == 1
    assert rows[0][0]["total"] == 150
```

Note: `NormalizedAdmissionRecord` field names should match `ingestion/models/pipeline_models.py`. If a field is required and not nullable, adjust the constructor call accordingly — open that file first to verify.

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/ingestion/test_db_writer_per_source_upsert.py -v`

Expected: `test_distinct_sources_coexist` fails because the existing writer uses `ON CONFLICT (school_id, admission_year, program_id, admission_method)` and de-duplicates the two rows down to one (the second row overwrites the first). The single remaining row has `quota={"total": 200}`.

- [ ] **Step 3: Update the writer's ON CONFLICT target**

In `ingestion/storage/db_writer.py`, locate the `ON CONFLICT (school_id, admission_year, program_id, admission_method)` clause inside `save_canonical_records` (around lines 181–194). Change exactly that line to:

```sql
                    ON CONFLICT (school_id, admission_year, program_id, admission_method, source_url)
```

Leave the rest of the `INSERT ... DO UPDATE SET ...` block unchanged.

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/ingestion/test_db_writer_per_source_upsert.py -v`

Expected: both tests PASS.

- [ ] **Step 5: Run the full ingestion test suite to confirm no regression**

Run: `pytest tests/ingestion/ -v`

Expected: all green. If any existing test relied on the old upsert collapsing distinct-source rows, fix the test fixture or assertion to reflect that distinct sources now coexist — this is the intended product change, not a regression.

- [ ] **Step 6: Commit**

```powershell
git add ingestion/storage/db_writer.py tests/ingestion/test_db_writer_per_source_upsert.py tests/ingestion/__init__.py
git commit -m "feat(ingestion): upsert canonical records per source_url"
```

---

## Task 3: Pre-flight check on VNU-UET sources

This task is a **manual investigation**, not code. Its only artifact is `docs/superpowers/dataset_curation_log.md`. Skip code execution but produce the document.

**Files:**
- Create: `docs/superpowers/dataset_curation_log.md`

- [ ] **Step 1: Inspect both sources by hand**

For VNU-UET (Đại học Công nghệ, ĐHQGHN):

- Visit `https://uet.vnu.edu.vn/` and locate the 2026 admission information page(s). Record the exact URL(s) of each program page.
- Locate the ĐHQGHN admission proposal PDF for 2026 (typically published on `https://vnu.edu.vn/` or a sub-page). Record the URL.

For HUST:

- The existing fixture is the 2026 HUST program data. Identify whether HUST publishes both a program page and a separate proposal PDF in 2026. If yes, both go in. If only one, supplement with a second HUST official channel (e.g., a HUST admission announcement page distinct from the program page).

- [ ] **Step 2: Confirm the three pre-flight criteria**

In `docs/superpowers/dataset_curation_log.md`, record:

```markdown
# Dataset Curation Log — Conflict-Aware Advisory V1

## Pre-flight (date: <YYYY-MM-DD>)

### VNU-UET

- Source A URL: <fill in>
- Source A reachable without auth? yes/no
- Source A format: HTML / PDF (text) / PDF (scanned)
- Source B URL: <fill in>
- Source B reachable without auth? yes/no
- Source B format: HTML / PDF (text) / PDF (scanned)

### Quota difference scan (>=3 programs required)

| Program (canonical name) | Source A quota | Source B quota | Differ? |
|---|---|---|---|
| ... | ... | ... | yes/no |
| ... | ... | ... | yes/no |
| ... | ... | ... | yes/no |

### Program-name alignment

- Are the program names in source A and source B unambiguously alignable (same canonical program)? yes/no
- If "no", which programs are ambiguous?

### Pre-flight verdict

- [ ] At least 3 programs have differing numeric quotas across two reachable, parseable sources.
- [ ] Program-name alignment is unambiguous.
- [ ] No need to swap school.

### HUST (mirror the same structure)

...
```

- [ ] **Step 3: Decide and record the bail-out path if any criterion fails**

If pre-flight fails, document which bail-out applies in the same log file:

- ĐHQGHN PDF unparseable → switch to two HTML sources for VNU-UET.
- Fewer than 3 organic conflicts → add NEU or FTU as a third school and re-run pre-flight for that school.
- Program-name alignment ambiguous → swap school before parser work begins.

Do **not** proceed to Task 4 until pre-flight produces a "verdict: proceed" line in the log.

- [ ] **Step 4: Commit the log**

```powershell
git add docs/superpowers/dataset_curation_log.md
git commit -m "docs: pre-flight dataset curation log for slice 1"
```

---

## Task 4: Source-registry entries

**Files:**
- Read first: `ingestion/config/sources.json` (or wherever existing source-registry rows live — verify by `Grep`-ing for `is_official` in `ingestion/config/`).
- Modify: the source-registry config file with new VNU-UET + ĐHQGHN entries.

- [ ] **Step 1: Locate the source-registry config**

Run: `Grep` for `is_official` under `ingestion/config/`. Open the file that defines the existing HUST registry rows.

- [ ] **Step 2: Add entries for VNU-UET sources**

Add one entry per URL captured in the pre-flight log. Fields to populate (match existing entries' shape):

- `source_id` — a stable slug, e.g., `uet_program_page`, `vnuhn_admission_proposal_2026`.
- `base_url` — the URL recorded in pre-flight.
- `is_official` — `true` for both (school's own page, parent university's proposal).
- `trust_level` — assign per existing convention: official proposal PDF > school admission homepage > school program page. Mirror the numeric scale already in use (read existing HUST entries first).
- `parser_profile` — the parser hint string referenced by the parser layer (e.g., `html_default`, `pdf_table`).

- [ ] **Step 3: Run the ingestion config validator if one exists**

Run: `pytest tests/ingestion/test_source_registry.py -v` if such a test exists. Otherwise verify by loading the config in a Python REPL with no exception.

- [ ] **Step 4: Commit**

```powershell
git add ingestion/config/<config-file>
git commit -m "feat(ingestion): register VNU-UET and ĐHQGHN admission sources"
```

---

## Task 5: Parser tuning for VNU-UET

This task is **conditional**: only do it if Task 3 pre-flight indicates the existing `html_parser.py` and `pdf_parser.py` are insufficient.

**Files:**
- Read first: `ingestion/parsers/html_parser.py`, `ingestion/parsers/pdf_parser.py`, `ingestion/parsers/hust_program_parser.py`.
- Possibly create: `ingestion/parsers/uet_program_parser.py` (only if the generic HTML parser cannot capture VNU-UET's program tables).

- [ ] **Step 1: Try the generic parsers first**

Run an ingestion dry-run for one VNU-UET program URL and one ĐHQGHN PDF URL using the existing CLI (check `main.py` or `scripts/` for the entry point — e.g., `python scripts/run_ingestion.py --source-id uet_program_page --dry-run`).

Expected: a `ParsedContent` or `ExtractedAdmissionFact` is produced with non-empty `program_name` and `quota_raw` fields.

- [ ] **Step 2: If generic parsing fails, create a thin school-specific parser**

Only if step 1 produces empty `quota_raw` or `program_name`, create `ingestion/parsers/uet_program_parser.py`. Mirror the shape of `ingestion/parsers/hust_program_parser.py`:

- Same function/class signature as the existing parser.
- Same return type (`ParsedContent` and/or `ExtractedAdmissionFact`).
- Hook into the parser dispatch table the same way HUST is hooked (verify by reading where `hust_program_parser` is imported and registered).

Do **not** redesign the parser pipeline. Add a parser; do not refactor.

- [ ] **Step 3: Add a small unit test for the new parser if one was created**

If a new parser file was created, add `tests/ingestion/test_uet_program_parser.py` with a fixture HTML snippet captured from one VNU-UET program page (saved under `tests/ingestion/fixtures/uet_program_sample.html`). Assert that the parser extracts the program name and quota raw value.

- [ ] **Step 4: Commit**

```powershell
git add ingestion/parsers/<new-or-modified-files> tests/ingestion/
git commit -m "feat(ingestion): tune parsers for VNU-UET admission sources"
```

---

## Task 6: Normalization — program-name → canonical program mapping

**Files:**
- Read first: `Grep` for `programs.json` to locate the canonical-program dictionary. Likely under `ingestion/config/`.
- Modify: that file, adding entries for VNU-UET's programs that surfaced in Task 3.

- [ ] **Step 1: Identify the program-name → canonical mapping file**

Run: `Grep` for `programs.json` across the repo.

- [ ] **Step 2: Add missing entries**

For each program named in the pre-flight log's quota-difference table that has no canonical mapping yet, add one entry. Match the existing entry shape exactly — open the file and copy the structure.

- [ ] **Step 3: Run any related normalization test**

Run: `pytest tests/ingestion/ -k normalize -v`

Expected: green.

- [ ] **Step 4: Commit**

```powershell
git add ingestion/config/programs.json
git commit -m "feat(ingestion): add VNU-UET program canonical mappings"
```

---

## Task 7: Ingest the curated corpus

**Files:**
- No new code. Run the ingestion CLI against the registered sources.

- [ ] **Step 1: Apply migrations to the target DB**

Run:

```powershell
psql $env:DATABASE_URL -f db/migrations/010_canonical_records_per_source.sql
```

(Earlier migrations are assumed already applied; if not, apply 001–009 first.)

- [ ] **Step 2: Run ingestion for HUST sources**

Use whatever ingestion CLI exists (`Grep` for the entry script — likely `scripts/run_ingestion.py` or invoked via `main.py`). Run for each HUST source registered.

- [ ] **Step 3: Run ingestion for VNU-UET sources**

Same as step 2, for VNU-UET program page(s) and the ĐHQGHN proposal PDF (or the bail-out HTML source).

- [ ] **Step 4: Verify the acceptance-criteria SQL check**

Run:

```powershell
psql $env:DATABASE_URL -c "
SELECT school_id, admission_year, program_id, admission_method,
       COUNT(*) AS row_count,
       COUNT(DISTINCT quota::text) AS distinct_quota_count,
       array_agg(source_url) AS sources
FROM canonical_admission_records
WHERE admission_year = 2026
GROUP BY school_id, admission_year, program_id, admission_method
HAVING COUNT(DISTINCT quota::text) >= 2
ORDER BY school_id, program_id;
"
```

Expected: at least 3 rows returned, covering both HUST and VNU-UET programs. Each row's `row_count` >= 2 and `distinct_quota_count` >= 2.

- [ ] **Step 5: If acceptance check fails, apply the appropriate bail-out**

If fewer than 3 program-method tuples meet the criteria:

- Re-check parser output: are quotas being extracted but normalized identically?
- Re-check source-registry trust levels: are both sources being ingested at all?
- If genuinely fewer than 3 organic conflicts exist, add a third school per the spec's bail-out and loop back to Task 3 pre-flight for that school.

Do **not** synthesize rows to meet the threshold. The dataset policy is absolute: no synthetic data in the evaluation dataset.

- [ ] **Step 6: Record the acceptance result in the curation log**

Append to `docs/superpowers/dataset_curation_log.md`:

```markdown
## Ingestion acceptance (date: <YYYY-MM-DD>)

- Acceptance SQL returned <N> conflict-bearing program-method tuples.
- Specifically:
  - `<school_id>` / `<program_id>` / `<admission_method>`: sources <A>, <B>, quotas <Qa>, <Qb>
  - ...
- Verdict: proceed / re-curate / slip.
```

- [ ] **Step 7: Commit the log update**

```powershell
git add docs/superpowers/dataset_curation_log.md
git commit -m "docs: record ingestion acceptance results"
```

---

## Task 8: Export curated rows as a fixture dump

**Files:**
- Create: `tests/e2e/fixtures/real_dataset_dump.sql`

- [ ] **Step 1: Export the relevant tables with data only**

Run:

```powershell
pg_dump --data-only --inserts --no-owner `
  --table=source_registry `
  --table=raw_documents `
  --table=extracted_facts `
  --table=canonical_admission_records `
  $env:DATABASE_URL > tests/e2e/fixtures/real_dataset_dump.sql
```

If `source_registry` is config rather than a table, omit that line. The critical tables are `raw_documents`, `extracted_facts`, `canonical_admission_records`.

- [ ] **Step 2: Verify the dump can be loaded into a clean DB**

Manual verification (on a scratch DB):

```powershell
createdb advisory_fixture_test
psql advisory_fixture_test -f db/migrations/001_source_registry.sql
psql advisory_fixture_test -f db/migrations/002_discovered_resources.sql
psql advisory_fixture_test -f db/migrations/003_raw_documents.sql
psql advisory_fixture_test -f db/migrations/004_extracted_facts.sql
psql advisory_fixture_test -f db/migrations/005_canonical_programs.sql
psql advisory_fixture_test -f db/migrations/006_rename_conditions_to_metadata.sql
psql advisory_fixture_test -f db/migrations/007_advisory_indexes.sql
psql advisory_fixture_test -f db/migrations/008_advisory_runs.sql
psql advisory_fixture_test -f db/migrations/009_chat_sessions.sql
psql advisory_fixture_test -f db/migrations/010_canonical_records_per_source.sql
psql advisory_fixture_test -f tests/e2e/fixtures/real_dataset_dump.sql
psql advisory_fixture_test -c "SELECT COUNT(*) FROM canonical_admission_records;"
dropdb advisory_fixture_test
```

Expected: load completes without error; count is non-zero and matches the source DB's count.

- [ ] **Step 3: Commit the dump**

```powershell
git add tests/e2e/fixtures/real_dataset_dump.sql
git commit -m "test: export curated HUST+VNU-UET corpus as e2e fixture"
```

---

## Slice 1 Exit Gate

Before declaring Slice 1 complete:

1. Migration 010 applied to dev DB without error.
2. `pytest tests/ingestion/test_db_writer_per_source_upsert.py` green.
3. The acceptance SQL in Task 7 Step 4 returns **at least 3** conflict-bearing program-method tuples on the dev DB.
4. `tests/e2e/fixtures/real_dataset_dump.sql` exists and loads cleanly into a fresh DB.
5. `docs/superpowers/dataset_curation_log.md` records a "proceed" verdict.

If any gate fails, Slice 1 is not done. Do **not** start Slice 2 work that depends on real data until the dump exists; Slice 2 can run on synthetic fixtures independently, but Slice 4 cannot.

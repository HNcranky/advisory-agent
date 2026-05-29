# Tech-debt Cleanup & Inference Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close eight technical debts from the 2026-05-29 review — make the Gemini gateway robust, activate the dormant LLM conflict tiebreaker, add safety logging, and remove dead code — without adding any user-facing feature beyond the tiebreaker.

**Architecture:** Three slice groups executed in risk order. **C** = pure cleanup (Pydantic v2, delete dead stub). **B** = observability/safety logging (mock-bypass, trace extractor error, SSL). **A** = inference hardening (provider error handling → call-site degradation → telemetry → tiebreaker). Group A is last because its later tasks depend on the earlier hardening.

**Tech Stack:** Python 3.12, Pydantic v2, LangGraph, FastAPI, Google Gemini (`google-genai`), pytest, PostgreSQL (Docker).

**Spec:** `docs/superpowers/specs/2026-05-29-tech-debt-cleanup-design.md`

**Branch:** `chore/stabilize-cleanup` (already created; spec already committed there).

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `ingestion/registry/models.py` | Modify | Pydantic v2 `model_config` |
| `ingestion/models/pipeline_models.py` | Modify | Pydantic v2 `model_config` |
| `services/reasoning_inference_service.py` | Delete | Empty abandoned stub |
| `tests/services/test_reasoning_inference_service.py` | Delete | Dead test scaffolding |
| `services/retrieval_service.py` | Modify | Warn on mock-bypass |
| `services/tracing/agent_tracer.py` | Modify | Log extractor-error path |
| `ingestion/config/settings.py` | Modify | `FETCH_VERIFY_SSL` setting |
| `ingestion/fetchers/http_fetcher.py` | Modify | SSL default + warning, drop blanket suppress |
| `services/inference/models.py` | Modify | Add `InferenceError` |
| `services/inference/providers/gemini_provider.py` | Modify | Error handling + `STRUCTURE_FAILURE` |
| `services/policy_inference_service.py` | Modify | Degrade on hard error |
| `services/profile_inference_service.py` | Modify | Degrade on hard error |
| `services/inference/gateway.py` | Modify | Telemetry wiring |
| `services/conflict/resolution_inference_service.py` | Create | LLM tiebreaker adapter |
| `agents/conflict_agent.py` | Modify | Inject gateway into `resolve()` |

Run all tests with the Docker Postgres DB up (matches the verified baseline):
```bash
docker compose up -d --wait db
.venv/Scripts/python.exe -m db.setup_db
```
Use `.venv/Scripts/python.exe -m pytest ...` for every test command below.

---

## GROUP C — Pure cleanup

### Task 1: Migrate Pydantic v1 `class Config` to v2 `model_config`

**Files:**
- Modify: `ingestion/registry/models.py:73-74`
- Modify: `ingestion/models/pipeline_models.py:48-50`
- Test: `tests/ingestion/test_pydantic_config_migration.py` (create)

- [ ] **Step 1: Write the failing test**

Create `tests/ingestion/test_pydantic_config_migration.py`:

```python
from ingestion.registry.models import SourceEntry
from ingestion.models.pipeline_models import FetchResult


def test_source_entry_uses_model_config():
    assert not hasattr(SourceEntry, "Config")
    assert SourceEntry.model_config.get("use_enum_values") is True


def test_fetch_result_uses_model_config():
    assert not hasattr(FetchResult, "Config")
    assert FetchResult.model_config.get("arbitrary_types_allowed") is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/ingestion/test_pydantic_config_migration.py -v`
Expected: FAIL — `SourceEntry` still has a `Config` attribute, so `not hasattr(...)` is False.

- [ ] **Step 3: Migrate `ingestion/registry/models.py`**

Ensure `ConfigDict` is imported (add to the existing pydantic import line, e.g. `from pydantic import BaseModel, Field, ConfigDict`). Replace lines 73-74:

```python
    class Config:
        use_enum_values = True
```

with (placed where the other fields end, as a class attribute):

```python
    model_config = ConfigDict(use_enum_values=True)
```

- [ ] **Step 4: Migrate `ingestion/models/pipeline_models.py`**

Ensure `ConfigDict` is imported. Replace lines 48-50:

```python
    class Config:

        arbitrary_types_allowed = True
```

with:

```python
    model_config = ConfigDict(arbitrary_types_allowed=True)
```

- [ ] **Step 5: Run the migration test + warning check**

Run: `.venv/Scripts/python.exe -m pytest tests/ingestion/test_pydantic_config_migration.py -v -W error::DeprecationWarning`
Expected: PASS, and no `PydanticDeprecatedSince20` error raised on import of these modules.

- [ ] **Step 6: Commit**

```bash
git add ingestion/registry/models.py ingestion/models/pipeline_models.py tests/ingestion/test_pydantic_config_migration.py
git commit -m "refactor: migrate Pydantic v1 Config to v2 model_config"
```

---

### Task 2: Delete the abandoned LLM-reasoning stub and its dead test

**Files:**
- Delete: `services/reasoning_inference_service.py`
- Delete: `tests/services/test_reasoning_inference_service.py`

- [ ] **Step 1: Confirm the stub is referenced nowhere in live code**

Run: `.venv/Scripts/python.exe -m pytest --co -q 2>&1 | head -5` (sanity: collection works now)
Then search for imports:
Run: `git grep -n "reasoning_inference_service"`
Expected: only matches are the empty module file and the commented import in the test file. No live import.

- [ ] **Step 2: Delete both files**

```bash
git rm services/reasoning_inference_service.py tests/services/test_reasoning_inference_service.py
```

- [ ] **Step 3: Run the suite to confirm nothing breaks**

Run: `.venv/Scripts/python.exe -m pytest -m "not integration" -q`
Expected: PASS, no collection/import errors, test count drops only by the deleted (already-skipped/commented) file.

- [ ] **Step 4: Commit**

```bash
git commit -m "chore: remove empty reasoning_inference_service stub and dead test"
```

---

## GROUP B — Observability & safety logging

### Task 3: Warn when mock retrieval bypasses the DB

**Files:**
- Modify: `services/retrieval_service.py` (top of file + `fetch_candidates`, around line 51-54)
- Test: `tests/services/test_retrieval_service.py` (add a test)

- [ ] **Step 1: Write the failing test**

Append to `tests/services/test_retrieval_service.py`:

```python
import logging

import services.retrieval_service as retrieval_service


def test_fetch_candidates_warns_on_mock_bypass(monkeypatch, caplog):
    monkeypatch.setattr(retrieval_service, "mock_conflicts_enabled", lambda: True)
    monkeypatch.setattr(
        retrieval_service, "build_mock_conflict_candidates", lambda filters, limit: []
    )

    with caplog.at_level(logging.WARNING, logger="services.retrieval_service"):
        result = retrieval_service.fetch_candidates({"admission_year": 2026})

    assert result == []
    assert any(
        "ADVISORY_MOCK_CONFLICTS" in record.message and "bypass" in record.message.lower()
        for record in caplog.records
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/services/test_retrieval_service.py::test_fetch_candidates_warns_on_mock_bypass -v`
Expected: FAIL — no warning is emitted.

- [ ] **Step 3: Add the logger and warning**

At the top of `services/retrieval_service.py`, after the existing imports, add (if not already present):

```python
import logging

logger = logging.getLogger(__name__)
```

In `fetch_candidates`, replace the mock branch (currently lines 52-54):

```python
    # ADVISORY_MOCK_CONFLICTS keeps local/demo conflict retrieval off the DB path.
    if mock_conflicts_enabled():
        return build_mock_conflict_candidates(filters=filters, limit=limit)
```

with:

```python
    # ADVISORY_MOCK_CONFLICTS keeps local/demo conflict retrieval off the DB path.
    if mock_conflicts_enabled():
        logger.warning(
            "ADVISORY_MOCK_CONFLICTS is enabled: bypassing the database and "
            "returning in-memory mock conflict candidates. Do NOT use in production."
        )
        return build_mock_conflict_candidates(filters=filters, limit=limit)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/services/test_retrieval_service.py::test_fetch_candidates_warns_on_mock_bypass -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add services/retrieval_service.py tests/services/test_retrieval_service.py
git commit -m "feat: warn when mock retrieval bypasses the database"
```

---

### Task 4: Log the trace extractor-error path

**Files:**
- Modify: `services/tracing/agent_tracer.py:36-39`
- Test: `tests/services/tracing/test_agent_tracer.py` (add a test)

- [ ] **Step 1: Write the failing test**

Append to `tests/services/tracing/test_agent_tracer.py`:

```python
import logging

from services.tracing.agent_tracer import traced


class _NoopRepo:
    def start_event(self, run_id, stage, sequence):
        return 1

    def complete_event(self, event_id, output_json):
        return None

    def fail_event(self, event_id, error_text):
        return None


class _State:
    trace_run_id = "run-1"


def test_traced_logs_when_extractor_raises(caplog):
    def agent_fn(state):
        return {"ok": True}

    def bad_extractor(result, state):
        raise ValueError("boom")

    wrapped = traced("reason", 3, bad_extractor, repository=_NoopRepo())(agent_fn)

    with caplog.at_level(logging.WARNING, logger="services.tracing.agent_tracer"):
        result = wrapped(_State())

    assert result == {"ok": True}
    assert any(
        "extractor" in record.message and "reason" in record.message
        for record in caplog.records
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/services/tracing/test_agent_tracer.py::test_traced_logs_when_extractor_raises -v`
Expected: FAIL — the extractor error is swallowed into `output_json` without a log record.

- [ ] **Step 3: Add the warning**

In `services/tracing/agent_tracer.py`, replace lines 36-39:

```python
            try:
                output_json = output_extractor(result, state)
            except Exception as exc:
                output_json = {"_extractor_error": repr(exc)}
```

with:

```python
            try:
                output_json = output_extractor(result, state)
            except Exception as exc:
                logger.warning("trace extractor failed for stage=%s: %r", stage, exc)
                output_json = {"_extractor_error": repr(exc)}
```

(`logger` already exists at line 8.)

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/services/tracing/test_agent_tracer.py::test_traced_logs_when_extractor_raises -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add services/tracing/agent_tracer.py tests/services/tracing/test_agent_tracer.py
git commit -m "feat: log trace extractor failures instead of swallowing them"
```

---

### Task 5: Make SSL verification explicit and configurable for crawling

**Files:**
- Modify: `ingestion/config/settings.py` (after line 59, with the other `FETCH_` settings)
- Modify: `ingestion/fetchers/http_fetcher.py:15` and `:24-29`, plus the `requests.get` call site
- Modify: `.env.example` (document the new flag)
- Test: `tests/ingestion/test_http_fetcher_ssl.py` (create)

- [ ] **Step 1: Write the failing test**

Create `tests/ingestion/test_http_fetcher_ssl.py`:

```python
import logging

import ingestion.fetchers.http_fetcher as http_fetcher


class _FakeResponse:
    content = b"<html>ok</html>"
    url = "https://example.test/page"
    headers = {"Content-Type": "text/html"}
    status_code = 200

    def raise_for_status(self):
        return None


def _patch_requests(monkeypatch):
    captured = {}

    def fake_get(url, headers=None, timeout=None, verify=None, allow_redirects=None):
        captured["verify"] = verify
        return _FakeResponse()

    monkeypatch.setattr(http_fetcher.requests, "get", fake_get)
    return captured


def test_http_fetch_warns_when_ssl_verification_disabled(monkeypatch, caplog):
    captured = _patch_requests(monkeypatch)

    with caplog.at_level(logging.WARNING, logger="ingestion.fetchers.http_fetcher"):
        http_fetcher.http_fetch("https://example.test/page", verify_ssl=False)

    assert captured["verify"] is False
    assert any("SSL verification" in record.message for record in caplog.records)


def test_http_fetch_no_warning_when_ssl_verification_enabled(monkeypatch, caplog):
    captured = _patch_requests(monkeypatch)

    with caplog.at_level(logging.WARNING, logger="ingestion.fetchers.http_fetcher"):
        http_fetcher.http_fetch("https://example.test/page", verify_ssl=True)

    assert captured["verify"] is True
    assert not any("SSL verification" in record.message for record in caplog.records)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/ingestion/test_http_fetcher_ssl.py -v`
Expected: FAIL — no "SSL verification" warning is emitted.

- [ ] **Step 3: Add the setting**

In `ingestion/config/settings.py`, after line 59 (`FETCH_RETRY_BACKOFF = ...`), add:

```python
# Default OFF: several official .gov.vn admission sources ship broken certs.
# Set ADVISORY_FETCH_VERIFY_SSL=true to enforce verification.
FETCH_VERIFY_SSL = os.getenv("ADVISORY_FETCH_VERIFY_SSL", "false").strip().lower() in (
    "1",
    "true",
    "yes",
)
```

- [ ] **Step 4: Update `http_fetcher.py`**

Remove the blanket suppression at line 15 (`urllib3.disable_warnings(...)`) — delete that line. Update the import block (lines 10-12) to also import the new setting:

```python
from ingestion.config.settings import (
    FETCH_TIMEOUT, FETCH_MAX_RETRIES, FETCH_RETRY_BACKOFF, USER_AGENTS,
    FETCH_VERIFY_SSL,
)
```

Change the signature default (line 28) from `verify_ssl: bool = False,` to:

```python
    verify_ssl: bool = FETCH_VERIFY_SSL,
```

Immediately after the `headers = {...}` block (before `last_exception = None`, around line 51), add:

```python
    if not verify_ssl:
        logger.warning(
            "SSL verification is disabled for %s. "
            "Set ADVISORY_FETCH_VERIFY_SSL=true to enforce it.",
            url,
        )
```

(`logger` already exists at line 17; `urllib3` import may now be unused — remove the `import urllib3` line at the top if so.)

- [ ] **Step 5: Document the flag in `.env.example`**

Add a line under the existing fetch/LLM config in `.env.example`:

```
# Crawl: verify TLS certs of crawled sources. Default false (some official sources have broken certs).
ADVISORY_FETCH_VERIFY_SSL=false
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/ingestion/test_http_fetcher_ssl.py -v`
Expected: PASS (both tests).

- [ ] **Step 7: Commit**

```bash
git add ingestion/config/settings.py ingestion/fetchers/http_fetcher.py .env.example tests/ingestion/test_http_fetcher_ssl.py
git commit -m "feat: make crawl SSL verification configurable and logged"
```

---

## GROUP A — Inference / gateway hardening

### Task 6: Harden `GeminiProvider.generate()` and add `InferenceError`

**Files:**
- Modify: `services/inference/models.py` (add exception)
- Modify: `services/inference/providers/gemini_provider.py` (rewrite `generate`)
- Test: `tests/services/inference/test_gemini_provider.py` (add tests)

- [ ] **Step 1: Write the failing tests**

Append to `tests/services/inference/test_gemini_provider.py` (create the file if it does not exist, with the imports shown):

```python
import pytest

from services.inference.models import InferenceError, InferencePolicy, InferenceRequest
from services.inference.providers.gemini_provider import GeminiProvider


class _Resp:
    def __init__(self, text):
        self.text = text


class _FakeModels:
    def __init__(self, text=None, exc=None):
        self._text = text
        self._exc = exc

    def generate_content(self, **kwargs):
        if self._exc is not None:
            raise self._exc
        return _Resp(self._text)


class _FakeClient:
    def __init__(self, text=None, exc=None):
        self.models = _FakeModels(text=text, exc=exc)


def _provider(client):
    provider = GeminiProvider(api_key="dummy")
    provider._client = client
    provider._api_key_present = True
    return provider


def _request():
    return InferenceRequest(
        agent_name="resolution_agent",
        task_type="conflict_tiebreak",
        system_prompt="sys",
        user_prompt="usr",
        output_mode="json",
    )


def _policy():
    return InferencePolicy(agent_name="resolution_agent", primary_model="gemini-2.5-flash-lite")


def test_malformed_json_returns_structure_failure():
    provider = _provider(_FakeClient(text="not json{"))
    result = provider.generate(_request(), _policy())
    assert result.failure_type == "STRUCTURE_FAILURE"
    assert result.parsed_data is None


def test_empty_text_returns_structure_failure():
    provider = _provider(_FakeClient(text=""))
    result = provider.generate(_request(), _policy())
    assert result.failure_type == "STRUCTURE_FAILURE"


def test_valid_json_parses():
    provider = _provider(_FakeClient(text='{"confidence": "high"}'))
    result = provider.generate(_request(), _policy())
    assert result.failure_type is None
    assert result.parsed_data == {"confidence": "high"}


def test_hard_api_error_raises_inference_error():
    provider = _provider(_FakeClient(exc=RuntimeError("429 rate limit")))
    with pytest.raises(InferenceError):
        provider.generate(_request(), _policy())
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/services/inference/test_gemini_provider.py -v`
Expected: FAIL — `InferenceError` does not exist (ImportError) and malformed JSON currently raises instead of returning a result.

- [ ] **Step 3: Add `InferenceError` to `services/inference/models.py`**

At the top of `services/inference/models.py`, after the imports, add:

```python
class InferenceError(RuntimeError):
    """Raised when the inference provider hits a hard failure (network, auth, rate limit)."""
```

- [ ] **Step 4: Rewrite `GeminiProvider.generate`**

Replace the body of `generate` in `services/inference/providers/gemini_provider.py` (lines 21-47) with:

```python
    def generate(self, request, policy):
        if not self._api_key_present:
            raise InferenceError("GEMINI_API_KEY is not configured")

        json_mode = request.output_mode == "json"
        try:
            response = self._client.models.generate_content(
                model=policy.primary_model,
                contents=request.user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=request.system_prompt,
                    temperature=request.temperature,
                    response_mime_type="application/json" if json_mode else None,
                ),
            )
        except Exception as exc:  # hard API failure: network, auth, rate limit, 5xx
            raise InferenceError(
                f"Gemini API call failed for agent={request.agent_name} "
                f"model={policy.primary_model}: {exc!r}"
            ) from exc

        text = (getattr(response, "text", "") or "").strip()

        if not json_mode:
            return InferenceResult(
                agent_name=request.agent_name,
                model=policy.primary_model,
                provider=self.provider_name,
                content=text,
            )

        if not text:
            return InferenceResult(
                agent_name=request.agent_name,
                model=policy.primary_model,
                provider=self.provider_name,
                content=text,
                failure_type="STRUCTURE_FAILURE",
            )

        try:
            parsed = json.loads(text)
        except (ValueError, TypeError):
            return InferenceResult(
                agent_name=request.agent_name,
                model=policy.primary_model,
                provider=self.provider_name,
                content=text,
                failure_type="STRUCTURE_FAILURE",
            )

        return InferenceResult(
            agent_name=request.agent_name,
            model=policy.primary_model,
            provider=self.provider_name,
            content=text,
            parsed_data=parsed,
        )
```

Update the import at the top of the file (line 7) to include the new exception:

```python
from services.inference.models import InferenceError, InferenceResult
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/services/inference/test_gemini_provider.py -v`
Expected: PASS (all four tests).

- [ ] **Step 6: Run the broader inference + retry suite for regressions**

Run: `.venv/Scripts/python.exe -m pytest tests/services/inference -v`
Expected: PASS. (The gateway's `STRUCTURE_FAILURE` retry path is now actually reachable.)

- [ ] **Step 7: Commit**

```bash
git add services/inference/models.py services/inference/providers/gemini_provider.py tests/services/inference/test_gemini_provider.py
git commit -m "feat: harden Gemini provider error handling and structure-failure retries"
```

---

### Task 7: Make optional LLM call sites degrade gracefully on hard errors

**Files:**
- Modify: `services/policy_inference_service.py:13-25`
- Modify: `services/profile_inference_service.py:131-147`
- Test: `tests/services/test_policy_inference_service.py` (add a test; create if absent)
- Test: `tests/services/test_profile_inference_service.py` (add a test)

- [ ] **Step 1: Write the failing tests**

Append to `tests/services/test_policy_inference_service.py` (create with imports if absent):

```python
from services.inference.models import InferenceError
from services.policy_inference_service import interpret_policy_ambiguity


class _RaisingGateway:
    def is_available(self):
        return True

    def run(self, request):
        raise InferenceError("boom")


def test_policy_ambiguity_degrades_on_inference_error():
    result = interpret_policy_ambiguity("query", ["some conflict"], _RaisingGateway())
    assert result == {"warnings": [], "requires_human_verification": False}
```

Append to `tests/services/test_profile_inference_service.py`:

```python
from services.inference.models import InferenceError
from services.profile_inference_service import build_profile_with_gateway


class _RaisingGateway:
    def is_available(self):
        return True

    def run(self, request):
        raise InferenceError("boom")


def test_build_profile_degrades_to_rule_based_on_inference_error():
    profile = build_profile_with_gateway("Em duoc 27 diem khoi A00", _RaisingGateway())
    # Rule-based fallback still extracts the score from the query.
    assert profile.total_score == 27
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/services/test_policy_inference_service.py tests/services/test_profile_inference_service.py -v -k degrade`
Expected: FAIL — `InferenceError` propagates out of both functions.

- [ ] **Step 3: Guard `interpret_policy_ambiguity`**

Replace the body of `services/policy_inference_service.py` (lines 13-25) with:

```python
def interpret_policy_ambiguity(user_query: str, conflicts, gateway):
    default = {"warnings": [], "requires_human_verification": False}
    if hasattr(gateway, "is_available") and not gateway.is_available():
        return default

    payload = {"user_query": user_query, "conflicts": conflicts}
    try:
        result = gateway.run(
            InferenceRequest(
                agent_name="policy_agent",
                task_type="policy_ambiguity",
                system_prompt=POLICY_SYSTEM_PROMPT.strip(),
                user_prompt=json.dumps(payload, ensure_ascii=False),
                output_mode="json",
                temperature=0.0,
            )
        )
    except InferenceError:
        return default
    return result.parsed_data or default
```

Add the import at the top of the file:

```python
from services.inference.models import InferenceError, InferenceRequest
```

(Replace the existing `from services.inference.models import InferenceRequest` line.)

- [ ] **Step 4: Guard `build_profile_with_gateway`**

In `services/profile_inference_service.py`, wrap the `gateway.run(...)` call (lines 135-146). Replace:

```python
    result = gateway.run(
        InferenceRequest(
            agent_name="profile_agent",
            task_type="profile_extraction",
            system_prompt=PROFILE_SYSTEM_PROMPT.format(
                major_ids=", ".join(MAJOR_ID_GUIDE)
            ).strip(),
            user_prompt=user_query,
            output_mode="json",
            temperature=0.0,
        )
    )
    return _normalize_profile(StudentProfile(**(result.parsed_data or {})))
```

with:

```python
    try:
        result = gateway.run(
            InferenceRequest(
                agent_name="profile_agent",
                task_type="profile_extraction",
                system_prompt=PROFILE_SYSTEM_PROMPT.format(
                    major_ids=", ".join(MAJOR_ID_GUIDE)
                ).strip(),
                user_prompt=user_query,
                output_mode="json",
                temperature=0.0,
            )
        )
    except InferenceError:
        return build_profile(user_query)
    return _normalize_profile(StudentProfile(**(result.parsed_data or {})))
```

Update the import line (line 2) from `from services.inference.models import InferenceRequest` to:

```python
from services.inference.models import InferenceError, InferenceRequest
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/services/test_policy_inference_service.py tests/services/test_profile_inference_service.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add services/policy_inference_service.py services/profile_inference_service.py tests/services/test_policy_inference_service.py tests/services/test_profile_inference_service.py
git commit -m "feat: degrade optional LLM call sites gracefully on hard inference errors"
```

---

### Task 8: Wire telemetry into `gateway.run()`

**Files:**
- Modify: `services/inference/gateway.py:15-28`
- Test: `tests/services/inference/test_gateway_telemetry.py` (create)

- [ ] **Step 1: Write the failing test**

Create `tests/services/inference/test_gateway_telemetry.py`:

```python
from services.inference.gateway import LLMGateway
from services.inference.models import InferenceResult
from services.inference.registry import ModelRegistry
from services.inference.telemetry import InferenceTelemetry


class _FlakyProvider:
    """First call returns STRUCTURE_FAILURE, second call succeeds."""

    def __init__(self):
        self.calls = 0

    def is_available(self):
        return True

    def generate(self, request, policy):
        self.calls += 1
        failure = "STRUCTURE_FAILURE" if self.calls == 1 else None
        return InferenceResult(
            agent_name=request.agent_name,
            model=policy.primary_model,
            provider="fake",
            content="{}",
            parsed_data={} if failure is None else None,
            failure_type=failure,
        )


def _gateway(provider, telemetry):
    registry = ModelRegistry(
        default_model="m",
        agent_overrides={"profile_agent": {"output_mode": "json", "max_retries": 1}},
    )
    return LLMGateway(registry=registry, providers={"gemini": provider}, telemetry=telemetry)


def test_gateway_records_one_event_per_attempt():
    from services.inference.models import InferenceRequest

    telemetry = InferenceTelemetry()
    provider = _FlakyProvider()
    gateway = _gateway(provider, telemetry)

    gateway.run(
        InferenceRequest(
            agent_name="profile_agent",
            task_type="profile_extraction",
            system_prompt="s",
            user_prompt="u",
            output_mode="json",
        )
    )

    assert len(telemetry.events) == 2
    assert telemetry.events[0]["failure_type"] == "STRUCTURE_FAILURE"
    assert telemetry.events[0]["attempt"] == 0
    assert telemetry.events[1]["failure_type"] is None
    assert telemetry.events[1]["attempt"] == 1
    assert all(event["agent_name"] == "profile_agent" for event in telemetry.events)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/services/inference/test_gateway_telemetry.py -v`
Expected: FAIL — `telemetry.events` is empty; `gateway.run` never records.

- [ ] **Step 3: Wire telemetry into `gateway.run`**

Replace the body of `services/inference/gateway.py` (the `run` method, lines 15-28) with:

```python
    def run(self, request):
        policy = self.registry.resolve(request.agent_name)
        provider = self.providers["gemini"]

        result = None
        for attempt in range(policy.max_retries + 1):
            result = provider.generate(request, policy)
            self._record(request, policy.primary_model, attempt, result.failure_type, used_fallback=False)
            if result.failure_type != "STRUCTURE_FAILURE":
                return result

        if policy.allow_fallback and policy.fallback_model:
            fallback_policy = policy.model_copy(update={"primary_model": policy.fallback_model})
            result = provider.generate(request, fallback_policy)
            self._record(
                request, fallback_policy.primary_model, policy.max_retries + 1,
                result.failure_type, used_fallback=True,
            )
            return result

        return result

    def _record(self, request, model, attempt, failure_type, used_fallback):
        if self.telemetry is None:
            return
        self.telemetry.record(
            agent_name=request.agent_name,
            model=model,
            attempt=attempt,
            failure_type=failure_type,
            used_fallback=used_fallback,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/services/inference/test_gateway_telemetry.py -v`
Expected: PASS.

- [ ] **Step 5: Run the inference suite for regressions**

Run: `.venv/Scripts/python.exe -m pytest tests/services/inference -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add services/inference/gateway.py tests/services/inference/test_gateway_telemetry.py
git commit -m "feat: record per-attempt inference telemetry in the gateway"
```

---

### Task 9: Activate the LLM conflict tiebreaker

**Files:**
- Create: `services/conflict/resolution_inference_service.py`
- Modify: `agents/conflict_agent.py`
- Test: `tests/services/conflict/test_resolution_inference_service.py` (create)
- Test: `tests/agents/test_conflict_agent.py` (add an activation test)

- [ ] **Step 1: Write the failing test for the adapter service**

Create `tests/services/conflict/test_resolution_inference_service.py`:

```python
from services.conflict.models import ComparisonReport, ConflictRecord, EvidenceOption
from services.conflict.resolution_inference_service import interpret_conflict_tiebreak
from services.inference.models import InferenceError, InferenceResult


def _record():
    return ConflictRecord(
        conflict_key="hust:2026:cs:thpt",
        field_name="quota",
        school_id="hust",
        school_name="HUST",
        admission_year=2026,
        program_name="Khoa hoc May tinh",
    )


def _report():
    return ComparisonReport(
        ranked_options=[
            EvidenceOption(evidence_id="a", source_url="https://a.test", trust_level=5, value=120),
            EvidenceOption(evidence_id="b", source_url="https://b.test", trust_level=3, value=150),
        ],
        is_decisive=False,
    )


class _Gateway:
    def __init__(self, parsed=None, exc=None):
        self._parsed = parsed
        self._exc = exc

    def is_available(self):
        return True

    def run(self, request):
        assert request.agent_name == "resolution_agent"
        assert request.output_mode == "json"
        if self._exc is not None:
            raise self._exc
        return InferenceResult(
            agent_name="resolution_agent", model="m", provider="fake",
            content="{}", parsed_data=self._parsed,
        )


def test_returns_parsed_data():
    gateway = _Gateway(parsed={"confidence": "high", "chosen_source_url": "https://a.test", "rationale": "r"})
    out = interpret_conflict_tiebreak(_record(), _report(), gateway)
    assert out["confidence"] == "high"
    assert out["chosen_source_url"] == "https://a.test"


def test_degrades_on_inference_error():
    gateway = _Gateway(exc=InferenceError("boom"))
    out = interpret_conflict_tiebreak(_record(), _report(), gateway)
    assert out == {"confidence": "low"}


def test_degrades_when_gateway_unavailable():
    class _Unavailable:
        def is_available(self):
            return False

        def run(self, request):
            raise AssertionError("should not be called")

    out = interpret_conflict_tiebreak(_record(), _report(), _Unavailable())
    assert out == {"confidence": "low"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/services/conflict/test_resolution_inference_service.py -v`
Expected: FAIL — module `resolution_inference_service` does not exist.

- [ ] **Step 3: Create the adapter service**

Create `services/conflict/resolution_inference_service.py`:

```python
import json

from services.inference.models import InferenceError, InferenceRequest

RESOLUTION_SYSTEM_PROMPT = """
You are resolving a conflict between admission-data sources for the same program field.
Choose the single most trustworthy source. Prefer higher trust_level, more recent
fetched_at, and higher confidence_score. Never invent a value.
Return JSON with exactly these keys:
- confidence: "high" or "low"
- chosen_source_url: the source_url of the option you trust most
- rationale: one short Vietnamese sentence explaining the choice
Use "high" only when one source is clearly more trustworthy than the others.
""".strip()


def _serialize_option(option):
    return {
        "source_url": option.source_url,
        "trust_level": option.trust_level,
        "fetched_at": option.fetched_at.isoformat() if option.fetched_at else None,
        "confidence_score": option.confidence_score,
        "value": option.value,
    }


def interpret_conflict_tiebreak(record, report, gateway) -> dict:
    default = {"confidence": "low"}
    if hasattr(gateway, "is_available") and not gateway.is_available():
        return default

    payload = {
        "field_name": record.field_name,
        "school_name": record.school_name,
        "program_name": record.program_name,
        "admission_year": record.admission_year,
        "options": [_serialize_option(option) for option in report.ranked_options],
    }
    try:
        result = gateway.run(
            InferenceRequest(
                agent_name="resolution_agent",
                task_type="conflict_tiebreak",
                system_prompt=RESOLUTION_SYSTEM_PROMPT,
                user_prompt=json.dumps(payload, ensure_ascii=False, default=str),
                output_mode="json",
                temperature=0.0,
            )
        )
    except InferenceError:
        return default
    return result.parsed_data or default
```

- [ ] **Step 4: Run the adapter test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/services/conflict/test_resolution_inference_service.py -v`
Expected: PASS (all three tests).

- [ ] **Step 5: Write the failing activation test for `conflict_agent`**

Add to `tests/agents/test_conflict_agent.py` (append; reuse existing imports where present):

```python
import agents.conflict_agent as conflict_agent_module
from agents.conflict_agent import conflict_agent
from agents.models import CandidateProgram, Evidence
from state import AgentState


def _conflicting_state():
    """Two sources disagree on quota for the same program/method (non-decisive)."""
    def candidate(evidence_id, quota, trust):
        return CandidateProgram(
            school_id="hust",
            school_name="HUST",
            admission_year=2026,
            program_id="computer_science",
            program_name="Khoa hoc May tinh",
            admission_method="thpt_score",
            quota={"value": quota},
            evidence=[
                Evidence(
                    source_url=f"https://src-{evidence_id}.test",
                    school_name="HUST",
                    admission_year=2026,
                    field_name="quota",
                    trust_level=trust,
                )
            ],
        )

    return AgentState(
        user_query="q",
        retrieved_programs=[candidate("a", 120, 5), candidate("b", 150, 5)],
    )


def test_conflict_agent_resolves_via_llm_tiebreaker(monkeypatch):
    class _Gateway:
        def is_available(self):
            return True

    monkeypatch.setattr(conflict_agent_module, "build_default_gateway", lambda: _Gateway())

    def fake_tiebreak(record, report, gateway):
        chosen = report.ranked_options[0].source_url
        return {"confidence": "high", "chosen_source_url": chosen, "rationale": "nguon dang tin nhat"}

    monkeypatch.setattr(conflict_agent_module, "interpret_conflict_tiebreak", fake_tiebreak)

    state = conflict_agent(_conflicting_state())

    assert any(o.used_llm_tiebreaker and o.status == "resolved" for o in state.resolution_outcomes)
```

> NOTE: If `compare()` rules already make this fixture *decisive* (single trust tier with a deterministic winner), tune the fixture so the two options tie on every axis (same `trust_level`, same fetched-at, same confidence) — the tiebreaker only fires when `report.is_decisive` is False. Verify by asserting `report.is_decisive is False` in a scratch check if needed.

- [ ] **Step 6: Run the activation test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/agents/test_conflict_agent.py::test_conflict_agent_resolves_via_llm_tiebreaker -v`
Expected: FAIL — `build_default_gateway`/`interpret_conflict_tiebreak` are not referenced by `conflict_agent`, so the tiebreaker never runs and no outcome has `used_llm_tiebreaker=True`.

- [ ] **Step 7: Wire the gateway into `conflict_agent`**

In `agents/conflict_agent.py`, add imports at the top:

```python
from services import build_default_gateway
from services.conflict.resolution_inference_service import interpret_conflict_tiebreak
```

Replace the start of `conflict_agent` (lines 22-31) so it builds the gateway once and passes a closure to `resolve()`:

```python
def conflict_agent(state: AgentState):
    records = detect_quota_conflicts(state.retrieved_programs)
    outcomes = []

    gateway = build_default_gateway() if records else None
    tiebreak = (
        (lambda record, report: interpret_conflict_tiebreak(record, report, gateway))
        if gateway is not None
        else None
    )

    for record in records:
        options = package_evidence(record, state.retrieved_programs)
        record.options = options
        report = compare(options)
        outcome = resolve(record, report, gateway=tiebreak)
        outcomes.append(outcome)
        if outcome.status == "unresolved":
            _mark_uncertain(state, record.conflict_key, record.field_name)
```

(The remainder of the function — setting `state.conflict_records`, `state.resolution_outcomes`, `state.conflicts`, `return state` — is unchanged.)

- [ ] **Step 8: Run the activation test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/agents/test_conflict_agent.py -v`
Expected: PASS (new test + existing conflict-agent tests still green).

- [ ] **Step 9: Run the full conflict + e2e suites for regressions**

Run: `.venv/Scripts/python.exe -m pytest tests/services/conflict tests/agents tests/e2e/test_real_conflict_resolution.py -v`
Expected: PASS.

- [ ] **Step 10: Commit**

```bash
git add services/conflict/resolution_inference_service.py agents/conflict_agent.py tests/services/conflict/test_resolution_inference_service.py tests/agents/test_conflict_agent.py
git commit -m "feat: activate LLM tiebreaker for non-decisive conflicts"
```

---

## Final verification

- [ ] **Run the entire suite with the DB up**

```bash
docker compose up -d --wait db
.venv/Scripts/python.exe -m db.setup_db
.venv/Scripts/python.exe -m pytest -q
```
Expected: ≥ prior 174 passed (plus the new tests), 1 skipped (`requires_real_dataset`), 0 failures, and no `PydanticDeprecatedSince20` warnings from the two migrated files.

- [ ] **Open the PR**

```bash
git push -u origin chore/stabilize-cleanup
gh pr create --base main --title "Tech-debt cleanup & inference hardening" --body "Implements docs/superpowers/specs/2026-05-29-tech-debt-cleanup-design.md"
```

---

## Self-Review (author checklist — completed)

**Spec coverage:** C1→Task 1, C2→Task 2, B1→Task 3, B2→Task 4, B3→Task 5, A1→Task 6, A2→Task 7, A3→Task 8, A4→Task 9. All eight items mapped. ✅

**Type consistency:** `InferenceError` (models.py) used by Tasks 6/7/9. `interpret_conflict_tiebreak(record, report, gateway)` defined in Task 9 Step 3 and called identically in Task 9 Step 7. `_record(...)` signature in Task 8 matches its call sites. `failure_type="STRUCTURE_FAILURE"` string consistent across Tasks 6 and 8. ✅

**Placeholder scan:** No TBD/TODO; every code step shows full code. The one NOTE (Task 9 Step 5) is a contingency instruction with concrete guidance, not a missing implementation. ✅

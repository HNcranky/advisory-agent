# Quickstart

How to run the advisory-agent locally on Windows.

## Prerequisites

- Python 3.12 with the project virtualenv already created at `.venv/`
- Docker Desktop (or compatible runtime — `docker version` must exit 0)
- `.env` at the repo root (copy `.env.example` if absent)

## 1. Bring up the Postgres database (Docker)

The repo ships with a `docker-compose.yml` that runs Postgres 16-alpine on `localhost:5432`. The Python app connects via `DB_CONFIG` in `ingestion/config/settings.py`, which defaults to the same host/port/credentials.

### First-time setup

```powershell
copy .env.example .env       # creates .env with safe dev defaults
docker compose up -d --wait db
python -m db.setup_db        # applies db/migrations/ and seeds the source registry
```

`--wait` blocks until the container reports `healthy` (≈5 s after first pull). `setup_db` is idempotent — safe to re-run after adding a migration.

### Day-to-day

```powershell
docker compose start db      # resume an existing container
docker compose stop db       # pause without losing data
docker compose down -v       # NUKE: drop the container AND the data volume
```

### Verify the connection

```powershell
python -c "from ingestion.storage.db_connection import get_connection; get_connection().close(); print('OK')"
```

Expected: prints `OK`.

### Port conflicts

If `5432` is already in use (e.g., a local `postgresql-x64-18` service is running), either stop it (`Stop-Service postgresql-x64-18`) or change `DB_PORT=5433` in `.env` — compose maps `${DB_PORT}:5432`, so the container internally stays on 5432 while the host-side port shifts.

### Design

See [`docs/superpowers/specs/2026-05-19-docker-postgres-db-design.md`](./docs/superpowers/specs/2026-05-19-docker-postgres-db-design.md) for the full spec and rationale.

## 2. Activate the virtualenv

PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

cmd:

```cmd
.\.venv\Scripts\activate.bat
```

Confirm with `python -c "import sys; print(sys.prefix)"` — the path should end in `.venv`.

## 3. Load `.env` into the shell

The app reads `GEMINI_API_KEY` from `os.environ` directly (no `dotenv` loader). Export the values into the current shell before running anything that talks to Gemini.

PowerShell:

```powershell
Get-Content .env | ForEach-Object {
    if ($_ -match '^\s*([^#=\s][^=]*)=(.*)$') {
        Set-Item "Env:$($matches[1].Trim())" $matches[2].Trim()
    }
}
```

Verify: `echo $env:GEMINI_API_KEY` should print the key.

## 4. Run the tests

```powershell
pytest
```

Tests do not need a live Gemini key — they stub the provider.

Integration tests (`pytest -m integration`) require the Docker DB from step 1 to be running. Skip them with `pytest -m "not integration"` if Docker is unavailable.

## 5. Run the chat web app

```powershell
uvicorn web.app:build_app --factory --reload --host 127.0.0.1 --port 8000
```

Open <http://127.0.0.1:8000/> in a browser. The first visit creates an anonymous session; the session token is persisted in `localStorage` so refreshing rejoins the same conversation.

## 6. Demo flow

1. Send a freeform message describing a student's situation.
2. The assistant will ask follow-up questions until the profile is complete.
3. Once complete, the UI enters an "analyzing" state and polls the session snapshot until the advisory run finishes.
4. The final recommendation appears as an assistant result turn.

Stale local session tokens (e.g. after the database is wiped) are detected on startup and cleared automatically — refresh the page to recover.

## Troubleshooting

- **"GEMINI_API_KEY is not configured"** — step 2 was skipped or run in a different shell than step 4. Re-run the export block in the same PowerShell window before starting uvicorn.
- **Port 8000 in use** — pass a different `--port` to uvicorn.
- **Chat page loads but shows a startup error** — open the browser devtools network tab; a `404` on `/api/sessions` means the server did not start the chat router. Restart uvicorn.

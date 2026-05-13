# Quickstart

How to run the advisory-agent locally on Windows.

## Prerequisites

- Python 3.12 with the project virtualenv already created at `.venv/`
- `.env` at the repo root containing `GEMINI_API_KEY=...`

## 1. Activate the virtualenv

PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

cmd:

```cmd
.\.venv\Scripts\activate.bat
```

Confirm with `python -c "import sys; print(sys.prefix)"` — the path should end in `.venv`.

## 2. Load `.env` into the shell

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

## 3. Run the tests

```powershell
pytest
```

Tests do not need a live Gemini key — they stub the provider.

## 4. Run the chat web app

```powershell
uvicorn web.app:build_app --factory --reload --host 127.0.0.1 --port 8000
```

Open <http://127.0.0.1:8000/> in a browser. The first visit creates an anonymous session; the session token is persisted in `localStorage` so refreshing rejoins the same conversation.

## 5. Demo flow

1. Send a freeform message describing a student's situation.
2. The assistant will ask follow-up questions until the profile is complete.
3. Once complete, the UI enters an "analyzing" state and polls the session snapshot until the advisory run finishes.
4. The final recommendation appears as an assistant result turn.

Stale local session tokens (e.g. after the database is wiped) are detected on startup and cleared automatically — refresh the page to recover.

## Troubleshooting

- **"GEMINI_API_KEY is not configured"** — step 2 was skipped or run in a different shell than step 4. Re-run the export block in the same PowerShell window before starting uvicorn.
- **Port 8000 in use** — pass a different `--port` to uvicorn.
- **Chat page loads but shows a startup error** — open the browser devtools network tab; a `404` on `/api/sessions` means the server did not start the chat router. Restart uvicorn.

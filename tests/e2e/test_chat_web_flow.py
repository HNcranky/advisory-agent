from fastapi.testclient import TestClient
from pathlib import Path


from web.app import build_app


def test_chat_page_references_static_client_assets():
    client = TestClient(build_app())

    response = client.get("/")

    assert '/static/js/chat.js' in response.text
    assert '/static/css/chat.css' in response.text
    
    
def test_chat_client_supports_snapshot_refresh_and_run_polling():
    script = Path("web/static/js/chat.js").read_text(encoding="utf-8")

    assert "async function fetchSessionSnapshot" in script
    assert "function renderTranscript" in script
    assert "function renderProfileSummary" in script
    assert "function schedulePolling" in script
    assert "window.localStorage" in script
    assert "`/api/sessions/${sessionToken}`" in script
    
    
def test_chat_client_clears_stale_session_token_and_reports_startup_errors():
    script = Path("web/static/js/chat.js").read_text(encoding="utf-8")
    styles = Path("web/static/css/chat.css").read_text(encoding="utf-8")

    assert "window.localStorage.removeItem(SESSION_KEY)" in script
    assert 'setStatus("Khong the khoi tao phien chat.", "error")' in script
    assert ".chat-status[data-tone=\"error\"]" in styles
    assert ".message--assistant" in styles
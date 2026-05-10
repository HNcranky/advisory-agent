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
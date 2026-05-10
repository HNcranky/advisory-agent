from fastapi.testclient import TestClient

from web.app import build_app


def test_chat_page_renders_status_reset_and_results_regions():
    client = TestClient(build_app())

    response = client.get("/")

    assert response.status_code == 200
    assert 'id="chat-status"' in response.text
    assert 'id="reset-session"' in response.text
    assert 'id="recommendation-panel"' in response.text
    assert 'id="send-button"' in response.text
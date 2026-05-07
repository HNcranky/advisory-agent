from fastapi.testclient import TestClient

from web.app import build_app


def test_chat_page_renders_shell():
    client = TestClient(build_app())

    response = client.get("/")

    assert response.status_code == 200
    assert "Student Advisory Chat" in response.text
    assert 'id="chat-transcript"' in response.text
    assert 'id="profile-summary"' in response.text
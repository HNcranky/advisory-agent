from fastapi.testclient import TestClient

from web.app import build_app


def test_chat_page_references_static_client_assets():
    client = TestClient(build_app())

    response = client.get("/")

    assert '/static/js/chat.js' in response.text
    assert '/static/css/chat.css' in response.text
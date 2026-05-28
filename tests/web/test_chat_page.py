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


def test_chat_page_renders_three_column_shell():
    client = TestClient(build_app())

    response = client.get("/")
    body = response.text

    assert response.status_code == 200
    assert 'class="app-shell"' in body or 'class="app-shell chat-shell"' in body
    assert 'class="app-header"' in body
    assert 'id="profile-panel"' in body
    assert 'id="chat-panel"' in body
    assert 'id="trace-panel"' in body


def test_chat_page_renders_collapse_and_drawer_buttons():
    client = TestClient(build_app())

    response = client.get("/")
    body = response.text

    assert response.status_code == 200
    assert 'id="collapse-left"' in body
    assert 'id="collapse-right"' in body
    assert 'id="open-left-drawer"' in body
    assert 'id="open-right-drawer"' in body


def test_chat_page_preserves_legacy_ids_for_existing_js():
    client = TestClient(build_app())

    response = client.get("/")
    body = response.text

    assert response.status_code == 200
    for legacy in ("chat-transcript", "chat-form", "chat-input", "profile-summary", "trace-cards"):
        assert f'id="{legacy}"' in body

import os
from unittest.mock import patch

from fastapi.testclient import TestClient

from web.app import build_app


def test_chat_page_renders_debug_flag_true_when_env_set():
    with patch.dict(os.environ, {"ADVISORY_DEBUG_UI": "1"}):
        client = TestClient(build_app())
        response = client.get("/")
    assert response.status_code == 200
    assert 'data-debug-ui="true"' in response.text


def test_chat_page_renders_debug_flag_false_by_default():
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("ADVISORY_DEBUG_UI", None)
        client = TestClient(build_app())
        response = client.get("/")
    assert response.status_code == 200
    assert 'data-debug-ui="false"' in response.text


def test_chat_page_theme_default_light_when_env_unset():
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("ADVISORY_THEME_DEFAULT", None)
        client = TestClient(build_app())
        response = client.get("/")
    assert response.status_code == 200
    assert 'data-theme-default="light"' in response.text


def test_chat_page_theme_default_dark_when_env_set_dark():
    with patch.dict(os.environ, {"ADVISORY_THEME_DEFAULT": "dark"}):
        client = TestClient(build_app())
        response = client.get("/")
    assert response.status_code == 200
    assert 'data-theme-default="dark"' in response.text


def test_chat_page_theme_default_falls_back_to_light_for_invalid_value():
    with patch.dict(os.environ, {"ADVISORY_THEME_DEFAULT": "neon-purple"}):
        client = TestClient(build_app())
        response = client.get("/")
    assert response.status_code == 200
    assert 'data-theme-default="light"' in response.text

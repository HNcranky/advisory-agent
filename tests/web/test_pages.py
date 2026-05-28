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

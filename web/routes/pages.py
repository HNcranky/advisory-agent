import os

from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="web/templates")

_VALID_THEMES = {"light", "dark"}


def _debug_ui_enabled() -> bool:
    return os.environ.get("ADVISORY_DEBUG_UI") == "1"


def _theme_default() -> str:
    value = (os.environ.get("ADVISORY_THEME_DEFAULT") or "").strip().lower()
    return value if value in _VALID_THEMES else "light"


@router.get("/")
def chat_page(request: Request):
    return templates.TemplateResponse(
        request,
        "chat.html",
        {
            "page_title": "Student Advisory Chat",
            "debug_ui_enabled": _debug_ui_enabled(),
            "theme_default": _theme_default(),
        },
    )

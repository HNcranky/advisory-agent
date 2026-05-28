import os

from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="web/templates")


def _debug_ui_enabled() -> bool:
    return os.environ.get("ADVISORY_DEBUG_UI") == "1"


@router.get("/")
def chat_page(request: Request):
    return templates.TemplateResponse(
        request,
        "chat.html",
        {
            "page_title": "Student Advisory Chat",
            "debug_ui_enabled": _debug_ui_enabled(),
        },
    )

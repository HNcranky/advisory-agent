from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="web/templates")

@router.get("/")
def chat_page(request: Request):
    return templates.TemplateResponse(
        request,
        "chat.html",
        {"page_title": "Student Advisory Chat"},
    )
from fastapi import FastAPI

from web.routes.system import router as system_router
from web.routes.chat_api import router as chat_router


def build_app() -> FastAPI:
    app = FastAPI(title="Student Advisory Chat")
    app.include_router(system_router)
    app.include_router(chat_router)
    return app
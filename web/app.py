from fastapi import FastAPI

from web.routes.system import router as system_router


def build_app() -> FastAPI:
    app = FastAPI(title="Student Advisory Chat")
    app.include_router(system_router)
    return app
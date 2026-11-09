"""FastAPI 入口：/api 路由；正式前端在 frontend/（Next.js，3010）。"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.core.config import Settings, settings as default_settings
from app.core.db import init_db
from app.core.errors import AppError
from app.services.agent import AgentService
from app.services.audit import AuditService
from app.services.changes import ChangeService
from app.services.llm import LLMClient, build_llm
from app.services.providers.mock import MockProviderSet

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("dcops")


def create_app(llm: LLMClient | None = None, providers: MockProviderSet | None = None,
               app_settings: Settings | None = None) -> FastAPI:
    s = app_settings or default_settings

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        init_db()
        yield

    app = FastAPI(title="数据中心运维助理", version="0.1.0", lifespan=lifespan)
    app.state.settings = s
    app.state.providers = providers or MockProviderSet()
    app.state.llm = llm or build_llm(s)
    app.state.audit = AuditService()
    app.state.changes = ChangeService(app.state.providers, app.state.audit, settings=s)
    app.state.agent = AgentService(app.state.llm, app.state.providers, s,
                                   change_service=app.state.changes)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:3010", "http://localhost:3010"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(AppError)
    async def app_error(_request: Request, exc: AppError):
        return JSONResponse(status_code=exc.status_code,
                            content={"error": {"code": exc.code, "message": exc.message}})

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, exc: RequestValidationError):
        first = exc.errors()[0] if exc.errors() else {}
        message = f"{'.'.join(str(x) for x in first.get('loc', []))}: {first.get('msg', '请求参数不合法')}"
        return JSONResponse(status_code=422,
                            content={"error": {"code": "VALIDATION_ERROR", "message": message}})

    @app.exception_handler(Exception)
    async def unhandled(_request: Request, exc: Exception):
        logger.exception("unhandled error: %s", type(exc).__name__)
        return JSONResponse(status_code=500,
                            content={"error": {"code": "INTERNAL_ERROR", "message": "服务内部错误"}})

    app.include_router(router)

    @app.get("/")
    def index():
        return JSONResponse({"status": "ok", "message": "正式前端：http://127.0.0.1:3010"})

    return app


app = create_app()

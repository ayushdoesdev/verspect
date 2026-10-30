"""FastAPI application entrypoint."""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.v1.router import api_router
from app.api.v1 import ai as ai_api
from app.core.config import get_settings
from app.core.database import async_engine
from app.core.logging import get_logger, setup_logging
from app.core.rate_limit import auth_rate_limiter

setup_logging()
logger = get_logger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    logger.info(
        "starting_application",
        env=settings.app_env,
        app=settings.app_name,
        ai_provider=settings.ai_provider,
    )
    try:
        from app.services.bootstrap_admin import ensure_bootstrap_admin

        await ensure_bootstrap_admin()
    except Exception as exc:  # noqa: BLE001
        logger.warning("bootstrap_admin_failed", error=str(exc))
    yield
    logger.info("shutting_down_application")
    await async_engine.dispose()


_docs = None if settings.is_production else "/docs"
_redoc = None if settings.is_production else "/redoc"
_openapi = None if settings.is_production else "/openapi.json"

app = FastAPI(
    title=settings.app_name,
    description=(
        "Dependency Intelligence continuously watches connected GitHub repositories and "
        "surfaces library usage, outdated packages, vulnerabilities, breaking changes, "
        "license compliance, health scores, and migration guidance."
    ),
    version="1.0.0",
    docs_url=_docs,
    redoc_url=_redoc,
    openapi_url=_openapi,
    lifespan=lifespan,
)


class AuthRateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path.startswith("/api/v1/auth/"):
            client = request.client.host if request.client else "unknown"
            if not auth_rate_limiter.allow(f"{client}:{path}"):
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Too many authentication requests. Try again shortly."},
                )
        return await call_next(request)


app.add_middleware(AuthRateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if settings.is_production:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.allowed_hosts_list,
    )

app.include_router(api_router, prefix="/api/v1")
# Canonical health path requested by product: /api/ai/health (also available under /api/v1/ai)
app.include_router(ai_api.router, prefix="/api/ai", tags=["ai"])


@app.get("/health", tags=["health"])
async def health():
    """Readiness-style health: verifies PostgreSQL connectivity."""
    db_ok = False
    try:
        from sqlalchemy import text

        async with async_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        db_ok = True
    except Exception as exc:  # noqa: BLE001
        logger.warning("health_db_check_failed", error=str(exc))

    payload = {
        "status": "healthy" if db_ok else "degraded",
        "service": settings.app_name,
        "version": "1.0.0",
        "environment": settings.app_env,
        "ai_provider": settings.ai_provider,
        "checks": {"database": db_ok},
    }
    if not db_ok:
        return JSONResponse(status_code=503, content=payload)
    return payload


@app.get("/", tags=["root"])
async def root() -> dict:
    return {
        "name": settings.app_name,
        "docs": _docs or "disabled",
        "api": "/api/v1",
        "health": "/health",
    }


@app.exception_handler(ValueError)
async def value_error_handler(_request: Request, exc: ValueError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(Exception)
async def unhandled_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled_exception", error=str(exc))
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )

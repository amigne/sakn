import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import settings
from app.database import engine

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> Any:
    # Redis
    try:
        from app.redis.connection import init_redis

        await init_redis(settings.REDIS_URL)
        logger.info("Redis connected")
    except Exception:
        logger.warning("Redis unavailable, continuing without it")

    # Tool registry
    from app.tools.registry import ToolRegistry
    from app.tools.ping import PingTool

    registry = ToolRegistry()
    registry.register(PingTool())
    app.state.tool_registry = registry

    # WebSocket manager
    from app.websocket.manager import ConnectionManager

    app.state.ws_manager = ConnectionManager()

    yield

    # Cleanup
    try:
        from app.redis.connection import close_redis

        await close_redis()
    except Exception:
        pass


app = FastAPI(
    title="SAKN API",
    description="Swiss Army Knife for Network Engineers",
    version="0.0.1",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Session middleware (anonymous for Slice 3)
from app.middleware.session import SessionMiddleware

app.add_middleware(SessionMiddleware)

# API router
from app.api.v1.router import v1_router

app.include_router(v1_router)

# Error handlers
from app.api.errors import AppError, app_error_handler, register_error_handlers

register_error_handlers(app)


@app.get("/health")
async def health():
    checks = {}

    # Database check
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "unavailable"

    # Redis check
    try:
        from app.redis.connection import get_redis

        redis = await get_redis()
        await redis.ping()
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "unavailable"

    return {"status": "ok", "checks": checks}

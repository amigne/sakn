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

    # Ensure tables exist (idempotent — safe to call even after alembic migrations)
    from app.models import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Tool registry
    from app.tools.registry import ToolRegistry
    from app.tools.ping import PingTool
    from app.tools.traceroute import TracerouteTool

    registry = ToolRegistry()
    registry.register(PingTool())
    registry.register(TracerouteTool())
    app.state.tool_registry = registry

    # Seed tool modules in DB (idempotent)
    from app.database import async_session_factory
    from app.models import ToolModule
    from sqlalchemy import select

    async with async_session_factory() as db:
        for tool in registry._tools.values():
            definition = tool.get_definition()
            row = await db.execute(
                select(ToolModule).where(ToolModule.name == definition.name)
            )
            if row.scalar_one_or_none() is None:
                db.add(ToolModule(
                    name=definition.name,
                    display_name_key=definition.display_name_key,
                    description_key=definition.description_key,
                    enabled=True,
                    version=definition.version,
                ))
        await db.commit()

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

# Session middleware
from app.middleware.session import SessionMiddleware

app.add_middleware(SessionMiddleware)

# Security headers
from app.middleware.security_headers import SecurityHeadersMiddleware

app.add_middleware(SecurityHeadersMiddleware)

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

import logging
from contextlib import asynccontextmanager, suppress
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import settings
from app.database import engine

# Setup structured logging early
from app.logs.logger import setup_logging

setup_logging(settings.LOG_LEVEL)

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
    from app.config import settings as cfg
    from app.database import set_db_available
    from app.models import Base

    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        set_db_available(True)
        db_available = True
    except Exception:
        # In production, fail fast — no silent fallback to SQLite
        if settings.ENVIRONMENT != "development":
            logger.critical(
                "Primary database unavailable at %s in %s environment, shutting down",
                cfg.DATABASE_URL,
                settings.ENVIRONMENT,
            )
            raise

        logger.warning(
            "Primary database unavailable at %s, trying SQLite fallback",
            cfg.DATABASE_URL,
        )
        # Fall back to local SQLite in development only
        try:
            from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine as cae

            fallback_url = "sqlite+aiosqlite:///./sakn.db"
            fallback_engine = cae(fallback_url, echo=False, future=True)
            async with fallback_engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

            # Swap engines: replace the inaccessible one with the working one
            import app.database as db_mod

            db_mod.engine = fallback_engine
            db_mod.async_session_factory = async_sessionmaker(
                fallback_engine, class_=AsyncSession, expire_on_commit=False
            )
            logger.info("Falling back to SQLite at %s", fallback_url)
            set_db_available(True)
            db_available = True
        except Exception as fallback_err:
            logger.warning("SQLite fallback also failed: %s", fallback_err)
            logger.warning("Database unavailable, continuing with limited functionality")
            set_db_available(False)
            db_available = False

    # Tool registry (always available, even without DB)
    from app.tools.dns_lookup import DnsLookupTool
    from app.tools.ping import PingTool
    from app.tools.registry import ToolRegistry
    from app.tools.ssl_viewer import SslViewerTool
    from app.tools.traceroute import TracerouteTool

    registry = ToolRegistry()
    registry.register(PingTool())
    registry.register(TracerouteTool())
    registry.register(DnsLookupTool())
    registry.register(SslViewerTool())
    app.state.tool_registry = registry

    # Seed tool modules + default config rows (idempotent)
    if db_available:
        try:
            from sqlalchemy import select

            from app.database import async_session_factory
            from app.models import ToolModule
            from app.models.preferences import GlobalSetting
            from app.models.tool_module import DnsServerPreset, RateLimitConfig, RoleToolPermission

            async with async_session_factory() as db:
                # Upsert tool modules
                tool_ids: dict[str, str] = {}
                for tool in registry._tools.values():
                    definition = tool.get_definition()
                    row = await db.execute(
                        select(ToolModule).where(ToolModule.name == definition.name)
                    )
                    existing = row.scalar_one_or_none()
                    if existing is None:
                        existing = ToolModule(
                            name=definition.name,
                            display_name_key=definition.display_name_key,
                            description_key=definition.description_key,
                            enabled=True,
                            version=definition.version,
                        )
                        db.add(existing)
                        await db.flush()
                    tool_ids[definition.name] = existing.id

                # Seed default RoleToolPermission rows (all roles → all tools allowed)
                all_roles = ["visitor", "authenticated", "administrator"]
                for role in all_roles:
                    for _tool_name, tool_id in tool_ids.items():
                        row = await db.execute(
                            select(RoleToolPermission).where(
                                RoleToolPermission.role == role,
                                RoleToolPermission.tool_id == tool_id,
                            )
                        )
                        if row.scalar_one_or_none() is None:
                            db.add(RoleToolPermission(role=role, tool_id=tool_id, allowed=True))

                # Seed default RateLimitConfig rows
                default_limits = {
                    "visitor": (1, 200, 3600),
                    "authenticated": (1, 500, 3600),
                    "administrator": (0, 3600, 3600),
                }
                for role, (soft, hard, window) in default_limits.items():
                    row = await db.execute(
                        select(RateLimitConfig).where(
                            RateLimitConfig.role == role,
                            RateLimitConfig.tool_id.is_(None),
                        )
                    )
                    if row.scalar_one_or_none() is None:
                        db.add(RateLimitConfig(
                            role=role,
                            tool_id=None,
                            soft_limit=soft,
                            hard_limit=hard,
                            window_seconds=window,
                        ))

                # Seed default DnsServerPreset rows for dns_lookup tool
                dns_tool_id = tool_ids.get("dns_lookup")
                if dns_tool_id:
                    from sqlalchemy import func as sa_func

                    row = await db.execute(
                        select(sa_func.count(DnsServerPreset.id)).where(
                            DnsServerPreset.tool_module_id == dns_tool_id
                        )
                    )
                    existing_count = row.scalar() or 0
                    if existing_count == 0:
                        default_dns_servers = [
                            ("8.8.8.8", "Google DNS"),
                            ("1.1.1.1", "Cloudflare DNS"),
                            ("9.9.9.9", "Quad9 DNS"),
                            ("208.67.222.222", "OpenDNS"),
                        ]
                        for idx, (ip, desc) in enumerate(default_dns_servers):
                            db.add(DnsServerPreset(
                                tool_module_id=dns_tool_id,
                                ip_address=ip,
                                description=desc,
                                sort_order=idx,
                            ))

                # Seed default GlobalSetting rows
                default_settings = {
                    "log_retention_days": "90",
                    "session_duration_hours": "24",
                    "max_concurrent_sessions": "10",
                    "visitor_ip_soft_limit": "5",
                    "visitor_ip_hard_limit": "500",
                }
                for key, value in default_settings.items():
                    row = await db.execute(
                        select(GlobalSetting).where(GlobalSetting.key == key)
                    )
                    if row.scalar_one_or_none() is None:
                        db.add(GlobalSetting(key=key, value=value))

                await db.commit()
        except Exception:
            logger.exception("Seed data creation failed, continuing")

    # WebSocket manager
    from app.websocket.manager import ConnectionManager

    app.state.ws_manager = ConnectionManager()

    # Log cleanup scheduler (apscheduler, daily)
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler

        scheduler = AsyncIOScheduler()
        app.state.scheduler = scheduler

        @scheduler.scheduled_job("cron", hour=3, minute=0)
        async def cleanup_logs():
            import app.services.log_service as log_svc

            try:
                async with async_session_factory() as db:
                    from sqlalchemy import select as sel

                    from app.models.preferences import GlobalSetting

                    row = await db.execute(
                        sel(GlobalSetting).where(GlobalSetting.key == "log_retention_days")
                    )
                    setting = row.scalar_one_or_none()
                    retention = int(setting.value) if setting else 90
                    deleted = await log_svc.cleanup_old_logs(db, retention)
                    await db.commit()
                    logger.info("Log cleanup completed", extra={"deleted": deleted})
            except Exception:
                logger.exception("Log cleanup failed")

        @scheduler.scheduled_job("cron", hour=3, minute=30)
        async def cleanup_unverified_accounts():
            """Delete user accounts that haven't been verified within 7 days."""
            try:
                from app.services.account_cleanup_service import cleanup_unverified_accounts as do_cleanup

                async with async_session_factory() as db:
                    count = await do_cleanup(db, retention_days=7)
                    await db.commit()
                    if count:
                        logger.info("Unverified account cleanup", extra={"deleted": count})
            except Exception:
                logger.exception("Unverified account cleanup failed")

        @scheduler.scheduled_job("cron", hour=3, minute=35)
        async def cleanup_expired_anonymous_sessions():
            """Delete anonymous sessions (user_id IS NULL) past their expiration."""
            try:
                from app.services.session_cleanup_service import cleanup_expired_anonymous_sessions as do_cleanup

                async with async_session_factory() as db:
                    count = await do_cleanup(db)
                    await db.commit()
                    if count:
                        logger.info("Anonymous session cleanup", extra={"deleted": count})
            except Exception:
                logger.exception("Anonymous session cleanup failed")

        scheduler.start()
    except Exception:
        logger.exception("Scheduler initialization failed")

    yield

    # Cleanup
    if hasattr(app.state, "scheduler"):
        with suppress(Exception):
            app.state.scheduler.shutdown(wait=False)
    try:
        from app.redis.connection import close_redis

        await close_redis()
    except Exception:
        pass


app = FastAPI(
    title="SAKN API",
    description="Swiss Army Knife for Network Engineers",
    version="0.0.2",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    lifespan=lifespan,
)

# Request ID middleware
from app.middleware.request_id import RequestIDMiddleware

app.add_middleware(RequestIDMiddleware)

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

# Rate limit middleware (before security headers so headers apply to 429 responses too)
from app.middleware.rate_limit import RateLimitMiddleware

app.add_middleware(RateLimitMiddleware)

# Security headers
from app.middleware.security_headers import SecurityHeadersMiddleware

app.add_middleware(SecurityHeadersMiddleware)

# Trusted proxy middleware (outermost — corrects scope["scheme"] and scope["client"]
# before any other middleware reads them)
from app.middleware.proxy_trust import TrustedProxyMiddleware

app.add_middleware(TrustedProxyMiddleware, trusted_hops=settings.TRUSTED_PROXY_HOPS)

# API router
from app.api.v1.router import v1_router

app.include_router(v1_router)

# Error handlers
from app.api.errors import AppError, register_error_handlers

register_error_handlers(app)


@app.get("/health")
async def health():
    """Minimal liveness probe — no infrastructure checks, no auth required."""
    return {"status": "ok"}


@app.get("/health/full")
async def health_full(request: Request):
    """Full health check with database and Redis checks.

    Protected by X-Health-Token header matching HEALTH_FULL_TOKEN env var.
    Returns 503 if HEALTH_FULL_TOKEN is not configured, 401 if token is
    missing or incorrect.
    """
    import secrets

    if not settings.HEALTH_FULL_TOKEN:
        raise AppError(
            status_code=503,
            code="SERVICE_UNAVAILABLE",
            message_key="errors.not_configured",
            message="Health check endpoint not configured. Set HEALTH_FULL_TOKEN to enable.",
        )

    token = request.headers.get("X-Health-Token", "")
    if not secrets.compare_digest(token.encode("utf-8"), settings.HEALTH_FULL_TOKEN.encode("utf-8")):
        raise AppError(
            status_code=401,
            code="UNAUTHORIZED",
            message_key="errors.unauthorized",
            message="Missing or invalid health check token.",
        )

    checks = {}

    # Database check
    try:
        from app.database import engine as live_engine

        async with live_engine.connect() as conn:
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

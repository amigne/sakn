import logging
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

logger = logging.getLogger(__name__)

engine = create_async_engine(settings.DATABASE_URL, echo=False, future=True)

async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Track whether the database was reachable at startup.
# Defaults to True (optimistic) — only set to False when the lifespan
# explicitly detects an unreachable database. This ensures that:
# - Normal startup with a working DB: True (lifespan confirms)
# - Docker with PostgreSQL down: False (lifespan catches it)
# - TestClient (lifespan may not run): True (safe default)
_db_available = True


def set_db_available(available: bool) -> None:
    global _db_available
    _db_available = available


def is_db_available() -> bool:
    return _db_available


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    if not _db_available:
        from app.api.errors import AppError
        raise AppError(503, "DATABASE_UNAVAILABLE", "errors.database_unavailable",
                       "Database is not available. Check DATABASE_URL configuration.")
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

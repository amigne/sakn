import asyncio
import os
from collections.abc import AsyncGenerator
from typing import Any

# Set ENVIRONMENT before any app import — config.py has no default (#55)
os.environ.setdefault("ENVIRONMENT", "development")

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import get_session
from app.main import app
from app.models import Base
import app.database as db_module
import app.middleware.rate_limit as rl_module
import app.middleware.session as mw_module

TEST_DATABASE_URL = "sqlite+aiosqlite://"


@pytest.fixture(scope="session")
def event_loop() -> Any:
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def _engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(_engine) -> AsyncGenerator[AsyncSession, None]:
    session_factory = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        async with session.begin():
            yield session
            await session.rollback()


@pytest_asyncio.fixture
async def client(_engine) -> AsyncGenerator[AsyncClient, None]:
    """Test client with dependency overrides for the test DB."""
    session_factory = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)

    # Override endpoint DI
    async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_session] = override_get_session

    # Monkey-patch the global async_session_factory so middleware also uses test DB
    original_factory = db_module.async_session_factory
    db_module.async_session_factory = session_factory
    mw_module.async_session_factory = session_factory
    rl_module.async_session_factory = session_factory

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    # Restore
    app.dependency_overrides.clear()
    db_module.async_session_factory = original_factory
    if hasattr(mw_module, "async_session_factory"):
        del mw_module.async_session_factory
    if hasattr(rl_module, "async_session_factory"):
        del rl_module.async_session_factory

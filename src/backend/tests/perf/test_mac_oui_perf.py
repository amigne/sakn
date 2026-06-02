"""Performance and ReDoS tests for MAC OUI lookup (Sprint 5).

Markers: @pytest.mark.perf (non-blocking in CI).
"""

from __future__ import annotations

import time

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.main import app
from app.models.base import new_uuid7
from app.models.mac_oui import MacOui
from app.models.tool_module import RoleToolPermission, ToolModule

pytestmark = [pytest.mark.perf, pytest.mark.asyncio]


@pytest.fixture(autouse=True)
def _clear_rate_limits():
    """Clear in-memory rate limit counters between tests."""
    from app.redis.rate_limit_store import get_rate_limiter
    get_rate_limiter().clear_for_tests()
    yield


# ── Helpers ────────────────────────────────────────────────────────────


async def _seed_many_ouis(db: AsyncSession, count: int) -> None:
    """Seed N unique MA-L OUI rows."""
    from datetime import UTC, date

    today = date.today()
    for i in range(count):
        oui_hex = f"{i:06X}"
        db.add(
            MacOui(
                id=new_uuid7(),
                oui=oui_hex,
                oui_type="MA-L",
                organization=f"Org-{i}",
                address=f"Address {i}",
                first_seen=today,
                last_seen=today,
            )
        )
    await db.flush()


async def _cleanup(db: AsyncSession) -> None:
    """Remove all OUI data and tool module rows."""
    from app.models.mac_oui_history import MacOuiHistory

    await db.execute(delete(MacOuiHistory.__table__))
    await db.execute(delete(MacOui.__table__))
    await db.execute(
        delete(RoleToolPermission.__table__).where(
            RoleToolPermission.tool_id.in_(
                select(ToolModule.id).where(ToolModule.name == "mac_oui")
            )
        )
    )
    await db.execute(delete(ToolModule.__table__).where(ToolModule.name == "mac_oui"))
    await db.flush()


async def _create_test_client(_engine) -> AsyncClient:
    """Build a test client wired to the test DB."""
    import app.database as db_module
    import app.middleware.rate_limit as rl_module
    import app.middleware.session as mw_module
    from app.database import get_session

    session_factory = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_session():
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_session] = override_get_session
    original_factory = db_module.async_session_factory
    original_rl_factory = rl_module.async_session_factory
    original_mw_factory = getattr(mw_module, "async_session_factory", None)
    db_module.async_session_factory = session_factory
    mw_module.async_session_factory = session_factory
    rl_module.async_session_factory = session_factory

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
    db_module.async_session_factory = original_factory
    rl_module.async_session_factory = original_rl_factory
    if original_mw_factory is None:
        del mw_module.async_session_factory
    else:
        mw_module.async_session_factory = original_mw_factory


async def _seed_tool_and_ouis(_engine, ouis_count: int = 2000):
    """Seed tool + OUIs using a fresh session that auto-commits.

    Idempotent: skips tool creation if it already exists in the shared engine.
    """
    from app.constants.roles import ROLE_VISITOR

    session_factory = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as db, db.begin():
        row = await db.execute(select(ToolModule).where(ToolModule.name == "mac_oui"))
        tool = row.scalar_one_or_none()
        if tool is None:
            tool = ToolModule(
                id=new_uuid7(),
                name="mac_oui",
                display_name_key="tools.mac_oui.name",
                description_key="tools.mac_oui.description",
                enabled=True,
                version="1.0.0",
                has_settings=True,
                has_status=True,
            )
            db.add(tool)
            await db.flush()
            db.add(RoleToolPermission(id=new_uuid7(), role=ROLE_VISITOR, tool_id=tool.id, allowed=True))
        else:
            # Ensure allowed visitor permission exists
            perm_row = await db.execute(
                select(RoleToolPermission).where(
                    RoleToolPermission.role == ROLE_VISITOR,
                    RoleToolPermission.tool_id == tool.id,
                )
            )
            if perm_row.scalar_one_or_none() is None:
                db.add(RoleToolPermission(id=new_uuid7(), role=ROLE_VISITOR, tool_id=tool.id, allowed=True))
        if ouis_count > 0:
            await _seed_many_ouis(db, ouis_count)


# ── Perf Tests ─────────────────────────────────────────────────────────


@pytest.mark.perf
async def test_lookup_2000_unique_ouis_under_500ms(_engine):
    """N=2000 unique OUIs (max batch) → lookup < 500 ms."""
    await _seed_tool_and_ouis(_engine, 2000)

    async for client in _create_test_client(_engine):
        ouis = [f"{i:012X}" for i in range(2000)]
        start = time.perf_counter()
        resp = await client.post("/api/v1/tools/mac_oui/execute", json={"ouis": ouis})
        elapsed = time.perf_counter() - start
        assert resp.status_code == 200
        data = resp.json()
        assert data["result"]["success"]
        assert data["result"]["data"]["parse_stats"]["valid"] == 2000
        assert elapsed < 0.5, f"Lookup took {elapsed:.3f}s, expected < 0.5s"

    # Cleanup
    session_factory = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as db, db.begin():
        await _cleanup(db)


@pytest.mark.perf
async def test_rejected_2000_entries_under_500ms(_engine):
    """Payload of 2000 all-invalid entries → validation < 500 ms."""
    await _seed_tool_and_ouis(_engine, 0)

    async for client in _create_test_client(_engine):
        ouis = ["INVALID_VALUE_XXXXX" for _ in range(2000)]
        start = time.perf_counter()
        resp = await client.post("/api/v1/tools/mac_oui/execute", json={"ouis": ouis})
        elapsed = time.perf_counter() - start
        assert resp.status_code == 200
        data = resp.json()
        assert data["result"]["data"]["parse_stats"]["rejected"] == 2000
        assert elapsed < 0.5, f"Rejection took {elapsed:.3f}s, expected < 0.5s"

    session_factory = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as db, db.begin():
        await _cleanup(db)


@pytest.mark.perf
async def test_redos_payload_under_1s(_engine):
    """Payload with 2000 long-format strings (ReDoS resilience) → < 1 s."""
    await _seed_tool_and_ouis(_engine, 0)

    async for client in _create_test_client(_engine):
        ouis = ["A" * 100 + ":" + "B" * 100 for _ in range(2000)]
        start = time.perf_counter()
        resp = await client.post("/api/v1/tools/mac_oui/execute", json={"ouis": ouis})
        elapsed = time.perf_counter() - start
        assert resp.status_code == 200
        assert elapsed < 1.0, f"ReDoS payload took {elapsed:.3f}s, expected < 1.0s"

    session_factory = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as db, db.begin():
        await _cleanup(db)

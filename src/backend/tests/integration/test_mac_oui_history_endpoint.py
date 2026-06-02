"""Integration tests for GET /api/v1/tools/mac_oui/history."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.roles import ROLE_ADMINISTRATOR, ROLE_VISITOR
from app.models.base import new_uuid7, utcnow
from app.models.mac_oui import MacOui
from app.models.mac_oui_history import MacOuiHistory
from app.models.tool_module import RoleToolPermission, ToolModule
from app.security.password import hash_password
from app.security.tokens import generate_token, hash_token
from tests.factories import create_user

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _clear_rate_limits():
    """Clear in-memory rate limit counters between tests."""
    from app.redis.rate_limit_store import get_rate_limiter
    get_rate_limiter().clear_for_tests()
    yield


# ── Helpers ────────────────────────────────────────────────────────────


async def _create_session(db: AsyncSession, role: str) -> str:
    from datetime import timedelta

    from app.models import Session, User

    email = f"{role}_hist@test.com"
    existing = await db.execute(select(User).where(User.email == email))
    user = existing.scalar_one_or_none()
    if user is None:
        user = await create_user(
            db,
            email=email,
            password_hash=hash_password("testpass"),
            role=role,
        )

    token = generate_token()
    session = Session(
        id=new_uuid7(),
        user_id=user.id,
        token_hash=hash_token(token),
        ip_address="127.0.0.1",
        expires_at=utcnow() + timedelta(hours=24),
    )
    db.add(session)
    await db.commit()
    return token


async def _ensure_tool_mac_oui(db: AsyncSession) -> ToolModule:
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
    else:
        tool.enabled = True
    return tool


# ── Cleanup ────────────────────────────────────────────────────────────


@pytest_asyncio.fixture(autouse=True)
async def _cleanup(_engine):
    from sqlalchemy.ext.asyncio import async_sessionmaker

    yield
    session_factory = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as db, db.begin():
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


# ── Tests ──────────────────────────────────────────────────────────────


async def test_history_unauthenticated_403(client: AsyncClient):
    """Unauthenticated → 403 (tool may or may not be disabled, so accept 403 or 404)."""
    response = await client.get("/api/v1/tools/mac_oui/history?oui=001122&oui_type=MA-L")
    # 403 = permission denied (tool disabled or role not allowed)
    # 404 = tool not found
    assert response.status_code in (403, 404)


async def test_history_bad_oui_type_400(client: AsyncClient, db_session: AsyncSession):
    await _ensure_tool_mac_oui(db_session)
    token = await _create_session(db_session, ROLE_VISITOR)
    response = await client.get(
        "/api/v1/tools/mac_oui/history?oui=001122&oui_type=INVALID",
        cookies={"sakn_session": token},
    )
    assert response.status_code == 400


async def test_history_unknown_oui_returns_empty(client: AsyncClient, db_session: AsyncSession):
    await _ensure_tool_mac_oui(db_session)
    token = await _create_session(db_session, ROLE_ADMINISTRATOR)
    response = await client.get(
        "/api/v1/tools/mac_oui/history?oui=ABCDEF&oui_type=MA-L",
        cookies={"sakn_session": token},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["has_more"] is False


async def test_history_pagination(client: AsyncClient, db_session: AsyncSession):
    await _ensure_tool_mac_oui(db_session)

    mac = MacOui(
        id=new_uuid7(),
        oui="001122",
        oui_type="MA-L",
        organization="TestOrg",
        address="Test Address",
        first_seen=datetime.now(UTC).date(),
        last_seen=datetime.now(UTC).date(),
    )
    db_session.add(mac)
    await db_session.flush()

    for i in range(15):
        db_session.add(
            MacOuiHistory(
                id=new_uuid7(),
                oui_id=mac.id,
                oui="001122",
                previous_organization=f"OldOrg{i}",
                new_organization=f"NewOrg{i}",
                change_type="name_change",
                detected_at=datetime.now(UTC),
            )
        )
    await db_session.flush()

    token = await _create_session(db_session, ROLE_ADMINISTRATOR)

    resp1 = await client.get(
        "/api/v1/tools/mac_oui/history?oui=001122&oui_type=MA-L&limit=10&offset=0",
        cookies={"sakn_session": token},
    )
    assert resp1.status_code == 200
    d1 = resp1.json()
    assert len(d1["items"]) == 10
    assert d1["total"] == 15
    assert d1["has_more"] is True

    resp2 = await client.get(
        "/api/v1/tools/mac_oui/history?oui=001122&oui_type=MA-L&limit=10&offset=10",
        cookies={"sakn_session": token},
    )
    assert resp2.status_code == 200
    d2 = resp2.json()
    assert len(d2["items"]) == 5
    assert d2["has_more"] is False

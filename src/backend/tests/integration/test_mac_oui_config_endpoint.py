"""Integration tests for GET /api/v1/tools/mac_oui/config (M1, R1)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.roles import ROLE_AUTHENTICATED, ROLE_VISITOR
from app.models.base import new_uuid7, utcnow
from app.models.preferences import GlobalSetting
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

    email = f"{role}_config@test.com"
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


async def _ensure_tool(db: AsyncSession) -> ToolModule:
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
    # Seed explicit allow permissions for all roles. Since #404 (default-deny),
    # _check_tool_access no longer auto-grants on a missing row (the RBAC test
    # below overrides visitor to allowed=False to assert the 403 path).
    from app.constants.roles import ROLE_ADMINISTRATOR, ROLE_AUTHENTICATED, ROLE_VISITOR

    for role in (ROLE_VISITOR, ROLE_AUTHENTICATED, ROLE_ADMINISTRATOR):
        perm_row = await db.execute(
            select(RoleToolPermission).where(
                RoleToolPermission.role == role,
                RoleToolPermission.tool_id == tool.id,
            )
        )
        perm = perm_row.scalar_one_or_none()
        if perm is None:
            db.add(RoleToolPermission(id=new_uuid7(), role=role, tool_id=tool.id, allowed=True))
        else:
            perm.allowed = True
    await db.flush()
    return tool


# ── Tests ──────────────────────────────────────────────────────────────


async def test_config_default_when_no_setting(client: AsyncClient, db_session: AsyncSession):
    """No DB row → returns default 50_000."""
    await _ensure_tool(db_session)
    # Remove any existing setting row (from prior tests) through a fresh
    # connection so it's committed before our test session starts.
    from sqlalchemy import delete as sa_delete
    await db_session.execute(
        sa_delete(GlobalSetting).where(
            GlobalSetting.key == "module.mac_oui.MAC_OUI_FRONTEND_INPUT_MAX_CHARS"
        )
    )
    await db_session.flush()

    token = await _create_session(db_session, ROLE_AUTHENTICATED)
    response = await client.get(
        "/api/v1/tools/mac_oui/config",
        cookies={"sakn_session": token},
    )
    assert response.status_code == 200
    assert response.json() == {"max_chars": 50_000}


async def test_config_returns_admin_set_value(client: AsyncClient, db_session: AsyncSession):
    """Non-default DB value is served."""
    await _ensure_tool(db_session)

    # Use upsert pattern: delete then insert to avoid UNIQUE conflicts
    from sqlalchemy import delete as sa_delete
    await db_session.execute(
        sa_delete(GlobalSetting).where(
            GlobalSetting.key == "module.mac_oui.MAC_OUI_FRONTEND_INPUT_MAX_CHARS"
        )
    )
    db_session.add(
        GlobalSetting(
            key="module.mac_oui.MAC_OUI_FRONTEND_INPUT_MAX_CHARS",
            value="123000",
        )
    )
    await db_session.flush()

    token = await _create_session(db_session, ROLE_AUTHENTICATED)
    response = await client.get(
        "/api/v1/tools/mac_oui/config",
        cookies={"sakn_session": token},
    )
    assert response.status_code == 200
    assert response.json() == {"max_chars": 123000}


async def test_config_respects_tool_access_rbac(client: AsyncClient, db_session: AsyncSession):
    """Visitor with mac_oui denied → 403."""
    await _ensure_tool(db_session)
    # Disable visitor permission for mac_oui
    tool_row = await db_session.execute(
        select(ToolModule).where(ToolModule.name == "mac_oui")
    )
    tool = tool_row.scalar_one_or_none()
    perm_row = await db_session.execute(
        select(RoleToolPermission).where(
            RoleToolPermission.role == ROLE_VISITOR,
            RoleToolPermission.tool_id == tool.id,
        )
    )
    perm = perm_row.scalar_one_or_none()
    if perm is not None:
        perm.allowed = False
    else:
        db_session.add(
            RoleToolPermission(
                id=new_uuid7(), role=ROLE_VISITOR, tool_id=tool.id, allowed=False
            )
        )
    # Commit so the client's request sees the permission change.
    await db_session.commit()

    # Make the request as a visitor (no cookies) to test RBAC
    response = await client.get("/api/v1/tools/mac_oui/config")
    assert response.status_code == 403

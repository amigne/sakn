"""Integration tests for admin module settings: audit log (M3/R3bis) + validation (M4/R4)."""

from __future__ import annotations

import json

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.roles import ROLE_ADMINISTRATOR
from app.models.base import new_uuid7, utcnow
from app.models.log import AuditLog
from app.models.preferences import GlobalSetting
from app.models.tool_module import ToolModule
from app.security.password import hash_password
from app.security.tokens import generate_token, hash_token
from tests.factories import create_user

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _clear_rate_limits():
    from app.redis.rate_limit_store import get_rate_limiter
    get_rate_limiter().clear_for_tests()
    yield


# ── Helpers ────────────────────────────────────────────────────────────


async def _create_session(db: AsyncSession, role: str) -> str:
    from datetime import timedelta

    from app.models import Session, User

    email = f"{role}_setval@test.com"
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


async def _ensure_tool(db: AsyncSession) -> None:
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


# ── R3bis — Audit log on settings update ───────────────────────────────


async def test_settings_update_creates_audit_log(
    client: AsyncClient, db_session: AsyncSession, _engine
):
    """PUT /admin/modules/mac_oui/settings creates an AuditLog row with old/new values."""
    await _ensure_tool(db_session)

    # Seed an initial value (delete any pre-existing first to avoid UNIQUE conflict)
    from sqlalchemy import delete as sa_delete
    await db_session.execute(
        sa_delete(GlobalSetting).where(
            GlobalSetting.key == "module.mac_oui.MAC_OUI_HISTORY_PAGE_SIZE"
        )
    )
    db_session.add(
        GlobalSetting(
            key="module.mac_oui.MAC_OUI_HISTORY_PAGE_SIZE",
            value="10",
        )
    )
    await db_session.flush()

    token = await _create_session(db_session, ROLE_ADMINISTRATOR)
    response = await client.put(
        "/api/v1/admin/modules/mac_oui/settings",
        cookies={"sakn_session": token},
        json={"settings": {"MAC_OUI_HISTORY_PAGE_SIZE": "25"}},
    )
    assert response.status_code == 200

    # Query the AuditLog via a fresh committed session (db_session is dead
    # after _create_session's commit).
    from sqlalchemy.ext.asyncio import async_sessionmaker
    session_factory = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as db, db.begin():
        rows = await db.execute(
            select(AuditLog)
            .where(AuditLog.action == "module.settings.update")
            .order_by(AuditLog.created_at.desc())
        )
        entry = rows.scalars().first()
        assert entry is not None, "Expected an AuditLog row for the settings update"
        assert entry.entity_type == "tool_module"
        old_val = json.loads(entry.old_value) if entry.old_value else {}
        new_val = json.loads(entry.new_value) if entry.new_value else {}
        assert old_val.get("MAC_OUI_HISTORY_PAGE_SIZE") == "10"
        assert new_val.get("MAC_OUI_HISTORY_PAGE_SIZE") == "25"


# ── R4 — Backend settings validation ───────────────────────────────────


@pytest.mark.parametrize(
    "key,bad_value",
    [
        ("MAC_OUI_FRONTEND_INPUT_MAX_CHARS", "abc"),
        ("MAC_OUI_BACKEND_BATCH_MAX_SIZE", "not_a_number"),
        ("OUI_SYNC_HOUR", "noon"),
    ],
)
async def test_settings_invalid_type_returns_400(
    client: AsyncClient, db_session: AsyncSession, key: str, bad_value: str
):
    """Non-integer values for known integer settings → 400."""
    await _ensure_tool(db_session)
    token = await _create_session(db_session, ROLE_ADMINISTRATOR)
    response = await client.put(
        "/api/v1/admin/modules/mac_oui/settings",
        cookies={"sakn_session": token},
        json={"settings": {key: bad_value}},
    )
    assert response.status_code == 400


@pytest.mark.parametrize(
    "key,out_of_range",
    [
        ("MAC_OUI_FRONTEND_INPUT_MAX_CHARS", "999"),
        ("MAC_OUI_FRONTEND_INPUT_MAX_CHARS", "200001"),
        ("MAC_OUI_BACKEND_BATCH_MAX_SIZE", "99"),
        ("MAC_OUI_BACKEND_BATCH_MAX_SIZE", "10001"),
        ("MAC_OUI_HISTORY_PAGE_SIZE", "4"),
        ("MAC_OUI_HISTORY_PAGE_SIZE", "51"),
        ("OUI_SYNC_HOUR", "-1"),
        ("OUI_SYNC_HOUR", "24"),
    ],
)
async def test_settings_out_of_range_returns_400(
    client: AsyncClient, db_session: AsyncSession, key: str, out_of_range: str
):
    """Values outside the allowed range → 400."""
    await _ensure_tool(db_session)
    token = await _create_session(db_session, ROLE_ADMINISTRATOR)
    response = await client.put(
        "/api/v1/admin/modules/mac_oui/settings",
        cookies={"sakn_session": token},
        json={"settings": {key: out_of_range}},
    )
    assert response.status_code == 400


async def test_settings_valid_value_returns_200(
    client: AsyncClient, db_session: AsyncSession
):
    """Valid values return 200 and the setting is persisted."""
    await _ensure_tool(db_session)
    token = await _create_session(db_session, ROLE_ADMINISTRATOR)
    response = await client.put(
        "/api/v1/admin/modules/mac_oui/settings",
        cookies={"sakn_session": token},
        json={"settings": {"MAC_OUI_HISTORY_PAGE_SIZE": "20"}},
    )
    assert response.status_code == 200
    assert response.json()["settings"]["MAC_OUI_HISTORY_PAGE_SIZE"] == "20"

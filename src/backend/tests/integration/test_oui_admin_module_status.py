"""Integration tests for GET /api/v1/admin/modules/{tool_name}/status."""

from __future__ import annotations

import json

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.roles import ROLE_ADMINISTRATOR, ROLE_AUTHENTICATED
from app.models.base import new_uuid7, utcnow
from app.models.oui_sync_log import OuiSyncLog
from app.models.tool_module import RoleToolPermission, ToolModule
from app.security.password import hash_password
from app.security.tokens import generate_token, hash_token
from tests.factories import create_user

pytestmark = pytest.mark.asyncio


# ── Helpers ────────────────────────────────────────────────────────────


async def _create_session(db: AsyncSession, role: str) -> str:
    """Create a user + session and return the session token.

    Calls db.commit() at the end — must be the LAST operation on db.
    """
    from datetime import timedelta

    from app.models import Session, User

    email = f"{role}_status@test.com"
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


async def _ensure_tool(db: AsyncSession, name: str, has_status: bool = True) -> ToolModule:
    row = await db.execute(select(ToolModule).where(ToolModule.name == name))
    tool = row.scalar_one_or_none()
    if tool is None:
        tool = ToolModule(
            id=new_uuid7(),
            name=name,
            display_name_key=f"tools.{name}.name",
            description_key=f"tools.{name}.description",
            enabled=True,
            version="1.0.0",
            has_settings=False,
            has_status=has_status,
        )
        db.add(tool)
        await db.flush()
    else:
        tool.has_status = has_status
    return tool


# ── Cleanup ────────────────────────────────────────────────────────────


@pytest_asyncio.fixture(autouse=True)
async def _cleanup_oui_sync_log(_engine):
    from sqlalchemy.ext.asyncio import async_sessionmaker

    yield
    session_factory = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as db, db.begin():
        await db.execute(delete(OuiSyncLog.__table__))
        for name in ("mac_oui", "test_no_status"):
            await db.execute(
                delete(RoleToolPermission.__table__).where(
                    RoleToolPermission.tool_id.in_(
                        select(ToolModule.id).where(ToolModule.name == name)
                    )
                )
            )
            await db.execute(delete(ToolModule.__table__).where(ToolModule.name == name))


# ── Tests ──────────────────────────────────────────────────────────────


async def test_status_unauthenticated_403(client: AsyncClient):
    response = await client.get("/api/v1/admin/modules/mac_oui/status")
    assert response.status_code == 403


async def test_status_non_admin_403(client: AsyncClient, db_session: AsyncSession):
    await _ensure_tool(db_session, "mac_oui", has_status=True)
    token = await _create_session(db_session, ROLE_AUTHENTICATED)
    response = await client.get(
        "/api/v1/admin/modules/mac_oui/status",
        cookies={"sakn_session": token},
    )
    assert response.status_code == 403


async def test_status_module_not_found_404(client: AsyncClient, db_session: AsyncSession):
    token = await _create_session(db_session, ROLE_ADMINISTRATOR)
    response = await client.get(
        "/api/v1/admin/modules/nonexistent/status",
        cookies={"sakn_session": token},
    )
    assert response.status_code == 404


async def test_status_has_status_false_returns_null(client: AsyncClient, db_session: AsyncSession):
    await _ensure_tool(db_session, "test_no_status", has_status=False)
    token = await _create_session(db_session, ROLE_ADMINISTRATOR)
    response = await client.get(
        "/api/v1/admin/modules/test_no_status/status",
        cookies={"sakn_session": token},
    )
    assert response.status_code == 200
    assert response.json() is None


async def test_status_idle_when_no_logs(client: AsyncClient, db_session: AsyncSession):
    await _ensure_tool(db_session, "mac_oui", has_status=True)
    token = await _create_session(db_session, ROLE_ADMINISTRATOR)
    response = await client.get(
        "/api/v1/admin/modules/mac_oui/status",
        cookies={"sakn_session": token},
    )
    assert response.status_code == 200
    data = response.json()
    assert data is not None
    assert data["status"] == "idle"
    assert data["last_run"] is None
    assert data["history"] == []


async def test_status_success_after_good_sync(client: AsyncClient, db_session: AsyncSession):
    await _ensure_tool(db_session, "mac_oui", has_status=True)
    from datetime import UTC, datetime

    log = OuiSyncLog(
        id=new_uuid7(),
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
        triggered_by="scheduler",
        status="success",
        added=10,
        changed=2,
        confirmed=48700,
        files_failed=None,
    )
    db_session.add(log)
    await db_session.flush()

    token = await _create_session(db_session, ROLE_ADMINISTRATOR)
    response = await client.get(
        "/api/v1/admin/modules/mac_oui/status",
        cookies={"sakn_session": token},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["last_run"] is not None
    assert data["last_run"]["added"] == 10


async def test_status_partial_when_files_failed(client: AsyncClient, db_session: AsyncSession):
    await _ensure_tool(db_session, "mac_oui", has_status=True)
    from datetime import UTC, datetime

    log = OuiSyncLog(
        id=new_uuid7(),
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
        triggered_by="scheduler",
        status="partial",
        added=10,
        changed=0,
        confirmed=48700,
        files_failed=json.dumps(["MA-L"]),
    )
    db_session.add(log)
    await db_session.flush()

    token = await _create_session(db_session, ROLE_ADMINISTRATOR)
    response = await client.get(
        "/api/v1/admin/modules/mac_oui/status",
        cookies={"sakn_session": token},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "partial"
    assert data["last_run"]["files_failed"] == ["MA-L"]


async def test_status_alert_when_all_three_files_failed(client: AsyncClient, db_session: AsyncSession):
    """Covers #382 — all 3 IEEE files failed → derived status is 'alert', not 'success'."""
    await _ensure_tool(db_session, "mac_oui", has_status=True)
    from datetime import UTC, datetime

    log = OuiSyncLog(
        id=new_uuid7(),
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
        triggered_by="scheduler",
        status="partial",
        added=0,
        changed=0,
        confirmed=0,
        files_failed=json.dumps(["MA-L", "MA-M", "MA-S"]),
    )
    db_session.add(log)
    await db_session.flush()

    token = await _create_session(db_session, ROLE_ADMINISTRATOR)
    response = await client.get(
        "/api/v1/admin/modules/mac_oui/status",
        cookies={"sakn_session": token},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "alert"
    assert data["last_run"]["files_failed"] == ["MA-L", "MA-M", "MA-S"]


async def test_status_running_when_active_log(client: AsyncClient, db_session: AsyncSession):
    await _ensure_tool(db_session, "mac_oui", has_status=True)
    from datetime import UTC, datetime

    log = OuiSyncLog(
        id=new_uuid7(),
        started_at=datetime.now(UTC),
        finished_at=None,
        triggered_by="admin",
        status="running",
        added=0,
        changed=0,
        confirmed=0,
    )
    db_session.add(log)
    await db_session.flush()

    token = await _create_session(db_session, ROLE_ADMINISTRATOR)
    response = await client.get(
        "/api/v1/admin/modules/mac_oui/status",
        cookies={"sakn_session": token},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "running"


async def test_status_includes_history(client: AsyncClient, db_session: AsyncSession):
    await _ensure_tool(db_session, "mac_oui", has_status=True)
    from datetime import UTC, datetime, timedelta

    for i in range(5):
        log = OuiSyncLog(
            id=new_uuid7(),
            started_at=datetime.now(UTC) - timedelta(hours=i),
            finished_at=datetime.now(UTC) - timedelta(hours=i, minutes=-2),
            triggered_by="scheduler",
            status="success",
            added=1,
            changed=0,
            confirmed=100,
        )
        db_session.add(log)
    await db_session.flush()

    token = await _create_session(db_session, ROLE_ADMINISTRATOR)
    response = await client.get(
        "/api/v1/admin/modules/mac_oui/status",
        cookies={"sakn_session": token},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["history"]) == 5
    assert data["history"][0]["status"] == "success"

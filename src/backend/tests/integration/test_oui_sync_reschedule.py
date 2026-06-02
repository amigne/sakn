"""Integration test for M2 reschedule on OUI_SYNC_HOUR change (R3)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.roles import ROLE_ADMINISTRATOR
from app.models.base import new_uuid7, utcnow
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


async def _create_session(db: AsyncSession, role: str) -> str:
    from datetime import timedelta

    from app.models import Session, User

    email = f"{role}_resched@test.com"
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


@pytest.fixture
def app_with_mock_scheduler():
    """Replace app.state.scheduler with a MagicMock for assertion."""
    from app.main import app

    # Save original
    original = getattr(app.state, "scheduler", None)
    mock_scheduler = MagicMock(spec=AsyncIOScheduler)
    app.state.scheduler = mock_scheduler
    yield app
    # Restore
    if original is not None:
        app.state.scheduler = original
    else:
        del app.state.scheduler


async def test_update_sync_hour_reschedules_job(
    client: AsyncClient,
    db_session: AsyncSession,
    app_with_mock_scheduler,
):
    """Changing OUI_SYNC_HOUR via admin triggers scheduler.reschedule_job."""
    app = app_with_mock_scheduler
    mock_scheduler = app.state.scheduler

    await _ensure_tool(db_session)

    token = await _create_session(db_session, ROLE_ADMINISTRATOR)
    response = await client.put(
        "/api/v1/admin/modules/mac_oui/settings",
        cookies={"sakn_session": token},
        json={"settings": {"OUI_SYNC_HOUR": "7"}},
    )
    assert response.status_code == 200

    mock_scheduler.reschedule_job.assert_called_once()
    args, kwargs = mock_scheduler.reschedule_job.call_args
    assert args[0] == "oui_sync_daily"
    trigger = kwargs.get("trigger") or args[1]
    assert isinstance(trigger, CronTrigger)
    # CronTrigger exposes `fields` — check hour=7
    hour_field = next(f for f in trigger.fields if f.name == "hour")
    assert "7" in str(hour_field)

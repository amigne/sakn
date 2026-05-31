"""Integration tests for POST /api/v1/admin/oui/sync."""

import pytest
from httpx import AsyncClient
from sqlalchemy import select as sa_select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.constants.roles import ROLE_ADMINISTRATOR, ROLE_AUTHENTICATED
from app.models.base import new_uuid7, utcnow
from app.models.preferences import GlobalSetting
from app.security.password import hash_password
from app.security.tokens import generate_token, hash_token
from tests.factories import create_user


async def _create_session_for_role(db, role: str) -> str:
    """Create a user + session and return the session token."""
    from datetime import timedelta

    from app.models import Session, User

    email = f"{role}@test.com"
    existing = await db.execute(sa_select(User).where(User.email == email))
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


@pytest.mark.asyncio
async def test_post_unauthenticated_403(client: AsyncClient):
    """Unauthenticated request → 403."""
    response = await client.post("/api/v1/admin/oui/sync", json={})
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_post_non_admin_403(client: AsyncClient, db_session):
    """Authenticated but non-admin → 403."""
    token = await _create_session_for_role(db_session, ROLE_AUTHENTICATED)
    response = await client.post(
        "/api/v1/admin/oui/sync",
        json={},
        cookies={"sakn_session": token},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_post_admin_202(client: AsyncClient, db_session):
    """Admin session → 202 with task_id."""
    token = await _create_session_for_role(db_session, ROLE_ADMINISTRATOR)
    response = await client.post(
        "/api/v1/admin/oui/sync",
        json={},
        cookies={"sakn_session": token},
    )
    assert response.status_code == 202
    data = response.json()
    assert "task_id" in data
    assert "started_at" in data


@pytest.mark.asyncio
async def test_post_when_running_409(client: AsyncClient, db_session, _engine):
    """Sync already in progress → 409 with OUI_SYNC_ALREADY_RUNNING."""
    # Seed the running flag using a separate session (avoids transaction issues)
    test_factory = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)
    async with test_factory() as seed_session, seed_session.begin():
        row = await seed_session.execute(
            sa_select(GlobalSetting).where(GlobalSetting.key == "oui_sync_running")
        )
        setting = row.scalar_one_or_none()
        if setting:
            setting.value = "1"
        else:
            seed_session.add(GlobalSetting(key="oui_sync_running", value="1"))

    token = await _create_session_for_role(db_session, ROLE_ADMINISTRATOR)
    response = await client.post(
        "/api/v1/admin/oui/sync",
        json={},
        cookies={"sakn_session": token},
    )
    assert response.status_code == 409
    data = response.json()
    assert data["error"]["code"] == "OUI_SYNC_ALREADY_RUNNING"

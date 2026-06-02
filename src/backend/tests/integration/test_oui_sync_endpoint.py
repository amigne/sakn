"""Integration tests for POST /api/v1/admin/oui/sync."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient
from sqlalchemy import select as sa_select

from app.constants.roles import ROLE_ADMINISTRATOR, ROLE_AUTHENTICATED
from app.models.base import new_uuid7, utcnow
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


@pytest.fixture
def mock_oui_service():
    """M1: Override get_oui_sync_service to inject a mock service."""
    from app.api.v1.endpoints.admin_oui_sync import get_oui_sync_service
    from app.main import app

    service = MagicMock()
    service.try_acquire_running_lock = AsyncMock(return_value=True)
    service.sync_all = AsyncMock(return_value=None)
    app.dependency_overrides[get_oui_sync_service] = lambda: service
    yield service
    app.dependency_overrides.pop(get_oui_sync_service, None)


@pytest.mark.asyncio
async def test_post_unauthenticated_403(client: AsyncClient):
    """Unauthenticated request → 403 (require_admin treats no-session as visitor)."""
    response = await client.post("/api/v1/admin/oui/sync", json={})
    assert response.status_code == 403


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
async def test_post_admin_202(client: AsyncClient, db_session, mock_oui_service):
    """Admin session → 202 with task_id. M1: mock injected, no real HTTP call."""
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
async def test_post_when_running_409(client: AsyncClient, db_session, mock_oui_service):
    """Sync already in progress → 409 with OUI_SYNC_ALREADY_RUNNING. M2: atomic lock rejects."""
    mock_oui_service.try_acquire_running_lock.return_value = False

    token = await _create_session_for_role(db_session, ROLE_ADMINISTRATOR)
    response = await client.post(
        "/api/v1/admin/oui/sync",
        json={},
        cookies={"sakn_session": token},
    )
    assert response.status_code == 409
    data = response.json()
    assert data["error"]["code"] == "OUI_SYNC_ALREADY_RUNNING"


@pytest.mark.asyncio
async def test_concurrent_admin_posts_only_one_gets_202(
    client: AsyncClient, db_session, mock_oui_service
):
    """M2: 5 concurrent POSTs → exactly 1 gets 202, rest get 409."""
    token = await _create_session_for_role(db_session, ROLE_ADMINISTRATOR)

    # Simulate try_acquire_running_lock: first call succeeds, rest fail
    call_count = [0]

    async def acquire_lock(session):
        call_count[0] += 1
        return call_count[0] == 1

    mock_oui_service.try_acquire_running_lock = acquire_lock

    async def post():
        return await client.post(
            "/api/v1/admin/oui/sync",
            json={},
            cookies={"sakn_session": token},
        )

    responses = await asyncio.gather(*(post() for _ in range(5)))
    statuses = sorted(r.status_code for r in responses)
    assert statuses == [202, 409, 409, 409, 409]

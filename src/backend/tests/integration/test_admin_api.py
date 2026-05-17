"""Integration tests for admin API endpoints.

Requires Redis for session storage. Test admin creates/manages users,
views logs, and manages tool modules.
"""

import pytest
from httpx import AsyncClient

from app.security.password import hash_password
from app.security.tokens import generate_token, hash_token
from tests.factories import create_user


async def _create_admin_session(client: AsyncClient, db) -> tuple[str, str]:
    """Create an admin user, set up a session, and return (user_id, session_token)."""
    from app.models import Session

    user = await create_user(
        db,
        email="admin@test.com",
        password_hash=hash_password("adminpass"),
        role="administrator",
    )
    session_token = generate_token()
    session = Session(
        id="ses_admin",
        user_id=user.id,
        token_hash=hash_token(session_token),
        ip_address="127.0.0.1",
    )
    db.add(session)
    await db.flush()
    return user.id, session_token


class TestAdminUserList:
    @pytest.mark.asyncio
    async def test_requires_admin(self, client: AsyncClient):
        """Unauthenticated request must be rejected."""
        response = await client.get("/api/v1/admin/users")
        assert response.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_list_users_as_admin(self, client: AsyncClient, db_session):
        """Admin can list users."""
        user_id, token = await _create_admin_session(client, db_session)

        response = await client.get(
            "/api/v1/admin/users",
            cookies={"sakn_session": token},
        )
        assert response.status_code == 200
        data = response.json()
        assert "users" in data
        assert any(u["email"] == "admin@test.com" for u in data["users"])


class TestAdminUserActions:
    @pytest.mark.asyncio
    async def test_block_user(self, client: AsyncClient, db_session):
        """Admin can block a user."""
        admin_id, token = await _create_admin_session(client, db_session)

        # Create a regular user to block
        user = await create_user(db_session, email="target@test.com")

        response = await client.post(
            f"/api/v1/admin/users/{user.id}/block",
            cookies={"sakn_session": token},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["message_key"] == "admin.user_blocked"

    @pytest.mark.asyncio
    async def test_unblock_user(self, client: AsyncClient, db_session):
        """Admin can unblock a user."""
        admin_id, token = await _create_admin_session(client, db_session)
        user = await create_user(
            db_session, email="blocked@test.com", status="blocked"
        )

        response = await client.post(
            f"/api/v1/admin/users/{user.id}/unblock",
            cookies={"sakn_session": token},
        )
        assert response.status_code == 200
        assert response.json()["message_key"] == "admin.user_unblocked"

    @pytest.mark.asyncio
    async def test_cannot_block_self(self, client: AsyncClient, db_session):
        """Admin cannot block their own account."""
        admin_id, token = await _create_admin_session(client, db_session)

        response = await client.post(
            f"/api/v1/admin/users/{admin_id}/block",
            cookies={"sakn_session": token},
        )
        assert response.status_code in (400, 422, 403)

    @pytest.mark.asyncio
    async def test_non_admin_cannot_block(self, client: AsyncClient, db_session):
        """Regular user cannot use admin endpoints."""
        from app.models import Session

        user = await create_user(
            db_session, email="regular@test.com", role="authenticated"
        )
        reg_token = generate_token()
        session = Session(
            id="ses_reg",
            user_id=user.id,
            token_hash=hash_token(reg_token),
            ip_address="127.0.0.1",
        )
        db_session.add(session)
        await db_session.flush()

        target = await create_user(db_session, email="target2@test.com")

        response = await client.post(
            f"/api/v1/admin/users/{target.id}/block",
            cookies={"sakn_session": reg_token},
        )
        assert response.status_code in (401, 403)


class TestAdminSettings:
    @pytest.mark.asyncio
    async def test_get_settings(self, client: AsyncClient, db_session):
        """Admin can read global settings."""
        admin_id, token = await _create_admin_session(client, db_session)

        response = await client.get(
            "/api/v1/admin/settings",
            cookies={"sakn_session": token},
        )
        assert response.status_code == 200


class TestAdminRateLimits:
    @pytest.mark.asyncio
    async def test_list_rate_limits(self, client: AsyncClient, db_session):
        """Admin can list rate limits."""
        admin_id, token = await _create_admin_session(client, db_session)

        response = await client.get(
            "/api/v1/admin/rate-limits",
            cookies={"sakn_session": token},
        )
        assert response.status_code == 200

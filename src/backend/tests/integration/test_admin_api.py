"""Integration tests for admin API endpoints.

Requires Redis for session storage. Test admin creates/manages users,
views logs, and manages tool modules.
"""

import pytest
from httpx import AsyncClient

from app.constants.roles import ROLE_ADMINISTRATOR, ROLE_AUTHENTICATED
from app.security.password import hash_password
from app.security.tokens import generate_token, hash_token
from tests.factories import create_user


async def _create_admin_session(client: AsyncClient, db) -> tuple[str, str]:
    """Create an admin user, set up a session, and return (user_id, session_token)."""
    from datetime import timedelta

    from sqlalchemy import select as sa_select

    from app.models import Session, User
    from app.models.base import new_uuid7, utcnow

    # Check if admin already exists (committed from a previous test)
    existing = await db.execute(
        sa_select(User).where(User.email == "admin@test.com")
    )
    user = existing.scalar_one_or_none()
    if user is None:
        user = await create_user(
            db,
            email="admin@test.com",
            password_hash=hash_password("adminpass"),
            role=ROLE_ADMINISTRATOR,
        )

    session_token = generate_token()
    session = Session(
        id=new_uuid7(),
        user_id=user.id,
        token_hash=hash_token(session_token),
        ip_address="127.0.0.1",
        expires_at=utcnow() + timedelta(hours=24),
    )
    db.add(session)
    await db.commit()
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
        # Create a regular user to block BEFORE _create_admin_session (which commits)
        user = await create_user(db_session, email="target@test.com")

        admin_id, token = await _create_admin_session(client, db_session)

        response = await client.put(
            f"/api/v1/admin/users/{user.id}/block",
            cookies={"sakn_session": token},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["message_key"] == "admin.user_blocked"

    @pytest.mark.asyncio
    async def test_unblock_user(self, client: AsyncClient, db_session):
        """Admin can unblock a user."""
        user = await create_user(
            db_session, email="blocked@test.com", status="blocked"
        )

        admin_id, token = await _create_admin_session(client, db_session)

        response = await client.put(
            f"/api/v1/admin/users/{user.id}/unblock",
            cookies={"sakn_session": token},
        )
        assert response.status_code == 200
        assert response.json()["message_key"] == "admin.user_unblocked"

    @pytest.mark.asyncio
    async def test_cannot_block_self(self, client: AsyncClient, db_session):
        """Admin cannot block their own account."""
        admin_id, token = await _create_admin_session(client, db_session)

        response = await client.put(
            f"/api/v1/admin/users/{admin_id}/block",
            cookies={"sakn_session": token},
        )
        assert response.status_code in (400, 422, 403)

    @pytest.mark.asyncio
    async def test_non_admin_cannot_block(self, client: AsyncClient, db_session):
        """Regular user cannot use admin endpoints."""
        from datetime import timedelta

        from app.models import Session
        from app.models.base import utcnow

        user = await create_user(
            db_session, email="regular@test.com", role=ROLE_AUTHENTICATED
        )
        reg_token = generate_token()
        session = Session(
            id="ses_reg",
            user_id=user.id,
            token_hash=hash_token(reg_token),
            ip_address="127.0.0.1",
            expires_at=utcnow() + timedelta(hours=24),
        )
        db_session.add(session)
        await db_session.flush()

        target = await create_user(db_session, email="target2@test.com")

        response = await client.put(
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


class TestAdminLikeEscape:
    """Issue #50: LIKE wildcards (% and _) must be escaped in admin user search."""

    @pytest.mark.asyncio
    async def test_search_percent_escaped(self, client: AsyncClient, db_session):
        """Search for % should match only literal %, not all users."""
        # Create test users BEFORE _create_admin_session (which commits)
        await create_user(db_session, email="wildcard%test@example.com")
        await create_user(db_session, email="normal@example.com")

        admin_id, token = await _create_admin_session(client, db_session)

        resp = await client.get(
            "/api/v1/admin/users",
            params={"search": "%"},
            cookies={"sakn_session": token},
        )
        assert resp.status_code == 200
        users = resp.json()["users"]
        emails = [u["email"] for u in users]
        assert "wildcard%test@example.com" in emails
        assert "normal@example.com" not in emails

    @pytest.mark.asyncio
    async def test_search_underscore_escaped(self, client: AsyncClient, db_session):
        """Search for _ should match only literal _, not any single character."""
        await create_user(db_session, email="test_user@example.com")
        await create_user(db_session, email="testZuser@example.com")

        admin_id, token = await _create_admin_session(client, db_session)

        resp = await client.get(
            "/api/v1/admin/users",
            params={"search": "_"},
            cookies={"sakn_session": token},
        )
        assert resp.status_code == 200
        users = resp.json()["users"]
        emails = [u["email"] for u in users]
        assert "test_user@example.com" in emails
        assert "testZuser@example.com" not in emails

    @pytest.mark.asyncio
    async def test_search_backslash_escaped(self, client: AsyncClient, db_session):
        """Search with backslash should be properly escaped and match literal backslash."""
        await create_user(db_session, email="bslash\\user@example.com")
        await create_user(db_session, email="bslashZuser@example.com")

        admin_id, token = await _create_admin_session(client, db_session)

        resp = await client.get(
            "/api/v1/admin/users",
            params={"search": "\\"},
            cookies={"sakn_session": token},
        )
        assert resp.status_code == 200
        users = resp.json()["users"]
        emails = [u["email"] for u in users]
        assert "bslash\\user@example.com" in emails
        assert "bslashZuser@example.com" not in emails


class TestAdminSearchMaxLength:
    """Issue #51: search query param must enforce max_length=128."""

    @pytest.mark.asyncio
    async def test_search_max_length_ok(self, client: AsyncClient, db_session):
        """search=128 chars is accepted."""
        admin_id, token = await _create_admin_session(client, db_session)

        resp = await client.get(
            "/api/v1/admin/users",
            params={"search": "x" * 128},
            cookies={"sakn_session": token},
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_search_max_length_exceeded(self, client: AsyncClient, db_session):
        """search=129 chars returns 422."""
        admin_id, token = await _create_admin_session(client, db_session)

        resp = await client.get(
            "/api/v1/admin/users",
            params={"search": "x" * 129},
            cookies={"sakn_session": token},
        )
        assert resp.status_code == 422


class TestAdminDnsServers:
    """Issue #59: Admin /dns-servers endpoint requires admin auth."""

    @pytest.mark.asyncio
    async def test_non_admin_returns_403(self, client: AsyncClient):
        """Unauthenticated request to admin DNS servers returns 401/403."""
        response = await client.get("/api/v1/admin/modules/ping/dns-servers")
        assert response.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_admin_gets_dns_servers(self, client: AsyncClient, db_session):
        """Admin can list DNS server presets for a tool."""
        from tests.factories import (
            create_dns_server_preset,
            create_tool_module,
        )

        # Create test data before _create_admin_session (which commits)
        tool = await create_tool_module(
            db_session, name="dns_admin_tool", enabled=True
        )
        await create_dns_server_preset(
            db_session,
            tool_module_id=tool.id,
            ip_address="8.8.8.8",
            description="Google DNS",
            sort_order=0,
        )

        admin_id, token = await _create_admin_session(client, db_session)

        response = await client.get(
            "/api/v1/admin/modules/dns_admin_tool/dns-servers",
            cookies={"sakn_session": token},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["tool"] == "dns_admin_tool"
        assert "presets" in data
        presets = data["presets"]
        assert len(presets) >= 1
        assert presets[0]["ip_address"] == "8.8.8.8"
        assert "id" in presets[0]
        assert "sort_order" in presets[0]

    @pytest.mark.asyncio
    async def test_nonexistent_tool_returns_404(self, client: AsyncClient, db_session):
        """Admin query for a non-existent tool returns 404."""
        admin_id, token = await _create_admin_session(client, db_session)

        response = await client.get(
            "/api/v1/admin/modules/nonexistent/dns-servers",
            cookies={"sakn_session": token},
        )
        assert response.status_code == 404

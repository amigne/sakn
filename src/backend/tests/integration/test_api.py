import pytest


@pytest.mark.asyncio
async def test_health_endpoint_minimal(client):
    """/health returns minimal liveness probe — no checks key, no auth."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data == {"status": "ok"}
    assert "checks" not in data
    # Security headers must be present on /health (issue #21 — M-1 fix)
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "Content-Security-Policy" in response.headers
    csp = response.headers["Content-Security-Policy"]
    # CSP style-src hardening (#22): unsafe-inline must not be in style-src-elem
    assert "style-src-elem 'self'" in csp
    assert "style-src-attr 'unsafe-inline'" in csp
    assert "object-src 'none'" in csp
    assert "base-uri 'self'" in csp
    assert "frame-ancestors 'none'" in csp
    assert response.headers["Permissions-Policy"] == "camera=(), microphone=(), geolocation=()"
    assert response.headers["Cross-Origin-Opener-Policy"] == "same-origin"
    assert response.headers["Cross-Origin-Embedder-Policy"] == "unsafe-none"


@pytest.mark.asyncio
async def test_health_full_not_configured(client):
    """/health/full returns 503 when HEALTH_FULL_TOKEN is not set."""
    response = await client.get("/health/full")
    assert response.status_code == 503
    data = response.json()
    assert data["error"]["code"] == "SERVICE_UNAVAILABLE"


@pytest.mark.asyncio
async def test_health_full_missing_token(client, monkeypatch):
    """/health/full returns 401 when token is missing but endpoint IS configured."""
    monkeypatch.setattr("app.main.settings.HEALTH_FULL_TOKEN", "configured-token")
    response = await client.get("/health/full")
    assert response.status_code == 401
    data = response.json()
    assert data["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_health_full_bad_token(client, monkeypatch):
    """/health/full returns 401 when token is wrong."""
    monkeypatch.setattr("app.main.settings.HEALTH_FULL_TOKEN", "correct-token")
    response = await client.get("/health/full", headers={"X-Health-Token": "wrong"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_health_full_correct_token(client, monkeypatch):
    """/health/full returns checks when token is correct (constant-time comparison)."""
    monkeypatch.setattr("app.main.settings.HEALTH_FULL_TOKEN", "test-health-token")
    response = await client.get("/health/full", headers={"X-Health-Token": "test-health-token"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "checks" in data
    assert data["checks"]["database"] in ("ok", "unavailable")
    assert data["checks"]["redis"] in ("ok", "unavailable")


@pytest.mark.asyncio
async def test_list_tools(client):
    from app.database import async_session_factory
    from app.models.tool_module import ToolModule, RoleToolPermission
    from sqlalchemy import select

    # Use the monkey-patched factory so middleware sees the data
    # Use unique names to avoid conflicts with model tests
    async with async_session_factory() as db:
        tool = ToolModule(name="ping", display_name_key="t.ping", description_key="d.ping",
                          enabled=True, version="1.0")
        db.add(tool)
        await db.flush()
        db.add(RoleToolPermission(role="visitor", tool_id=tool.id, allowed=True))
        await db.commit()

    try:
        response = await client.get("/api/v1/tools")
        assert response.status_code == 200
        data = response.json()
        assert "tools" in data
        tools = data["tools"]
        assert isinstance(tools, list)
        ping_tools = [t for t in tools if t["name"] == "ping"]
        assert len(ping_tools) == 1
        ping = ping_tools[0]
        assert ping["category"] == "network"
        assert len(ping["parameters"]) > 0
    finally:
        # Clean up to avoid polluting other tests
        async with async_session_factory() as db:
            from sqlalchemy import delete
            await db.execute(delete(RoleToolPermission).where(RoleToolPermission.tool_id == tool.id))
            await db.execute(delete(ToolModule).where(ToolModule.id == tool.id))
            await db.commit()


@pytest.mark.asyncio
async def test_execute_unknown_tool(client):
    response = await client.post("/api/v1/tools/nonexistent/execute", json={})
    assert response.status_code == 404
    data = response.json()
    # FastAPI HTTPException(detail=...) puts the structured error under "detail"
    assert data["detail"]["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_list_tools_for_role_validation(client):
    """GET /tools/available-for/{role}: valid roles return 200, unknown roles return 422."""
    from app.redis.rate_limit_store import get_rate_limiter

    # Clear before first request to avoid pollution from prior tests
    get_rate_limiter().clear_for_tests()

    # Valid role
    response = await client.get("/api/v1/tools/available-for/administrator")
    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "administrator"
    assert isinstance(data["tools"], list)

    # Clear in-memory rate limiter so the next request isn't blocked
    get_rate_limiter().clear_for_tests()

    # Unknown role — FastAPI returns 422 before the endpoint logic runs
    response = await client.get("/api/v1/tools/available-for/superadmin")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_health_database_check(client):
    """/health/minimal does NOT return checks — moved to /health/full."""
    response = await client.get("/health")
    data = response.json()
    assert "checks" not in data
    assert data == {"status": "ok"}


@pytest.mark.asyncio
async def test_rate_limit_blocks_after_hard_limit_reached(client):
    """Authenticated user is rate-limited after exceeding the hard limit.

    This test would have caught the UnboundLocalError on async_session_factory
    (issue #37): if the rate-limit middleware silently fails, no 429 is returned.
    """
    from datetime import timedelta
    from sqlalchemy import delete
    from app.database import async_session_factory as test_factory
    from app.models.base import new_uuid7, utcnow
    from app.models import User, Session
    from app.models.tool_module import RateLimitConfig
    from app.security.tokens import generate_token, hash_token
    from app.redis.rate_limit_store import get_rate_limiter

    # Clear the in-memory rate limit store between tests
    get_rate_limiter().clear_for_tests()

    raw_token = generate_token()
    token_hash = hash_token(raw_token)

    try:
        async with test_factory() as db:
            user = User(
                id=new_uuid7(),
                email="ratelimit-test@example.com",
                password_hash="hashed",
                role="authenticated",
                status="active",
                email_verified_at=utcnow(),
            )
            db.add(user)
            await db.flush()
            user_id = user.id

            session_obj = Session(
                id=new_uuid7(),
                user_id=user.id,
                token_hash=token_hash,
                ip_address="127.0.0.1",
                expires_at=utcnow() + timedelta(hours=24),
            )
            db.add(session_obj)
            await db.flush()

            # Low hard limit so the test doesn't need 500 requests
            rlc = RateLimitConfig(
                role="authenticated",
                tool_id=None,
                soft_limit=5,
                hard_limit=3,
                window_seconds=3600,
            )
            db.add(rlc)
            await db.flush()
            rlc_id = rlc.id
            await db.commit()

        cookies = {"sakn_session": raw_token}

        # First 3 requests should pass (hard_limit=3)
        for i in range(3):
            resp = await client.post(
                "/api/v1/tools/nonexistent/execute", json={}, cookies=cookies
            )
            assert resp.status_code != 429, (
                f"Request {i+1}/3: expected non-429, got {resp.status_code}"
            )

        # 4th request must be rate-limited
        resp = await client.post(
            "/api/v1/tools/nonexistent/execute", json={}, cookies=cookies
        )
        assert resp.status_code == 429
        data = resp.json()
        assert data["error"]["code"] == "RATE_LIMIT_EXCEEDED"
        assert data["error"]["details"]["limit_type"] == "hard"

    finally:
        # Clean up only the rows this test created, scoped by ID
        async with test_factory() as db:
            await db.execute(
                delete(Session).where(Session.token_hash == token_hash)
            )
            await db.execute(
                delete(RateLimitConfig).where(RateLimitConfig.id == rlc_id)
            )
            await db.execute(
                delete(User).where(User.id == user_id)
            )
            await db.commit()


class TestPublicDnsServers:
    """Issue #59: Public /dns-servers endpoint with enabled filter + role perm."""

    @pytest.fixture(autouse=True)
    def _clear_rate_limiter(self):
        from app.redis.rate_limit_store import get_rate_limiter
        get_rate_limiter().clear_for_tests()

    @pytest.mark.asyncio
    async def test_disabled_tool_returns_empty(self, client: AsyncClient, db_session):
        """Disabled tool returns empty servers list."""
        from tests.factories import (
            create_tool_module,
            create_role_permission,
            create_dns_server_preset,
        )

        tool = await create_tool_module(db_session, name="dns_disabled", enabled=False)
        await create_role_permission(
            db_session, role="visitor", tool_id=tool.id, allowed=True
        )
        await create_dns_server_preset(
            db_session, tool_module_id=tool.id, ip_address="1.2.3.4"
        )
        await db_session.commit()

        resp = await client.get("/api/v1/tools/dns_disabled/dns-servers")
        assert resp.status_code == 200
        data = resp.json()
        assert data == {"tool": "dns_disabled", "servers": []}

    @pytest.mark.asyncio
    async def test_enabled_tool_visitor_allowed_returns_presets(
        self, client: AsyncClient, db_session,
    ):
        """Enabled tool with visitor allowed returns DNS presets."""
        from tests.factories import (
            create_tool_module,
            create_role_permission,
            create_dns_server_preset,
        )

        tool = await create_tool_module(
            db_session, name="dns_enabled", enabled=True
        )
        await create_role_permission(
            db_session, role="visitor", tool_id=tool.id, allowed=True
        )
        await create_dns_server_preset(
            db_session,
            tool_module_id=tool.id,
            ip_address="8.8.8.8",
            description="Google",
        )
        await db_session.commit()

        resp = await client.get("/api/v1/tools/dns_enabled/dns-servers")
        assert resp.status_code == 200
        data = resp.json()
        assert data["tool"] == "dns_enabled"
        assert len(data["servers"]) == 1
        assert data["servers"][0]["value"] == "8.8.8.8"
        assert data["servers"][0]["label"] == "Google"

    @pytest.mark.asyncio
    async def test_visitor_not_allowed_returns_empty(
        self, client: AsyncClient, db_session,
    ):
        """Enabled tool where visitor is not allowed returns empty."""
        from tests.factories import (
            create_tool_module,
            create_role_permission,
            create_dns_server_preset,
        )

        tool = await create_tool_module(
            db_session, name="dns_visitor_denied", enabled=True
        )
        await create_role_permission(
            db_session, role="visitor", tool_id=tool.id, allowed=False
        )
        await create_dns_server_preset(
            db_session, tool_module_id=tool.id, ip_address="1.2.3.4"
        )
        await db_session.commit()

        resp = await client.get("/api/v1/tools/dns_visitor_denied/dns-servers")
        assert resp.status_code == 200
        data = resp.json()
        assert data == {"tool": "dns_visitor_denied", "servers": []}

    @pytest.mark.asyncio
    async def test_no_role_permission_returns_empty(
        self, client: AsyncClient, db_session,
    ):
        """Enabled tool with no role permission row at all returns empty."""
        from tests.factories import create_tool_module, create_dns_server_preset

        tool = await create_tool_module(
            db_session, name="dns_no_perm", enabled=True
        )
        await create_dns_server_preset(
            db_session, tool_module_id=tool.id, ip_address="1.2.3.4"
        )
        await db_session.commit()

        resp = await client.get("/api/v1/tools/dns_no_perm/dns-servers")
        assert resp.status_code == 200
        data = resp.json()
        assert data == {"tool": "dns_no_perm", "servers": []}

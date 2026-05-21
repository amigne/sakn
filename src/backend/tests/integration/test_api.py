import pytest


@pytest.mark.asyncio
async def test_health_endpoint(client):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "database" in data["checks"]
    assert "redis" in data["checks"]
    # Security headers must be present on /health (issue #21 — M-1 fix)
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "Content-Security-Policy" in response.headers


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
    assert response.status_code == 200
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_health_database_check(client):
    response = await client.get("/health")
    data = response.json()
    assert data["checks"]["database"] in ("ok", "unavailable")


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
    import app.middleware.rate_limit as rl_module

    # Monkey-patch the rate-limit middleware's module-level reference so it
    # uses the test DB (the mw_module patch in conftest.py doesn't cover it).
    original_rl_factory = rl_module.async_session_factory
    rl_module.async_session_factory = test_factory

    # Clear the in-memory rate limit store between tests
    get_rate_limiter()._db_fallback.clear()

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
            db.add(RateLimitConfig(
                role="authenticated",
                tool_id=None,
                soft_limit=5,
                hard_limit=3,
                window_seconds=3600,
            ))
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
        rl_module.async_session_factory = original_rl_factory

        # Clean up DB rows
        async with test_factory() as db:
            await db.execute(
                delete(Session).where(Session.token_hash == token_hash)
            )
            await db.execute(
                delete(RateLimitConfig).where(RateLimitConfig.role == "authenticated")
            )
            await db.execute(
                delete(User).where(User.email == "ratelimit-test@example.com")
            )
            await db.commit()

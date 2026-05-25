"""WebSocket fail-closed tests (#43, #60, #61).

The starlette TestClient accepts WebSocket connections regardless of server
behavior, making it unsuitable for testing close-before-accept scenarios.
Instead, we call tool_stream directly with a mock WebSocket, which correctly
exercises the authorization/rate-limit logic in isolation.
"""
import logging
from unittest.mock import AsyncMock, patch

import pytest

import app.api.v1.endpoints.tools as tools_mod
import app.database as db_module
from app.api.v1.endpoints.ws_codes import (
    WS_CLOSE_DB_UNAVAILABLE,
    WS_CLOSE_INVALID_ORIGIN,
    WS_CLOSE_RATE_LIMITED,
)
from app.security.tokens import generate_token, hash_token
from app.redis.rate_limit_store import get_rate_limiter
from tests.factories import (
    create_user,
    create_session,
    create_tool_module,
    create_role_permission,
    create_rate_limit_config,
)


def _make_mock_ws(origin="http://localhost:5173", cookies=""):
    """Build a mock WebSocket with the minimum attributes tool_stream reads."""
    ws = AsyncMock()
    ws.headers = {"origin": origin, "cookie": cookies}
    ws.client.host = "127.0.0.1"
    return ws


class TestWebSocketExceptionFailClosed:
    """Issue #43: WebSocket closes with WS_CLOSE_DB_UNAVAILABLE when DB raises during pre-accept."""

    @pytest.mark.asyncio
    async def test_db_exception_during_init_closes_WS_CLOSE_DB_UNAVAILABLE_and_logs(self):
        """If async_session_factory raises, the WS closes with WS_CLOSE_DB_UNAVAILABLE."""
        ws = _make_mock_ws()
        original = db_module.async_session_factory

        def raising_factory():
            raise Exception("DB connection failed")

        db_module.async_session_factory = raising_factory
        try:
            with patch.object(
                logging.getLogger("app.api.v1.endpoints.tools"), "exception"
            ) as mock_log:
                await tools_mod.tool_stream(ws, "ping")

            ws.close.assert_called_once()
            assert ws.close.call_args[1]["code"] == WS_CLOSE_DB_UNAVAILABLE
            assert ws.close.call_args[1]["reason"] == "db_unavailable"
            mock_log.assert_called_once()
            assert "DB error" in mock_log.call_args[0][0]
        finally:
            db_module.async_session_factory = original

    @pytest.mark.asyncio
    async def test_db_session_aenter_failure_closes_WS_CLOSE_DB_UNAVAILABLE(self):
        """If the DB session context manager raises on __aenter__, close WS_CLOSE_DB_UNAVAILABLE."""

        class _FailingCtx:
            async def __aenter__(self):
                raise Exception("Mid-query failure")

            async def __aexit__(self, *args):
                pass

        ws = _make_mock_ws()
        original = db_module.async_session_factory
        db_module.async_session_factory = lambda: _FailingCtx()
        try:
            await tools_mod.tool_stream(ws, "ping")
            ws.close.assert_called_once()
            assert ws.close.call_args[1]["code"] == WS_CLOSE_DB_UNAVAILABLE
            assert ws.close.call_args[1]["reason"] == "db_unavailable"
        finally:
            db_module.async_session_factory = original


class TestWebSocketDBUnavailable:
    """Issue #60: WebSocket closes with WS_CLOSE_DB_UNAVAILABLE when is_db_available() returns False."""

    @pytest.mark.asyncio
    async def test_db_unavailable_closes_WS_CLOSE_DB_UNAVAILABLE(self):
        """When is_db_available() is False, close immediately with WS_CLOSE_DB_UNAVAILABLE."""
        ws = _make_mock_ws()
        with patch.object(db_module, "is_db_available", return_value=False):
            await tools_mod.tool_stream(ws, "traceroute")

        ws.close.assert_called_once()
        assert ws.close.call_args[1]["code"] == WS_CLOSE_DB_UNAVAILABLE
        assert ws.close.call_args[1]["reason"] == "db_unavailable"
        # Accept must NOT have been called
        ws.accept.assert_not_called()


class TestWebSocketRateLimit:
    """Issue #61: WebSocket closes with WS_CLOSE_RATE_LIMITED when rate limit is exceeded."""

    @pytest.mark.asyncio
    async def test_rate_limit_rejected_with_WS_CLOSE_RATE_LIMITED(self, db_session, _engine):
        """Second connection attempt should be rate-limited with code WS_CLOSE_RATE_LIMITED."""
        get_rate_limiter()._db_fallback.clear()

        # Seed test data
        user = await create_user(db_session, email="wsratelimit@example.com")
        tool = await create_tool_module(db_session, name="ping", enabled=True)
        await create_role_permission(
            db_session, role="authenticated", tool_id=tool.id, allowed=True
        )

        raw_token = generate_token()
        await create_session(
            db_session, user_id=user.id, token_hash=hash_token(raw_token)
        )
        await create_rate_limit_config(
            db_session,
            role="authenticated",
            tool_id=None,
            soft_limit=1,
            hard_limit=1,
        )
        await db_session.commit()

        # Point app.database at the test DB so the WS endpoint sees seeded data
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

        test_factory = async_sessionmaker(
            _engine, class_=AsyncSession, expire_on_commit=False
        )
        original_factory = db_module.async_session_factory

        # Also patch the module-level reference in tools_mod
        original_tools_factory = tools_mod.async_session_factory
        db_module.async_session_factory = test_factory
        tools_mod.async_session_factory = test_factory

        try:
            cookies = f"sakn_session={raw_token}"
            ws1 = _make_mock_ws(cookies=cookies)

            # First call should NOT be rate-limited
            await tools_mod.tool_stream(ws1, "ping")
            assert ws1.close.call_args is None or ws1.close.call_args[1]["code"] != WS_CLOSE_RATE_LIMITED, (
                f"First connection should not be rate-limited"
            )

            # Second call must be rate-limited
            ws2 = _make_mock_ws(cookies=cookies)
            await tools_mod.tool_stream(ws2, "ping")
            ws2.close.assert_called_once()
            assert ws2.close.call_args[1]["code"] == WS_CLOSE_RATE_LIMITED, (
                f"Expected WS_CLOSE_RATE_LIMITED, got {ws2.close.call_args}"
            )
            assert ws2.close.call_args[1]["reason"] == "rate_limit_exceeded"
        finally:
            # Clean up committed DB rows (db_session rollback won't cover the commit above)
            from sqlalchemy import delete
            from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
            from app.models.tool_module import RoleToolPermission, RateLimitConfig
            from app.models.tool_module import ToolModule

            cleanup_factory = async_sessionmaker(
                _engine, class_=AsyncSession, expire_on_commit=False
            )
            async with cleanup_factory() as cleanup_db:
                await cleanup_db.execute(
                    delete(RateLimitConfig).where(
                        RateLimitConfig.role == "authenticated"
                    )
                )
                await cleanup_db.execute(
                    delete(RoleToolPermission).where(
                        RoleToolPermission.tool_id == tool.id
                    )
                )
                await cleanup_db.execute(
                    delete(ToolModule).where(ToolModule.id == tool.id)
                )
                await cleanup_db.commit()

            db_module.async_session_factory = original_factory
            tools_mod.async_session_factory = original_tools_factory
            get_rate_limiter()._db_fallback.clear()


class TestWebSocketRedisSessionException:
    """Issue #42: Redis session lookup failure logs the exception instead of silent pass."""

    @pytest.mark.asyncio
    async def test_redis_session_exception_is_logged(self):
        """When Redis session lookup raises, logger.exception is called and flow continues."""
        ws = _make_mock_ws(cookies="sakn_session=some-token-value")
        logger = logging.getLogger("app.api.v1.endpoints.tools")

        with patch.object(logger, "exception") as mock_log:
            # Patch redis_get to raise BEFORE it's imported inside tool_stream
            with patch(
                "app.redis.session_store.get_session",
                side_effect=Exception("Redis connection refused"),
            ):
                await tools_mod.tool_stream(ws, "ping")

        mock_log.assert_any_call("Redis session lookup failed for WS")


    @pytest.mark.asyncio
    async def test_rate_limit_creates_security_event_log(self, db_session, _engine):
        """Issue #62: rate limit rejection logs a SecurityEventLog row."""
        from app.models.log import SecurityEventLog
        from app.models.tool_module import ToolModule
        from sqlalchemy import delete, select as sa_select

        get_rate_limiter()._db_fallback.clear()

        # Clean up any leftover data from previous tests
        from app.models.tool_module import RateLimitConfig, RoleToolPermission
        await db_session.execute(delete(SecurityEventLog))
        await db_session.execute(delete(RateLimitConfig).where(RateLimitConfig.role == "authenticated"))
        await db_session.execute(delete(ToolModule).where(ToolModule.name == "ping"))

        user = await create_user(db_session, email="ws62@example.com")
        tool = await create_tool_module(db_session, name="ping", enabled=True)
        await create_role_permission(
            db_session, role="authenticated", tool_id=tool.id, allowed=True
        )

        raw_token = generate_token()
        await create_session(
            db_session, user_id=user.id, token_hash=hash_token(raw_token)
        )
        await create_rate_limit_config(
            db_session,
            role="authenticated",
            tool_id=None,
            soft_limit=1,
            hard_limit=1,
        )
        await db_session.commit()

        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

        test_factory = async_sessionmaker(
            _engine, class_=AsyncSession, expire_on_commit=False
        )
        original_factory = db_module.async_session_factory
        original_tools_factory = tools_mod.async_session_factory
        db_module.async_session_factory = test_factory
        tools_mod.async_session_factory = test_factory

        try:
            cookies = f"sakn_session={raw_token}"

            # Burn the one allowed request
            ws1 = _make_mock_ws(cookies=cookies)
            await tools_mod.tool_stream(ws1, "ping")

            # This call triggers rate limit → should create SecurityEventLog
            ws2 = _make_mock_ws(cookies=cookies)
            await tools_mod.tool_stream(ws2, "ping")
            assert ws2.close.call_args[1]["code"] == WS_CLOSE_RATE_LIMITED
            assert ws2.close.call_args[1]["reason"] == "rate_limit_exceeded"

            # Verify SecurityEventLog row was created
            from app.models.log import SecurityEventLog
            from sqlalchemy import select

            async with test_factory() as check_db:
                row = await check_db.execute(
                    select(SecurityEventLog).where(
                        SecurityEventLog.event_type == "ws_rate_limit_exceeded"
                    ).order_by(SecurityEventLog.created_at.desc()).limit(1)
                )
                entry = row.scalar_one_or_none()
                assert entry is not None, "Expected SecurityEventLog row for rate limit"
                assert entry.source_ip == "127.0.0.1"
        finally:
            db_module.async_session_factory = original_factory
            tools_mod.async_session_factory = original_tools_factory
            get_rate_limiter()._db_fallback.clear()


class TestWebSocketOriginValidation:
    """Issue #46: Origin validation with WS_REQUIRE_ORIGIN flag (ADR-009)."""

    @pytest.mark.asyncio
    async def test_origin_absent_allowed_when_flag_false(self):
        """Default: absent Origin → allow (non-browser clients pass)."""
        ws = _make_mock_ws(origin=None)
        # Remove origin from headers entirely to simulate absent Origin
        del ws.headers["origin"]

        with patch.object(db_module, "is_db_available", return_value=False):
            await tools_mod.tool_stream(ws, "ping")

        # Should close with DB_UNAVAILABLE (4503), meaning origin check passed
        ws.close.assert_called_once()
        assert ws.close.call_args[1]["code"] == WS_CLOSE_DB_UNAVAILABLE
        assert ws.close.call_args[1]["reason"] == "db_unavailable"

    @pytest.mark.asyncio
    async def test_origin_absent_rejected_when_flag_true(self):
        """WS_REQUIRE_ORIGIN=True: absent Origin → reject with 4003."""
        ws = _make_mock_ws(origin=None)
        del ws.headers["origin"]

        with patch.object(tools_mod.settings, "WS_REQUIRE_ORIGIN", True):
            await tools_mod.tool_stream(ws, "ping")

        ws.close.assert_called_once()
        assert ws.close.call_args[1]["code"] == WS_CLOSE_INVALID_ORIGIN
        assert ws.close.call_args[1]["reason"] == "origin_not_allowed"

    @pytest.mark.asyncio
    async def test_origin_not_in_allowlist_rejected(self):
        """Bad Origin → reject regardless of flag."""
        ws = _make_mock_ws(origin="https://evil.com")

        await tools_mod.tool_stream(ws, "ping")

        ws.close.assert_called_once()
        assert ws.close.call_args[1]["code"] == WS_CLOSE_INVALID_ORIGIN
        assert ws.close.call_args[1]["reason"] == "origin_not_allowed"

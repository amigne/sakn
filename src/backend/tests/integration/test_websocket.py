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
    """Issue #43: WebSocket closes with 4503 when DB raises during pre-accept."""

    @pytest.mark.asyncio
    async def test_db_exception_during_init_closes_4503_and_logs(self):
        """If async_session_factory raises, the WS closes with 4503."""
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
            assert ws.close.call_args[1]["code"] == 4503
            mock_log.assert_called_once()
            assert "DB error" in mock_log.call_args[0][0]
        finally:
            db_module.async_session_factory = original

    @pytest.mark.asyncio
    async def test_db_session_aenter_failure_closes_4503(self):
        """If the DB session context manager raises on __aenter__, close 4503."""

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
            assert ws.close.call_args[1]["code"] == 4503
        finally:
            db_module.async_session_factory = original


class TestWebSocketDBUnavailable:
    """Issue #60: WebSocket closes with 4503 when is_db_available() returns False."""

    @pytest.mark.asyncio
    async def test_db_unavailable_closes_4503(self):
        """When is_db_available() is False, close immediately with 4503."""
        ws = _make_mock_ws()
        with patch.object(db_module, "is_db_available", return_value=False):
            await tools_mod.tool_stream(ws, "traceroute")

        ws.close.assert_called_once()
        assert ws.close.call_args[1]["code"] == 4503
        # Accept must NOT have been called
        ws.accept.assert_not_called()


class TestWebSocketRateLimit:
    """Issue #61: WebSocket closes with 4029 when rate limit is exceeded."""

    @pytest.mark.asyncio
    async def test_rate_limit_rejected_with_4029(self, db_session, _engine):
        """Second connection attempt should be rate-limited with code 4029."""
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
            assert ws1.close.call_args is None or ws1.close.call_args[1]["code"] != 4029, (
                f"First connection should not be rate-limited"
            )

            # Second call must be rate-limited
            ws2 = _make_mock_ws(cookies=cookies)
            await tools_mod.tool_stream(ws2, "ping")
            ws2.close.assert_called_once()
            assert ws2.close.call_args[1]["code"] == 4029, (
                f"Expected 4029, got {ws2.close.call_args}"
            )
        finally:
            db_module.async_session_factory = original_factory
            tools_mod.async_session_factory = original_tools_factory
            get_rate_limiter()._db_fallback.clear()

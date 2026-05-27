"""WebSocket fail-closed tests (#43, #60, #61).

The starlette TestClient accepts WebSocket connections regardless of server
behavior, making it unsuitable for testing close-before-accept scenarios.
Instead, we call tool_stream directly with a mock WebSocket, which correctly
exercises the authorization/rate-limit logic in isolation.

NOTE: Starlette TestClient does not expose the pre-accept close code sent
by the server — it always reports 1000 regardless of the actual code.
The mock-based approach below records the real close code via
AsyncMock.close.call_args. See docs/qa/websocket-testing.md.
"""
import logging
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import WebSocketDisconnect

import app.api.v1.endpoints.tools as tools_mod
import app.database as db_module
from app.api.v1.endpoints.ws_codes import (
    WS_CLOSE_DB_UNAVAILABLE,
    WS_CLOSE_INVALID_ORIGIN,
    WS_CLOSE_RATE_LIMITED,
)
from app.redis.rate_limit_store import get_rate_limiter
from app.security.tokens import generate_token, hash_token
from tests.factories import (
    create_rate_limit_config,
    create_role_permission,
    create_session,
    create_tool_module,
    create_user,
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
    async def test_db_exception_during_init_closes_WS_CLOSE_DB_UNAVAILABLE_and_logs(self, monkeypatch):
        """If async_session_factory raises, the WS closes with WS_CLOSE_DB_UNAVAILABLE."""
        ws = _make_mock_ws()

        def raising_factory():
            raise Exception("DB connection failed")

        monkeypatch.setattr(db_module, "async_session_factory", raising_factory)
        monkeypatch.setattr(db_module, "is_db_available", lambda: True)
        with patch.object(
            logging.getLogger("app.api.v1.endpoints.tools"), "exception"
        ) as mock_log:
            await tools_mod.tool_stream(ws, "ping")

        ws.close.assert_called_once()
        assert ws.close.call_args[1]["code"] == WS_CLOSE_DB_UNAVAILABLE
        assert ws.close.call_args[1]["reason"] == "db_unavailable"
        mock_log.assert_called_once()
        assert "DB error" in mock_log.call_args[0][0]

    @pytest.mark.asyncio
    async def test_db_session_aenter_failure_closes_WS_CLOSE_DB_UNAVAILABLE(self, monkeypatch):
        """If the DB session context manager raises on __aenter__, close WS_CLOSE_DB_UNAVAILABLE."""

        class _FailingCtx:
            async def __aenter__(self):
                raise Exception("Mid-query failure")

            async def __aexit__(self, *args):
                pass

        ws = _make_mock_ws()
        monkeypatch.setattr(db_module, "async_session_factory", lambda: _FailingCtx())
        monkeypatch.setattr(db_module, "is_db_available", lambda: True)
        await tools_mod.tool_stream(ws, "ping")
        ws.close.assert_called_once()
        assert ws.close.call_args[1]["code"] == WS_CLOSE_DB_UNAVAILABLE
        assert ws.close.call_args[1]["reason"] == "db_unavailable"


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
    async def test_rate_limit_rejected_with_WS_CLOSE_RATE_LIMITED(self, db_session, _engine, monkeypatch):
        """Second connection attempt should be rate-limited with code WS_CLOSE_RATE_LIMITED."""
        get_rate_limiter().clear_for_tests()

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
        monkeypatch.setattr(db_module, "async_session_factory", test_factory)
        monkeypatch.setattr(tools_mod, "async_session_factory", test_factory)
        monkeypatch.setattr(db_module, "is_db_available", lambda: True)

        try:
            cookies = f"sakn_session={raw_token}"
            ws1 = _make_mock_ws(cookies=cookies)

            # First call should NOT be rate-limited
            await tools_mod.tool_stream(ws1, "ping")
            assert ws1.close.call_args is None or ws1.close.call_args[1]["code"] != WS_CLOSE_RATE_LIMITED, (
                "First connection should not be rate-limited"
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

            from app.models.tool_module import RateLimitConfig, RoleToolPermission, ToolModule

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

            get_rate_limiter().clear_for_tests()


class TestWebSocketRedisSessionException:
    """Issue #42: Redis session lookup failure logs the exception instead of silent pass."""

    @pytest.mark.asyncio
    async def test_redis_session_exception_is_logged(self, _engine, monkeypatch):
        """When Redis session lookup raises, logger.exception is called and flow continues."""
        from sqlalchemy import delete
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

        from app.models import ToolModule
        from app.models.base import new_uuid7
        from app.models.tool_module import RoleToolPermission

        # Seed a deterministic DB so tool_stream finds ToolModule(name="ping")
        # regardless of CWD or the state of the production sakn.db.
        test_factory = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)
        tool_id = new_uuid7()

        async with test_factory() as seed_db:
            seed_db.add(ToolModule(
                id=tool_id, name="ping", display_name_key="t.ping",
                description_key="d.ping", enabled=True, version="1.0",
            ))
            await seed_db.flush()
            seed_db.add(RoleToolPermission(
                id=new_uuid7(), role="visitor", tool_id=tool_id, allowed=True,
            ))
            await seed_db.commit()

        monkeypatch.setattr(db_module, "async_session_factory", test_factory)
        monkeypatch.setattr(tools_mod, "async_session_factory", test_factory)
        monkeypatch.setattr(db_module, "is_db_available", lambda: True)

        try:
            ws = _make_mock_ws(cookies="sakn_session=some-token-value")
            logger = logging.getLogger("app.api.v1.endpoints.tools")

            with patch.object(logger, "exception") as mock_log, patch(
                "app.redis.session_store.get_session",
                side_effect=Exception("Redis connection refused"),
            ):
                await tools_mod.tool_stream(ws, "ping")

            mock_log.assert_any_call("Redis session lookup failed for WS")
        finally:
            # Clean up seeded data so we don't pollute other tests
            async with test_factory() as cleanup_db:
                await cleanup_db.execute(
                    delete(RoleToolPermission).where(RoleToolPermission.tool_id == tool_id)
                )
                await cleanup_db.execute(
                    delete(ToolModule).where(ToolModule.id == tool_id)
                )
                await cleanup_db.commit()


    @pytest.mark.asyncio
    async def test_rate_limit_creates_security_event_log(self, db_session, _engine, monkeypatch):
        """Issue #62: rate limit rejection logs a SecurityEventLog row."""
        from sqlalchemy import delete

        from app.models.log import SecurityEventLog
        from app.models.tool_module import ToolModule

        get_rate_limiter().clear_for_tests()

        # Clean up any leftover data from previous tests
        from app.models.tool_module import RateLimitConfig
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
        monkeypatch.setattr(db_module, "async_session_factory", test_factory)
        monkeypatch.setattr(tools_mod, "async_session_factory", test_factory)
        monkeypatch.setattr(db_module, "is_db_available", lambda: True)

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
            from sqlalchemy import select

            from app.models.log import SecurityEventLog

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
            get_rate_limiter().clear_for_tests()


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


class TestTracerouteWSMasking:
    """Issue #227: mask_private_hops is applied in the WebSocket handler.

    Regression test for PR #225 which fixed IP masking of private hops.
    If someone removes the _mask_private call in handle_traceroute_stream,
    this test fails — private IPs leak into the WebSocket output.
    """

    @pytest.mark.asyncio
    async def test_masks_private_hops_in_ws_stream(self, monkeypatch):
        import asyncio as asyncio_mod
        from unittest.mock import AsyncMock, MagicMock

        from app.websocket.handlers.traceroute_ws import handle_traceroute_stream

        # ── Mock filter_target: allow the target, return a public IP ──
        async def _mock_filter_target(target):
            return ("93.184.216.34", None)

        monkeypatch.setattr(
            "app.websocket.handlers.traceroute_ws.filter_target",
            _mock_filter_target,
        )

        # ── Mock DB: async_session_factory returns a session with show_private=False ──
        class _MockDBSession:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            async def execute(self, *args, **kwargs):
                mock_setting = MagicMock()
                mock_setting.value = "false"
                mock_result = MagicMock()
                mock_result.scalar_one_or_none.return_value = mock_setting
                return mock_result

        def _mock_session_factory():
            return _MockDBSession()

        monkeypatch.setattr(
            "app.websocket.handlers.traceroute_ws.async_session_factory",
            _mock_session_factory,
        )

        # ── Mock subprocess: emit a hop with a private IP (10.0.0.1) ──
        fake_stdout_lines = [
            b" 1  10.0.0.1  2.334 ms  2.123 ms  1.987 ms\n",
        ]

        mock_stdout = MagicMock()
        mock_stdout.readline = AsyncMock(side_effect=fake_stdout_lines + [b""])

        mock_stderr = MagicMock()
        mock_stderr.readline = AsyncMock(return_value=b"")

        async def _mock_process_wait():
            return 0

        mock_process = MagicMock()
        mock_process.stdout = mock_stdout
        mock_process.stderr = mock_stderr
        mock_process.wait = _mock_process_wait
        mock_process.returncode = 0

        async def _mock_create_subprocess_exec(*args, **kwargs):
            return mock_process

        monkeypatch.setattr(
            asyncio_mod, "create_subprocess_exec", _mock_create_subprocess_exec
        )

        # ── Mock WebSocket: send start, collect all output messages ──
        sent_messages: list[dict] = []

        async def _collect_send_json(data):
            sent_messages.append(data)

        ws = AsyncMock()
        ws.send_json = _collect_send_json
        # Second receive_json() is called by listen_cancel; raise to end the
        # cancel loop (safe because the mock process already completed).
        ws.receive_json = AsyncMock(side_effect=[
            {"type": "start", "params": {"target": "example.com"}},
            WebSocketDisconnect(code=1000, reason=""),
        ])

        await handle_traceroute_stream(ws, "session-id", None, "127.0.0.1")

        # ── Assertions ──
        # Find all "result" messages
        hop_messages = [m for m in sent_messages if m.get("type") == "result"]
        assert len(hop_messages) == 1, (
            f"Expected 1 hop message, got {len(hop_messages)}: {sent_messages}"
        )

        hop_data = hop_messages[0]["data"]
        # The private IP (10.0.0.1) MUST be masked to [hidden]
        assert hop_data["ip"] == "[hidden]", (
            f"Private IP leaked: expected '[hidden]', got '{hop_data['ip']}'"
        )
        # Probes must still be present (the fix in #225 preserves them)
        assert "probes" in hop_data, "probes key missing from hop data"
        assert len(hop_data["probes"]) == 3, (
            f"Expected 3 probes, got {len(hop_data['probes'])}"
        )

        # Verify a "complete" message was sent eventually
        complete = [m for m in sent_messages if m.get("type") == "complete"]
        assert len(complete) == 1, "Expected a 'complete' message at the end"

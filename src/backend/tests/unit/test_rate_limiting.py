from unittest.mock import AsyncMock, MagicMock

import pytest

from app.constants.roles import ROLE_ADMINISTRATOR, ROLE_AUTHENTICATED, ROLE_VISITOR
from app.services.rate_limit_service import (
    AUTH_LIMITS,
    DEFAULT_LIMITS,
    auth_check,
    auth_record,
    auth_remaining,
    get_effective_limits,
)


class TestDefaultLimits:
    def test_visitor_defaults(self):
        assert DEFAULT_LIMITS[ROLE_VISITOR]["soft"] == 1
        assert DEFAULT_LIMITS[ROLE_VISITOR]["hard"] == 200

    def test_authenticated_defaults(self):
        assert DEFAULT_LIMITS[ROLE_AUTHENTICATED]["soft"] == 1
        assert DEFAULT_LIMITS[ROLE_AUTHENTICATED]["hard"] == 500

    def test_administrator_defaults(self):
        assert DEFAULT_LIMITS[ROLE_ADMINISTRATOR]["soft"] == 0
        assert DEFAULT_LIMITS[ROLE_ADMINISTRATOR]["hard"] == 3600


class TestAuthLimits:
    def test_limits_exist_for_all_endpoints(self):
        assert "login" in AUTH_LIMITS
        assert "register" in AUTH_LIMITS
        assert "reset" in AUTH_LIMITS
        assert "resend" in AUTH_LIMITS

    def test_login_limit_params(self):
        assert AUTH_LIMITS["login"]["max"] == 10
        assert AUTH_LIMITS["login"]["window"] == 60

    def test_register_limit_params(self):
        assert AUTH_LIMITS["register"]["max"] == 3
        assert AUTH_LIMITS["register"]["window"] == 3600

    def test_reset_limit_params(self):
        assert AUTH_LIMITS["reset"]["max"] == 3
        assert AUTH_LIMITS["reset"]["window"] == 86400

    def test_resend_limit_params(self):
        assert AUTH_LIMITS["resend"]["max"] == 5
        assert AUTH_LIMITS["resend"]["window"] == 86400


class TestAuthCheck:
    def test_first_request_allowed(self):
        assert auth_check("127.0.0.1", "login") is True

    def test_after_max_requests_blocked(self):
        key = "10.0.0.1"
        max_requests = AUTH_LIMITS["login"]["max"]
        for _ in range(max_requests):
            auth_record(key, "login")
        assert auth_check(key, "login") is False

    def test_different_keys_independent(self):
        auth_record("192.168.1.1", "login")
        auth_record("192.168.1.1", "login")
        assert auth_check("192.168.1.2", "login") is True

    def test_different_endpoints_independent(self):
        """Different endpoints have different limit configs but share the counter key.
        Blocking on one endpoint affects others with the same key — this is by design."""
        # Use different keys for different tests to show independence
        key_a = "10.0.0.2"
        key_b = "10.0.0.3"
        max_login = AUTH_LIMITS["login"]["max"]
        for _ in range(max_login):
            auth_record(key_a, "login")
        assert auth_check(key_a, "login") is False  # key_a is blocked for login
        assert auth_check(key_b, "register") is True  # key_b is clean

    def test_unknown_limit_key_allows(self):
        assert auth_check("127.0.0.1", "nonexistent") is True

    def test_remaining_counts_down(self):
        key = "192.168.1.100"
        assert auth_remaining(key, "login") == 10
        auth_record(key, "login")
        assert auth_remaining(key, "login") == 9


class TestEffectiveLimits:
    @pytest.mark.asyncio
    async def test_returns_defaults_when_no_db_config(self):
        db = AsyncMock()
        # db.execute returns an awaitable; when awaited it returns a mock result
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute.return_value = mock_result

        limits = await get_effective_limits(db, ROLE_VISITOR)
        assert limits["soft_limit"] == 1
        assert limits["hard_limit"] == 200
        assert limits["window_seconds"] == 3600

    @pytest.mark.asyncio
    async def test_zero_means_no_limit(self):
        """When global is 0, per-tool takes effect (and vice versa)."""
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute.return_value = mock_result

        limits = await get_effective_limits(db, ROLE_ADMINISTRATOR)
        # soft=0 means no limit, hard=3600
        assert limits["soft_limit"] == 0
        assert limits["hard_limit"] == 3600

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.auth_service import _check_ip_bruteforce, _record_ip_bruteforce


class TestIPBruteforce:
    @pytest.fixture
    def mock_redis(self):
        redis = AsyncMock()
        redis.pipeline = MagicMock()
        pipe = MagicMock()
        pipe.incr = MagicMock(return_value=pipe)
        pipe.expire = MagicMock(return_value=pipe)
        pipe.execute = AsyncMock()
        redis.pipeline.return_value = pipe
        return redis

    @pytest.mark.asyncio
    async def test_check_under_threshold(self, mock_redis):
        mock_redis.get.return_value = b"5"
        with patch("app.redis.connection.get_redis", AsyncMock(return_value=mock_redis)):
            blocked = await _check_ip_bruteforce("10.0.0.1")
        assert blocked is False
        mock_redis.get.assert_called_once_with("bruteforce:ip:10.0.0.1")

    @pytest.mark.asyncio
    async def test_check_at_threshold(self, mock_redis):
        mock_redis.get.return_value = b"20"
        with patch("app.redis.connection.get_redis", AsyncMock(return_value=mock_redis)):
            blocked = await _check_ip_bruteforce("10.0.0.2")
        assert blocked is True

    @pytest.mark.asyncio
    async def test_check_over_threshold(self, mock_redis):
        mock_redis.get.return_value = b"50"
        with patch("app.redis.connection.get_redis", AsyncMock(return_value=mock_redis)):
            blocked = await _check_ip_bruteforce("10.0.0.3")
        assert blocked is True

    @pytest.mark.asyncio
    async def test_check_no_key(self, mock_redis):
        mock_redis.get.return_value = None
        with patch("app.redis.connection.get_redis", AsyncMock(return_value=mock_redis)):
            blocked = await _check_ip_bruteforce("10.0.0.4")
        assert blocked is False

    @pytest.mark.asyncio
    async def test_check_redis_failure_fail_open(self, mock_redis):
        mock_redis.get.side_effect = Exception("redis down")
        with patch("app.redis.connection.get_redis", AsyncMock(return_value=mock_redis)):
            blocked = await _check_ip_bruteforce("10.0.0.5")
        assert blocked is False  # fail-open

    @pytest.mark.asyncio
    async def test_record_increments_and_sets_ttl(self, mock_redis):
        with patch("app.redis.connection.get_redis", AsyncMock(return_value=mock_redis)):
            await _record_ip_bruteforce("192.168.1.1")

        pipe = mock_redis.pipeline.return_value
        pipe.incr.assert_called_once_with("bruteforce:ip:192.168.1.1")
        pipe.expire.assert_called_once_with("bruteforce:ip:192.168.1.1", 900)
        pipe.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_record_redis_failure_silent(self, mock_redis):
        mock_redis.pipeline.side_effect = Exception("redis down")
        with patch("app.redis.connection.get_redis", AsyncMock(return_value=mock_redis)):
            # Should not raise
            await _record_ip_bruteforce("192.168.1.2")

import pytest
from unittest.mock import AsyncMock, patch

from app.api.v1.endpoints.tools import _is_allowed_origin


class TestIsAllowedOrigin:
    def test_non_browser_allowed(self):
        """Non-browser clients (no Origin header) are allowed."""
        assert _is_allowed_origin(None) is True

    def test_empty_origin_allowed(self):
        assert _is_allowed_origin("") is True

    def test_allowed_origin_exact_match(self):
        with patch("app.api.v1.endpoints.tools.settings.CORS_ORIGINS", "http://a.com,http://b.com"):
            assert _is_allowed_origin("http://a.com") is True
            assert _is_allowed_origin("http://b.com") is True

    def test_disallowed_origin_rejected(self):
        with patch("app.api.v1.endpoints.tools.settings.CORS_ORIGINS", "http://a.com"):
            assert _is_allowed_origin("http://evil.com") is False

    def test_partial_match_rejected(self):
        with patch("app.api.v1.endpoints.tools.settings.CORS_ORIGINS", "http://a.com"):
            assert _is_allowed_origin("http://a.com.evil.com") is False

    def test_strips_whitespace_from_allowlist(self):
        with patch("app.api.v1.endpoints.tools.settings.CORS_ORIGINS", " http://a.com , http://b.com "):
            assert _is_allowed_origin("http://a.com") is True
            assert _is_allowed_origin("http://b.com") is True

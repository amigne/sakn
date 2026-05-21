import pytest
from unittest.mock import AsyncMock, patch

from starlette.responses import Response


class TestSecurityHeaders:
    """Tests for SecurityHeadersMiddleware — applies headers to all routes except exempt paths."""

    @pytest.fixture
    def middleware(self):
        from app.middleware.security_headers import SecurityHeadersMiddleware
        return SecurityHeadersMiddleware(app=None)

    @pytest.fixture
    async def call_next(self):
        async def _call_next(request):
            return Response("ok")
        return _call_next

    @pytest.mark.asyncio
    async def test_health_path_gets_headers(self, middleware, call_next):
        """/health is not under /api/ — it should still receive security headers."""
        from starlette.requests import Request
        scope = {"type": "http", "method": "GET", "path": "/health", "headers": []}
        request = Request(scope)
        response = await middleware.dispatch(request, call_next)
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
        assert "Content-Security-Policy" in response.headers

    @pytest.mark.asyncio
    async def test_api_path_gets_headers(self, middleware, call_next):
        from starlette.requests import Request
        scope = {"type": "http", "method": "GET", "path": "/api/v1/tools", "headers": []}
        request = Request(scope)
        response = await middleware.dispatch(request, call_next)
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
        assert "Content-Security-Policy" in response.headers

    @pytest.mark.asyncio
    async def test_docs_path_skips_headers(self, middleware, call_next):
        from starlette.requests import Request
        scope = {"type": "http", "method": "GET", "path": "/docs", "headers": []}
        request = Request(scope)
        response = await middleware.dispatch(request, call_next)
        assert "X-Content-Type-Options" not in response.headers
        assert "X-Frame-Options" not in response.headers

    @pytest.mark.asyncio
    async def test_redoc_path_skips_headers(self, middleware, call_next):
        from starlette.requests import Request
        scope = {"type": "http", "method": "GET", "path": "/redoc", "headers": []}
        request = Request(scope)
        response = await middleware.dispatch(request, call_next)
        assert "X-Content-Type-Options" not in response.headers

    @pytest.mark.asyncio
    async def test_hsts_not_set_in_dev(self, middleware, call_next):
        from starlette.requests import Request
        with patch("app.middleware.security_headers.settings.ENVIRONMENT", "development"):
            scope = {"type": "http", "method": "GET", "path": "/health", "headers": []}
            request = Request(scope)
            response = await middleware.dispatch(request, call_next)
        assert "Strict-Transport-Security" not in response.headers

    @pytest.mark.asyncio
    async def test_hsts_set_in_production(self, middleware, call_next):
        from starlette.requests import Request
        with patch("app.middleware.security_headers.settings.ENVIRONMENT", "production"):
            scope = {"type": "http", "method": "GET", "path": "/health", "headers": []}
            request = Request(scope)
            response = await middleware.dispatch(request, call_next)
        assert response.headers["Strict-Transport-Security"] == "max-age=63072000; includeSubDomains"

    @pytest.mark.asyncio
    async def test_root_path_gets_headers(self, middleware, call_next):
        """Even if no route is registered at /, middleware should still apply headers."""
        from starlette.requests import Request
        scope = {"type": "http", "method": "GET", "path": "/", "headers": []}
        request = Request(scope)
        response = await middleware.dispatch(request, call_next)
        assert response.headers["X-Content-Type-Options"] == "nosniff"

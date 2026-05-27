from unittest.mock import patch

import pytest
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

    @pytest.mark.asyncio
    async def test_csp_style_src_elem_blocks_unsafe_inline(self, middleware, call_next):
        """style-src-elem must allow 'self' but NOT 'unsafe-inline'."""
        from starlette.requests import Request
        scope = {"type": "http", "method": "GET", "path": "/health", "headers": []}
        request = Request(scope)
        response = await middleware.dispatch(request, call_next)
        csp = response.headers["Content-Security-Policy"]
        # Extract the style-src-elem directive value
        elem_part = [d.strip() for d in csp.split(";") if "style-src-elem" in d][0]
        assert "'self'" in elem_part
        assert "'unsafe-inline'" not in elem_part

    @pytest.mark.asyncio
    async def test_csp_style_src_attr_allows_unsafe_inline(self, middleware, call_next):
        """style-src-attr must contain 'unsafe-inline' for Radix UI Popper."""
        from starlette.requests import Request
        scope = {"type": "http", "method": "GET", "path": "/health", "headers": []}
        request = Request(scope)
        response = await middleware.dispatch(request, call_next)
        csp = response.headers["Content-Security-Policy"]
        assert "style-src-attr 'unsafe-inline'" in csp

    @pytest.mark.asyncio
    async def test_csp_hardening_directives_present(self, middleware, call_next):
        """object-src, base-uri, frame-ancestors must all be present."""
        from starlette.requests import Request
        scope = {"type": "http", "method": "GET", "path": "/health", "headers": []}
        request = Request(scope)
        response = await middleware.dispatch(request, call_next)
        csp = response.headers["Content-Security-Policy"]
        assert "object-src 'none'" in csp
        assert "base-uri 'self'" in csp
        assert "frame-ancestors 'none'" in csp

    @pytest.mark.asyncio
    async def test_csp_style_src_fallback_absent(self, middleware, call_next):
        """Bare style-src (without -elem or -attr suffix) must NOT be present."""
        from starlette.requests import Request
        scope = {"type": "http", "method": "GET", "path": "/health", "headers": []}
        request = Request(scope)
        response = await middleware.dispatch(request, call_next)
        csp = response.headers["Content-Security-Policy"]
        import re
        assert not re.search(r"\bstyle-src\s", csp)

    @pytest.mark.asyncio
    async def test_permissions_policy_present(self, middleware, call_next):
        from starlette.requests import Request
        scope = {"type": "http", "method": "GET", "path": "/health", "headers": []}
        request = Request(scope)
        response = await middleware.dispatch(request, call_next)
        assert response.headers["Permissions-Policy"] == "camera=(), microphone=(), geolocation=()"

    @pytest.mark.asyncio
    async def test_coop_present(self, middleware, call_next):
        from starlette.requests import Request
        scope = {"type": "http", "method": "GET", "path": "/health", "headers": []}
        request = Request(scope)
        response = await middleware.dispatch(request, call_next)
        assert response.headers["Cross-Origin-Opener-Policy"] == "same-origin"

    @pytest.mark.asyncio
    async def test_coep_present(self, middleware, call_next):
        from starlette.requests import Request
        scope = {"type": "http", "method": "GET", "path": "/health", "headers": []}
        request = Request(scope)
        response = await middleware.dispatch(request, call_next)
        assert response.headers["Cross-Origin-Embedder-Policy"] == "unsafe-none"

    @pytest.mark.asyncio
    async def test_docs_path_skips_new_headers(self, middleware, call_next):
        """Exempt paths must not receive Permissions-Policy, COOP, or COEP."""
        from starlette.requests import Request
        scope = {"type": "http", "method": "GET", "path": "/docs", "headers": []}
        request = Request(scope)
        response = await middleware.dispatch(request, call_next)
        assert "Permissions-Policy" not in response.headers
        assert "Cross-Origin-Opener-Policy" not in response.headers
        assert "Cross-Origin-Embedder-Policy" not in response.headers

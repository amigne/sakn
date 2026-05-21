from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.config import settings

# Paths excluded from security headers (OpenAPI docs, only relevant when enabled in dev)
_EXEMPT_PREFIXES = {"/docs", "/redoc", "/openapi.json"}

# Security header values — computed once at import time
_CSP_HEADER = (
    "default-src 'self'; script-src 'self'; style-src-elem 'self'; "
    "style-src-attr 'unsafe-inline'; img-src 'self' data:; "
    "connect-src 'self' ws: wss:; form-action 'self'; "
    "object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
)
_HSTS_HEADER = "max-age=63072000; includeSubDomains"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses (except OpenAPI doc paths)."""

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)

        if request.url.path in _EXEMPT_PREFIXES:
            return response

        response.headers["Content-Security-Policy"] = _CSP_HEADER
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        if settings.ENVIRONMENT == "production":
            response.headers["Strict-Transport-Security"] = _HSTS_HEADER

        return response

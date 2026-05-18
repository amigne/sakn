"""ASGI rate limit middleware.

Enforces global rate limits on tool execution endpoints, adding
standard X-RateLimit-* and Retry-After response headers.

Visitors get dual session+IP checks. Auth endpoints have their
own hardcoded limits (applied in auth endpoint handlers, not here).
"""

import logging
import time
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request, Response
from fastapi.responses import JSONResponse

from app.database import async_session_factory, is_db_available
from app.services.rate_limit_service import check_tool_rate_limit

logger = logging.getLogger(__name__)

# Tool execution paths subject to rate limiting
RATE_LIMITED_PREFIXES = ("/api/v1/tools/",)

# Auth paths with hardcoded limits — rate limit applied in endpoint handlers
AUTH_PREFIXES = ("/api/v1/auth/",)

# Admin paths — different limits but still enforced
ADMIN_PREFIXES = ("/api/v1/admin/",)


def _build_rate_limit_headers(result) -> dict[str, str]:
    """Build standard rate limit response headers."""
    headers: dict[str, str] = {}

    if result.limit_type == "soft":
        headers["Retry-After"] = str(result.retry_after)
        headers["X-RateLimit-Limit"] = str(result.soft_limit)
        headers["X-RateLimit-Remaining"] = "0"
        headers["X-RateLimit-Policy"] = f"{result.soft_limit} req/{result.soft_window_s}s"
    elif result.limit_type == "hard":
        headers["Retry-After"] = str(result.retry_after)
        headers["X-RateLimit-Limit"] = str(result.hard_limit)
        headers["X-RateLimit-Remaining"] = "0"
        headers["X-RateLimit-Policy"] = f"{result.hard_limit} req/{result.hard_window_s}s"
    else:
        remaining = max(0, result.hard_limit - result.hard_count) if result.hard_limit > 0 else 0
        headers["X-RateLimit-Limit"] = str(result.hard_limit)
        headers["X-RateLimit-Remaining"] = str(remaining)
        # Warning at ≥80% usage
        if result.hard_limit > 0 and result.hard_count > 0:
            usage = result.hard_count / result.hard_limit
            if usage >= 0.8:
                headers["X-RateLimit-Warning"] = "true"

    return headers


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Enforce rate limits on tool execution and admin endpoints."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Admin endpoints are protected by require_admin — no rate limiting needed
        if path.startswith("/api/v1/admin/"):
            return await call_next(request)

        # Only rate-limit tool execution paths
        if not any(path.startswith(p) for p in RATE_LIMITED_PREFIXES):
            return await call_next(request)

        # Skip GET /tools (listing) for rate limiting
        if path == "/api/v1/tools" and request.method == "GET":
            return await call_next(request)

        # Resolve identity from request state (set by SessionMiddleware)
        role = getattr(request.state, "role", "visitor")
        user_id = getattr(request.state, "user_id", None)
        session_id = getattr(request.state, "session_id", "unknown")
        source_ip = request.client.host if request.client else "unknown"

        # If session middleware didn't resolve the user but a cookie is present,
        # try to resolve it directly from the DB
        if role == "visitor" and user_id is None:
            from app.security.cookies import get_session_token

            session_token = get_session_token(request)
            if session_token:
                try:
                    from app.security.tokens import hash_token
                    from app.database import async_session_factory
                    from sqlalchemy import select
                    from app.models import Session, User

                    token_hash = hash_token(session_token)
                    async with async_session_factory() as db:
                        srow = await db.execute(
                            select(Session).where(Session.token_hash == token_hash)
                        )
                        sess = srow.scalar_one_or_none()
                        if sess and sess.user_id:
                            urow = await db.execute(
                                select(User.role).where(User.id == sess.user_id)
                            )
                            urole = urow.scalar_one_or_none()
                            if urole:
                                role = urole
                                user_id = sess.user_id
                                session_id = sess.id
                except Exception:
                    pass  # Keep visitor defaults if lookup fails

        result = None
        if is_db_available():
            try:
                async with async_session_factory() as db:
                    result = await check_tool_rate_limit(
                        db,
                        role=role,
                        user_id=user_id,
                        session_id=session_id,
                        source_ip=source_ip,
                    )
            except Exception:
                logger.exception("Rate limit check failed, allowing request")
                return await call_next(request)
        else:
            # No DB: allow request, skip rate limiting
            return await call_next(request)

        if result is not None and not result.allowed:
            headers = _build_rate_limit_headers(result)
            logger.warning(
                "Rate limit exceeded",
                extra={
                    "role": role,
                    "session_id": session_id,
                    "source_ip": source_ip,
                    "limit_type": result.limit_type,
                    "path": path,
                },
            )
            # Persist SecurityEventLog row
            try:
                from app.database import async_session_factory
                from app.models.log import SecurityEventLog
                from app.models.base import new_uuid7

                async with async_session_factory() as se_db:
                    se_db.add(SecurityEventLog(
                        id=new_uuid7(),
                        event_type="rate_limit_exceeded",
                        source_ip=source_ip,
                        user_id=user_id,
                        session_id=session_id if session_id != "unknown" else None,
                        details={
                            "role": role,
                            "path": path,
                            "limit_type": result.limit_type,
                            "soft_limit": result.soft_limit,
                            "hard_limit": result.hard_limit,
                            "soft_count": result.soft_count,
                            "hard_count": result.hard_count,
                        },
                    ))
                    await se_db.commit()
            except Exception:
                pass  # Don't block the 429 response on logging failure

            limit_type = result.limit_type
            retry_msg = f"{limit_type.capitalize()} limit reached ({result.soft_limit}/s soft, {result.hard_limit}/h hard). Retry after {result.retry_after}s."
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": "RATE_LIMIT_EXCEEDED",
                        "message_key": "errors.rate_limit_exceeded",
                        "message": retry_msg,
                        "details": {
                            "limit_type": limit_type,
                            "soft_limit": result.soft_limit,
                            "hard_limit": result.hard_limit,
                            "soft_count": result.soft_count,
                            "hard_count": result.hard_count,
                            "retry_after": result.retry_after,
                        },
                    }
                },
                headers=headers,
            )

        response = await call_next(request)

        # Add rate limit headers to successful responses
        if result is not None and response.status_code < 400:
            headers = _build_rate_limit_headers(result)
            for key, value in headers.items():
                response.headers[key] = value

        return response

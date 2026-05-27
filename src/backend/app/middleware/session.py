import logging

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.models.base import new_uuid7
from app.security.cookies import get_session_token, session_cookie_name
from app.security.csrf import generate_csrf_token, set_csrf_cookie
from app.security.tokens import hash_token

logger = logging.getLogger(__name__)


async def _resolve_role(user_id: str | None) -> str:
    """Look up the user's actual role from the database."""
    if not user_id:
        return "visitor"
    try:
        from sqlalchemy import select

        from app.database import async_session_factory, is_db_available
        from app.models import User

        if not is_db_available():
            return "authenticated"  # fallback for known user_id when DB is down

        async with async_session_factory() as db:
            result = await db.execute(select(User.role).where(User.id == user_id))
            role = result.scalar_one_or_none()
            if role:
                return role
    except Exception:
        logger.exception("Failed to resolve user role")
    return "authenticated"


async def _resolve_session(token_hash: str) -> dict | None:
    """Look up session by HMAC token_hash in Redis then DB."""
    # Redis first
    try:
        from app.redis.session_store import get_session as redis_get_session

        redis_data = await redis_get_session(token_hash)
        if redis_data:
            try:
                from app.redis.session_store import update_activity
                await update_activity(token_hash)
            except Exception:
                pass
            return {
                "session_id": redis_data.get("session_id", token_hash),
                "user_id": redis_data.get("user_id") or None,
            }
    except Exception:
        pass  # Redis unavailable, fall through to DB

    # DB fallback
    try:
        from sqlalchemy import select

        from app.database import async_session_factory, is_db_available
        from app.models import Session

        if not is_db_available():
            return None

        async with async_session_factory() as db:
            result = await db.execute(
                select(Session).where(Session.token_hash == token_hash)
            )
            session = result.scalar_one_or_none()
            if session:
                return {
                    "session_id": session.id,
                    "user_id": session.user_id,
                }
    except Exception:
        logger.exception("DB session lookup failed")
    return None


async def _create_anonymous_session(request: Request) -> dict | None:
    """Persist an anonymous session. Returns dict with token, session_id or None on failure."""
    try:
        from app.database import async_session_factory, is_db_available
        from app.services import session_service

        if not is_db_available():
            return None

        async with async_session_factory() as db:
            token, session = await session_service.create(
                db,
                user_id=None,
                ip_address=request.client.host if request.client else "unknown",
                user_agent=request.headers.get("user-agent"),
            )
            await db.commit()
            return {"token": token, "session_id": session.id}
    except Exception:
        logger.exception("Failed to create anonymous session")
        return None


class SessionMiddleware(BaseHTTPMiddleware):
    """Resolve session from cookie, attach user/session to request state.

    For authenticated users: reads sakn_session cookie, resolves from Redis/DB
    (HMAC-SHA256 only — ADR-007 migration completed).
    For visitors: creates anonymous session identifiers.
    """

    async def dispatch(self, request: Request, call_next):
        session_token = get_session_token(request)
        created_session_token: str | None = None

        if session_token:
            token_hash = hash_token(session_token)
            request.state.session_token_hash = token_hash
            request.state.session_token = session_token

            session = await _resolve_session(token_hash)
            if session:
                request.state.session_id = session["session_id"]
                request.state.user_id = session["user_id"]
                request.state.role = await _resolve_role(session["user_id"])
            else:
                # Session cookie exists but session not found (expired/revoked).
                # Create a persisted anonymous session; fall back to ephemeral if DB is down.
                anon = await _create_anonymous_session(request)
                if anon:
                    created_session_token = anon["token"]
                    request.state.session_token = anon["token"]
                    request.state.session_token_hash = hash_token(anon["token"])
                    request.state.session_id = anon["session_id"]
                    request.state.user_id = None
                    request.state.role = "visitor"
                else:
                    request.state.session_id = f"anon_{new_uuid7()}"
                    request.state.user_id = None
                    request.state.role = "visitor"
        else:
            # No session cookie — create a persisted anonymous session.
            anon = await _create_anonymous_session(request)
            if anon:
                created_session_token = anon["token"]
                request.state.session_token = anon["token"]
                request.state.session_token_hash = hash_token(anon["token"])
                request.state.session_id = anon["session_id"]
                request.state.user_id = None
                request.state.role = "visitor"
            else:
                anon_id = new_uuid7()
                request.state.session_id = f"anon_{anon_id}"
                request.state.user_id = None
                request.state.role = "visitor"

        response = await call_next(request)

        # Set session cookie for newly created anonymous sessions
        if created_session_token:
            is_secure = request.url.scheme == "https"
            response.set_cookie(
                key=session_cookie_name(is_secure),
                value=created_session_token,
                httponly=True,
                samesite="lax",
                secure=is_secure,
                path="/",
                max_age=86400,
            )

        # Set CSRF cookie for visitors if not present
        if not request.cookies.get("sakn_csrf"):
            csrf_token = generate_csrf_token()
            is_secure = request.url.scheme == "https"
            set_csrf_cookie(response, csrf_token, secure=is_secure)

        return response

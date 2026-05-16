import logging

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.models.base import new_uuid7
from app.security.tokens import hash_token
from app.security.csrf import generate_csrf_token, set_csrf_cookie

logger = logging.getLogger(__name__)


async def _resolve_role(user_id: str | None) -> str:
    """Look up the user's actual role from the database."""
    if not user_id:
        return "visitor"
    try:
        from app.database import async_session_factory, is_db_available
        from sqlalchemy import select
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


class SessionMiddleware(BaseHTTPMiddleware):
    """Resolve session from cookie, attach user/session to request state.

    For authenticated users: reads sakn_session cookie, resolves from Redis/DB.
    For visitors: creates anonymous session identifiers.
    """

    async def dispatch(self, request: Request, call_next):
        session_token = request.cookies.get("sakn_session")

        if session_token:
            token_hash = hash_token(session_token)
            request.state.session_token_hash = token_hash
            request.state.session_token = session_token
            request.state.session_id = token_hash  # placeholder, replaced below

            # Try to resolve the session
            redis_data = None
            try:
                from app.redis.session_store import get_session as redis_get_session

                redis_data = await redis_get_session(token_hash)
            except Exception:
                pass  # Redis unavailable, fall through to DB

            if redis_data:
                request.state.session_id = redis_data.get("session_id", token_hash)
                request.state.user_id = redis_data.get("user_id") or None
                request.state.role = await _resolve_role(request.state.user_id)

                # Update sliding expiration
                try:
                    from app.redis.session_store import update_activity

                    await update_activity(token_hash)
                except Exception:
                    pass
            else:
                # Try DB fallback
                from app.database import async_session_factory, is_db_available
                from sqlalchemy import select
                from app.models import Session

                if is_db_available():
                    try:
                        async with async_session_factory() as db:
                            result = await db.execute(
                                select(Session).where(Session.token_hash == token_hash)
                            )
                            session = result.scalar_one_or_none()
                            if session:
                                request.state.session_id = session.id
                                request.state.user_id = session.user_id
                                request.state.role = await _resolve_role(session.user_id)
                            else:
                                request.state.session_id = f"anon_{new_uuid7()}"
                                request.state.user_id = None
                                request.state.role = "visitor"
                                request.state.session_id = f"anon_{new_uuid7()}"
                                request.state.user_id = None
                                request.state.role = "visitor"
                    except Exception:
                        logger.exception("DB session lookup failed, falling back to anonymous")
                        request.state.session_id = f"anon_{new_uuid7()}"
                        request.state.user_id = None
                        request.state.role = "visitor"
                else:
                    request.state.session_id = f"anon_{new_uuid7()}"
                    request.state.user_id = None
                    request.state.role = "visitor"
        else:
            # Anonymous
            anon_id = new_uuid7()
            request.state.session_id = f"anon_{anon_id}"
            request.state.user_id = None
            request.state.role = "visitor"

        response = await call_next(request)

        # Set CSRF cookie for visitors if not present
        if not request.cookies.get("sakn_csrf"):
            csrf_token = generate_csrf_token()
            is_secure = request.url.scheme == "https"
            set_csrf_cookie(response, csrf_token, secure=is_secure)

        return response

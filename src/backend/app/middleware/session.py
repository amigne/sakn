import logging

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.models.base import new_uuid7
from app.security.tokens import hash_token
from app.security.csrf import generate_csrf_token, set_csrf_cookie

logger = logging.getLogger(__name__)


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
            try:
                from app.redis.session_store import get_session as redis_get_session

                redis_data = await redis_get_session(token_hash)
                if redis_data:
                    request.state.session_id = redis_data.get("session_id", token_hash)
                    request.state.user_id = redis_data.get("user_id") or None
                    request.state.role = "authenticated" if request.state.user_id else "visitor"

                    # Update sliding expiration
                    from app.redis.session_store import update_activity

                    await update_activity(token_hash)
                else:
                    # Try DB fallback
                    from app.database import async_session_factory
                    from sqlalchemy import select
                    from app.models import Session

                    async with async_session_factory() as db:
                        result = await db.execute(
                            select(Session).where(Session.token_hash == token_hash)
                        )
                        session = result.scalar_one_or_none()
                        if session:
                            request.state.session_id = session.id
                            request.state.user_id = session.user_id
                            request.state.role = "authenticated" if session.user_id else "visitor"
                        else:
                            request.state.session_id = f"anon_{new_uuid7()}"
                            request.state.user_id = None
                            request.state.role = "visitor"
            except Exception:
                logger.exception("Session resolution failed")
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

import logging

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.models.base import new_uuid7
from app.security.tokens import hash_token, hash_token_legacy
from app.security.csrf import generate_csrf_token, set_csrf_cookie
from app.security.cookies import get_session_token

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


async def _resolve_session(token_hash: str, legacy_hash: str) -> dict | None:
    """Try HMAC hash first, fall back to legacy SHA-256 (ADR-007).

    Returns a dict with keys: session_id, user_id, is_legacy (bool).
    """
    # Try HMAC first
    session = await _lookup_session(token_hash)
    if session:
        session["is_legacy"] = False
        return session

    # Fallback to legacy SHA-256
    session = await _lookup_session(legacy_hash)
    if session:
        session["is_legacy"] = True
        return session

    return None


async def _lookup_session(token_hash: str) -> dict | None:
    """Look up session by token_hash in Redis then DB."""
    # Redis first
    try:
        from app.redis.session_store import get_session as redis_get_session

        redis_data = await redis_get_session(token_hash)
        if redis_data:
            # Update sliding expiration
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
        from app.database import async_session_factory, is_db_available
        from sqlalchemy import select
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


async def _upgrade_session_hash(legacy_hash: str, hmac_hash: str, session_data: dict) -> None:
    """Silently upgrade a legacy SHA-256 session to HMAC (ADR-007).

    Updates DB token_hash and migrates Redis key.
    """
    try:
        # Update DB
        from app.database import async_session_factory, is_db_available
        from sqlalchemy import update
        from app.models import Session

        if is_db_available():
            async with async_session_factory() as db:
                await db.execute(
                    update(Session)
                    .where(Session.token_hash == legacy_hash)
                    .values(token_hash=hmac_hash)
                )
                await db.commit()
    except Exception:
        logger.exception("Failed to upgrade session hash in DB for legacy=%s", legacy_hash[:16])

    # Migrate Redis key
    try:
        from app.redis.session_store import migrate_session_hash
        await migrate_session_hash(legacy_hash, hmac_hash, session_data)
    except Exception:
        logger.exception("Failed to upgrade session hash in Redis for legacy=%s", legacy_hash[:16])


class SessionMiddleware(BaseHTTPMiddleware):
    """Resolve session from cookie, attach user/session to request state.

    For authenticated users: reads sakn_session cookie, resolves from Redis/DB
    with dual lookup (HMAC → legacy SHA-256 fallback, per ADR-007).
    For visitors: creates anonymous session identifiers.
    """

    async def dispatch(self, request: Request, call_next):
        session_token = get_session_token(request)

        if session_token:
            token_hash = hash_token(session_token)
            legacy_hash = hash_token_legacy(session_token)
            request.state.session_token_hash = token_hash
            request.state.session_token = session_token

            session = await _resolve_session(token_hash, legacy_hash)
            if session:
                request.state.session_id = session["session_id"]
                request.state.user_id = session["user_id"]
                request.state.role = await _resolve_role(session["user_id"])
                if session.get("is_legacy"):
                    await _upgrade_session_hash(legacy_hash, token_hash, session)
                    request.state.session_token_hash = token_hash
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

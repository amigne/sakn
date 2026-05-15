from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Session
from app.models.base import utcnow
from app.redis.session_store import (
    create_session as redis_create_session,
    get_session as redis_get_session,
    delete_session as redis_delete_session,
    list_user_sessions,
    update_activity,
    enforce_concurrent_limit,
    MAX_CONCURRENT_SESSIONS,
)
from app.security.tokens import generate_token, hash_token

SESSION_DURATION_HOURS = 24


def _now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def create(db: AsyncSession, *, user_id: str | None, ip_address: str, user_agent: str | None = None) -> tuple[str, Session]:
    """Create a session in Redis and DB. Returns (raw_token, db_session)."""
    token = generate_token()
    token_hash = hash_token(token)
    now = utcnow()
    expires_at = now + timedelta(hours=SESSION_DURATION_HOURS)

    if user_id:
        await enforce_concurrent_limit(user_id)

    session = Session(
        user_id=user_id,
        token_hash=token_hash,
        ip_address=ip_address,
        user_agent=user_agent,
        expires_at=expires_at,
    )
    db.add(session)
    await db.flush()

    await redis_create_session(
        token_hash,
        {
            "session_id": session.id,
            "user_id": user_id or "",
            "ip_address": ip_address,
            "user_agent": user_agent or "",
            "created_at": now.isoformat(),
            "last_activity_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
        },
        ttl_seconds=SESSION_DURATION_HOURS * 3600,
    )

    return token, session


async def get(db: AsyncSession, session_token: str) -> Session | None:
    """Resolve a session from its raw cookie token."""
    token_hash = hash_token(session_token)
    now = _now_naive()

    redis_data = await redis_get_session(token_hash)
    if redis_data:
        result = await db.execute(select(Session).where(Session.token_hash == token_hash))
        session = result.scalar_one_or_none()
        if session and session.expires_at > now:
            return session
        return None

    result = await db.execute(select(Session).where(Session.token_hash == token_hash))
    session = result.scalar_one_or_none()
    if session and session.expires_at > now:
        return session
    return None


async def touch(token_hash: str) -> None:
    """Update last activity (sliding expiration)."""
    await update_activity(token_hash, SESSION_DURATION_HOURS * 3600)


async def revoke(db: AsyncSession, session_id: str) -> str | None:
    """Delete a session by its DB id. Returns the token_hash for cookie clearing."""
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()
    if session is None:
        return None
    token_hash = session.token_hash
    await db.delete(session)
    await db.flush()
    await redis_delete_session(token_hash)
    return token_hash


async def list_for_user(db: AsyncSession, user_id: str, current_token_hash: str | None = None) -> list[dict]:
    """List all active sessions for a user."""
    now = _now_naive()
    result = await db.execute(
        select(Session).where(
            Session.user_id == user_id,
            Session.expires_at > now,
        ).order_by(Session.last_activity_at.desc())
    )
    sessions = result.scalars().all()
    return [
        {
            "id": s.id,
            "ip_address": s.ip_address,
            "user_agent": s.user_agent,
            "created_at": s.created_at.isoformat(),
            "last_activity_at": s.last_activity_at.isoformat(),
            "current": s.token_hash == current_token_hash if current_token_hash else False,
        }
        for s in sessions
    ]


async def revoke_all_for_user(db: AsyncSession, user_id: str, *, except_token_hash: str | None = None) -> int:
    """Revoke all sessions for a user. Returns count of revoked sessions."""
    result = await db.execute(select(Session).where(Session.user_id == user_id))
    sessions = result.scalars().all()
    count = 0
    for s in sessions:
        if except_token_hash and s.token_hash == except_token_hash:
            continue
        await redis_delete_session(s.token_hash)
        await db.delete(s)
        count += 1
    await db.flush()
    return count

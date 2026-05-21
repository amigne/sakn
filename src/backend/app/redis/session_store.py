import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.preferences import GlobalSetting
from app.redis.connection import get_redis

logger = logging.getLogger(__name__)

MAX_CONCURRENT_SESSIONS = 10


async def _get_max_sessions(db: AsyncSession) -> int:
    """Read max_concurrent_sessions from GlobalSetting. Default 10."""
    try:
        result = await db.execute(
            select(GlobalSetting).where(GlobalSetting.key == "max_concurrent_sessions")
        )
        row = result.scalar_one_or_none()
        if row:
            return int(row.value)
    except (ValueError, TypeError, Exception):
        pass
    return MAX_CONCURRENT_SESSIONS


async def _redis_available() -> bool:
    try:
        r = await get_redis()
        await r.ping()
        return True
    except Exception:
        return False


def _session_key(token_hash: str) -> str:
    return f"session:{token_hash}"


def _user_sessions_key(user_id: str) -> str:
    return f"user_sessions:{user_id}"


async def create_session(token_hash: str, data: dict[str, Any], ttl_seconds: int = 86400) -> None:
    try:
        redis = await get_redis()
        key = _session_key(token_hash)
        await redis.hset(key, mapping=data)
        await redis.expire(key, ttl_seconds)
        user_id = data.get("user_id")
        if user_id:
            await redis.sadd(_user_sessions_key(user_id), token_hash)
    except Exception:
        logger.warning("Redis unavailable, session not cached in Redis")


async def get_session(token_hash: str) -> dict[str, str] | None:
    try:
        redis = await get_redis()
        key = _session_key(token_hash)
        data = await redis.hgetall(key)
        return data if data else None
    except Exception:
        return None


async def delete_session(token_hash: str) -> None:
    try:
        redis = await get_redis()
        key = _session_key(token_hash)
        data = await redis.hgetall(key)
        user_id = data.get("user_id")
        if user_id:
            await redis.srem(_user_sessions_key(user_id), token_hash)
        await redis.delete(key)
    except Exception:
        pass


async def list_user_sessions(user_id: str) -> list[str]:
    try:
        redis = await get_redis()
        return list(await redis.smembers(_user_sessions_key(user_id)))
    except Exception:
        return []


async def count_user_sessions(user_id: str) -> int:
    try:
        redis = await get_redis()
        return await redis.scard(_user_sessions_key(user_id))
    except Exception:
        return 0


async def update_activity(token_hash: str, ttl_seconds: int = 86400) -> None:
    try:
        redis = await get_redis()
        key = _session_key(token_hash)
        now = datetime.now(timezone.utc).isoformat()
        await redis.hset(key, "last_activity_at", now)
        await redis.expire(key, ttl_seconds)
    except Exception:
        pass


async def enforce_concurrent_limit(user_id: str, max_sessions: int = MAX_CONCURRENT_SESSIONS) -> list[str] | None:
    """Revoke oldest sessions if count exceeds limit. Returns list of revoked token_hashes."""
    try:
        redis = await get_redis()
        token_hashes = await redis.smembers(_user_sessions_key(user_id))
        if len(token_hashes) <= max_sessions:
            return None

        sessions = []
        for th in token_hashes:
            data = await redis.hgetall(_session_key(th))
            created = data.get("created_at", "")
            sessions.append((created, th))

        sessions.sort(key=lambda x: x[0])
        to_revoke = sessions[: len(sessions) - max_sessions]
        revoked = []
        for _, th in to_revoke:
            await delete_session(th)
            revoked.append(th)

        return revoked
    except Exception:
        logger.warning("Redis unavailable, concurrent limit not enforced")
        return None


async def migrate_session_hash(legacy_hash: str, hmac_hash: str, session_data: dict) -> None:
    """Migrate a session from legacy SHA-256 to HMAC hash in Redis (ADR-007).

    Renames the session key and updates the user_sessions set entry.
    No-op if the legacy key doesn't exist.
    """
    try:
        redis = await get_redis()
    except Exception:
        logger.warning("Redis unavailable, skipping session hash migration")
        return

    try:
        # RENAME session:{legacy} → session:{hmac}
        await redis.rename(_session_key(legacy_hash), _session_key(hmac_hash))

        # Update user_sessions set: remove legacy, add hmac
        user_id = session_data.get("user_id")
        if user_id:
            user_key = _user_sessions_key(user_id)
            pipe = redis.pipeline()
            pipe.srem(user_key, legacy_hash)
            pipe.sadd(user_key, hmac_hash)
            await pipe.execute()
    except Exception:
        logger.exception("Failed to migrate session hash from legacy=%s to hmac=%s",
                         legacy_hash[:16], hmac_hash[:16])

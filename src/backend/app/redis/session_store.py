import logging
from datetime import datetime, timezone
from typing import Any

from app.redis.connection import get_redis

logger = logging.getLogger(__name__)

MAX_CONCURRENT_SESSIONS = 10


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

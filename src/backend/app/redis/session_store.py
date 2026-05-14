from datetime import datetime, timezone
from typing import Any

from app.redis.connection import get_redis


def _session_key(token_hash: str) -> str:
    return f"session:{token_hash}"


def _user_sessions_key(user_id: str) -> str:
    return f"user_sessions:{user_id}"


async def create_session(token_hash: str, data: dict[str, Any], ttl_seconds: int = 86400) -> None:
    redis = await get_redis()
    key = _session_key(token_hash)
    await redis.hset(key, mapping=data)
    await redis.expire(key, ttl_seconds)
    user_id = data.get("user_id")
    if user_id:
        await redis.sadd(_user_sessions_key(user_id), token_hash)


async def get_session(token_hash: str) -> dict[str, str] | None:
    redis = await get_redis()
    key = _session_key(token_hash)
    data = await redis.hgetall(key)
    return data if data else None


async def delete_session(token_hash: str) -> None:
    redis = await get_redis()
    key = _session_key(token_hash)
    data = await redis.hgetall(key)
    user_id = data.get("user_id")
    if user_id:
        await redis.srem(_user_sessions_key(user_id), token_hash)
    await redis.delete(key)


async def list_user_sessions(user_id: str) -> list[str]:
    redis = await get_redis()
    return list(await redis.smembers(_user_sessions_key(user_id)))


async def update_activity(token_hash: str, ttl_seconds: int = 86400) -> None:
    redis = await get_redis()
    key = _session_key(token_hash)
    now = datetime.now(timezone.utc).isoformat()
    await redis.hset(key, "last_activity_at", now)
    await redis.expire(key, ttl_seconds)

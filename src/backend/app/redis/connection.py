import redis.asyncio as aioredis


_redis: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        raise RuntimeError("Redis connection pool not initialized. Call init_redis() first.")
    return _redis


async def init_redis(url: str) -> None:
    global _redis
    _redis = aioredis.from_url(url, encoding="utf-8", decode_responses=True)
    await _redis.ping()


async def close_redis() -> None:
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None

"""Sliding-window rate limit counters backed by Redis sorted sets.

Uses a Lua script to atomically: prune expired entries, count within
soft/hard windows, and record the request. Falls back to in-memory
counters when Redis is unavailable.
"""

import json
import logging
import time
from dataclasses import dataclass
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

# Lua script: atomic ZREMRANGEBYSCORE + ZCOUNT + conditional ZADD + EXPIRE
# Only records the request if it would NOT exceed either limit (0 = no limit).
LUA_RATE_LIMIT = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local soft_cutoff = tonumber(ARGV[2])
local hard_cutoff = tonumber(ARGV[3])
local member = ARGV[4]
local ttl = tonumber(ARGV[5])
local soft_limit = tonumber(ARGV[6])
local hard_limit = tonumber(ARGV[7])

-- Clean up expired entries
redis.call('ZREMRANGEBYSCORE', key, '-inf', hard_cutoff)

-- Count within soft and hard windows
local soft_count = redis.call('ZCOUNT', key, soft_cutoff, '+inf')
local hard_count = redis.call('ZCOUNT', key, hard_cutoff, '+inf')

-- Only record if under both limits (0 = unlimited)
local allowed = 1
if (soft_limit > 0 and soft_count >= soft_limit) or (hard_limit > 0 and hard_count >= hard_limit) then
    allowed = 0
else
    redis.call('ZADD', key, now, member)
    redis.call('EXPIRE', key, ttl)
    soft_count = soft_count + 1
    hard_count = hard_count + 1
end

return {allowed, soft_count, hard_count}
"""


@dataclass
class RateLimitResult:
    allowed: bool
    soft_count: int
    hard_count: int
    soft_limit: int
    hard_limit: int
    soft_window_s: int
    hard_window_s: int
    retry_after: int  # seconds
    limit_type: str  # "soft" | "hard" | "none"


def _rate_limit_key(key_type: str, identifier: str) -> str:
    return f"ratelimit:{key_type}:{identifier}"


async def get_current_counts(
    key_type: str, identifier: str,
    soft_window_s: int = 1, hard_window_s: int = 3600,
) -> tuple[int, int]:
    """Read current soft/hard counts for a key from the in-memory fallback."""
    limiter = get_rate_limiter()
    key = _rate_limit_key(key_type, identifier)
    timestamps = limiter._db_fallback.get(key, {}).get("timestamps", [])
    now = time.time()
    soft_count = sum(1 for t in timestamps if t > now - soft_window_s)
    hard_count = sum(1 for t in timestamps if t > now - hard_window_s)
    return soft_count, hard_count


class SlidingWindowRateLimiter:
    """Rate limiter backed by Redis sorted sets with optional DB fallback."""

    def __init__(self) -> None:
        self._lua_sha: str | None = None
        self._db_fallback: dict[str, dict[str, Any]] = {}

    def clear_for_tests(self) -> None:
        """Clear the in-memory fallback store — testing only, do not call in prod."""
        self._db_fallback.clear()

    async def _redis(self):
        from app.redis.connection import get_redis

        return await get_redis()

    async def check(
        self,
        key_type: str,
        identifier: str,
        soft_limit: int,
        hard_limit: int,
        soft_window_s: int = 1,
        hard_window_s: int = 3600,
    ) -> RateLimitResult:
        """Check and record a request. Returns result with counts and retry info."""

        if settings.RATE_LIMIT_STORAGE == "database":
            return await self._check_db(
                key_type, identifier, soft_limit, hard_limit, soft_window_s, hard_window_s
            )
        return await self._check_redis(
            key_type, identifier, soft_limit, hard_limit, soft_window_s, hard_window_s
        )

    async def _check_redis(
        self,
        key_type: str,
        identifier: str,
        soft_limit: int,
        hard_limit: int,
        soft_window_s: int,
        hard_window_s: int,
    ) -> RateLimitResult:
        from uuid_extensions import uuid7

        key = _rate_limit_key(key_type, identifier)
        now = time.time()
        soft_cutoff = now - soft_window_s
        hard_cutoff = now - hard_window_s
        member = str(uuid7())
        ttl = max(hard_window_s * 2, 7200)

        try:
            redis = await self._redis()
            allowed_raw, soft_count, hard_count = await redis.eval(
                LUA_RATE_LIMIT,
                1,
                key,
                now,
                soft_cutoff,
                hard_cutoff,
                member,
                ttl,
                soft_limit,
                hard_limit,
            )
            allowed = int(allowed_raw) == 1
            soft_count = int(soft_count)
            hard_count = int(hard_count)
        except Exception:
            logger.warning("Redis rate limit check failed, falling back to in-memory store")
            return await self._check_db(
                key_type, identifier, soft_limit, hard_limit, soft_window_s, hard_window_s
            )

        return _compute_result(
            soft_count, hard_count, soft_limit, hard_limit, soft_window_s, hard_window_s,
            already_allowed=allowed,
        )

    async def _check_db(
        self,
        key_type: str,
        identifier: str,
        soft_limit: int,
        hard_limit: int,
        soft_window_s: int,
        hard_window_s: int,
    ) -> RateLimitResult:
        """In-memory fallback for SQLite development without Redis."""
        now = time.time()
        key = _rate_limit_key(key_type, identifier)

        if key not in self._db_fallback:
            self._db_fallback[key] = {"timestamps": []}

        timestamps = self._db_fallback[key]["timestamps"]
        soft_cutoff = now - soft_window_s
        hard_cutoff = now - hard_window_s

        # Prune expired
        self._db_fallback[key]["timestamps"] = [t for t in timestamps if t > hard_cutoff]

        soft_count = sum(1 for t in self._db_fallback[key]["timestamps"] if t > soft_cutoff)
        hard_count = len(self._db_fallback[key]["timestamps"])

        # Check before recording
        if (soft_limit > 0 and soft_count >= soft_limit) or (hard_limit > 0 and hard_count >= hard_limit):
            return _compute_result(
                soft_count, hard_count, soft_limit, hard_limit, soft_window_s, hard_window_s,
                already_allowed=False,
            )

        # Record the request
        self._db_fallback[key]["timestamps"].append(now)
        soft_count += 1
        hard_count += 1

        # Cleanup old keys periodically
        if len(self._db_fallback) > 10000:
            stale = [k for k, v in self._db_fallback.items() if not v["timestamps"]]
            for k in stale[:1000]:
                del self._db_fallback[k]

        return _compute_result(
            soft_count, hard_count, soft_limit, hard_limit, soft_window_s, hard_window_s,
            already_allowed=True,
        )


def _compute_result(
    soft_count: int,
    hard_count: int,
    soft_limit: int,
    hard_limit: int,
    soft_window_s: int,
    hard_window_s: int,
    already_allowed: bool | None = None,
) -> RateLimitResult:
    """Compute the effective rate limit result.

    If already_allowed is provided (from Lua script), use it directly.
    Otherwise, compute from counts and limits (for DB fallback).
    """
    if already_allowed is not None:
        if already_allowed:
            return RateLimitResult(
                allowed=True, soft_count=soft_count, hard_count=hard_count,
                soft_limit=soft_limit, hard_limit=hard_limit,
                soft_window_s=soft_window_s, hard_window_s=hard_window_s,
                retry_after=0, limit_type="none",
            )
        # Determine which limit was hit (use >= to match the check in _check_db / Lua)
        if soft_limit > 0 and soft_count >= soft_limit:
            return RateLimitResult(
                allowed=False, soft_count=soft_count, hard_count=hard_count,
                soft_limit=soft_limit, hard_limit=hard_limit,
                soft_window_s=soft_window_s, hard_window_s=hard_window_s,
                retry_after=soft_window_s, limit_type="soft",
            )
        return RateLimitResult(
            allowed=False, soft_count=soft_count, hard_count=hard_count,
            soft_limit=soft_limit, hard_limit=hard_limit,
            soft_window_s=soft_window_s, hard_window_s=hard_window_s,
            retry_after=hard_window_s, limit_type="hard",
        )

    # Legacy path for DB fallback (check uses >= to match rejection logic)
    if soft_limit > 0 and soft_count >= soft_limit:
        return RateLimitResult(
            allowed=False,
            soft_count=soft_count,
            hard_count=hard_count,
            soft_limit=soft_limit,
            hard_limit=hard_limit,
            soft_window_s=soft_window_s,
            hard_window_s=hard_window_s,
            retry_after=soft_window_s,
            limit_type="soft",
        )

    # Check hard limit
    if hard_limit > 0 and hard_count > hard_limit:
        return RateLimitResult(
            allowed=False,
            soft_count=soft_count,
            hard_count=hard_count,
            soft_limit=soft_limit,
            hard_limit=hard_limit,
            soft_window_s=soft_window_s,
            hard_window_s=hard_window_s,
            retry_after=hard_window_s,
            limit_type="hard",
        )

    return RateLimitResult(
        allowed=True,
        soft_count=soft_count,
        hard_count=hard_count,
        soft_limit=soft_limit,
        hard_limit=hard_limit,
        soft_window_s=soft_window_s,
        hard_window_s=hard_window_s,
        retry_after=0,
        limit_type="none",
    )


# Module-level singleton
_limiter: SlidingWindowRateLimiter | None = None


def get_rate_limiter() -> SlidingWindowRateLimiter:
    global _limiter
    if _limiter is None:
        _limiter = SlidingWindowRateLimiter()
    return _limiter

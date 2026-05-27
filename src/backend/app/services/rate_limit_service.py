"""Rate limit service.

Resolves effective limits per (role, tool) from DB configuration,
delegates enforcement to the Redis sliding-window limiter.

Hardcoded auth limits (Slice 4) are preserved for auth endpoints
which bypass the DB-configured limit system.
"""

import logging
import time
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tool_module import RateLimitConfig
from app.redis.rate_limit_store import (
    RateLimitResult,
    get_rate_limiter,
)

logger = logging.getLogger(__name__)

# Hardcoded auth rate limits (spec-backend.md §6.9)
AUTH_LIMITS = {
    "login": {"max": 10, "window": 60},
    "register": {"max": 3, "window": 3600},
    "reset": {"max": 3, "window": 86400},
    "resend": {"max": 5, "window": 86400},
}

# In-memory counters for auth limits (lightweight, no Redis needed for these)
_auth_counters: dict[str, list[float]] = defaultdict(list)

# Default rate limits per role when no DB config exists (spec-backend.md §6.3)
DEFAULT_LIMITS = {
    "visitor": {"soft": 1, "hard": 200},
    "authenticated": {"soft": 1, "hard": 500},
    "administrator": {"soft": 0, "hard": 3600},
}


async def get_effective_limits(
    db: AsyncSession,
    role: str,
    tool_id: str | None = None,
) -> dict[str, int]:
    """Resolve effective limits: min(global, per_tool) where 0 = no limit.

    Returns {"soft_limit": int, "hard_limit": int, "window_seconds": int}
    """
    # Query global limit for the role
    global_row = await db.execute(
        select(RateLimitConfig).where(
            RateLimitConfig.role == role,
            RateLimitConfig.tool_id.is_(None),
        )
    )
    global_config = global_row.scalar_one_or_none()

    global_soft = global_config.soft_limit if global_config else DEFAULT_LIMITS.get(role, {}).get("soft", 0)
    global_hard = global_config.hard_limit if global_config else DEFAULT_LIMITS.get(role, {}).get("hard", 0)
    global_window = global_config.window_seconds if global_config else 3600

    per_tool_soft = 0
    per_tool_hard = 0

    if tool_id:
        tool_row = await db.execute(
            select(RateLimitConfig).where(
                RateLimitConfig.role == role,
                RateLimitConfig.tool_id == tool_id,
            )
        )
        tool_config = tool_row.scalar_one_or_none()
        if tool_config:
            per_tool_soft = tool_config.soft_limit
            per_tool_hard = tool_config.hard_limit

    # Effective = min(global, per_tool) where 0 = no limit
    def effective(a: int, b: int) -> int:
        if a == 0:
            return b
        if b == 0:
            return a
        return min(a, b)

    return {
        "soft_limit": effective(global_soft, per_tool_soft),
        "hard_limit": effective(global_hard, per_tool_hard),
        "window_seconds": global_window,
    }


async def _get_visitor_ip_limits(db: AsyncSession) -> tuple[int, int]:
    """Return (soft_limit, hard_limit) for visitor IP-based rate limiting.

    Reads from GlobalSettings so admins can adjust via the admin panel.
    Defaults: soft=5 req/s, hard=500 req/h.
    """
    from sqlalchemy import select as sel

    from app.models.preferences import GlobalSetting

    soft = 5
    hard = 500
    try:
        row = await db.execute(
            sel(GlobalSetting).where(GlobalSetting.key.in_(
                ("visitor_ip_soft_limit", "visitor_ip_hard_limit")
            ))
        )
        for s in row.scalars().all():
            try:
                val = int(s.value)
            except (ValueError, TypeError):
                continue
            if s.key == "visitor_ip_soft_limit":
                soft = val
            elif s.key == "visitor_ip_hard_limit":
                hard = val
    except Exception:
        pass  # DB might not be available, use defaults
    return soft, hard


async def check_tool_rate_limit(
    db: AsyncSession,
    *,
    role: str,
    user_id: str | None,
    session_id: str,
    source_ip: str,
    tool_id: str | None = None,
) -> RateLimitResult:
    """Check tool execution rate limits for a given role/session/user/IP.

    Visitors: both session AND IP checks must pass.
    Authenticated/admins: user-based check. Admins default to soft=0 (no
    burst limit) and hard=3600 — limits only apply if explicitly configured.
    """
    limits = await get_effective_limits(db, role, tool_id)
    limiter = get_rate_limiter()

    soft_limit = limits["soft_limit"]
    hard_limit = limits["hard_limit"]
    window_s = limits["window_seconds"]
    soft_window_s = 1  # 1-second burst window
    hard_window_s = window_s  # configured window (default 3600)

    if role == "visitor" or (role == "visitor" and user_id is None):
        # Dual check: session + IP
        session_result = await limiter.check(
            "session", session_id, soft_limit, hard_limit, soft_window_s, hard_window_s
        )
        if not session_result.allowed:
            return session_result

        # Visitor IP limits: read from GlobalSettings (fallback to defaults)
        ip_soft, ip_hard = await _get_visitor_ip_limits(db)
        ip_result = await limiter.check(
            "ip", source_ip, ip_soft, ip_hard, soft_window_s, hard_window_s
        )
        if not ip_result.allowed:
            return ip_result

        # Both passed — return session result for headers
        return session_result

    # Authenticated / admin: user-based
    key_id = user_id or session_id
    key_type = "user" if user_id else "session"

    return await limiter.check(
        key_type, key_id, soft_limit, hard_limit, soft_window_s, hard_window_s
    )


# ── Auth endpoint rate limits (hardcoded, in-memory) ─────────────────


def _prune_auth(key: str, window: int) -> None:
    now = time.time()
    cutoff = now - window
    _auth_counters[key] = [t for t in _auth_counters[key] if t > cutoff]


def auth_check(key: str, limit_key: str) -> bool:
    """Return True if the request is allowed, False if rate-limited."""
    limit = AUTH_LIMITS.get(limit_key)
    if not limit:
        return True
    _prune_auth(key, limit["window"])
    return len(_auth_counters[key]) < limit["max"]


def auth_record(key: str, limit_key: str) -> None:
    if limit_key in AUTH_LIMITS:
        _auth_counters[key].append(time.time())


def auth_remaining(key: str, limit_key: str) -> int:
    limit = AUTH_LIMITS.get(limit_key)
    if not limit:
        return 999
    _prune_auth(key, limit["window"])
    return max(0, limit["max"] - len(_auth_counters[key]))

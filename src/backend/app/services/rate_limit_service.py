"""Hardcoded auth rate limiters (Slice 4). Replaced by Redis store in Slice 7."""

import time
from collections import defaultdict

# Sliding-window counters: key → sorted list of timestamps (unix seconds)
_auth_counters: dict[str, list[float]] = defaultdict(list)

# Hardcoded limits from spec-backend.md §6.9
LIMITS = {
    "login": {"max": 10, "window": 60},        # per IP
    "register": {"max": 3, "window": 3600},     # per IP
    "reset": {"max": 3, "window": 86400},       # per email
    "resend": {"max": 5, "window": 86400},       # per user
}


def _prune(key: str, window: int) -> None:
    now = time.time()
    cutoff = now - window
    entries = _auth_counters[key]
    # Keep only entries within the window
    _auth_counters[key] = [t for t in entries if t > cutoff]


def check(key: str, limit_key: str) -> bool:
    """Return True if the request is allowed, False if rate-limited."""
    limit = LIMITS.get(limit_key)
    if not limit:
        return True

    _prune(key, limit["window"])
    if len(_auth_counters[key]) >= limit["max"]:
        return False
    return True


def record(key: str, limit_key: str) -> None:
    """Record a request for the given key and limit."""
    if limit_key in LIMITS:
        _auth_counters[key].append(time.time())


def remaining(key: str, limit_key: str) -> int:
    """Return how many requests remain before hitting the limit."""
    limit = LIMITS.get(limit_key)
    if not limit:
        return 999
    _prune(key, limit["window"])
    return max(0, limit["max"] - len(_auth_counters[key]))

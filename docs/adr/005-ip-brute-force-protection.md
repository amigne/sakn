# ADR-005: IP-Based Brute-Force Protection

## Status
Accepted — 2026-05-21

## Context
SAKN's brute-force protection operates at two layers:

1. **In-memory auth rate limits** (`rate_limit_service.py:AUTH_LIMITS`) — IP-keyed
   counters for login (10 req/60s), register (3 req/h), password reset (3 req/day).
   These are process-local, lost on restart, and not shared across workers.

2. **Per-user lockout** (`auth_service.py:BRUTE_FORCE_TIERS`) — escalating
   lockout on the `User.failed_login_attempts` column (5→5min, 10→15min,
   15→45min, 20+→90min).

An attacker can defeat both layers simultaneously by distributing attempts
across many email addresses while staying under 4 failures per user. With 100
email addresses, the attacker can fire 400 attempts from a single IP without
triggering either layer.

## Decision
Add a third layer — **IP-based credential-stuffing detection** using a
Redis-backed counter with a sliding TTL:

```
Key:   bruteforce:ip:{source_ip}
Ops:   INCR + EXPIRE (on each failed login)
TTL:   BRUTEFORCE_IP_WINDOW_SECONDS (default 900s = 15min)
Check: if count >= BRUTEFORCE_IP_MAX_ATTEMPTS (default 20), return 429
```

**Why Redis INCR+EXPIRE (not the existing SlidingWindowRateLimiter)?**

The `SlidingWindowRateLimiter` is designed for per-role/per-tool rate limits
with DB-backed configuration. For brute-force detection:
- A simple `INCR` + `EXPIRE` pattern is sufficient — the counter auto-expires
  after the window, creating a natural cool-down.
- Lower Redis overhead (1 round-trip with pipeline vs Lua script).
- The "idle timeout" sliding behavior (TTL resets on each failure) is
  acceptable: an attacker sending 1 attempt every 14 minutes won't reach the
  20-attempt threshold anyway.

**Why 429 (not 401)?**

At 20+ failed attempts from a single IP within 15 minutes, the client is
clearly automated. Returning HTTP 429 with `Retry-After` is the correct
semantic. Enumeration safety (per ADR-002) is preserved because the IP check
fires BEFORE the user lookup — a blocked IP cannot probe email existence at
all.

**Why fail-open on Redis error?**

Consistent with the existing patterns (rate limiter, session store). If Redis
is unavailable, the per-user lockout (DB-backed, Layer 2) still provides
protection. A Redis outage should not block legitimate login attempts.

## Consequences
- Credential-stuffing attacks (many users × few attempts each) are detected
  at the IP level and blocked with 429.
- Legitimate users behind the same NAT as an attacker may be affected during
  the 15-minute window. This is the standard trade-off of IP-based rate
  limiting and is mitigated by the self-expiring TTL.
- `BRUTEFORCE_IP_MAX_ATTEMPTS` and `BRUTEFORCE_IP_WINDOW_SECONDS` are
  configurable via environment variables, allowing operators to tune
  thresholds for their deployment.
- The counter is IP-keyed using `source_ip` from the `TrustedProxyMiddleware`
  (per ADR-003), ensuring the real client IP is used in proxied deployments.

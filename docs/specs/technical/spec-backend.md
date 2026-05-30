# Backend Specification — SAKN MVP

> **Version:** 3.0 — Extracted from technical-spec v2.0
> **Status:** Draft
> **Date:** 2026-05-14

Server-side architecture: API, data model, security, rate limiting, logging, Docker, module system. Load with `spec-common.md` and `spec-api-contract.md`. For tool-specific logic, also load `spec-tools-live.md` or `spec-tools-instant.md`.

---

## 1. Project Structure

```
src/
  backend/
    pyproject.toml
    uv.lock
    .python-version             # 3.14
    alembic.ini
    Dockerfile
    .env.example

    app/
      __init__.py
      main.py                  # FastAPI app, lifespan events
      config.py                # Pydantic Settings
      database.py              # Engine, session factory, async session DI

      api/
        __init__.py
        v1/
          __init__.py
          router.py            # Aggregates all v1 endpoint routers
          endpoints/
            __init__.py
            auth.py             # Register, login, logout, verify-email, reset-password
            tools.py            # POST /tools/{tool_name}/execute
            admin_users.py      # User management CRUD
            admin_tools.py      # Tool configuration
            admin_rate_limits.py
            admin_logs.py
            admin_modules.py    # Module activation, DNS server presets
            admin_settings.py   # Global settings
            preferences.py      # User preferences get/set
            sessions.py         # Session listing and revocation
        errors.py              # Custom exception handlers

      models/                   # SQLAlchemy ORM models
        __init__.py             # Base = declarative_base()
        user.py, session.py, tool_module.py, role_tool_permission.py
        rate_limit_config.py, tool_execution_log.py, security_event_log.py
        audit_log.py, user_preference.py, email_verification.py
        password_reset.py, dns_server_preset.py, global_setting.py

      redis/
        __init__.py
        connection.py           # Connection pool and client
        session_store.py        # Redis-backed session storage
        rate_limit_store.py     # Redis-backed rate limit counters

      websocket/
        __init__.py
        manager.py              # WebSocket connection manager
        handlers/
          __init__.py
          ping_ws.py
          traceroute_ws.py

      cli/
        __init__.py
        main.py                 # CLI entry point (click/typer)
        create_admin.py         # `sakn-cli create-admin`

      schemas/                  # Pydantic request/response schemas
        __init__.py
        auth.py, tool.py, admin.py, common.py

      services/
        __init__.py
        auth_service.py, session_service.py
        rate_limit_service.py, log_service.py, admin_service.py
        admin_modules.py, admin_settings.py, email_service.py
        preference_service.py

      security/
        __init__.py
        address_filter.py       # IP range blocking
        password.py             # argon2 hashing + validation
        tokens.py               # CSPRNG token generation
        csrf.py                 # CSRF token generation + validation

      tools/
        __init__.py
        registry.py             # ToolRegistry (explicit registration)
        base.py                 # BaseTool, ToolDefinition, ExecutionContext, ToolResult
        ping.py, traceroute.py, dns_lookup.py, ssl_viewer.py
        network/
          __init__.py
          executor.py           # Subprocess runner with sandboxing

      middleware/
        __init__.py
        session.py              # Session resolution and injection
        rate_limit.py           # Rate limit enforcement (ASGI)
        security_headers.py     # CSP, HSTS, X-Frame-Options, etc.

      logs/
        __init__.py
        logger.py               # Structlog JSON logger

      email/
        __init__.py
        templates/              # Jinja2 templates (verification, reset)
        sender.py               # SMTP client wrapper

      i18n/
        __init__.py
        en/messages.json
        fr/messages.json

    alembic/
      versions/                 # Migration scripts
      env.py, script.mako

    tests/
      __init__.py
      unit/
        test_address_filter.py, test_rate_limiting.py, test_tool_registry.py
      integration/
        test_auth_api.py, test_tool_execution.py, test_admin_api.py
      conftest.py               # Fixtures, test database setup
      factories.py              # Model factories for tests
```

---

## 2. Dependency Injection

FastAPI DI used for: database session, current user, rate limit state, tool registry.

```python
async def get_current_user(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> User:
    session_token = request.cookies.get("session")
    # validate and return user or raise 401

def get_tool_registry() -> ToolRegistry:
    return app.state.tool_registry
```

---

## 3. API Design

### 3.1 REST over GraphQL

REST chosen: well-defined API surface, simpler to debug/cache/document. FastAPI automatic OpenAPI.

### 3.2 Authentication: Session Cookies

Session-based auth with httpOnly cookies (not JWT in localStorage).

- On login: create session in Redis. CSPRNG 256-bit token → SHA-256 hash → stored as key in Redis with session data as value.
- Raw token set as `sakn_session` cookie: httpOnly, SameSite=Lax, Secure (prod), `__Host-` prefix.
- Session middleware: reads cookie, looks up session in Redis, attaches user to request context.
- Sliding expiration: `last_activity_at` updated each request. Redis TTL = configured duration (default 24h inactivity).
- Max concurrent sessions: default 10 per user. Exceeding revokes oldest.
- Sessions revocable: user or admin deletes from Redis.
- Visitors get anonymous sessions for preferences and rate limiting.

### 3.3 API Endpoints

Base path: `/api/v1`

#### Authentication

| Method | Path | Description | Auth |
|---|---|---|---|
| POST | `/auth/register` | Register new user | None |
| POST | `/auth/login` | Login, set session cookie | None |
| POST | `/auth/logout` | Destroy session | Session |
| POST | `/auth/verify-email` | Verify email with token | None |
| POST | `/auth/resend-verification` | Resend verification email | Session (authenticated) |
| POST | `/auth/request-password-reset` | Request password reset | None |
| POST | `/auth/reset-password` | Reset password with token | None |

#### Tool Execution

| Method | Path | Description | Auth |
|---|---|---|---|
| POST | `/tools/{tool_name}/execute` | Execute instant tool | Session (or visitor) |
| GET  | `/tools` | List available tools | Session (or visitor) |

See `spec-tools-instant.md` for HTTP execution format. See `spec-tools-live.md` for WebSocket streaming.

#### User Preferences

| Method | Path | Auth |
|---|---|---|
| GET | `/preferences` | Session (or visitor) |
| PUT | `/preferences` | Session (or visitor) |

#### Session Management

| Method | Path | Auth |
|---|---|---|
| GET | `/sessions` | Session |
| DELETE | `/sessions/{session_id}` | Session |

#### Administration (all Admin-only)

| Method | Path | Description |
|---|---|---|
| GET | `/admin/users` | List users (paginated) |
| GET | `/admin/users/{user_id}` | Get user details |
| PUT | `/admin/users/{user_id}/block` | Block user |
| PUT | `/admin/users/{user_id}/unblock` | Unblock user |
| PUT | `/admin/users/{user_id}/lock` | Lock user |
| PUT | `/admin/users/{user_id}/unlock` | Unlock user |
| PUT | `/admin/users/{user_id}/notes` | Update admin notes |
| DELETE | `/admin/users/{user_id}` | Delete user |
| GET | `/admin/tools` | List tool configurations |
| PUT | `/admin/tools/{tool_name}` | Update tool config |
| GET | `/admin/role-permissions` | List role-tool permissions |
| PUT | `/admin/role-permissions` | Update role-tool permissions |
| GET | `/admin/rate-limits` | List rate limit configs |
| PUT | `/admin/rate-limits` | Update rate limit config |
| GET | `/admin/logs/tool-executions` | View tool execution logs |
| GET | `/admin/logs/security-events` | View security event logs |
| GET | `/admin/logs/audit` | View audit logs |
| GET | `/admin/modules/{tool_name}/dns-servers` | List DNS server presets |
| POST | `/admin/modules/{tool_name}/dns-servers` | Add DNS server preset |
| PUT | `/admin/modules/{tool_name}/dns-servers/{id}` | Edit DNS server preset |
| DELETE | `/admin/modules/{tool_name}/dns-servers/{id}` | Delete DNS server preset |
| PUT | `/admin/modules/{tool_name}/dns-servers/reorder` | Reorder DNS server presets |
| GET | `/admin/settings` | List global settings |
| PUT | `/admin/settings` | Update global settings |

#### Health

| Method | Path | Auth |
|---|---|---|
| GET | `/health` | None |

### 3.4 API Versioning

URL prefix (`/api/v1/`). Deprecation: old version maintained 6+ months with `Deprecation` header.

---

## 4. Data Model

### 4.1 Entity Overview

- **User** 1:N **Session** (sessions may be anonymous — user_id nullable)
- **User** 1:1 **UserPreference** (nullable user_id for visitors, keyed by session_id)
- **User** 1:N **EmailVerification**, **PasswordReset** — one-time security tokens
- **ToolModule** 1:N **RoleToolPermission** — per-role allow/deny per tool
- **ToolModule** 1:N **DnsServerPreset** — admin-managed DNS server list
- **RateLimitConfig** — keyed by `(role, tool_id)`; tool_id=NULL = global. Roles: `visitor-session`, `visitor-ip`, `authenticated`, `administrator`. See Section 6.
- **ToolExecutionLog**, **SecurityEventLog**, **AuditLog** — immutable logs, default 90-day retention
- **GlobalSetting** — key-value store (e.g., `log_retention_days`)

**Account deletion**: Preferences hard-deleted. Logs anonymized (user_id/session_id → NULL; source_ip retained).

### 4.2 Key Entity Definitions

#### User

| Field | Type | Constraints |
|---|---|---|
| id | UUIDv7 | PK |
| email | VARCHAR(255) | UNIQUE, NOT NULL, lowercase-normalized |
| password_hash | VARCHAR(255) | NOT NULL, argon2id |
| role | VARCHAR(20) | NOT NULL, DEFAULT 'authenticated' — enum: visitor, authenticated, administrator |
| status | VARCHAR(20) | NOT NULL, DEFAULT 'pending' — enum: pending, active, blocked, locked |
| failed_login_attempts | INTEGER | NOT NULL, DEFAULT 0 |
| locked_until | TIMESTAMPTZ | NULLABLE |
| admin_notes | TEXT | NULLABLE |
| email_verified_at | TIMESTAMPTZ | NULLABLE |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() |

**Status lifecycle**:
- registration → pending → email verification → active
- active → admin blocks → blocked → admin unblocks → active
- active → 5/10/15/20+ failed logins → temporary lock_until (5min/15min/45min/90min) → auto-unlock
- active → admin locks → locked (status=locked) → admin unlocks → active
- self-deletion → preferences deleted, logs anonymized

**Rules**: `locked` status is admin-managed only (app NEVER sets it automatically). Brute force uses `locked_until` (temporary). Last admin cannot be deleted/demoted.

#### Session

| Field | Type | Constraints |
|---|---|---|
| id | UUIDv7 | PK |
| user_id | UUID | FK -> User, NULLABLE (NULL = visitor) |
| token_hash | VARCHAR(64) | UNIQUE, NOT NULL, SHA-256 of session token |
| ip_address | INET | NOT NULL |
| user_agent | VARCHAR(512) | NULLABLE |
| expires_at | TIMESTAMPTZ | NOT NULL, created + 24h |
| last_activity_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW(), sliding window |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() |

#### ToolModule

| Field | Type |
|---|---|
| id | UUIDv7 PK |
| name | VARCHAR(64) UNIQUE NOT NULL (e.g., "ping") |
| display_name_key | VARCHAR(128) NOT NULL (i18n key) |
| description_key | VARCHAR(128) NOT NULL (i18n key) |
| enabled | BOOLEAN NOT NULL DEFAULT true |
| version | VARCHAR(20) NOT NULL (semver) |
| created_at, updated_at | TIMESTAMPTZ |

#### RoleToolPermission

| Field | Type |
|---|---|
| id | UUIDv7 PK |
| role | VARCHAR(20) NOT NULL |
| tool_id | UUID FK -> ToolModule |
| allowed | BOOLEAN NOT NULL |
| UNIQUE | (role, tool_id) |

#### RateLimitConfig

| Field | Type |
|---|---|
| id | UUIDv7 PK |
| role | VARCHAR(20) NOT NULL |
| tool_id | UUID FK -> ToolModule, NULLABLE (NULL = global) |
| soft_limit | INTEGER NOT NULL DEFAULT 0 (0 = no limit) |
| hard_limit | INTEGER NOT NULL DEFAULT 0 |
| window_seconds | INTEGER NOT NULL DEFAULT 60 |
| UNIQUE | (role, tool_id) |

#### ToolExecutionLog

| Field | Type |
|---|---|
| id | UUIDv7 PK |
| user_id | UUID FK -> User, NULLABLE |
| session_id | UUID FK -> Session |
| source_ip | INET NOT NULL |
| tool_name | VARCHAR(64) NOT NULL (denormalized) |
| parameters | JSONB NOT NULL |
| result | VARCHAR(20) NOT NULL (success/failure/partial) |
| duration_ms | INTEGER NOT NULL |
| error_message | TEXT NULLABLE |
| created_at | TIMESTAMPTZ NOT NULL, indexed |

#### SecurityEventLog

| Field | Type |
|---|---|
| id | UUIDv7 PK |
| event_type | VARCHAR(40) NOT NULL (blocked_address, rate_limit_exceeded, auth_brute_force, etc.) |
| source_ip | INET NOT NULL |
| user_id | UUID FK -> User, NULLABLE |
| details | JSONB NOT NULL |
| created_at | TIMESTAMPTZ NOT NULL, indexed |

#### AuditLog

| Field | Type |
|---|---|
| id | UUIDv7 PK |
| admin_id | UUID FK -> User |
| action | VARCHAR(64) NOT NULL (e.g., "user.block") |
| entity_type | VARCHAR(64) NOT NULL |
| entity_id | VARCHAR(64) NOT NULL |
| old_value | JSONB NULLABLE |
| new_value | JSONB NOT NULL |
| created_at | TIMESTAMPTZ NOT NULL, indexed |

### 4.3 Migration Strategy

Alembic with auto-generation. Workflow: change model → `alembic revision --autogenerate -m "desc"` → review → `alembic upgrade head`.

Guidelines: new columns NULLABLE or have DEFAULT. Production migrations in deployment startup. Backfill scripts separate from schema migrations. SQLite + PostgreSQL must share migration set.

SQLite compat: use `sa.Text()` for JSONB, `sa.String()` for INET, `sa.String(64)` for UUID (SQLite has no native UUID/INET/JSONB).

#### Revision IDs — always auto-generated

**Mandatory rule (humans and AI agents alike)**: never hand-write the `revision: str = "..."` value of a migration. Always run:

```bash
cd src/backend
alembic revision -m "short description"
# or, when generating from model changes:
alembic revision --autogenerate -m "short description"
```

Alembic produces a random 12-character hexadecimal ID (e.g. `d7091a29b949`). Use that ID as-is and let Alembic also name the file (`<id>_<slug>.py`). Do **not**:

- compose a "looking-random" ID by hand (e.g. `5a1b2c3d4e56`, `f1a2b3c4d5e6`) — these sequential or low-entropy strings risk colliding with a future auto-generated ID and break Alembic's diff tooling
- copy an existing revision ID from another project
- rename a migration file after it has been committed to master (renaming after merge requires every dev/staging/prod environment to run `UPDATE alembic_version SET version_num='<new>' WHERE version_num='<old>'` manually)

If you discover a manually-composed ID after merge, file an issue rather than renaming silently. The cleanup PR must document the required `UPDATE alembic_version` step for each environment that has already applied the migration.

---

## 5. Security Architecture

### 5.1 Network Address Filtering

Enforced before every Ping, Traceroute, DNS Lookup execution.

**Blocked ranges** (in `app/security/address_filter.py`):

```python
BLOCKED_NETWORKS = [
    # IPv4
    ip_network("0.0.0.0/8"),         # "This" network
    ip_network("10.0.0.0/8"),        # Private (RFC 1918)
    ip_network("100.64.0.0/10"),     # CGNAT (RFC 6598)
    ip_network("127.0.0.0/8"),       # Loopback
    ip_network("169.254.0.0/16"),    # Link-local
    ip_network("172.16.0.0/12"),     # Private (RFC 1918)
    ip_network("172.17.0.0/16"),     # Docker bridge (default)
    ip_network("172.18.0.0/16"),     # Docker bridge (common)
    ip_network("192.0.2.0/24"),      # Documentation (TEST-NET-1)
    ip_network("192.168.0.0/16"),    # Private (RFC 1918)
    ip_network("198.18.0.0/15"),     # Benchmarking (RFC 2544)
    ip_network("198.51.100.0/24"),   # Documentation (TEST-NET-2)
    ip_network("203.0.113.0/24"),    # Documentation (TEST-NET-3)
    ip_network("224.0.0.0/4"),       # Multicast
    ip_network("240.0.0.0/4"),       # Future use / reserved
    ip_network("255.255.255.255/32"),# Broadcast
    # IPv6
    ip_network("::1/128"),           # Loopback
    ip_network("::ffff:0:0/96"),     # IPv4-mapped IPv6
    ip_network("fc00::/7"),          # Unique local
    ip_network("fe80::/10"),         # Link-local
    ip_network("ff00::/8"),          # Multicast
]
```

**Filtering sequence**:
1. Validate input (hostname or IP). Reject if invalid.
2. If IP: check against blocklist directly.
3. If hostname: resolve via hardcoded external DNS (default `1.1.1.1`), check each resulting IP against blocklist.
4. Blocked → log security event, return "Target not allowed".
5. Pass → execute tool with resolved IP (not original hostname).

**Bypass prevention**:
- **CNAME**: each address in chain independently checked.
- **IPv6**: same blocklist (fc00::/7, fe80::/10, etc.).
- **DNS rebinding**: resolve once, pass IP to tool (not hostname). Filter uses hardcoded public resolver (`SECURITY_DNS_RESOLVER`, default `1.1.1.1`).
- **Internal names**: external DNS only — NXDOMAIN/SERVFAIL → reject.

### 5.2 Authentication Security

| Concern | Implementation |
|---|---|
| Password hashing | argon2id (`argon2-cffi`), time=2, memory=19456 KiB, parallelism=1 |
| Password validation | 8-128 chars, 1 upper + 1 lower + 1 digit. `zxcvbn` entropy ≥30 bits. |
| Brute force protection | Escalating `locked_until`: 5 fails→5min, 10→15min, 15→45min, 20+→90min (renewed every 5 subsequent). Counter resets on success. Backend NEVER sets `status=locked` (admin-only). Admins exempt. |
| Session security | See Section 3.2. httpOnly, SameSite=Lax, Secure in prod, `__Host-` prefix. 24h default, sliding expiration, max 10 concurrent. |
| User enumeration | Constant-time responses. All auth endpoints return identical messages for existing/non-existing accounts. |

### 5.3 CSRF Protection

Double Submit Cookie pattern:
- Server sets `sakn_session` (httpOnly) + `sakn_csrf` (NOT httpOnly — JS reads it), both SameSite=Lax.
- State-changing requests (POST/PUT/DELETE/PATCH): frontend sends `X-CSRF-Token` header with cookie value.
- Server validates header == cookie. Mismatch → 403.

### 5.4 Security Headers (via ASGI middleware)

| Header | Value (production) |
|---|---|
| `Content-Security-Policy` | `default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self' ws: wss:; form-action 'self'` |
| `Strict-Transport-Security` | `max-age=63072000; includeSubDomains` |
| `X-Content-Type-Options` | `nosniff` |
| `X-Frame-Options` | `DENY` |
| `Referrer-Policy` | `strict-origin-when-cross-origin` |

### 5.5 Security Event Logging

All security events logged to `SecurityEventLog` with: timestamp (UTC), source IP, user ID (if applicable), event type, detailed payload (blocked target, rule triggered). No internal infrastructure details in frontend error messages.

### 5.6 Proxy Trust Policy

The backend runs behind a reverse proxy (Caddy in the reference deployment; Traefik, Nginx, HAProxy or other HTTP-aware proxies in alternative deployments). To remain proxy-agnostic, the application implements its own ASGI middleware `TrustedProxyMiddleware` (`app/middleware/proxy_trust.py`). Uvicorn's built-in `ProxyHeadersMiddleware` is disabled via `--no-proxy-headers`.

**Configuration**: env var `TRUSTED_PROXY_HOPS` (integer, default `0`).

| Value | Meaning |
|---|---|
| `0` | App directly exposed. Forwarded headers ignored. Client = TCP peer. |
| `1` | Single reverse proxy in front (Caddy/Traefik/Nginx). Default for the production compose profile. |
| `N` | N proxies in front (e.g. CDN + ingress controller). |

**`X-Forwarded-Proto` handling**: when `TRUSTED_PROXY_HOPS > 0`, the rightmost value (`http`/`https` only) sets `scope["scheme"]`. For WebSocket connections, the scheme is mapped to `ws`/`wss`.

**`X-Forwarded-For` handling**: when `TRUSTED_PROXY_HOPS > 0`, the application parses the comma-separated list and takes the entry at position `-TRUSTED_PROXY_HOPS` (i.e. the Nth entry from the right). This is the IP observed by the trusted proxy; it cannot be spoofed by an external client because each proxy appends to the right.

**Effects downstream**: `request.url.scheme` returns `https` (→ cookies emitted with `Secure` + `__Host-` prefix in `auth.py`, `session.py`, `sessions.py`); `request.client.host` returns the original client IP (→ correct IP-based rate limit keys and `source_ip` in `SecurityEventLog`/`ToolExecutionLog`).

See ADR-003 (`docs/adr/003-proxy-trust-policy.md`) for the design rationale.

---

## 6. Rate Limiting Implementation

### 6.1 Algorithm: Sliding Window Counter

Redis sorted sets per key. Lua script atomically: cleans expired entries (`ZREMRANGEBYSCORE`), counts soft (1s) and hard (1h) windows (`ZCOUNT`), records request (`ZADD`), sets 2h TTL (`EXPIRE`). Returns `(soft_count, hard_count)`.

Python-side: `SlidingWindowRateLimiter` class with `check(key, soft_limit, hard_limit, soft_window_s, hard_window_s) -> RateLimitResult` and `increment(key)`.

The soft-limit window is fixed at 1 second and is not configurable via `window_seconds`. The `window_seconds` column in `RateLimitConfig` applies only to the hard limit. This is by design — a 1-second burst window is an industry standard for rate limiting.

### 6.2 Limit Types

- **Soft limit** (1s window): HTTP 429 + `Retry-After: 1`. Controls bursts.
- **Hard limit** (1h window): HTTP 429 + `Retry-After: 3600`. Controls volume.
- **Warning**: at ≥80% hard limit, response includes `X-RateLimit-Warning: true`.

### 6.3 Default Configuration

| Role | Global Soft | Global Hard |
|---|---|---|
| Visitor (session) | 1 req/sec | 200 req/hr |
| Visitor (IP) | 5 req/sec | 500 req/hr |
| Authenticated | 1 req/sec | 500 req/hr |
| Administrator | no limit | 3600 req/hr |

Per-tool limits default to 0 (no limit). Per-tool can only tighten, never relax. Visitors: both session AND IP checks must pass.

### 6.4 Rate Limit Keys

| Subject | Key |
|---|---|
| Visitor session | `session:{session_id}` |
| Visitor IP | `ip:{source_ip}` |
| Authenticated user | `user:{user_id}` |
| Administrator | `user:{user_id}` |

### 6.5 Storage

Redis sorted sets: key = `ratelimit:{key_type}:{identifier}`, score = unix timestamp, member = request UUIDv7.

Database fallback (SQLite dev without Redis): `RateLimitCounter` SQL table (key, window_start, count). Set `RATE_LIMIT_STORAGE=database`. Not recommended for production.

Cleanup: periodic task (every 5 min) deletes entries >2h old.

### 6.6 Enforcement Points

1. **ASGI Middleware** (`RateLimitMiddleware`): global check on all tool execution requests.
2. **Tool Service**: per-tool check after middleware passes.

Flow: visitor dual-check or user/IP check → middleware global check → tool service per-tool check. Any failure → 429 + headers + log.

### 6.7 Response Headers

**Soft 429**: `Retry-After: 1`, `X-RateLimit-Limit: 1`, `X-RateLimit-Remaining: 0`, `X-RateLimit-Policy: 1 req/sec`
**Hard 429**: `Retry-After: 3600`, `X-RateLimit-Limit: 200`, `X-RateLimit-Remaining: 0`, `X-RateLimit-Policy: 200 req/hr`
**Warning (200)**: `X-RateLimit-Limit: 200`, `X-RateLimit-Remaining: 35`, `X-RateLimit-Warning: true`

Body (all 429): `{"error": {"code": "RATE_LIMIT_EXCEEDED", "message": "Too many requests. Try again later."}}`

### 6.8 Effective Limit Computation

```
effective_soft = min(global_soft, per_tool_soft)
effective_hard = min(global_hard, per_tool_hard)
```

Where `min` treats 0 as "no limit". Tool limits can only tighten.

### 6.9 Auth Endpoint Rate Limits (hardcoded)

| Endpoint | Limit | Window |
|---|---|---|
| POST /auth/login | 10 per IP | 60s |
| POST /auth/register | 3 per IP | 3600s |
| POST /auth/request-password-reset | 3 per email | 86400s |
| POST /auth/resend-verification | 5 per user | 86400s |

### 6.10 Admin Overrides

Admins can set custom limits per role and per tool. Per-tool limits must be ≤ global limits. Changes take effect immediately. UI renders as matrix: roles as rows, global/tool as column groups.

---

## 7. Logging Strategy

### 7.1 Log Categories

| Category | Storage | Retention |
|---|---|---|
| Tool execution logs | `ToolExecutionLog` table | 90 days (admin-configurable) |
| Security events | `SecurityEventLog` table | 90 days |
| Admin audit trail | `AuditLog` table | 90 days |
| Application logs | Container stdout (JSON) | Per Docker logging driver |
| Authentication events | `SecurityEventLog` table | 90 days |

### 7.2 Structured Application Logging

JSON lines to stdout via `structlog` + `orjson`. Each log carries: `timestamp`, `level`, `logger`, `message`, `request_id` (UUID propagated from middleware for correlation), `user_id`, context-specific fields.

### 7.3 Logging Rules

| Event | Log Action | Level |
|---|---|---|
| Tool execution start | `ToolExecutionLog` row + structured log | INFO |
| Tool execution success/failure | Update `ToolExecutionLog` result | INFO / WARN |
| Security refusal | `SecurityEventLog` row | WARN |
| Rate limit exceeded | `SecurityEventLog` row | WARN |
| Login (success/fail) | `SecurityEventLog` (+ counter on fail) | INFO |
| Account locked/unlocked | `SecurityEventLog` row | WARN / INFO |
| Admin action | `AuditLog` row | INFO |
| Configuration change | `AuditLog` row with old/new values | INFO |
| Registration, verification, password reset, deletion | `SecurityEventLog` row | INFO |

### 7.4 Log Cleanup

Scheduled task (`apscheduler` in-process or cron) deletes entries older than configured retention. Runs daily.

---

## 8. Docker Architecture

### 8.1 Container Layout

Five containers: **caddy** (reverse proxy, TLS via Let's Encrypt), **backend** (Python 3.14 + FastAPI + Uvicorn, `cap_add: [NET_RAW, NET_ADMIN]`), **frontend** (Nginx serving React static files), **postgres** (PostgreSQL 18 Alpine), **redis** (Redis 7 Alpine).

Caddy is the entry point: listens 80/443, redirects HTTP→HTTPS, proxies `/api/*` and `/health` to backend, proxies everything else to frontend. Caddyfile mounted as volume. Avoids CORS issues (single domain), provides automatic HTTPS.

### 8.2 Networking

| Network | Purpose |
|---|---|
| `sakn-internal` | Backend ↔ PostgreSQL ↔ Redis. Internal only. |
| `sakn-public` | Caddy + Backend + Frontend. Only Caddy exposes ports. |

Dev: frontend runs on host (Vite), backend via CORS, Caddy optional.

### 8.3 Volumes

| Volume | Mount |
|---|---|
| `./volumes/postgres/` | postgres:/var/lib/postgresql/data |
| `./volumes/redis/` | redis:/data |
| `./volumes/caddy/` | caddy:/data |
| `./volumes/caddy-config/` | caddy:/config |
| `./volumes/sqlite/` (dev only) | backend:/data |

### 8.4 Dockerfile (Backend, Multi-stage)

```dockerfile
# Stage 1: Build
FROM python:3.14-slim AS builder
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev --frozen

# Stage 2: Runtime
FROM python:3.14-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    iputils-ping traceroute dnsutils openssl ca-certificates curl redis-tools \
    && rm -rf /var/lib/apt/lists/*
RUN setcap cap_net_raw+ep /usr/bin/ping \
    && setcap cap_net_raw+ep /usr/sbin/traceroute
COPY --from=builder /app/.venv /app/.venv
COPY app/ ./app/
COPY tests/ ./tests/
COPY alembic/ ./alembic/
COPY alembic.ini ./
COPY startup.sh ./
RUN chmod +x startup.sh
RUN useradd --create-home --uid 1000 sakn
USER sakn
ENV PATH="/app/.venv/bin:$PATH"
HEALTHCHECK --interval=30s --timeout=5s CMD curl -f http://localhost:8000/health || exit 1
EXPOSE 8000
CMD ["./startup.sh"]
```

**startup.sh** waits for PostgreSQL and Redis, runs Alembic migrations, then starts uvicorn.

Base image rationale: `python:3.14-slim` (Debian) — musl (Alpine) causes issues with Python C extensions (asyncpg, argon2-cffi). Debian Slim provides reliable network tool availability. Non-root user (`uid=1000`). Capabilities via `setcap` on ping/traceroute binaries at build time.

### 8.5 Docker Compose

See `docker-compose.yml` and `docker-compose.dev.yml` in the repository for the full configuration.

Key points:
- Caddy: image `caddy:2-alpine`, ports 80/443, Caddyfile mounted.
- Backend: env vars for `DATABASE_URL`, `REDIS_URL`, `SECRET_KEY`, `TRUSTED_PROXY_HOPS` (see §5.6); `cap_add: [NET_RAW, NET_ADMIN]`. Started with `uvicorn --no-proxy-headers` so the application controls proxy-header trust via `TrustedProxyMiddleware` (see ADR-003).
- PostgreSQL: image `postgres:18-alpine`, `POSTGRES_DB=sakn`.
- Redis: image `redis:7-alpine`, `--appendonly yes`, healthcheck via `redis-cli ping`.
- Dev: Caddy and frontend profiles set to `prod` only; backend uses SQLite; Redis active in both dev and prod.

### 8.6 Network Tool Privileges

At build time: `setcap cap_net_raw+ep` on `/usr/bin/ping` and `/usr/sbin/traceroute`. Container started with `cap_add: [NET_RAW, NET_ADMIN]`. This allows the non-root Python process to execute ping/traceroute as subprocesses.

---

## 9. Module System

### 9.1 Tool Interface

Each tool implements `BaseTool` (abstract class in `app/tools/base.py`):

**Core types** (frozen dataclasses):
- `ToolCategory` (enum): `NETWORK`, `DNS`, `SECURITY`.
- `ToolParameter`: `name`, `type` (string|integer|boolean|enum), `label_key`, `description_key`, `required`, `default`, `constraints` dict (e.g., `{"min":1,"max":100}` for integer, `{"values":["udp","icmp"]}` for enum).
- `ToolDefinition`: `name`, `display_name_key`, `description_key`, `category`, `version`, `parameters: list[ToolParameter]`, `requires_privileges: list[str]`.
- `ExecutionContext`: `user_id`, `session_id`, `source_ip`, `role`, `request_id`.
- `ToolResult`: `success`, `data`, `error`, `duration_ms`.

**Abstract methods**:
- `get_definition() -> ToolDefinition` — static metadata.
- `validate_params(params) -> dict` — validate/normalize; raises `ValueError` with `message_key`.
- `execute(params, context: ExecutionContext) -> ToolResult` — must check `address_filter` before network ops.
- `get_result_schema() -> dict` — JSON Schema for the result data field.

### 9.2 Registry

`ToolRegistry` (in `app/tools/registry.py`) holds a `dict[str, BaseTool]`. Tools are registered **explicitly** at startup in `main.py`'s lifespan handler — not via auto-discovery. Rationale: explicit imports make dependencies and initialization order visible and reviewable.

API: `register(tool)`, `get(name) -> BaseTool | None`, `list_available() -> list[ToolDefinition]`, `get_enabled() -> list[str]` (filtered by DB config).

### 9.3 Tool Directory Structure

```
app/tools/
  __init__.py
  base.py           # BaseTool, ToolDefinition, ExecutionContext, ToolResult
  registry.py       # ToolRegistry
  ping.py           # PingTool(BaseTool)
  traceroute.py     # TracerouteTool(BaseTool)
  dns_lookup.py     # DnsLookupTool(BaseTool)
  ssl_viewer.py     # SslViewerTool(BaseTool)
  network/
    __init__.py
    executor.py     # SubprocessExecutor: sandboxed subprocess runner
    blocking.py     # AddressBlocklist: shared blocklist instance
```

### 9.4 Tool Lifecycle

1. **Registration** (startup): Validate definition, ensure unique name, create default `RoleToolPermission` and `RateLimitConfig` DB rows.
2. **Configuration** (runtime, admin): Enable/disable, update permissions, update rate limits. All immediate.
3. **Execution** (per request): Resolve role/session → address filter → rate limits → permission check → enabled check → validate params → execute → log → return result.

### 9.5 Adding a New Tool (Post-MVP)

1. Create `app/tools/whois.py` implementing `BaseTool`.
2. Register in `main.py` startup.
3. Create frontend page + route + i18n keys.
4. Add default DB rows via Alembic migration.
5. Write tests.

No changes needed to core framework, API routing, auth, or rate limiting.

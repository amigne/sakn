# Threat Model — SAKN

**Date**: 2026-05-20
**Scope**: Application-layer threats for the SAKN web application (backend API,
frontend SPA, WebSocket handlers, Docker Compose infrastructure).
**Out of scope**: Physical security, OS kernel exploits, social engineering,
supply-chain attacks on base Docker images.

## 1. Introduction

This document identifies the security properties the SAKN system is designed
to uphold, the threats that could violate those properties, and the mitigations
in place. It uses the STRIDE methodology (Spoofing, Tampering, Repudiation,
Information Disclosure, Denial of Service, Elevation of Privilege) applied
per-component across the stack.

**Audience**: Operators deploying SAKN, contributors, security auditors.

**References**: This threat model draws on the
[security audit of 2026-05-18](./audit-2026-05-18.md) (29 findings across
critical, high, medium, and low severity) and the architecture decisions
recorded in the [ADR directory](../adr/).

## 2. System Overview

SAKN is deployed as a 5-container Docker Compose stack:

```
Browser → Caddy (TLS) → Frontend (nginx/SPA)
                      → Backend (FastAPI) → PostgreSQL 18
                                          → Redis 7
                                          → External DNS resolvers
```

| Container | Role | Network |
|-----------|------|---------|
| Caddy | TLS termination, reverse proxy, HSTS/CSP headers | `sakn-public` |
| Frontend | nginx serving React SPA | `sakn-public` |
| Backend | FastAPI API + WebSocket + scheduler | `sakn-public` + `sakn-internal` |
| PostgreSQL | User data, sessions, RBAC, audit logs | `sakn-internal` |
| Redis | Session cache, rate-limit counters | `sakn-internal` |

The `sakn-internal` network is marked `internal: true` in Docker Compose — no
external ingress. Only the backend container bridges both networks.

For detailed architecture, see [Technical Spec Index](../specs/technical/spec-index.md).

## 3. Trust Boundaries

| # | Boundary | Description |
|---|----------|-------------|
| B1 | Internet → Caddy | TLS termination, first ingress point. Caddy validates TLS, enforces HSTS/CSP. |
| B2 | Caddy → Backend | Internal Docker network. `X-Forwarded-For` and `X-Forwarded-Proto` headers are set by Caddy. Trust policy per [ADR-003](../adr/003-proxy-trust-policy.md). |
| B3 | Backend → PostgreSQL / Redis | Docker `sakn-internal` network. No external access. Passwords required. |
| B4 | Backend → External DNS | Egress to configurable upstream resolvers. Application enforces address blocklists regardless of resolver. |
| B5 | WebSocket upgrade | HTTP → WS upgrade path bypasses standard middleware chain. Custom auth, rate-limit, and Origin checks applied inline. |

## 4. Asset Inventory

| Asset | Storage | Sensitivity | Protection |
|-------|---------|-------------|------------|
| User credentials | PostgreSQL (`users.password_hash`) | High — Argon2id hashes | Argon2id with OWASP parameters; never logged |
| Session tokens | PostgreSQL + Redis (SHA-256 hash) | High — full account access if cracked | 256-bit CSPRNG; HttpOnly `__Host-` cookies; constant-time comparison |
| CSRF tokens | Cookie + request header | Medium — state-changing request forgery | Double-submit pattern; per-session token |
| User PII (email, prefs) | PostgreSQL | Medium — GDPR-relevant | Email HMAC-hashed in security logs; role-gated access |
| Tool execution logs | PostgreSQL (`tool_execution_logs`) | Low — operational data | Role-gated admin access; 90-day retention |
| Role-permission matrix | PostgreSQL (`role_tool_permissions`) | Medium — access control integrity | Admin-only modification; audit-logged |
| Audit/Security event logs | PostgreSQL (`audit_logs`, `security_event_logs`) | Medium — forensic value | Append-only (no update/delete endpoints); 90-day retention |

## 5. Threat Analysis

Each subsection covers one component area. Threats are classified by STRIDE
category: **S**poofing, **T**ampering, **R**epudiation, **I**nformation
Disclosure, **D**enial of Service, **E**levation of Privilege.

### 5.1 Authentication

| Threat | STRIDE | Severity | Mitigation | Reference |
|--------|--------|----------|------------|-----------|
| Credential brute-force (online, per-user) | S | High | Argon2id (time_cost=3, memory_cost=65536, parallelism=4); escalating per-user lockout: 5 failures → 5 min, 10 → 15 min, 15 → 45 min, 20+ → 90 min | `src/backend/app/services/auth_service.py` |
| Credential stuffing (cross-user, per-IP) | D | High | **Fixed** (issue #28, ADR-005). Redis-backed IP counter: `INCR` + `EXPIRE` with configurable threshold (default 20 failed attempts / 15 min). Returns 429 with `Retry-After` when exceeded. Checked BEFORE user lookup (enumeration-safe). | ADR-005; `auth_service.py:_check_ip_bruteforce()` |
| Email enumeration via registration | I | Medium | Uniform response: duplicate email returns HTTP 200 with identical message and timing; email HMAC-hashed in security event logs | ADR-002; `auth_service.py:_hash_email_for_log()` |
| Email enumeration via login | I | Medium | All login failures return identical `errors.invalid_credentials`; timing is independent of whether the email exists | ADR-002; `auth_service.py` |
| Email enumeration via password reset | I | Medium | Password reset always returns the same message regardless of email existence; rate-limited at 3 req/day | ADR-002; `auth_service.py` |
| Weak SECRET_KEY in production | I | Critical | Config validator rejects the default value and keys shorter than 32 characters when `ENVIRONMENT=production` | `src/backend/app/config.py:36-49` |
| Password too weak | S | Medium | Minimum 8 chars; requires uppercase + lowercase + digit; zxcvbn entropy check (≥ 2^30 guesses) | `src/backend/app/security/password.py` |

### 5.2 Sessions

| Threat | STRIDE | Severity | Mitigation | Reference |
|--------|--------|----------|------------|-----------|
| Session token prediction | S | High | 256-bit CSPRNG tokens via `secrets.token_urlsafe(32)` | `src/backend/app/security/tokens.py:5-7` |
| Token DB theft enables impersonation | I | High | SHA-256 hashing before storage; constant-time comparison via `secrets.compare_digest()` | `src/backend/app/security/tokens.py:10-17` |
| Session token lacks HMAC pepper | I | Medium | **Acknowledged limitation** (audit finding M-3). Token entropy (256 bits) makes brute-force impractical with current compute, but an HMAC pepper would add defence-in-depth if both DB and Redis are simultaneously compromised. | Audit M-3 |
| Session fixation | S | Medium | New session token generated on login; old token invalidated | `auth_service.py:login()` |
| Cookie theft / XSS | I | High | HttpOnly + SameSite=Lax cookies; `__Host-` prefix when HTTPS active (browser-enforced Secure + Path=/); 24h expiry with activity-based extension | `src/backend/app/security/cookies.py` |
| CSRF on state-changing endpoints | T | High | Double-submit cookie pattern: `sakn_csrf` cookie (readable by JS) + `X-CSRF-Token` header validated per mutation; auto-retry on 403 with fresh token | `src/backend/app/security/csrf.py` |
| Concurrent session abuse | E | Low | Max 10 concurrent sessions per user (configurable via `GlobalSetting`); oldest sessions evicted | `src/backend/app/redis/session_store.py` |

### 5.3 WebSocket

| Threat | STRIDE | Severity | Mitigation | Reference |
|--------|--------|----------|------------|-----------|
| Cross-Site WebSocket Hijacking (CSWSH) | S | High | **Fixed** (issue #45). `Origin` header validated against `CORS_ORIGINS` allowlist BEFORE any DB/Redis queries — rejected connections incur zero backend load. | `src/backend/app/api/v1/endpoints/tools.py` (WS handler) |
| Unauthenticated WebSocket access | S | High | Session token parsed from Cookie header before accept; Redis then DB lookup; connection closed (code 4501) if invalid | `tools.py` WS handler |
| Unauthorized tool execution via WS | E | High | `RoleToolPermission` checked for resolved role + tool before accept | `tools.py` WS handler |
| WebSocket fail-open on DB error | E | High | **Fixed** (audit H-2). Previously `try/except: pass` allowed execution on DB errors. Now fail-closed: connection terminated with code 4503. | Audit H-2; `tools.py` |
| Rate limit bypass via WebSocket | D | Medium | Inline rate limit check applied inside WS handler before tool execution; 4029 close code on exceeded | `tools.py` WS handler |
| Session reuse across WS connections | S | Low | Each WS connection independently validates the session token; no caching of auth decisions across connections | `tools.py` WS handler |

### 5.4 Admin

| Threat | STRIDE | Severity | Mitigation | Reference |
|--------|--------|----------|------------|-----------|
| Unauthorized admin access | E | Critical | `require_admin` dependency on all `/api/v1/admin/*` routes; returns 403 if `request.state.role != "administrator"` | `src/backend/app/middleware/admin.py` |
| Last-admin deletion blocks administration | D | High | Backend refuses to delete or demote the last remaining administrator | `src/backend/app/api/v1/endpoints/admin_users.py` |
| Audit log tampering | T | Medium | `audit_logs` and `security_event_logs` tables are append-only — no update or delete endpoints exposed | `src/backend/app/models/log.py` |
| Admin actions not tracked | R | Medium | All admin mutations logged to `audit_logs` with old/new values as JSON, admin user ID, and timestamp | `src/backend/app/services/admin_service.py` |
| Admin bypasses rate limits | D | Low | Admin paths (`/api/v1/admin/*`) are excluded from rate limiting. Mitigation: admin access is gated by session + role, and admin actions are audit-logged. | `src/backend/app/middleware/rate_limit.py` |

### 5.5 RBAC (Role-Based Access Control)

| Threat | STRIDE | Severity | Mitigation | Reference |
|--------|--------|----------|------------|-----------|
| Privilege escalation via role manipulation | E | High | 3 fixed roles: `visitor`, `authenticated`, `administrator` — enforced as string constants; role resolved from DB via session middleware on every request | `src/backend/app/middleware/session.py:_resolve_role()` |
| Unauthorized tool execution | E | High | `RoleToolPermission` join table gates every tool execution (HTTP + WS); checked on tool list, execute, and stream endpoints | `src/backend/app/api/v1/endpoints/tools.py:_check_tool_access()` |
| Self-healing permission creation is fail-open | E | Medium | **Acknowledged behaviour**: if a `RoleToolPermission` row is missing for a role/tool pair, it is auto-created with `allowed=True`. Startup seeding creates explicit entries for all known combinations; this fail-open only triggers for new role-tool pairs added post-deployment. | `tools.py:_check_tool_access()` |
| Arbitrary role enumeration | I | Low | **Fixed** (audit M-4). `/tools/available-for/{role}` now validates the role parameter against known roles instead of accepting arbitrary strings. | Audit M-4; `tools.py` |
| SQL LIKE wildcard injection in admin search | I | Medium | **Fixed** (audit H-5). Admin user search escapes `%` and `_` characters in search terms before constructing LIKE queries. | Audit H-5; `admin_users.py` |

### 5.6 DNS Recursion

| Threat | STRIDE | Severity | Mitigation | Reference |
|--------|--------|----------|------------|-----------|
| Internal network address resolution | I | High | Configurable upstream resolver (default `1.1.1.1` via `SECURITY_DNS_RESOLVER`); CNAME chain walking with IP blocklist check at every hop (max 16 hops); 35 blocked network ranges covering RFC 1918, CGNAT, loopback, link-local, multicast, documentation | `src/backend/app/security/address_filter.py` |
| CNAME chain loops | D | Medium | Loop detection via `seen` set during chain walking; max 16 hops | `address_filter.py` |
| Operator-supplied malicious resolver | I | Medium | Admin panel allows configuring arbitrary DNS server IPs as presets; same blocklist applied regardless of which resolver is selected; resolver IP itself is validated as a valid IP address | `src/backend/app/tools/dns_lookup.py`; `address_filter.py` |
| DNS query timeout stalls | D | Low | 3s timeout per query, 5s total lifetime for the resolver context | `address_filter.py` |
| DNSSEC bypass | T | Low | DNSSEC AD flag detected and reported; no enforcement (dnspython does not validate by default). Flagged for future hardening. | `dns_lookup.py` |

### 5.7 Rate Limiting

| Threat | STRIDE | Severity | Mitigation | Reference |
|--------|--------|----------|------------|-----------|
| Resource exhaustion via tool execution | D | High | Redis-backed sliding window counters with atomic Lua scripts; dual soft/hard limits; visitors enforced by session **and** IP; authenticated users by user ID; administrators have high limits | `src/backend/app/middleware/rate_limit.py`; `src/backend/app/redis/rate_limit_store.py` |
| Rate limit store unavailable | D | Medium | Middleware handles Redis connection failures gracefully: logs warning, falls back to in-memory counters if Redis is down | `rate_limit.py` |
| Auth endpoint brute-force | D | High | Hardcoded limits: login 10/min, register 3/hour, password reset 3/day, resend verification 5/day. Keyed by IP for public endpoints, by user_id for authenticated ones. | `src/backend/app/api/v1/endpoints/auth.py` |
| Credential stuffing (cross-user attack) | D | High | **Fixed** (issue #28, ADR-005). Redis-backed IP counter with sliding TTL: 20 failed logins per IP / 15 min → 429. Checked BEFORE user lookup (enumeration-safe per ADR-002). Configurable via `BRUTEFORCE_IP_MAX_ATTEMPTS` and `BRUTEFORCE_IP_WINDOW_SECONDS`. | ADR-005; `src/backend/app/services/auth_service.py:_check_ip_bruteforce()` |
| Auth rate limits are in-memory only | D | Low | **Acknowledged limitation**. Auth rate limits reset on backend restart and are not shared across instances. The primary defence against brute-force is Argon2id + account lockout + IP-based credential-stuffing detection. | `auth.py` |
| Distributed DoS | D | Medium | No built-in CDN/WAF integration. Mitigation at infrastructure level: Caddy rate limiting, external WAF, or CDN. | — |

### 5.8 Infrastructure

| Threat | STRIDE | Severity | Mitigation | Reference |
|--------|--------|----------|------------|-----------|
| Default PostgreSQL password | I | Critical | **Fixed** (audit C-4). `docker-compose.yml` uses `${POSTGRES_PASSWORD:?fail}` — Docker Compose refuses to start if unset or empty. | Audit C-4; `docker-compose.yml` |
| Default Redis password | I | High | **Fixed** (audit H-1). Production compose uses `${REDIS_PASSWORD:?fail}` fail-fast. Dev compose defaults to a known password (acceptable for local dev). | Audit H-1; `docker-compose.yml`; `docker-compose.dev.yml` |
| Non-TLS traffic in production | I | Critical | **Fixed** (audit C-2). Caddy provides ACME auto-TLS with HTTP→HTTPS redirect; HSTS with `includeSubDomains` and `preload`; `__Host-` cookie prefix active. | Audit C-2; `config/Caddyfile` |
| Proxy header spoofing | S | High | `TrustedProxyMiddleware` replaces Uvicorn's built-in proxy handling; configurable `TRUSTED_PROXY_HOPS` (default 0 = off); rightmost-N `X-Forwarded-For` extraction | ADR-003; `src/backend/app/middleware/proxy_trust.py` |
| Container breakout via network | E | High | `sakn-internal` Docker network marked `internal: true` — no external ingress to PostgreSQL or Redis; only backend bridges both networks | `docker-compose.yml` |
| Security headers missing on non-API paths | I | Low | **Fixed** (audit M-1, issue #21). Security headers now apply to ALL responses except `/docs`, `/redoc`, `/openapi.json`. | `src/backend/app/middleware/security_headers.py` |
| Health endpoint discloses infrastructure state | I | Medium | **Fixed** (issue #25). `/health` now returns only `{"status":"ok"}` (no DB/Redis checks). Detailed checks moved to `/health/full`, protected by `X-Health-Token` header authenticated against `HEALTH_FULL_TOKEN` env var. See ADR-004. | ADR-004; `src/backend/app/main.py` |
| Silently falling back to SQLite in production | I | High | **Fixed** (audit H-8). `DATABASE_URL` assembly logic properly detects missing PostgreSQL variables and raises a clear error in production mode. | Audit H-8; `src/backend/app/config.py` |

## 6. Key Audit Findings Cross-Reference

This table maps the most relevant findings from the [2026-05-18 security audit](./audit-2026-05-18.md)
to their current status:

| Finding | Severity | Description | Status |
|---------|----------|-------------|--------|
| C-1 | Critical | Account deletion simulated in frontend only | Open (sprint 2) |
| C-2 | Critical | Caddy in HTTP only, no TLS | Fixed |
| C-3 | Critical | `NameError` in cleanup scheduler (`datetime` not imported) | Fixed |
| C-4 | Critical | Default PostgreSQL password `sakn` | Fixed |
| H-1 | High | Redis without authentication | Fixed |
| H-2 | High | WebSocket fail-open on DB error | Fixed |
| H-3 | High | WebSocket no CSWSH/Origin validation | Fixed |
| H-5 | High | SQL LIKE wildcard escaping in admin search | Fixed |
| H-6 | High | Frontend nginx no security headers | Fixed |
| H-7 | High | Default SECRET_KEY in docker-compose.dev.yml | Fixed |
| H-8 | High | Silent SQLite fallback in production | Fixed |
| M-1 | Medium | Security headers scoped to /api/* only | Fixed (issue #21) |
| M-3 | Medium | Session token SHA-256 without HMAC pepper | Known, documented |
| M-4 | Medium | Available tools endpoint accepts arbitrary roles | Fixed |

## 7. Assumptions and Residual Risks

1. **Docker network isolation** is the primary defence against container breakout.
   If an attacker gains code execution inside the backend container, they can
   access PostgreSQL and Redis directly (they share the `sakn-internal` network).

2. **Proxy header trust** relies on `TRUSTED_PROXY_HOPS` being correctly
   configured for the deployment topology. If set too high, an attacker positioned
   before the trusted proxy chain could spoof client IPs. See
   [ADR-003](../adr/003-proxy-trust-policy.md).

3. **Session token hashing** uses raw SHA-256 without an HMAC pepper (audit
   finding M-3). A simultaneous compromise of both PostgreSQL and Redis would
   expose token hashes. The 256-bit entropy makes brute-force infeasible with
   current compute, but HMAC peppering would add defence-in-depth.

4. **Auth rate limits** are process-local (in-memory). On backend restart or
   multi-instance deployment, rate limit state is lost. The primary brute-force
   defence is Argon2id + account lockout.

5. **Admin rate limiting** is intentionally bypassed. A compromised admin session
   can issue unlimited requests. Compensating controls: admin actions are
   audit-logged, and the last-admin protection prevents total lockout.

6. **Self-healing RBAC** is fail-open: missing `RoleToolPermission` rows are
   auto-created with `allowed=True`. This only affects role-tool combinations
   not seeded at startup (i.e., newly added roles or tools).

## 8. References

- [Security Audit (2026-05-18)](./audit-2026-05-18.md)
- [Secrets Management](./secrets-management.md)
- [Incident Response Runbook](./incident-response.md)
- [ADR-002: Enumeration Protection](../adr/002-enumeration-protection.md)
- [ADR-003: Proxy Trust Policy](../adr/003-proxy-trust-policy.md)
- [Functional Specification](../specs/functional-spec.md)
- [Technical Spec Index](../specs/technical/spec-index.md)

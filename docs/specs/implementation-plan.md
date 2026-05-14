# Implementation Plan — SAKN MVP

> **Version:** 2.0 — Vertical slices
> **Status:** Draft
> **Date:** 2026-05-14

---

## 1. Strategy

**Vertical slices over horizontal layers.** Each slice delivers a complete, visible, testable increment of the product. No slice depends on "all backend being done" or "all frontend being done."

### 1.1 Agents

| Agent | Role |
|---|---|
| `backend-dev` | Python/FastAPI, API endpoints, services, models, tools, security, Docker |
| `frontend-dev` | React, components, pages, state, i18n, theming |
| `qa` | Tests (unit, integration, E2E), acceptance verification |
| `security` | Security review, audit, penetration testing |
| `lead` | Architecture decisions, PR review, cross-agent coordination |

### 1.2 Document Map for Agents

| Agent | Always load | + per context |
|---|---|---|
| `backend-dev` | `spec-common.md` + `spec-backend.md` + `spec-api-contract.md` | `spec-tools-live.md` or `spec-tools-instant.md` depending on tool |
| `frontend-dev` | `spec-common.md` + `spec-frontend.md` + `spec-api-contract.md` + `ui-spec.md` | `spec-tools-live.md` or `spec-tools-instant.md` for tool pages |
| `qa` | `functional-spec.md` + `ui-spec.md` + `spec-api-contract.md` | tool specs for tool-specific tests |
| `security` | `spec-common.md` + `spec-backend.md` §5-6 | — |
| `lead` | `spec-index.md` + `functional-spec.md` | anything under review |

### 1.3 Slices Overview

```
Slice 1: Hello World    Ping bout en bout
Slice 2: Identity       Auth + sessions
Slice 3: Traceroute     Deuxième outil continu
Slice 4: DNS + TLS      Outils instantanés
Slice 5: Platform       Admin, rate limiting, security filter, logging
Slice 6: Polish         i18n, theming, responsive, RTL, tests, Docker prod
```

---

## 2. Slice 1 — Hello World (Ping bout en bout)

**Goal** : l'application tourne dans Docker, un visiteur peut exécuter un ping et voir les résultats en temps réel via WebSocket.

### 2.1 Backend Scaffolding

| Agent | `backend-dev` |
|---|---|
| **Documents** | `spec-common.md` §2-4, `spec-backend.md` §1-2, `spec-backend.md` §8 |
| **Depends on** | Nothing |

**Tasks** :
- `pyproject.toml` + `uv.lock` (FastAPI, SQLAlchemy, asyncpg, aiosqlite, alembic, pydantic, argon2-cffi, structlog, redis, dnspython, cryptography, uuid7, click)
- `app/main.py` — FastAPI app with lifespan, CORS
- `app/config.py` — Pydantic BaseSettings (all env vars)
- `app/database.py` — async SQLAlchemy engine, session DI
- `app/models/__init__.py` — declarative base
- `Dockerfile` multi-stage (build + runtime, non-root user, setcap ping)
- `docker-compose.yml` + `docker-compose.dev.yml` + `Caddyfile`
- `.env.example`

### 2.2 Data Layer (Minimal)

| Agent | `backend-dev` |
|---|---|
| **Documents** | `spec-backend.md` §4, `spec-common.md` §3 |
| **Depends on** | 2.1 |

**Tasks** :
- Models: User, Session, ToolModule, RoleToolPermission, RateLimitConfig, ToolExecutionLog
- Initial Alembic migration
- Redis connection pool + session store

### 2.3 WebSocket + Subprocess Executor

| Agent | `backend-dev` |
|---|---|
| **Documents** | `spec-tools-live.md` §1, §2, §4 |
| **Depends on** | 2.2 |

**Tasks** :
- `app/tools/base.py` — BaseTool, ToolDefinition, ExecutionContext, ToolResult
- `app/tools/registry.py` — ToolRegistry
- `app/tools/network/executor.py` — sandboxed subprocess runner (no shell, list args, `asyncio.wait_for`)
- `app/websocket/manager.py` — WebSocket connection manager
- `app/websocket/handlers/ping_ws.py` — Ping WebSocket handler (parse output → structured messages)
- `app/tools/ping.py` — PingTool

### 2.4 Ping API Endpoint

| Agent | `backend-dev` |
|---|---|
| **Documents** | `spec-api-contract.md` §1, §6; `spec-backend.md` §3.3 |
| **Depends on** | 2.3 |

**Tasks** :
- `app/api/v1/router.py` — aggregates v1 routers
- `app/api/v1/endpoints/tools.py` — GET /tools, POST /tools/{tool_name}/execute, WS /tools/{tool_name}/stream
- Session middleware (basic: read cookie, allow anonymous for now)
- Wire into `main.py`

### 2.5 Frontend Scaffolding

| Agent | `frontend-dev` |
|---|---|
| **Documents** | `spec-frontend.md` §1-2, `spec-common.md` §2.4 |
| **Depends on** | Nothing (parallel with backend) |

**Tasks** :
- Vite 6 + React 19 + TypeScript project
- Tailwind CSS 4 (`darkMode: 'class'`, logical properties)
- `App.tsx`, `Providers.tsx`, `Router.tsx`
- Layout shell: top bar + sidebar (tool links) + content area
- Stores: `authStore`, `themeStore`, `toolStore`
- API client (`fetch` wrapper with CSRF)

### 2.6 Ping Frontend Page

| Agent | `frontend-dev` |
|---|---|
| **Documents** | `spec-tools-live.md` §1-2, `ui-spec.md` §4, §5.1, §12.1 |
| **Depends on** | 2.5 |

**Tasks** :
- `useWebSocket.ts` — WebSocket hook (connect, send start, receive result/complete/error, cancel, cleanup)
- `PingPage.tsx` — form (target, count, timeout, packet_size, advanced: df_bit, dscp, max_duration), Start/Stop button, output panel (table/text toggle, incremental rows, summary)
- Route: `/ping`

### 2.7 Slice 1 Acceptance

| Agent | `qa` + `security` |
|---|---|
| **Documents** | `functional-spec.md` §3.1, `spec-tools-live.md` §2 |

**Verify** :
- App starts with `docker compose up`
- Visitor opens `/ping`, enters `8.8.8.8`, sees incremental results via WebSocket
- Stop button works mid-execution
- Invalid target shows inline error
- Security review: subprocess uses list args (no `shell=True`), target resolved to IP

---

## 3. Slice 2 — Identity (Auth + Sessions)

**Goal** : un utilisateur peut créer un compte, vérifier son email, se connecter, et ses préférences sont persistées.

### 3.1 Security Primitives

| Agent | `backend-dev` |
|---|---|
| **Documents** | `spec-backend.md` §5.2-5.3, `spec-common.md` §3.1 |
| **Depends on** | Slice 1 data layer (2.2) |

**Tasks** :
- `app/security/password.py` — argon2id hash/verify, zxcvbn strength check
- `app/security/tokens.py` — CSPRNG 256-bit token generate/hash/verify (constant-time)
- `app/security/csrf.py` — Double Submit Cookie pattern
- `app/security/address_filter.py` — BLOCKED_NETWORKS, `is_address_blocked()`, `filter_target()`

### 3.2 Auth Service

| Agent | `backend-dev` |
|---|---|
| **Documents** | `spec-backend.md` §3.2, `spec-api-contract.md` §3 |
| **Depends on** | 3.1 |

**Tasks** :
- `app/services/auth_service.py` — register (pending user, send verification), login (verify password, check lock, create session), logout (delete session), verify-email, request-password-reset, reset-password, resend-verification
- `app/services/session_service.py` — create, get, delete, list, enforce concurrent limit
- `app/services/email_service.py` — SMTP client wrapper
- `app/services/preference_service.py` — get/set preferences
- `app/email/templates/` — Jinja2 verification + reset email templates

### 3.3 Auth API Endpoints

| Agent | `backend-dev` |
|---|---|
| **Documents** | `spec-api-contract.md` §1-5, §9 |
| **Depends on** | 3.2 |

**Tasks** :
- `app/api/v1/endpoints/auth.py` — all auth endpoints (register, login, logout, verify-email, resend-verification, request-password-reset, reset-password, csrf)
- `app/api/v1/endpoints/preferences.py` — GET/PUT preferences
- `app/api/v1/endpoints/sessions.py` — GET sessions, DELETE session
- Rate limiting on auth endpoints (hardcoded limits)
- User enumeration protection (constant-time responses)
- Brute force protection (escalating `locked_until`)

### 3.4 Middleware Stack

| Agent | `backend-dev` |
|---|---|
| **Documents** | `spec-backend.md` §2, §5.4, `spec-api-contract.md` §1.5 |
| **Depends on** | 3.3 |

**Tasks** :
- `app/middleware/session.py` — resolve session from cookie, attach user to request
- `app/middleware/security_headers.py` — CSP, HSTS, X-Content-Type-Options, X-Frame-Options, Referrer-Policy
- `app/middleware/rate_limit.py` — soft/hard limit enforcement
- `app/api/errors.py` — custom exception handlers (validation error, auth error, rate limit, not found)

### 3.5 Frontend Auth Pages

| Agent | `frontend-dev` |
|---|---|
| **Documents** | `spec-api-contract.md` §3, `ui-spec.md` §10 |
| **Depends on** | Slice 1 frontend (2.5) |

**Tasks** :
- `useAuth.ts` — login, logout, current user, CSRF handling
- `LoginPage.tsx` — email + password, error display
- `RegisterPage.tsx` — email + password + confirm + password requirements checklist
- `VerifyEmailPage.tsx`, `VerifyEmailSentPage.tsx`
- `ResetPasswordPage.tsx` — request + reset form
- Auth guarding: redirect authenticated users away from auth pages, redirect visitors from protected routes

### 3.6 Frontend Account Pages

| Agent | `frontend-dev` |
|---|---|
| **Documents** | `spec-api-contract.md` §4-5, `ui-spec.md` §3 (SCR-17/18/19) |
| **Depends on** | 3.5 |

**Tasks** :
- `ProfilePage.tsx` — language, locale, theme preferences
- `SessionsPage.tsx` — list + revoke
- `AccountDeletePage.tsx` — password confirmation + delete
- User menu in top bar (profile, sessions, logout)

### 3.7 Slice 2 Acceptance

| Agent | `qa` + `security` |
|---|---|
| **Documents** | `functional-spec.md` §4, `spec-api-contract.md` §3 |

**Verify** :
- Register → verify email → login → see preferences → logout → login again
- Brute force: 5 failed logins locks account temporarily
- Duplicate email: "verification link sent" (enumeration protection)
- CSRF: state-changing requests without header rejected
- Session: httpOnly cookie, SameSite=Lax, sliding expiration
- All auth error messages are constant-time and non-revealing

---

## 4. Slice 3 — Traceroute

**Goal** : deuxième outil continu opérationnel, pattern identique à Ping.

### 4.1 Traceroute Backend

| Agent | `backend-dev` |
|---|---|
| **Documents** | `spec-tools-live.md` §3-4 |
| **Depends on** | Slice 1 backend (2.3) |

**Tasks** :
- `app/websocket/handlers/traceroute_ws.py` — parse traceroute output → structured hop messages
- `app/tools/traceroute.py` — TracerouteTool (UDP/ICMP/TCP modes, probes per hop, max distance)

### 4.2 Traceroute Frontend

| Agent | `frontend-dev` |
|---|---|
| **Documents** | `spec-tools-live.md` §3, `ui-spec.md` §5.2 |
| **Depends on** | Slice 1 frontend (2.6) |

**Tasks** :
- `TraceroutePage.tsx` — form (target, protocol, port, probes_per_hop, timeout, max_distance, dns_resolution), output panel (hop table/text, incremental rows, multipath display, destination highlight)
- Route: `/traceroute`

### 4.3 Slice 3 Acceptance

| Agent | `qa` + `security` |
|---|---|
| **Documents** | `functional-spec.md` §3.2 |

**Verify** :
- UDP, ICMP, TCP modes each produce correct output
- DNS resolution ON shows hostnames, OFF shows raw IPs
- Stop button works mid-trace
- Command injection prevention: target passed as IP, no `shell=True`
- Multipath routing displayed correctly

---

## 5. Slice 4 — DNS Lookup + TLS/SSL Viewer

**Goal** : les 4 outils sont opérationnels.

### 5.1 DNS Lookup Backend

| Agent | `backend-dev` |
|---|---|
| **Documents** | `spec-tools-instant.md` §2, `spec-backend.md` §9 |
| **Depends on** | Slice 2 auth (3.2) — needs permission check |

**Tasks** :
- `app/tools/dns_lookup.py` — DnsLookupTool (dnspython, multi-record-type, recursive CNAME, custom DNS server)
- Register in `main.py`

### 5.2 DNS Lookup Frontend

| Agent | `frontend-dev` |
|---|---|
| **Documents** | `spec-tools-instant.md` §1-2, `ui-spec.md` §5.3 |
| **Depends on** | Slice 1 frontend (2.6) |

**Tasks** :
- `DnsLookupPage.tsx` — form (domain, record type checkboxes, DNS server dropdown + custom, CNAME toggle), output panel (grouped record cards, CNAME chain)
- `useToolExecution.ts` — mutation hook for instant tools (POST → render result)
- Route: `/dns`

### 5.3 TLS/SSL Viewer Backend

| Agent | `backend-dev` |
|---|---|
| **Documents** | `spec-tools-instant.md` §3 |
| **Depends on** | 5.1 (same pattern) |

**Tasks** :
- `app/tools/ssl_viewer.py` — SslViewerTool (ssl + socket + cryptography, full chain, validation, warning for < TLS 1.2, "revocation not checked" notice)
- Register in `main.py`

### 5.4 TLS/SSL Viewer Frontend

| Agent | `frontend-dev` |
|---|---|
| **Documents** | `spec-tools-instant.md` §3, `ui-spec.md` §5.4 |
| **Depends on** | 5.2 (same pattern) |

**Tasks** :
- `SslViewerPage.tsx` — form (URL, SNI), output panel (certificate chain cards, collapsible details, validation errors in red, "revocation not checked" notice)
- Route: `/ssl`

### 5.5 Slice 4 Acceptance

| Agent | `qa` + `security` |
|---|---|
| **Documents** | `functional-spec.md` §3.3-3.4 |

**Verify** :
- DNS: A, MX, CNAME chain, NXDOMAIN, custom DNS server, IDN (Punycode)
- TLS: valid cert (e.g., google.com), expired (expired.badssl.com), self-signed, wrong host
- TLS < 1.2 shows warning, "revocation not checked" always visible
- CNAME bypass: each hop in chain filtered

---

## 6. Slice 5 — Platform (Admin, Rate Limiting, Security Filter, Logging)

**Goal** : la plateforme est administrable, protégée, et auditable.

### 6.1 Rate Limiting Implementation

| Agent | `backend-dev` |
|---|---|
| **Documents** | `spec-backend.md` §6, `spec-api-contract.md` §9 (RATE_LIMIT_EXCEEDED) |
| **Depends on** | Slice 2 middleware (3.4) |

**Tasks** :
- `app/redis/rate_limit_store.py` — Redis sorted sets + Lua script, database fallback
- `app/services/rate_limit_service.py` — `check()` + `increment()`, effective limit computation
- Wire rate limit middleware to check on tool execution requests
- Rate limit response headers (Retry-After, X-RateLimit-*)
- Auth endpoint rate limits

### 6.2 Security Filter

| Agent | `backend-dev` |
|---|---|
| **Documents** | `spec-backend.md` §5.1 |
| **Depends on** | Slice 2 security primitives (3.1) |

**Tasks** :
- Wire `address_filter.py` into all tool execution paths (Ping, Traceroute, DNS) — filter before subprocess
- DNS rebinding protection: resolve once, pass IP, re-check if re-resolution occurs
- CNAME chain filtering for DNS Lookup
- Log security refusals to SecurityEventLog

### 6.3 Logging Infrastructure

| Agent | `backend-dev` |
|---|---|
| **Documents** | `spec-backend.md` §7 |
| **Depends on** | 6.2 (needs security event log model) |

**Tasks** :
- `app/logs/logger.py` — structlog JSON to stdout, request ID propagation
- `app/services/log_service.py` — log creation + querying
- Models: SecurityEventLog, AuditLog (already in data layer)
- Log cleanup scheduled task (apscheduler)

### 6.4 Admin Backend

| Agent | `backend-dev` |
|---|---|
| **Documents** | `spec-backend.md` §3.3, `spec-api-contract.md` §7 |
| **Depends on** | 6.1, 6.2, 6.3 |

**Tasks** :
- `app/api/v1/endpoints/admin_users.py` — CRUD, block/unblock, lock/unlock, notes, delete
- `app/api/v1/endpoints/admin_tools.py` — list, enable/disable
- `app/api/v1/endpoints/admin_rate_limits.py` — get/set rate limits (matrix)
- `app/api/v1/endpoints/admin_modules.py` — module enable/disable, DNS server presets CRUD
- `app/api/v1/endpoints/admin_logs.py` — tool execution, security events, audit log queries
- `app/api/v1/endpoints/admin_settings.py` — global settings
- `app/services/admin_service.py` — last admin protection, audit logging
- `app/api/errors.py` — admin-specific error handling

### 6.5 Admin Frontend

| Agent | `frontend-dev` |
|---|---|
| **Documents** | `spec-api-contract.md` §7, `ui-spec.md` §9, §12.2 |
| **Depends on** | Slice 2 frontend (3.6) |

**Tasks** :
- Admin layout + admin tabs component
- `AdminUsersPage.tsx` — searchable/filterable user table, user detail with actions
- `AdminAccessPage.tsx` — access rights matrix (tools × roles, toggles)
- `AdminRateLimitsPage.tsx` — rate limit matrix, click-to-edit, validation on blur
- `AdminModulesPage.tsx` — module enable/disable + DNS server presets editor
- `AdminSettingsPage.tsx` — global settings
- `AdminLogsPage.tsx` — log viewer with filters, pagination, expandable rows, auto-refresh toggle
- Admin guarding: redirect non-admins to 403

### 6.6 CLI Bootstrap Tool

| Agent | `backend-dev` |
|---|---|
| **Documents** | `spec-backend.md` §8.5, `spec-common.md` §4.1 |
| **Depends on** | 6.4 |

**Tasks** :
- `app/cli/main.py` — click/typer entry point
- `app/cli/create_admin.py` — `sakn-cli create-admin --email ... --password ...`

### 6.7 Slice 5 Acceptance

| Agent | `qa` + `security` |
|---|---|
| **Documents** | `functional-spec.md` §2, §5-6, `spec-backend.md` §6.3 |

**Verify** :
- Admin can block/unblock/lock/unlock/delete users
- Access rights matrix: toggle visitor access → visitor can/cannot use tool
- Rate limit matrix: set per-tool limit > global → rejected
- Module: disable Ping → disappears from sidebar, direct URL shows "not available"
- Log viewer: filter by date/user/tool/event, expand row
- Log retention setting takes effect
- Security filter blocks private IPs (127.0.0.1, 10.x, 192.168.x, ::1, fc00::)
- Rate limiting returns 429 with correct headers
- Last admin cannot be deleted/demoted
- First admin created via CLI, not auto-created

---

## 7. Slice 6 — Polish (i18n, Theming, Responsive, Tests, Docker Prod)

**Goal** : produit complet, prêt pour la production.

### 7.1 i18n

| Agent | `frontend-dev` + `backend-dev` |
|---|---|
| **Documents** | `spec-frontend.md` §6, `spec-api-contract.md` §10 |
| **Depends on** | Slice 5 |

**Tasks (backend)** :
- `app/i18n/en/messages.json` + `app/i18n/fr/messages.json` — backend error messages, system strings

**Tasks (frontend)** :
- `src/i18n/resources.ts` — namespace loading
- `en/` + `fr/` — common, tools, auth, admin namespaces
- All user-facing strings wrapped in `t()`
- Language switcher in top bar

### 7.2 Theme System

| Agent | `frontend-dev` |
|---|---|
| **Documents** | `spec-frontend.md` §7, `ui-spec.md` §7 |
| **Depends on** | 7.1 |

**Tasks** :
- Theme toggle in top bar (light/dark/system)
- `themeStore` with `matchMedia` listener for `system`
- CSS custom properties for all themed values
- Both palettes compile correctly

### 7.3 Responsive & Accessibility

| Agent | `frontend-dev` |
|---|---|
| **Documents** | `ui-spec.md` §6, §11 |
| **Depends on** | 7.2 |

**Tasks** :
- Responsive breakpoints (desktop/tablet/mobile)
- Collapsible sidebar, hamburger menu on mobile
- Card-style tables on mobile
- Keyboard navigation, focus management, aria-live regions
- Contrast compliance (both themes)
- RTL readiness (CSS logical properties everywhere)
- 200% zoom, reduced motion support

### 7.4 Tests

| Agent | `qa` |
|---|---|
| **Documents** | `spec-common.md` §5, `functional-spec.md`, `ui-spec.md` |
| **Depends on** | All previous slices |

**Tasks** :
- Backend unit tests (address filter, tool registry, auth service, rate limiting)
- Backend integration tests (auth API, tool execution, admin API)
- Frontend component tests (auth forms, tool pages, admin pages)
- E2E tests with Playwright (happy paths: visitor uses Ping, user registers and logs in, admin configures)
- Security tests (address filter bypass, rate limit enforcement, CSRF, enumeration, brute force)

### 7.5 Docker Production

| Agent | `backend-dev` |
|---|---|
| **Documents** | `spec-backend.md` §8 |
| **Depends on** | 7.4 |

**Tasks** :
- Finalize `docker-compose.yml` with proper health checks, restart policies, secrets
- Test full stack from scratch: `docker compose up` → working app
- Caddy TLS configuration validation
- Startup script: wait for DB + Redis → migrate → start

### 7.6 Slice 6 Acceptance

| Agent | `qa` + `security` + `lead` |
|---|---|
| **Documents** | All |

**Verify** :
- All UI strings in both EN and FR
- Theme toggle cycles light → dark → system without flash
- App usable at 800px, 400px, and 200% zoom
- All E2E tests pass
- Full Docker production deploy works
- Final security review: no exposed secrets, all cookies secure, CSP enforced

---

## 8. Dependency Graph

```
Slice 1: Hello World     ─────────────────────────────┐
                                                       │
Slice 2: Identity        ───────────────────────┐      │
                                                 │      │
Slice 3: Traceroute      ──────────┐            │      │
                                    │            │      │
Slice 4: DNS + TLS        ──────────┤            │      │
                                    │            │      │
Slice 5: Platform          ─────────┼────────────┼──────┤
                                    │            │      │
Slice 6: Polish            ─────────┴────────────┴──────┘
```

Slices 3 and 4 can run in parallel (both depend on Slice 2 for auth + Slice 1 for tool patterns). Slice 5 requires auth (Slice 2) and tools (Slices 1-4). Slice 6 requires everything.

Within each slice, backend and frontend tasks can run in parallel.

---

## 9. Visibility Milestones

| Slice Complete | What You Can See |
|---|---|
| 1 | `docker compose up` → browser → ping 8.8.8.8 → live results rolling in |
| 2 | Register → verify email → login → preferences → logout |
| 3 | Traceroute to google.com, watch hops appear one by one |
| 4 | DNS lookup with CNAME chain, TLS cert chain with validation |
| 5 | Admin panel: block a user, change rate limits, view logs |
| 6 | French UI, dark mode, mobile-friendly, production Docker |

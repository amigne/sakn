# Implementation Plan — SAKN MVP

> **Version:** 3.1 — Sprint 0 review: MAC OUI section realigned (frontend-heavy, 6 sprints)
> **Status:** Draft
> **Date:** 2026-05-31

---

## 1. Strategy

**Frontend-first, vertical slices.** Slice 2 builds the entire UI with mock data so it can be validated and refined before any backend code exists. Then each subsequent slice wires up a real backend, one capability at a time.

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
Slice 1: Environment    Scaffolding, Docker, tooling
Slice 2: Frontend UI    Toutes les pages avec mock data — validation UI
Slice 3: Ping Backend   Data layer, WebSocket, subprocess executor, Ping API
Slice 4: Identity       Auth (register, login, sessions, CSRF, email, preferences)
Slice 5: Traceroute     Traceroute backend + intégration frontend
Slice 6: DNS + TLS      Outils instantanés backend + intégration frontend
Slice 7: Platform       Admin, rate limiting, security filter, logging, CLI
Slice 8: Polish         i18n, theming, responsive, RTL, tests, Docker prod
```

---

## 2. Slice 1 — Environment

**Goal** : le projet est initialisé, buildable, et l'environnement Docker tourne.

### 2.1 Project Scaffolding

| Agent | `backend-dev` + `frontend-dev` |
|---|---|
| **Documents** | `spec-common.md` §2, `spec-backend.md` §1, §8, `spec-frontend.md` §1 |
| **Depends on** | Nothing |

**Tasks (backend)** :
- `src/backend/pyproject.toml` + `uv.lock` (FastAPI, SQLAlchemy, asyncpg, aiosqlite, alembic, pydantic, argon2-cffi, structlog, redis, dnspython, cryptography, uuid7, click, apscheduler)
- `src/backend/.python-version` (3.14)
- `src/backend/app/main.py` — FastAPI app with lifespan, CORS, health endpoint
- `src/backend/app/config.py` — Pydantic BaseSettings (all env vars from `spec-common.md` §4)
- `src/backend/app/database.py` — async SQLAlchemy engine, session DI
- `src/backend/app/models/__init__.py` — declarative base
- All empty `__init__.py` for package directories under `app/`
- `src/backend/Dockerfile` — multi-stage, uv sync, non-root uid=1000, setcap ping/traceroute, healthcheck
- `.env.example`

**Tasks (frontend)** :
- `src/frontend/package.json` (React 19, Vite 6, React Router 7, Zustand 5, TanStack Query 5, Tailwind CSS 4, Radix UI, react-i18next, React Hook Form, Zod)
- `src/frontend/vite.config.ts` — path aliases, dev proxy → backend:8000
- `src/frontend/tailwind.config.ts` — `darkMode: 'class'`, CSS logical properties
- `src/frontend/tsconfig.json` — strict
- `src/frontend/index.html`
- `src/frontend/src/App.tsx`, `Providers.tsx`, `Router.tsx`
- Empty directory structure: `pages/`, `components/`, `hooks/`, `services/`, `stores/`, `i18n/`, `types/`
- `src/frontend/Dockerfile` — Nginx serving built assets
- `src/frontend/nginx.conf`

**Tasks (shared)** :
- `docker-compose.yml` — 5 services (caddy, frontend, backend, postgres, redis)
- `docker-compose.dev.yml` — dev override (SQLite, Vite dev server)
- `Caddyfile` — reverse proxy with Let's Encrypt, security headers
- `src/frontend/src/services/api.ts` — fetch wrapper (base URL `/api/v1`)

### 2.2 Slice 1 Acceptance

| Agent | `qa` + `lead` |
|---|---|
| **Documents** | `spec-common.md` §4 |

**Verify** :
- `docker compose up` → backend health check OK, frontend serves
- `curl http://localhost:8000/health` → 200
- Frontend dev server starts (`npm run dev`)
- `uv run python -c "..."` executes in venv

---

## 3. Slice 2 — Frontend UI (Mock Data)

**Goal** : toutes les pages de l'application sont construites et navigables avec des données mockées. Le backend n'intervient pas — tout est simulé via des handlers MSW ou des hooks mockés. L'UI est validable et peaufinable sans dépendre du backend.

### 3.1 UI Component Library

| Agent | `frontend-dev` |
|---|---|
| **Documents** | `spec-frontend.md` §1, `ui-spec.md` §1-4 |
| **Depends on** | Slice 1 (3.1) |

**Tasks** :
- Atomic components: Button (primary/secondary/danger/ghost, loading, disabled), TextInput (focus, error, disabled, with icon), Select/Dropdown, ToggleSwitch, Checkbox, RadioButton, Badge/Tag, Tooltip, Modal/Dialog, ProgressBar, Spinner, Table (sortable, paginated), Pagination, Accordion, Tabs, Alert/Banner (success/warning/error/info, dismissible)
- Layout components: TopBar (logo, lang switcher placeholder, theme toggle placeholder, user menu placeholder), Sidebar (tool links, admin entry for admin role), PageLayout (top bar + sidebar + content + footer)

### 3.2 Tool Pages (All 4)

| Agent | `frontend-dev` |
|---|---|
| **Documents** | `spec-tools-live.md` §2-3, `spec-tools-instant.md` §2-3, `ui-spec.md` §4-5, §12.1 |
| **Depends on** | 3.1 |

**Tasks** :
- `ToolForm` component — parameter fields, validation, Start/Stop button, Reset, Advanced collapsible
- `ToolOutput` component — empty/loading/results/error states, table/text toggle, copy button
- `useMockToolExecution.ts` — simulates instant tool execution (200ms delay, returns fake data)
- `useMockWebSocket.ts` — simulates WebSocket streaming (emits incremental results with timers, supports cancel)
- `PingPage.tsx` — form (target, count, timeout, packet_size, advanced: df_bit, dscp, max_duration), output (table/text toggle, incremental rows, summary)
- `TraceroutePage.tsx` — form (target, protocol, port, probes_per_hop, timeout, max_distance, dns_resolution), output (hop table/text, multipath, destination highlight)
- `DnsLookupPage.tsx` — form (domain, record type checkboxes, DNS server dropdown + custom, CNAME toggle), output (grouped record cards, CNAME chain)
- `SslViewerPage.tsx` — form (URL, SNI), output (cert chain cards, collapsible details, validation errors in red)
- Routes: `/ping`, `/traceroute`, `/dns`, `/ssl` (redirect `/` to `/ping`)
- Zustand `toolStore` — active tool, table/text toggle preference

### 3.3 Auth Pages

| Agent | `frontend-dev` |
|---|---|
| **Documents** | `spec-api-contract.md` §3, `ui-spec.md` §10 |
| **Depends on** | 3.1 |

**Tasks** :
- `LoginPage.tsx` — centered card, email + password + visibility toggle, error banner, links (forgot password, sign up)
- `RegisterPage.tsx` — centered card, email + first name + last name + password + confirm, real-time password requirements checklist, on success → verification sent
- `VerifyEmailPage.tsx` — handle token from URL, success/expired/already-verified states
- `VerifyEmailSentPage.tsx` — mail icon + message + resend button (60s cooldown)
- `ResetPasswordPage.tsx` — request form (email), reset form (new password + confirm, token from URL)
- `ResetPasswordSuccessPage.tsx` — green check + link to login
- Zustand `authStore` — mock current user (toggleable: visitor / authenticated / admin via dev tool)
- Auth guarding: redirect authenticated away from auth pages, redirect visitors from protected routes, 403 for non-admin on admin routes
- Dev toolbar: role switcher (visitor / user / admin) to test UI states

### 3.4 Account Pages

| Agent | `frontend-dev` |
|---|---|
| **Documents** | `spec-api-contract.md` §4-5, `ui-spec.md` §3 |
| **Depends on** | 3.3 |

**Tasks** :
- `ProfilePage.tsx` — language dropdown, theme radio (light/dark/system), locale dropdown
- `SessionsPage.tsx` — table with session list, revoke button, "current" badge
- `AccountDeletePage.tsx` — password confirmation, delete button, confirmation dialog
- User menu dropdown in top bar (preferences, sessions, logout)
- Routes: `/account/preferences`, `/account/sessions`, `/account/delete`

### 3.5 Admin Pages

| Agent | `frontend-dev` |
|---|---|
| **Documents** | `spec-api-contract.md` §7, `ui-spec.md` §9, §12.2 |
| **Depends on** | 3.4 |

**Tasks** :
- Admin layout — horizontal tab bar (Users | Access | Rate Limits | Modules | Settings | Logs) within content area
- `AdminUsersPage.tsx` — searchable/filterable user table (email search, status/role dropdowns), paginated
- `AdminUserDetailPage.tsx` — info card (email, status badge, role, dates, failed attempts, lock status), action buttons (block/unblock, lock/unlock, delete), internal notes
- `AdminAccessPage.tsx` — access matrix (tools × roles, toggle switches)
- `AdminRateLimitsPage.tsx` — rate limit matrix (limit types × roles), click-to-edit, validation on blur
- `AdminModulesPage.tsx` — module table (enabled toggle, roles link, settings gear), DNS server presets editor (IP + description, add/edit/delete/reorder)
- `AdminSettingsPage.tsx` — global settings (log retention days)
- `AdminLogsPage.tsx` — log viewer (filters: date range, user, tool, event type; paginated table; expandable rows; auto-refresh toggle)
- Routes: all `/admin/*` routes
- Admin guarding: redirect non-admins to 403, hide Admin sidebar entry for non-admins

### 3.6 Slice 2 Acceptance

| Agent | `qa` + `lead` + `frontend-dev` |
|---|---|
| **Documents** | `ui-spec.md` (entire), `functional-spec.md` §3-4 |

**Verify (manual walkthrough)** :
- Navigate all 4 tool pages → forms render, fake results appear, table/text toggle works, stop button works
- Register flow → login flow → preferences → sessions → logout
- Password reset request + reset form
- Dev role switcher → admin sees admin sidebar + admin pages render with mock data
- Admin: user table, access matrix toggles, rate limit editing, module toggles, log viewer
- Responsive: resize to tablet/mobile widths, sidebar collapses, forms stack
- All page states: empty, loading, success, error, disabled

---

## 4. Slice 3 — Ping Backend

**Goal** : le backend Ping est réel. Le frontend Ping est branché dessus et abandonne ses mocks. Les autres pages restent mockées.

### 4.1 Data Layer

| Agent | `backend-dev` |
|---|---|
| **Documents** | `spec-backend.md` §4, `spec-common.md` §3 |
| **Depends on** | Slice 1 |

**Tasks** :
- All SQLAlchemy models: User, Session, ToolModule, RoleToolPermission, RateLimitConfig, ToolExecutionLog, SecurityEventLog, AuditLog, UserPreference, EmailVerification, PasswordReset, DnsServerPreset, GlobalSetting
- Initial Alembic migration
- Redis connection pool + session store (skeleton: create/get/delete/list)
- `src/backend/tests/conftest.py` (test DB SQLite fixtures)
- `src/backend/tests/factories.py` (model factories)
- Unit tests for models (creation, constraints)

### 4.2 WebSocket + Subprocess Executor

| Agent | `backend-dev` |
|---|---|
| **Documents** | `spec-tools-live.md` §1, §2, §4, `spec-backend.md` §9 |
| **Depends on** | 4.1 |

**Tasks** :
- `app/tools/base.py` — BaseTool, ToolDefinition, ExecutionContext, ToolResult, ToolCategory, ToolParameter
- `app/tools/registry.py` — ToolRegistry (explicit registration in lifespan)
- `app/tools/network/executor.py` — sandboxed subprocess runner: Popen list args (no shell=True), asyncio.wait_for timeout, process group, SIGTERM→SIGKILL, stderr logged not exposed
- `app/websocket/manager.py` — WebSocket connection manager (connect, disconnect, broadcast, heartbeat, idle cleanup)
- `app/websocket/handlers/ping_ws.py` — parse ping output → structured messages (start/result/notice/complete/error)
- `app/tools/ping.py` — PingTool
- `app/security/address_filter.py` — BLOCKED_NETWORKS, `is_address_blocked()`, `filter_target()` via hardcoded external DNS resolver
- Unit tests: mock subprocess, verify parsing, verify filter blocks private IPs

### 4.3 Ping API Endpoint

| Agent | `backend-dev` |
|---|---|
| **Documents** | `spec-api-contract.md` §1, §6, `spec-backend.md` §3.3 |
| **Depends on** | 4.2 |

**Tasks** :
- `app/api/v1/router.py` — aggregates v1 routers
- `app/api/v1/endpoints/tools.py` — GET /tools, POST /tools/{tool_name}/execute (skeleton for instant tools), WS /tools/{tool_name}/stream
- `app/middleware/session.py` — read cookie, anonymous session for now
- `app/api/errors.py` — custom exception handlers
- GET /health with DB + Redis status
- Wire address filter into tool execution path
- Register PingTool in main.py lifespan
- Integration tests: HTTP GET /tools, WebSocket ping to valid target, WebSocket rejected for blocked target

### 4.4 Wire Frontend Ping

| Agent | `frontend-dev` |
|---|---|
| **Documents** | `spec-tools-live.md` §1-2, `spec-api-contract.md` §1 |
| **Depends on** | 4.3 |

**Tasks** :
- `useWebSocket.ts` — real WebSocket hook (connect with session cookie, send start/cancel, receive result/complete/error/notice, cleanup on disconnect)
- `useToolExecution.ts` — mutation hook for instant tools (POST, render result/error)
- Switch PingPage.tsx from mock to real hooks
- Remove mock Ping data

### 4.5 Slice 3 Acceptance

| Agent | `qa` + `security` |
|---|---|
| **Documents** | `functional-spec.md` §3.1, `spec-tools-live.md` §2, §4 |

**Verify** :
- `docker compose up` → Ping 8.8.8.8 → incremental results via WebSocket
- Stop button works mid-execution, partial results retained
- Ping 127.0.0.1 → "Target not allowed"
- Invalid target → validation error
- No `shell=True` in subprocess code, target passed as IP only
- `pytest src/backend/tests/` passes

---

## 5. Slice 4 — Identity (Auth Backend)

**Goal** : le système d'authentification est réel. Les pages auth du frontend sont branchées.

### 5.1 Security Primitives

| Agent | `backend-dev` |
|---|---|
| **Documents** | `spec-backend.md` §5.2-5.3, `spec-common.md` §3.1 |
| **Depends on** | Slice 3 data layer (4.1) |

**Tasks** :
- `app/security/password.py` — argon2id hash/verify, zxcvbn strength check (8-128 chars, upper+lower+digit, entropy ≥30 bits)
- `app/security/tokens.py` — CSPRNG 256-bit: `secrets.token_urlsafe(32)`, SHA-256 hash, constant-time verify (`secrets.compare_digest`)
- `app/security/csrf.py` — Double Submit Cookie pattern: `sakn_csrf` cookie (NOT httpOnly, SameSite=Lax), `X-CSRF-Token` header validation

### 5.2 Auth Service

| Agent | `backend-dev` |
|---|---|
| **Documents** | `spec-backend.md` §3.2, `spec-api-contract.md` §3 |
| **Depends on** | 5.1 |

**Tasks** :
- `app/redis/session_store.py` — full Redis session store (create with TTL, get, delete, list user sessions, enforce concurrent limit, update activity/sliding expiration)
- `app/services/email_service.py` — SMTP client wrapper
- `app/services/auth_service.py`:
  - `register_user` — create pending user, send verification email
  - `verify_email` — validate token, mark verified
  - `login` — verify password, check lock/block, create session, set cookies
  - `logout` — delete session, clear cookies
  - `request_password_reset` — send reset email (enumeration-safe)
  - `reset_password` — validate token, set new password, terminate other sessions
  - `resend_verification` — cooldown + rate limit enforcement
- `app/services/session_service.py` — CRUD, concurrent limit, sliding expiration
- `app/services/preference_service.py` — get/set per user or per session
- `app/email/templates/` — Jinja2 verification + reset email templates

### 5.3 Auth API Endpoints

| Agent | `backend-dev` |
|---|---|
| **Documents** | `spec-api-contract.md` §1-5, §9 |
| **Depends on** | 5.2 |

**Tasks** :
- `app/api/v1/endpoints/auth.py` — POST register, POST login, POST logout, POST verify-email, POST resend-verification, POST request-password-reset, POST reset-password, GET csrf
- `app/api/v1/endpoints/preferences.py` — GET/PUT preferences
- `app/api/v1/endpoints/sessions.py` — GET sessions, DELETE session/{id}
- `app/middleware/security_headers.py` — CSP, HSTS, X-Content-Type-Options, X-Frame-Options, Referrer-Policy
- Auth-specific rate limiting (hardcoded: login 10/IP/60s, register 3/IP/3600s, reset 3/email/86400s, resend 5/user/86400s)
- Brute force protection: escalating `locked_until` (5→5min, 10→15min, 15→45min, 20+→90min)
- User enumeration protection: constant-time responses, identical messages
- Integration tests: register→verify→login→preferences→sessions→logout

### 5.4 Wire Frontend Auth

| Agent | `frontend-dev` |
|---|---|
| **Documents** | `spec-api-contract.md` §3-5 |
| **Depends on** | 5.3 |

**Tasks** :
- `useAuth.ts` — real auth hook (login, logout, register, verify, reset, current user)
- `services/authService.ts` — auth API calls
- `services/preferencesService.ts` — preferences API calls
- CSRF handling in api.ts (read `sakn_csrf` cookie, send `X-CSRF-Token` header, retry on 403)
- Session middleware integration (redirect on 401, refresh user state)
- Switch all auth pages from mock to real API calls
- Remove dev role switcher toolbar

### 5.5 Slice 4 Acceptance

| Agent | `qa` + `security` |
|---|---|
| **Documents** | `functional-spec.md` §4, `spec-api-contract.md` §3 |

**Verify** :
- Register → verify email → login → preferences → sessions → logout → login again
- 5 failed logins → temporary lock, 10 → 15min lock, counter resets on success
- Duplicate email → "verification link sent" (enumeration protection)
- CSRF: POST without header → 403; with header → 200
- Session: httpOnly cookie, SameSite=Lax, sliding expiration
- All auth error messages constant-time and non-revealing

---

## 6. Slice 5 — Traceroute Backend

**Goal** : Traceroute backend réel, frontend branché.

### 6.1 Traceroute Backend

| Agent | `backend-dev` |
|---|---|
| **Documents** | `spec-tools-live.md` §3-4 |
| **Depends on** | Slice 3 executor + registry (4.2) |

**Tasks** :
- `app/websocket/handlers/traceroute_ws.py` — parse traceroute output → structured hop messages (standard, timeout, multipath, destination reached)
- `app/tools/traceroute.py` — TracerouteTool (UDP/ICMP/TCP modes)
- Register in main.py
- Unit tests: mock subprocess, verify parsing per protocol mode

### 6.2 Wire Frontend Traceroute

| Agent | `frontend-dev` |
|---|---|
| **Documents** | `spec-tools-live.md` §3 |
| **Depends on** | 6.1 |

**Tasks** :
- Switch TraceroutePage.tsx from mock to real WebSocket hook
- Remove mock Traceroute data

### 6.3 Slice 5 Acceptance

| Agent | `qa` + `security` |
|---|---|
| **Documents** | `functional-spec.md` §3.2 |

**Verify** :
- UDP/ICMP/TCP modes produce correct output
- DNS resolution ON/OFF works
- Multipath routing displayed correctly
- Command injection: target passed as IP, no shell=True

---

## 7. Slice 6 — DNS Lookup + TLS/SSL Backend

**Goal** : outils instantanés réels, frontend branché.

### 7.1 DNS Lookup Backend

| Agent | `backend-dev` |
|---|---|
| **Documents** | `spec-tools-instant.md` §2 |
| **Depends on** | Slice 3 (4.2) |

**Tasks** :
- `app/tools/dns_lookup.py` — DnsLookupTool (dnspython, multi-record-type, recursive CNAME with chain filtering, custom DNS server)
- Register in main.py
- Unit tests: mock dnspython, verify CNAME chain, verify blocked address in chain

### 7.2 TLS/SSL Viewer Backend

| Agent | `backend-dev` |
|---|---|
| **Documents** | `spec-tools-instant.md` §3 |
| **Depends on** | 7.1 (same pattern) |

**Tasks** :
- `app/tools/ssl_viewer.py` — SslViewerTool (ssl + socket + cryptography, full chain, validation, warning for < TLS 1.2, "revocation not checked" notice)
- Register in main.py

### 7.3 Wire Frontend DNS + TLS

| Agent | `frontend-dev` |
|---|---|
| **Documents** | `spec-tools-instant.md` §1-3 |
| **Depends on** | 7.1, 7.2 |

**Tasks** :
- Switch DnsLookupPage.tsx and SslViewerPage.tsx from mock to `useToolExecution`
- Remove mock DNS and TLS data

### 7.4 Slice 6 Acceptance

| Agent | `qa` + `security` |
|---|---|
| **Documents** | `functional-spec.md` §3.3-3.4 |

**Verify** :
- DNS: A, MX, CNAME chain, NXDOMAIN, custom server, IDN (Punycode)
- TLS: valid cert, expired, self-signed, wrong host
- TLS < 1.2 shows warning, "revocation not checked" visible
- CNAME bypass: each hop filtered

---

## 8. Slice 7 — Platform (Admin, Rate Limiting, Security, Logging)

**Goal** : la plateforme est administrable, protégée, et auditable.

### 8.1 Rate Limiting Implementation

| Agent | `backend-dev` |
|---|---|
| **Documents** | `spec-backend.md` §6 |
| **Depends on** | Slice 3 Redis (4.1) |

**Tasks** :
- `app/redis/rate_limit_store.py` — Redis sorted sets + Lua script (ZREMRANGEBYSCORE, ZCOUNT, ZADD, EXPIRE), database fallback
- `app/services/rate_limit_service.py` — check() + increment(), effective limit = min(global, per_tool)
- `app/middleware/rate_limit.py` — ASGI middleware, rate limit response headers (Retry-After, X-RateLimit-*)
- Seed default RateLimitConfig rows
- Seed default RoleToolPermission rows
- Seed default ToolModule rows
- Seed default DnsServerPreset rows

### 8.2 Logging Infrastructure

| Agent | `backend-dev` |
|---|---|
| **Documents** | `spec-backend.md` §7 |
| **Depends on** | 8.1 |

**Tasks** :
- `app/logs/logger.py` — structlog JSON to stdout, request ID propagation via middleware
- `app/services/log_service.py` — create logs (ToolExecutionLog, SecurityEventLog, AuditLog), query with filters + pagination
- Log all tool executions, security refusals, auth events, admin actions
- Log cleanup scheduled task (apscheduler, daily)

### 8.3 Admin Backend

| Agent | `backend-dev` |
|---|---|
| **Documents** | `spec-backend.md` §3.3, `spec-api-contract.md` §7 |
| **Depends on** | 8.1, 8.2 |

**Tasks** :
- `app/api/v1/endpoints/admin_users.py` — list (paginated, filterable), get, block/unblock, lock/unlock, notes, delete
- `app/api/v1/endpoints/admin_tools.py` — list, enable/disable
- `app/api/v1/endpoints/admin_rate_limits.py` — get/set (matrix validation)
- `app/api/v1/endpoints/admin_modules.py` — enable/disable, DNS server presets CRUD + reorder
- `app/api/v1/endpoints/admin_logs.py` — tool executions, security events, audit log (filter + paginate)
- `app/api/v1/endpoints/admin_settings.py` — get/set global settings
- `app/services/admin_service.py` — last admin protection, audit logging on admin actions
- Admin middleware: verify admin role on all /admin/* routes

### 8.4 CLI Bootstrap Tool

| Agent | `backend-dev` |
|---|---|
| **Documents** | `spec-common.md` §4.1 |
| **Depends on** | 8.3 |

**Tasks** :
- `app/cli/main.py` — click/typer entry point
- `app/cli/create_admin.py` — `sakn-cli create-admin --email ... --password ...`

### 8.5 Wire Frontend Admin

| Agent | `frontend-dev` |
|---|---|
| **Documents** | `spec-api-contract.md` §7 |
| **Depends on** | 8.3 |

**Tasks** :
- `services/admin.ts` — admin API calls
- Switch all admin pages from mock to real API calls
- Admin guarding: 403 redirect for non-admins

### 8.6 Slice 7 Acceptance

| Agent | `qa` + `security` |
|---|---|
| **Documents** | `functional-spec.md` §2, §5-6, `spec-backend.md` §6.3 |

**Verify** :
- Admin can block/unblock/lock/unlock/delete users; last admin protected
- Access matrix: toggle visitor access → takes effect immediately
- Rate limit matrix: per-tool > global → rejected; 0 = no limit; changes immediate
- Module: disable Ping → sidebar hides it, direct URL shows "not available"
- DNS presets: add/edit/delete/reorder → auto-save
- Log viewer: filters work, rows expandable, auto-refresh toggleable
- Log retention setting takes effect
- Security filter blocks private/reserved/loopback IPs
- Rate limiting: 429 with correct headers at soft and hard limits
- First admin created via CLI, not auto-created

---

## 9. Slice 8 — Polish (i18n, Theming, Responsive, Tests, Docker Prod)

**Goal** : produit complet, prêt pour la production.

### 9.1 i18n

| Agent | `frontend-dev` + `backend-dev` |
|---|---|
| **Documents** | `spec-frontend.md` §6, `spec-api-contract.md` §10 |
| **Depends on** | Slice 7 |

**Tasks (backend)** :
- `app/i18n/en/messages.json` + `app/i18n/fr/messages.json` — system messages, error strings

**Tasks (frontend)** :
- `src/i18n/resources.ts` — namespace loading
- `en/` + `fr/` JSON namespaces: common, tools, auth, admin
- All user-facing strings wrapped in `t()`
- Language switcher in top bar

### 9.2 Theme System

| Agent | `frontend-dev` |
|---|---|
| **Documents** | `spec-frontend.md` §7, `ui-spec.md` §7 |
| **Depends on** | 9.1 |

**Tasks** :
- Theme toggle in top bar (light/dark/system)
- `themeStore` with `matchMedia` listener for system
- CSS custom properties for both palettes

### 9.3 Responsive & Accessibility

| Agent | `frontend-dev` |
|---|---|
| **Documents** | `ui-spec.md` §6, §11 |
| **Depends on** | 9.2 |

**Tasks** :
- Responsive breakpoints (desktop ≥1024, tablet 768-1023, mobile <768)
- Collapsible sidebar, hamburger menu on mobile
- Card-style tables on mobile
- Keyboard navigation, focus management, aria-live for WebSocket updates
- Contrast compliance both themes (4.5:1 normal, 3:1 large)
- RTL readiness: CSS logical properties everywhere
- Reduced motion support, 200% zoom

### 9.4 Tests

| Agent | `qa` |
|---|---|
| **Documents** | `spec-common.md` §5, `functional-spec.md`, `ui-spec.md` |
| **Depends on** | All previous slices |

**Tasks** :
- Backend unit tests (address filter, tool registry, auth service, rate limiting)
- Backend integration tests (auth API, tool execution, admin API)
- Frontend component tests (auth forms, tool pages, admin pages)
- E2E tests with Playwright (happy paths: visitor uses Ping, user registers+logs in, admin configures)
- Security tests (address filter bypass, rate limit enforcement, CSRF, enumeration, brute force)

### 9.5 Docker Production

| Agent | `backend-dev` |
|---|---|
| **Documents** | `spec-backend.md` §8 |
| **Depends on** | 9.4 |

**Tasks** :
- Finalize docker-compose.yml with health checks, restart policies, secrets
- Startup script: wait for DB + Redis → migrate → start
- Test full stack: `docker compose up` → working app
- Caddy TLS configuration validation

### 9.6 Slice 8 Acceptance

| Agent | `qa` + `security` + `lead` |
|---|---|
| **Documents** | All |

**Verify** :
- All UI in EN and FR, untranslated strings fall back to EN
- Theme toggle cycles light→dark→system without flash
- App usable at 800px, 400px, 200% zoom
- All E2E tests pass
- Full Docker prod deploy works
- Final security review: no exposed secrets, cookies secure, CSP enforced

---

## 10. Dependency Graph

```
Slice 1: Environment     ─────────────────────────┐
                                                   │
Slice 2: Frontend UI     ─────────────────────┐    │
                                               │    │
Slice 3: Ping Backend    ──────────┐          │    │
                                    │          │    │
Slice 4: Identity         ──────────┤          │    │
                                    │          │    │
Slice 5: Traceroute       ──────────┤          │    │
                                    │          │    │
Slice 6: DNS + TLS        ──────────┤          │    │
                                    │          │    │
Slice 7: Platform         ──────────┼──────────┼────┤
                                    │          │    │
Slice 8: Polish           ──────────┴──────────┴────┘
```

Slices 5 and 6 can run in parallel (both depend on Slice 4 for auth). Slice 2 is independent of backend slices — frontend UI is built and validated in isolation. Each backend slice (3-7) wires up one capability at a time.

---

## 11. Visibility Milestones

| Slice | What You Can See |
|---|---|
| 1 | `docker compose up` → backend health OK, frontend serves |
| 2 | Navigate all pages, tools produce fake results, auth flows work with dev role switcher, admin panel functional — **UI fully validatable** |
| 3 | Ping 8.8.8.8 → real live results via WebSocket |
| 4 | Register → verify email → login → preferences → sessions → logout |
| 5 | Traceroute to google.com, hops appear one by one |
| 6 | DNS query returns real records, TLS cert chain renders with validation |
| 7 | Admin panel controls real data: block user, change rate limits, view real logs |
| 8 | French UI, dark mode, mobile-friendly, production Docker |


---

## 12. MAC OUI Lookup (Module v0.2.0)

**Goal** : implement the MAC OUI Lookup tool — extract MAC/OUI patterns from arbitrary text in the browser, normalize, send a list to the backend, lookup vendor/manufacturer in a local database synced daily from IEEE, display results with change history.

**Architecture rappel** : extraction côté **frontend** (tolérant, ADR-014), backend reçoit une liste d'OUI/MAC normalisée et fait un lookup pur en zero-trust. Voir ADR-013 et ADR-014 pour les décisions structurantes.

**Integration branch** : `dev0.2.0-macoui`. Sprints 1-6 PR vers cette branche.

### 12.0 Sprint dependency graph

```
Sprint 1 (Models) ──► Sprint 2 (IEEE Sync)  ──┐
                  └─► Sprint 3 (Backend lookup) ──┐
                                                  ├──► Sprint 5 (Admin/Obs) ──► Sprint 6 (QA/Release)
                                Sprint 4 (Frontend) ──┘
```

Sprints 2 et 3 peuvent démarrer en parallèle après merge du Sprint 1. Sprint 4 démarre dès que le contrat API du Sprint 3 est stable. Sprint 5 fusionne admin/observabilité une fois 2-3-4 mergés. Sprint 6 valide l'ensemble.

---

### 12.1 Sprint 1 — Data Models & DB Migration

| Agent | `backend-dev` |
|---|---|
| **Documents** | `spec-backend.md` §4.2 (corrigé), ADR-013 §5.1 |
| **Depends on** | Slice 1 (existing environment) |
| **PR target** | `dev0.2.0-macoui` |

**Scope** :
- Modèle `MacOui` avec **`UNIQUE(oui, oui_type)`** (correction de spec actée ADR-013 §2.4).
- Modèle `MacOuiHistory` avec FK `ON DELETE CASCADE`.
- Migration Alembic auto-générée, revue manuelle (CHECK constraints, FK cascade, index `ix_*`).
- Pas de seed data dans la migration (le seed du tool / RBAC arrivera au Sprint 3 dans le pattern existant `main.py:126-137`).
- Tests unitaires modèles (contraintes, unicité, cascade, défauts auto).

**Files touched** :
- `src/backend/app/models/mac_oui.py` (new)
- `src/backend/app/models/mac_oui_history.py` (new)
- `src/backend/app/models/__init__.py` (exports)
- `src/backend/alembic/versions/<id>_add_mac_oui_tables.py` (new)
- `src/backend/tests/unit/database/test_mac_oui_model.py` (new)
- `src/backend/tests/unit/database/test_mac_oui_history_model.py` (new)

**Risks** :
- **Compatibilité SQLite vs PostgreSQL** : CHECK constraints sur `oui_type` et `change_type`. Vérifier le rendu Alembic sur les 2 DB.
- **Convention d'index** : suivre les noms existants (`ix_*`) en relisant une migration récente.
- **Ordre du downgrade** : `history` avant `mac_oui` (FK cascade) pour rejouer proprement.

---

### 12.2 Sprint 2 — IEEE Sync Service

| Agent | `backend-dev` |
|---|---|
| **Documents** | `spec-backend.md` §9.6 (URLs à corriger en HTTPS), ADR-013 §2 |
| **Depends on** | Sprint 1 |

**Scope** :
- Parser pur (`oui_parser.py`) qui transforme `OUI (hex) \t Org \t Address` → `ParsedOuiEntry`. Aucun I/O.
- Service de sync (`oui_sync_service.py`) :
  - Téléchargement **HTTPS** des 3 fichiers (timeout 120 s, configurable `OUI_DOWNLOAD_TIMEOUT_SECONDS`).
  - Logique upsert + comparaison champ par champ (ADR-013 §2.2).
  - Classification `change_type` à **3 valeurs** (`name_change`, `address_change`, `revoked`) — pas de `reassigned`.
  - Compteur d'échecs consécutifs **par fichier** ; CRITICAL log `ALERT_OUI_SYNC_FAILED_3X` au 3ᵉ échec.
  - Pas de DELETE, pas de purge.
- Job APScheduler quotidien à `OUI_SYNC_HOUR` UTC (défaut 03), `max_instances=1`, `coalesce=True`.
- Endpoint admin `POST /api/v1/admin/oui/sync` (déclenchement manuel). 409 si déjà en cours.
- Fixtures IEEE échantillonnées (10-20 entrées par fichier).
- Tests : parsing, idempotence, détection de changement, résilience aux pannes réseau (mocked).

**Files touched** :
- `src/backend/app/services/oui_parser.py` (new)
- `src/backend/app/services/oui_sync_service.py` (new)
- `src/backend/app/scheduler/jobs/oui_sync_job.py` (new)
- `src/backend/app/api/admin/oui_sync.py` (new)
- `src/backend/app/config.py` (ajout `OUI_SYNC_HOUR`, `OUI_SYNC_ENABLED`, `OUI_DOWNLOAD_TIMEOUT_SECONDS`)
- Liste centrale des codes d'erreur : `OUI_SYNC_ALREADY_RUNNING`
- `src/backend/tests/unit/services/test_oui_parser.py`
- `src/backend/tests/unit/services/test_oui_sync_service.py`
- `src/backend/tests/integration/test_oui_sync_endpoint.py`
- `src/backend/tests/fixtures/ieee/{oui,mam,oui36}-sample.txt`

**Risks** :
- **Changement de format IEEE** : le format `(hex)` tabulé est stable depuis 20+ ans mais non contractuel. Skip-malformed-lines limite la casse.
- **Heuristique `revoked`** : dépend du mot-clé `revoked` ou `----` dans `organization`. Si IEEE change son format, tous les `revoked` deviendront `name_change`. Monitoring Sprint 5.
- **SSRF** : URLs IEEE hardcodées, l'endpoint admin n'accepte aucun paramètre URL.

---

### 12.3 Sprint 3 — Backend Tool & API (lookup pur, zero-trust)

| Agent | `backend-dev` |
|---|---|
| **Documents** | `spec-tools-instant.md` §4 (à corriger : pas d'extraction backend), `spec-api-contract.md` §9-10, ADR-014 §2.7 |
| **Depends on** | Sprint 1 (modèles) ; Sprint 2 fortement recommandé (sinon fixture seed) |

**Scope** :
- `MacOuiLookupTool(BaseTool)` (chercher le pattern existant via DNS/SSL tools).
- **Pas d'extraction regex côté backend**. Le tool reçoit `{ "ouis": [str, ...] }` déjà normalisé par le frontend.
- Validation stricte (`re.fullmatch(r"^[0-9A-F]{6,12}$")`, longueur ∈ {6,7,9,12}).
- Sanitisation des entrées rejetées (`sample` 20 chars max, charset `[0-9a-fA-F:.\-]`, autres chars → `?`).
- Réponse **200 OK** avec `results[]` + `rejected[]` + `parse_stats` (cf. ADR-014 §2.7 + acceptance §8).
- 422 réservé au JSON malformé ou taille batch dépassée (`MAC_OUI_TOO_MANY_INPUTS`).
- Lookup en **1 seule requête SQL** (`WHERE (oui, oui_type) IN (...)`) pour éviter N+1. Règle longest-prefix appliquée côté Python.
- Détection OUI ambigu : si l'utilisateur soumet un préfixe 24-bit qui n'a pas de MA-L correspondant à un fabricant final ou qui appartient à une plage IEEE Registration Authority, retourner `ambiguous_extends_ma_m` / `ambiguous_extends_ma_s`.
- Enregistrement du tool dans `ToolModule` avec `has_settings=true` ET `has_status=true` (nouveau flag).
- Seed `RoleToolPermission` pour les 3 rôles avec `allowed=True` (pattern existant `main.py:126-137`).
- Codes d'erreur : `MAC_OUI_TOO_MANY_INPUTS` (422), pas de `MAC_OUI_PARSE_EMPTY` (la liste vide retourne 200 OK).
- Tests : validation stricte, rejection sanitisée (incluant payload XSS `<script>alert(1)</script>`), longest prefix, OUI ambigu, batch limit.

**Files touched** :
- `src/backend/app/tools/instant/mac_oui_lookup.py` (new)
- `src/backend/app/tools/instant/mac_oui_lookup_service.py` (new)
- Registre des tools (intégration)
- `src/backend/app/models/tool_module.py` (ajout `has_status: bool` si pas déjà existant)
- Migration data pour seeder le tool (idempotente)
- i18n FR + EN backend (uniquement clés strictement utilisées server-side : `errors.mac_oui_too_many_inputs`)
- `src/backend/tests/unit/tools/test_mac_oui_lookup_service.py`
- `src/backend/tests/integration/test_mac_oui_endpoint.py`

**Risks** :
- **N+1 queries** : risque si l'implémentation boucle sur chaque entrée. Test obligatoire : compter les requêtes SQL avec un event listener SQLAlchemy.
- **Sanitisation XSS** : test obligatoire avec payload contenant `<script>`. Vérifier que `sample` retourné est inoffensif.
- **`has_status` flag** : nouvelle colonne sur `ToolModule`. Doit être backward-compatible (default `False`).

---

### 12.4 Sprint 4 — Frontend Page (extraction tolérante + UX)

| Agent | `frontend-dev` |
|---|---|
| **Documents** | `ui-spec.md` SCR-26, `spec-frontend.md` §4.1 (à corriger : décrire l'extraction frontend), ADR-014 §2-3 |
| **Depends on** | Sprint 3 (API stable) |

**Scope** :
- Page `MacOuiLookupPage.tsx` avec `<textarea>` (max configurable via `MAC_OUI_FRONTEND_INPUT_MAX_CHARS`, défaut 50 000 — limite hardcodée par défaut, lue depuis settings Sprint 5).
- **Regex tolérante** côté JS (cf. ADR-014 §3) : 4 séparateurs (`:`, `-`, `.`, `""`), longueurs {6, 7, 9, 12}.
- Normalisation (strip separators, uppercase, validation, dédup) avant envoi.
- Affichage résultats :
  - Tableau avec OUI display (MA-M/MA-S avec `_` underscore stylé en gris, tooltip).
  - Légende sous tableau pour MA-M/MA-S.
  - Ligne en **orange** pour OUI ambigu (`ambiguous_extends_ma_m` ou `_ma_s`), tooltip d'invitation.
  - Historique dépliable par OUI (lazy load infinite scroll, taille de page = `MAC_OUI_HISTORY_PAGE_SIZE`).
  - En-tête historique : « Historique collecté depuis [date de mise en service du module] ».
  - Bandeau `rejected[]` au-dessus du tableau (avec samples sanitisés affichés via React escape).
  - Copy clipboard global + par ligne.
- États gérés : idle / typing / submitting / success / empty / error.
- Composants UI **strictement existants** : `Modal`, `ToggleSwitch`, `TextInput`, `Button`, `Spinner` (cf. `src/frontend/src/components/ui/`).
- Sidebar : entrée MAC OUI ajoutée (insérer entre TLS et WHOIS si présent, sinon en fin).
- i18n FR + EN (toutes les clés `tools.mac_oui.*`, `errors.mac_oui_too_many_inputs`).
- Accessibilité : `aria-label`, focus management, navigation clavier, contraste.
- Tests Vitest : extraction (25+ chaînes annexe A ADR-014), normalisation, dédup, états page.
- Test Playwright golden path : login → page → coller ARP table → résultats.

**Files touched** :
- `src/frontend/src/pages/tools/MacOuiLookupPage.tsx` (new)
- `src/frontend/src/pages/tools/components/MacOuiResultsTable.tsx` (new)
- `src/frontend/src/pages/tools/components/MacOuiHistoryDetails.tsx` (new)
- `src/frontend/src/pages/tools/components/MacOuiParseStats.tsx` (new)
- `src/frontend/src/pages/tools/components/MacOuiRejectedBanner.tsx` (new)
- `src/frontend/src/lib/macOuiExtractor.ts` (regex + normalisation + dédup)
- `src/frontend/src/api/tools/macOui.ts` (client typé)
- `src/frontend/src/i18n/locales/{en,fr}/tools/mac_oui.json` (new)
- `src/frontend/src/Router.tsx` (ajouter route `/mac-oui`)
- `src/frontend/src/components/layout/Sidebar.tsx` (entrée)
- Tests : `MacOuiLookupPage.test.tsx`, `MacOuiResultsTable.test.tsx`, `macOuiExtractor.test.ts`, `tests/e2e/mac-oui-lookup.spec.ts`

**Risks** :
- **ReDoS frontend** : test obligatoire avec payload pathologique (50 000 chars). Quantifiers fixes uniquement (cf. ADR-014 §5.3).
- **Performance rendu** : 500+ OUI uniques peuvent ralentir React. Prévoir virtualisation si nécessaire (chercher si TanStack Virtual déjà utilisé ailleurs dans le projet).
- **Faux positifs timestamps** : `12:34:56` matche OUI 3 octets. Politique acceptée (cf. ADR-014 §2.2 et acceptance AC-MAC-OUI-019). À surveiller en testing utilisateur.
- **Limite textarea** : 50 000 chars défaut hardcodé. La lecture depuis settings Sprint 5 arrive après. Documenter la dépendance.

---

### 12.5 Sprint 5 — Admin, Observabilité & Robustesse

| Agent | `backend-dev` + `frontend-dev` |
|---|---|
| **Documents** | acceptance §14 (administration) |
| **Depends on** | Sprints 2, 3, 4 |

**Scope backend** :
- Modèle `OuiSyncLog` (table persistante : timestamps, status, counts, files_failed JSON, error_message). Migration.
- Endpoint **générique** `GET /api/v1/admin/modules/{tool_name}/status` retournant `{status, last_run, history[]}`. `null` si le module n'a pas de statut.
- Métriques (utiliser le système existant ; si aucun → logs structurés et le noter dans `Known limitations`).
- Paramétrage via `ToolModuleSetting` (ou mécanisme équivalent existant) :
  - `MAC_OUI_FRONTEND_INPUT_MAX_CHARS` (1 000 – 200 000, défaut 50 000)
  - `MAC_OUI_BACKEND_BATCH_MAX_SIZE` (100 – 10 000, défaut 2 000)
  - `MAC_OUI_HISTORY_PAGE_SIZE` (5 – 50, défaut 10)
  - `OUI_SYNC_HOUR` (0 – 23, défaut 3)
- Endpoint paginé pour l'historique : `GET /api/v1/tools/mac_oui/history?oui=...&oui_type=...&offset=...&limit=...`
- Test ReDoS, test performance, test de payload pathologique (50k chars frontend → liste 2 000 entrées backend).

**Scope frontend** :
- Tableau Admin > Modules : **nouvelle colonne « Statut »** entre les permissions et « Paramètres ».
  - Cellule : icône colorée pour modules avec `has_status=true`, **vide sinon** (pas de tiret).
  - Couleurs : 🟢 success / 🟡 partial / 🔴 alert / ⚪ idle.
- Clic icône → ouvre **Modal centré** (composant existant `Modal.tsx`) avec :
  - Date dernière sync (locale-formatted)
  - Statut par fichier (MA-L/MA-M/MA-S)
  - Compteurs added/changed/confirmed
  - Compteurs d'échecs consécutifs par fichier
  - Bouton « Lancer une sync maintenant » (POST endpoint Sprint 2)
  - Tableau des 30 dernières exécutions
- Modal Settings du module : 4 paramètres ci-dessus.
- Polling intelligent (backoff + stop après N tentatives) quand une sync est en cours.
- i18n FR + EN pour `admin.oui_sync.*`, `admin.status`.

**Files touched** :
- `src/backend/app/models/oui_sync_log.py` (new)
- `src/backend/alembic/versions/<id>_add_oui_sync_log.py` (new)
- `src/backend/app/api/admin/module_status.py` (new, générique)
- `src/backend/app/api/v1/endpoints/tools/mac_oui_history.py` (new, paginé)
- `src/backend/app/services/oui_sync_service.py` (modifier pour persister dans `oui_sync_log`)
- `src/frontend/src/pages/admin/AdminModulesPage.tsx` (ajouter colonne Statut)
- `src/frontend/src/pages/admin/components/MacOuiStatusModal.tsx` (new)
- `src/frontend/src/pages/admin/components/MacOuiSettingsModal.tsx` (new ou extension du pattern existant)
- Tests intégration backend + Vitest frontend
- Tests `@pytest.mark.perf`

**Risks** :
- **Système de métriques absent** : si rien n'existe dans le projet, fallback en logs structurés et issue de suivi.
- **Polling frontend** : risque de boucle infinie sur erreur. Implémenter backoff exponentiel + stop après N erreurs consécutives.
- **Rétention `oui_sync_log`** : pas de purge ce sprint. Issue de suivi `severity:low` pour purge éventuelle après N jours.

---

### 12.6 Sprint 6 — QA finale, Sécurité, Release Notes

| Agent | `qa` + `security` |
|---|---|
| **Documents** | `docs/qa/acceptance-mac-oui.md`, ADR-013, ADR-014 |
| **Depends on** | Sprints 1-5 mergés |

**Scope** :
- Statut chaque AC `AC-MAC-OUI-XXX` en `passed`/`failed`/`dropped` avec preuve (test path + line number).
- Revue sécurité dédiée : `docs/security/review-mac-oui.md`.
  - Tests sécurité effectivement exécutés : ReDoS frontend + backend, DoS mémoire, XSS (payload `<script>`), authz admin endpoints, SSRF sur endpoint admin sync.
- Suite complète `pytest` depuis `src/backend/` (CI ne lance pas pytest).
- Suite complète frontend (tsc, lint, vitest, playwright).
- Vérification d'indentation manuelle sur au moins 1 fichier par sprint (rappel #288/#289).
- Smoke tests régression sur Ping, Traceroute, DNS, TLS.
- Cross-check specs ↔ implémentation : section par section, `OK` ou `DEVIATION (justification)`.
- Release notes `docs/release/release-notes-0.2.0-mac-oui.md`.
- Recommandation finale : `accept` / `accept with reservations` / `reject`.

**Files touched** :
- `docs/qa/qa-report-mac-oui.md` (new)
- `docs/security/review-mac-oui.md` (new)
- `docs/release/release-notes-0.2.0-mac-oui.md` (new)
- `docs/qa/acceptance-mac-oui.md` (statuts AC mis à jour)
- `CHANGELOG.md` (ligne sous `[0.2.0]` si le fichier existe)

**Risks** :
- **AC non couverts** : tout AC sans test → issue de suivi, recommandation `reject` ou `accept with reservations`.
- **Régression sur tools existants** : smoke tests manuels obligatoires.
- **Performance prod-like** : si la base contient les vrais 50 000 OUI IEEE, vérifier que les requêtes de lookup restent < 500 ms pour 1 000 entrées.

---

### 12.7 Sprint dependency notes

Sprint 2 fournit la donnée réelle nécessaire à un testing utile des Sprints 3 et 4. **Recommandation forte** : exécuter une première sync (manuelle via endpoint admin) dès la fin du Sprint 2, pour disposer des vraies données IEEE pendant les Sprints 3-4-5.

Sprints 2 et 3 peuvent démarrer en parallèle après merge Sprint 1, à condition que le Sprint 3 utilise une fixture seed pour ses tests d'intégration (sans dépendre d'une DB peuplée par le Sprint 2).

Sprint 4 dépend du contrat API du Sprint 3 stable. Si le Sprint 3 livre tôt, le Sprint 4 peut chevaucher la fin du Sprint 5.

Sprint 6 est strictement séquentiel après tous les autres.

---

### 12.8 Sprint 6 (révisé) — Cleanup, outillage & docs

> Note : le périmètre initial du Sprint 6 (« QA finale / Sécurité / Release Notes », §12.6) a été **décalé** en un gate QA/Release ultérieur, exécuté avant le bump `0.2.0` et la remontée `dev0.2.0` → `master`. Le Sprint 6 livré ci-dessous est un sprint de dette + outillage.

**Scope livré** :
- **CLI** `sakn-cli sync-oui` : sync IEEE à la demande (réutilise `OuiSyncService.sync_all(triggered_by="cli")`), sans POST authentifié. Exit `1` si échec fichier.
- **#374** — rétention bornée de `oui_sync_log` : setting `OUI_SYNC_LOG_RETENTION_DAYS` (défaut 365, plage 7–3650), job hebdo `oui_sync_log_cleanup` préservant toujours la dernière exécution.
- **#370** — `audit_logs.admin_id` nullable (migration `batch_alter_table`, portable SQLite) ; suppression du sentinel `"unknown"` (FK invalide).
- **#364** — `module_deployed_at` lu via la session de requête (servi + testable).
- NITs #369 / #365 / #366 (tests + commentaire).
- Docs : `docs/admin/mac-oui-administration.md` (nouveau), CHANGELOG, ACs `AC-MAC-OUI-097..100`.

**Notification d'échec sync (#373)** : reportée — nécessite une infra d'envoi transverse (email/webhook) + ADR. Le marker `ALERT_OUI_SYNC_FAILED_3X` reste la source d'alerte.

**Intégration** : branche `sprint-6-mac-oui-cleanup-cli` → `dev0.2.0-macoui`.

---

## 13. Doutes / arbitrages MAC OUI

Tous les doutes initiaux ont été levés lors de la revue Sprint 0. Voir `docs/qa/acceptance-mac-oui.md` §15 pour le tableau de résolution complet et la traçabilité.

**Décisions structurantes actées en revue** :

| Sujet | Décision |
|---|---|
| Architecture | Frontend extrait/normalise (tolérant), backend valide strict + lookup pur |
| Protocole IEEE | **HTTPS** (testé fonctionnel 2026-05-31) |
| `change_type` | 3 valeurs : `name_change` (englobe acquisition), `address_change`, `revoked`. `reassigned` abandonné. |
| Rétention | **Aucune suppression**, jamais |
| Contrainte unicité | `UNIQUE(oui, oui_type)` (correction de spec appliquée Sprint 0) |
| Format MA-M/MA-S | `XX:XX:XX:X_` et `XX:XX:XX:XX:X_` (underscore = wildcard, CSS grisé) |
| OUI ambigu | Affichage orange + invitation à fournir MAC complète |
| Rejet backend | 200 OK avec `rejected[]` sanitisé (20 chars, charset filter) |
| Historique | Lazy load infinite scroll, 10 par défaut, configurable admin |
| Settings admin | 4 paramètres exposés dans Administration > Modules > MAC OUI > Settings |
| Statut admin | Nouvelle colonne « Statut » + icône colorée + Modal centré |
| RBAC | Pattern standard SAKN (`allowed=True` pour les 3 rôles au seed) |

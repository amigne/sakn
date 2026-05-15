# Implementation Plan — SAKN MVP

> **Version:** 3.0 — Vertical slices, frontend-first
> **Status:** Draft
> **Date:** 2026-05-14

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

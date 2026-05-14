# Common Specification — SAKN MVP

> **Version:** 3.0 — Extracted from technical-spec v2.0
> **Status:** Draft
> **Date:** 2026-05-14

Foundational decisions shared by all components. Load this document first for any task.

---

## 1. Introduction

### 1.1 Purpose

SAKN (Swiss Army Knife for Network Engineers) MVP: a web application providing network diagnostic tools — Ping, Traceroute, DNS Lookup, TLS/SSL Certificate Viewer — with authentication, RBAC, rate limiting, security filtering, logging, admin interface, i18n (EN/FR), and theming.

### 1.2 Key Architectural Drivers

1. **Tool modularity**: Tools must be independently pluggable, configurable, and securable.
2. **Security-first design**: Network filtering robust against bypass techniques (DNS rebinding, CNAME redirect, IPv6 tunneling).
3. **Async capability**: Support real-time streaming (WebSocket) without a framework rewrite.
4. **No magic**: All choices made for clarity, maintainability, and debuggability.

---

## 2. Framework & Tooling

### 2.1 Python: FastAPI + Pydantic v2

**Decision**: FastAPI (Python 3.14+) with Pydantic v2. Served via Uvicorn.

| Concern | FastAPI | Django | Flask | Litestar |
|---|---|---|---|---|
| Async-native | Yes (Starlette) | Partial (3.1+) | No (WSGI) | Yes |
| Request validation | Built-in (Pydantic) | DRF / Pydantic plugin | Flask-RESTx | Built-in |
| OpenAPI generation | Automatic | Manual | Manual | Automatic |
| WebSocket support | Native Starlette | Channels (heavy) | Flask-SocketIO | Native |

- Async-native → future SSE/WebSocket without framework change.
- Pydantic v2 → type-safe validation shared across API, tools, and config.
- Automatic OpenAPI → interactive docs for free.
- Python 3.14 is a hard requirement.

### 2.2 Package Manager: `uv`

**Decision**: `uv` (Rust-based, by Astral). Single tool replacing `pip`, `pip-tools`, `poetry`, `pyenv`, `virtualenv`.

| Concern | `uv` |
|---|---|
| Speed | Extremely fast (Rust) |
| Lockfile | Native (`uv.lock`) |
| Virtual env | Automatic (`.venv/`) |
| PEP compliance | PEP 621 (`pyproject.toml`) |

Key commands: `uv sync`, `uv sync --no-dev`, `uv run`, `uv add`, `uv lock`.

### 2.3 ORM: SQLAlchemy 2.0+ (async) + Alembic

| Layer | Technology |
|---|---|
| ORM | SQLAlchemy 2.0+ (async session) |
| Migrations | Alembic |
| PostgreSQL driver | asyncpg |
| SQLite driver (dev) | aiosqlite |

**Pattern**: Repository + service layer. Models never directly exposed to API endpoints.

### 2.4 Frontend Stack

| Concern | Decision |
|---|---|
| Build tool | Vite 6+ |
| Framework | React 19 |
| Routing | React Router 7 |
| Client state | Zustand 5+ |
| Server state | TanStack Query 5 |
| UI toolkit | Tailwind CSS 4 + Radix UI |
| i18n | react-i18next |
| Form validation | React Hook Form + Zod |
| Unit testing | Vitest + React Testing Library |
| E2E testing | Playwright |

**State management**: Zustand for global client state (auth, theme, tool preferences). TanStack Query for all server data (caching, dedup, background refetch). React Hook Form local state for forms.

**Theming**: Tailwind `darkMode: 'class'` — `dark` class on `<html>`. Theme values: `light`, `dark`, `system` (uses `matchMedia`).

**i18n**: JSON namespaces (`common`, `tools`, `auth`, `admin`), bundled with app. Key convention: `namespace.section.key`. Fallback: `en`.

**RTL readiness** (built from day one): CSS logical properties (`ps-4` not `pl-4`), `dir` context on Radix UI components, no hardcoded left/right.

---

## 3. Identifiers & Tokens

### 3.1 CSPRNG 256-bit (Security Tokens)

Generated via `secrets.token_urlsafe(32)` (Python) or Web Crypto API (frontend for CSRF). Base64url-encoded, ~43 characters. 256 bits entropy (vs 122 for UUIDv4).

| Use Case | Storage |
|---|---|
| Email verification tokens | SHA-256 hash in DB |
| Session tokens | SHA-256 hash in Redis + DB |
| CSRF tokens | Double-submit cookie pattern |
| Password reset tokens | SHA-256 hash in DB |

### 3.2 UUIDv7 (Database Primary Keys)

Time-ordered with random component. Monotonic insertion minimizes B-tree page splits (~30% less overhead vs UUIDv4). Used for all PKs.

---

## 4. Configuration Management

All configuration via environment variables (12-factor). Loaded into Pydantic `BaseSettings` at startup.

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | Yes | — | PostgreSQL or SQLite URL |
| `SECRET_KEY` | Yes | — | Min 32 bytes, base64-encoded |
| `REDIS_URL` | Yes (prod) | `redis://redis:6379/0` | Session + rate limit storage |
| `HOST` | No | `0.0.0.0` | Bind address |
| `PORT` | No | `8000` | Listen port |
| `ENVIRONMENT` | No | `development` | `development`, `production`, `test` |
| `LOG_LEVEL` | No | `INFO` | Python log level |
| `CORS_ORIGINS` | No | `http://localhost:5173` | Comma-separated |
| `SMTP_HOST/PORT/USERNAME/PASSWORD/FROM` | No | — | SMTP config |
| `EMAIL_VERIFICATION_REQUIRED` | No | `true` | Require verification before tool use |
| `SECURITY_DNS_RESOLVER` | No | `1.1.1.1` | DNS resolver for security filter |
| `RATE_LIMIT_STORAGE` | No | `redis` | `redis` (default) or `database` (SQLite dev) |

**Secrets**: `SECRET_KEY`, `SMTP_PASSWORD`, `DATABASE_URL`, `REDIS_URL` loaded from env only, never logged. `.env` files dev-only, never committed.

### 4.1 First Admin Bootstrap

Manual CLI invocation (not automatic, not via env vars):

```bash
docker compose exec backend uv run sakn-cli create-admin --email admin@example.com --password "..."
```

Uses `click`/`typer`, shares app context with web server.

---

## 5. Testing Strategy

| Layer | Scope | Tool |
|---|---|---|
| **Unit** | Functions, models, schemas, filters | `pytest` + `pytest-asyncio` |
| **Integration** | API endpoints, services, DB | `pytest` + `httpx.AsyncClient` |
| **E2E** | Full user workflows | Playwright |
| **Security** | Filter bypass, rate limits | `pytest` + custom scenarios |

**Backend**: Unit tests = pure functions, no DB. Integration tests use dedicated test DB (SQLite for CI, PostgreSQL pre-merge), transaction-per-test rollback. Mock subprocess executor, dnspython, SMTP, TLS connections.

**Frontend**: `vitest` + React Testing Library + `msw` for API mocking. E2E via Playwright.

**CI (GitHub Actions)**: `ruff check` / `biome check` → `pytest` + `vitest` → `bandit` / `npm audit` / `trivy` → `playwright test` → `docker build`. Triggers: push, pull_request.

**Network-dependent tests** tagged `@network`; skipped if CI lacks outbound access.

---

## 6. Risk Register

| ID | Risk | L | I | Mitigation |
|---|---|---|---|---|
| R-001 | Redis unavailable → no sessions | M | H | Redis AOF persistence, health-checked, clear error at startup |
| R-002 | Command injection via subprocess | L | C | List-form args, no `shell=True`, IP-only target, validated params |
| R-003 | DNS rebinding bypass | M | H | Resolve once, pass IP to subprocess (not hostname) |
| R-004 | ICMP unavailable in container | M | M | Clear error at startup, documented Docker requirement |
| R-005 | Redis memory pressure | L | L | 2h TTL on sorted sets, Lua atomic cleanup |
| R-006 | Parse failures from ping/traceroute | M | M | Pin iputils-ping version, parser tests |
| R-007 | TLS chain incomplete | M | L | Display what's sent, don't block on validation errors |
| R-008 | Email delivery failure | M | H | Log attempts, SPF/DKIM for sending domain |
| R-009 | CSRF token mismatch on first render | L | M | Cookie set at login; lazy set for visitors |
| R-010 | WebSocket connection accumulation | M | M | In-memory tracking, idle cleanup, heartbeat/ping frames |
| R-011 | Last admin lockout | L | H | Admins exempt from brute-force lockout; last admin cannot be deleted/demoted |
| R-012 | WebSocket disconnection mid-exec | M | M | SIGTERM on disconnect, 5s grace, then SIGKILL |

---

## 7. Open Questions — Resolved

| OQ | Decision |
|---|---|
| OQ-001 IPv4 vs IPv6 | Prefer IPv6. No toggle in MVP. Post-MVP if feedback demands. |
| OQ-002 Loop detection | Defer. |
| OQ-003 TCP Ping | ICMP-only for MVP. |
| OQ-004 EDNS Client Subnet | Defer. |
| OQ-005 Revocation checking | Skip. Display expiry + trust only. |
| OQ-006 DNSSEC | Defer. Display AD flag if available. |
| OQ-007 Password complexity | 8-128 chars, upper+lower+digit, zxcvbn ≥30 bits. No special char. |
| OQ-008 Timing attacks | Monitor for MVP. Constant-time post-MVP if needed. |
| OQ-009 Visitor rate limiting | Both session AND IP checks for visitors. |
| OQ-010 Session storage | Persistent Redis. |
| OQ-011 Super-admin | None. Bootstrap via CLI. Last admin protected. |
| OQ-012 Bulk operations | Defer. |
| OQ-013 Log export | Defer. |
| OQ-014 Locale formatting | Locale-sensitive, separate from language. |
| OQ-015 RTL support | DESIGN from start with logical properties. |
| OQ-016 Docker base image | python:3.14-slim (Debian). |
| OQ-017 Email service | SMTP via `smtplib`, env-var configured. |
| OQ-018 Output formatting | Structured tables/cards, no raw CLI mode. |
| OQ-019 Parameter presets | Defer. |
| OQ-020 Concurrent execution | Frontend prevents; backend allows. |

# Changelog

All notable changes to SAKN will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Development cycle for `0.2.0` (backend: `0.2.0.dev0`, frontend: `0.2.0-dev`).

### Added

- **MAC OUI Lookup tool**: resolve MAC/OUI prefixes to their registered IEEE organization. Tolerant frontend extraction of MAC/OUI patterns from arbitrary text, zero-trust backend validation, single-query longest-prefix lookup against a local IEEE database, ambiguity detection (24-bit prefixes extended by MA-M/MA-S), and per-OUI change history.
- MAC OUI: daily IEEE OUI synchronization (MA-L / MA-M / MA-S over HTTPS) via APScheduler, persisted in `oui_sync_log`, with per-file consecutive-failure tracking.
- MAC OUI admin: module **Status** view and **Settings** modal (frontend input cap, backend batch size, history page size, sync hour, sync-log retention) — Admin → Modules.
- MAC OUI: `sakn-cli sync-oui` command to force an on-demand IEEE OUI sync without an authenticated HTTP call.
- MAC OUI: bounded retention for `oui_sync_log` — weekly purge job and admin setting `OUI_SYNC_LOG_RETENTION_DAYS` (default 365), always keeping the most recent run (#374).
- MAC OUI: email alert to administrators on the 3rd consecutive sync failure of an IEEE file, reusing the existing email service (best-effort; ADR-016, #373).
- Observability: Prometheus metrics exposed at `/metrics` for OUI sync and lookup (ADR-015, #372).
- Administrator guide for MAC OUI Lookup (`docs/admin/mac-oui-administration.md`).
- CI: SQLite job added to `migration-check` (migrations now validated on Postgres **and** SQLite); runtime import check for missing production dependencies (#368); compose env-wiring guard (`scripts/check_compose_env.py`).
- Docker: wire `HEALTH_FULL_TOKEN` and `WS_REQUIRE_ORIGIN` into the compose `environment:` blocks; `.env.example` documents them (#409).

### Security

- Add CSRF validation (`X-CSRF-Token`) to all admin endpoints and `POST /tools/{tool}/execute` (#405).
- DNS Lookup: validate the user-supplied resolver IP against the blocklist to prevent SSRF (#406).
- MAC OUI: per-input length cap (64 chars) to prevent memory/CPU amplification (#394).
- Auto-created tool permissions now default-**deny** (fail-closed) instead of default-allow (#404).
- `PUT /admin/settings`: allowlist of writable keys; internal control keys can no longer be mutated via this endpoint (#400).
- Brute-force: administrators are exempt from per-account lockout (R-011, #401); lockout duration uses the most restrictive matching tier with continuous renewal (#402).
- Production compose defaults `WS_REQUIRE_ORIGIN=true` (CSWSH protection for WebSockets, ADR-009).
- Upgrade `vitest` to `^4.1.8` to fix CVE GHSA-5xrq-8626-4rwp (critical, CVSS 9.8). devDependency only, no production runtime exposure. Ported from `dev0.1.1` (#334).

### Fixed

- Alembic: migrations `d7091a29b949` and `55cf8e97f4da` are now SQLite-portable (`batch_alter_table` / copy-and-move) — the chain was Postgres-only and broke `alembic upgrade` on SQLite (#412); the new `rate_limit_configs` UNIQUE migration is likewise batch-mode (#403, #310).
- Audit log: `audit_logs.admin_id` is now nullable (consistent with `ON DELETE SET NULL`); audit entries with an unknown actor are written with `NULL` instead of the invalid `"unknown"` sentinel that violated the users FK (#370).
- Admin → Modules: tool capability flags (`has_settings` / `has_status`) are synced from the tool class on every boot, fixing missing Settings/Status icons (#375, #376).
- MAC OUI: admin status shows `alert` (not `success`) when all 3 IEEE files fail in one run (#382); ambiguity flag is set for 24-bit inputs without an MA-L row (ADR-014, #383); history pagination works for full 48-bit MAC inputs (#380); `module_deployed_at` is read via the request session so it is served and testable (#364).
- MAC OUI sync: close a TOCTOU race in the lock TTL-reclaim path via CAS (#381).
- `sakn-cli`: set `PYTHONPATH=/app` in the Docker image so the CLI resolves the `app` package (#371).
- `bump-version.sh`: tighter version validation, atomic per-file writes, `jq` for precise `package.json` targeting (#337, #338, #340).
- Startup: clear error when the `sakn` package is not installed (`PackageNotFoundError`, #339).
- Remove hardcoded `"enabled": True` from `to_api_definition()` (#313); drop the redundant `window_seconds` default in admin rate limits (#314).

### Changed

- Alembic: merge migration `0ee01149004a` unites the `rate_limit_configs` UNIQUE and MAC OUI migration heads (#418).
- Backend: FastAPI version now sourced from `importlib.metadata` (`pyproject.toml` is the single source of truth). Ported from `dev0.1.1` (#333).
- Add `scripts/bump-version.sh` for atomic cross-stack version bumps (PEP 440 ↔ SemVer). Ported from `dev0.1.1` (#333).
- CI: remove `GHSA-5xrq-8626-4rwp` from the npm audit allowlist now that vitest 4.1.8 ships the fix.

## [0.1.0] — 2026-05-30

First post-MVP release.

### Added

- Network diagnostics tools: Ping, Traceroute, DNS Lookup, TLS/SSL Viewer
- WebSocket-based real-time output for Ping and Traceroute
- HTTP-based instant results for DNS Lookup and TLS/SSL Viewer
- Role-based access control (visitor / authenticated / administrator)
- User authentication with email verification flow
- Session management with HMAC-peppered tokens
- Immutable audit logging (tool execution, security events, admin actions)
- Rate limiting via Redis
- CSRF protection
- Internationalization (English and French) with locale-sensitive formatting
- Dark/light theme support
- Admin panel (user management, module management, settings, rate limits)
- Responsive UI with Radix UI primitives and Tailwind CSS
- Comprehensive test suites (pytest, Vitest, Playwright E2E)
- CI/CD pipelines (lint, E2E, migration checks, dependency scanning)
- Docker Compose production deployment with Caddy reverse proxy

### Security

- Security audit completed (2026-05-18): 29 findings addressed
- Argon2 password hashing, zxcvbn strength validation
- Enumeration protection on auth endpoints
- Proxy trust policy enforcement
- CSP headers with strict nonce-based policy
- WebSocket origin enforcement
- Dependency scanning (pip-audit, npm audit)

## [0.0.2] — Initial MVP

Initial minimum viable product release with core network diagnostic capabilities.

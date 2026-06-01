# Changelog

All notable changes to SAKN will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Development cycle for `0.2.0` (backend: `0.2.0.dev0`, frontend: `0.2.0-dev`).

### Security

- Upgrade `vitest` to `^4.1.8` to fix CVE GHSA-5xrq-8626-4rwp (critical, CVSS 9.8 — Vitest UI server unauthorized file access). devDependency only, no production runtime exposure. Ported from `dev0.1.1` (#334).

### Changed

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

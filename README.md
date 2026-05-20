# SAKN — Swiss Army Knife for Network Engineers

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Web-based network diagnostics toolkit. Run ping, traceroute, DNS lookups, and
TLS certificate inspection from your browser — no CLI tools needed.

**For**: Network engineers, system administrators, DevOps practitioners, and
security engineers.

## Features

- **Ping** — ICMP echo requests with configurable count, packet size, DF bit,
  and DSCP/ToS marking. Real-time WebSocket output.
- **Traceroute** — Path discovery with per-hop latency. UDP, ICMP, or TCP mode.
  Configurable max hops and timeout.
- **DNS Lookup** — A, AAAA, CNAME, MX, NS, TXT, SRV, SOA, PTR, CAA record
  queries with configurable upstream resolvers.
- **TLS/SSL Certificate Viewer** — Certificate chain inspection, expiry dates,
  SANs, issuer details, and OCSP revocation status.
- **Role-Based Access Control** — Three roles (visitor, authenticated,
  administrator) with fine-grained per-tool permissions.
- **Audit Logging** — Immutable tool execution, security event, and admin
  audit logs with configurable retention.
- **Internationalization** — English and French, locale-sensitive formatting.
- **Dark/Light themes** — System-aware with manual toggle.

See [docs/specs/functional-spec.md](docs/specs/functional-spec.md) for full details.

## Quick Start

```bash
# 1. Clone
git clone https://github.com/amigne/sakn.git && cd sakn

# 2. Configure
cp .env.example .env
# Edit .env — set SECRET_KEY, POSTGRES_PASSWORD, REDIS_PASSWORD, and DOMAIN
# Generate secrets: python -c "import secrets; print(secrets.token_urlsafe(32))"

# 3. Start (production profile with Caddy auto-TLS)
docker compose --profile prod up -d

# 4. Create your admin account
docker compose exec backend sakn-cli create-admin --email admin@example.com --password <strong-password>

# 5. Open
# Production:  https://<your-domain>
# Development: http://localhost:5173
```

Requirements: Docker 29+ and Docker Compose v5+. The production profile starts
5 containers: Caddy (reverse proxy + TLS), Frontend (nginx + React SPA),
Backend (FastAPI), PostgreSQL 18, and Redis 7.

## Architecture

| Container | Role | Stack |
|-----------|------|-------|
| Caddy | TLS termination, reverse proxy, HSTS/CSP | Caddy 2 |
| Frontend | Static SPA serving | nginx + React 19 + TypeScript 5.7 |
| Backend | REST API + WebSocket + scheduler | Python 3.14+ / FastAPI / SQLAlchemy async / structlog |
| PostgreSQL | Primary database | PostgreSQL 18 |
| Redis | Session cache, rate-limit counters | Redis 7 |

Package managers: [uv](https://docs.astral.sh/uv/) (Python),
[npm](https://www.npmjs.com/) (frontend).

See [docs/specs/technical/spec-index.md](docs/specs/technical/spec-index.md)
for the full technical specification, API contract, and component architecture.

## Development Setup

```bash
# Start with hot-reload (SQLite, no PostgreSQL needed)
docker compose --profile dev up -d

# Or run services individually:

# Backend (Python 3.14+, uv)
cd src/backend
uv sync
uv run uvicorn app.main:app --reload

# Frontend (Node.js 20+, npm)
cd src/frontend
npm install
npm run dev
```

- **Database**: SQLite for local dev (auto-fallback), PostgreSQL 18 for production.
- **Config**: Copy `.env.example` to `.env`, set `ENVIRONMENT=development`.
- **CLI**: `sakn-cli` for admin operations (`create-admin`).

See [docs/specs/technical/spec-backend.md](docs/specs/technical/spec-backend.md)
and [docs/specs/technical/spec-frontend.md](docs/specs/technical/spec-frontend.md)
for detailed setup instructions.

## Testing

```bash
# Backend (unit + integration)
cd src/backend
uv run pytest

# Frontend (unit)
cd src/frontend
npm test

# Frontend (E2E — Playwright)
cd src/frontend
npx playwright test
```

## Security

- [Threat Model](docs/security/threat-model.md) — STRIDE-based analysis
  covering authentication, sessions, WebSocket, admin, RBAC, DNS recursion,
  rate limiting, and infrastructure.
- [Secrets Management](docs/security/secrets-management.md) — Secret
  generation, storage, validation, and rotation procedures.
- [Incident Response](docs/security/incident-response.md) — Runbook with
  actionable checklists for 6 incident scenarios.
- [Security Audit (2026-05-18)](docs/security/audit-2026-05-18.md) — 29
  findings (4 critical, 9 high, 9 medium, 7 low/info).
- [ADR-002: Enumeration Protection](docs/adr/002-enumeration-protection.md)
- [ADR-003: Proxy Trust Policy](docs/adr/003-proxy-trust-policy.md)

To report a security vulnerability, please contact the maintainer directly
rather than opening a public issue.

## Contributing

1. Branch naming: `issueXX` (one branch per issue).
2. No implementation before spec validation: functional spec, UI spec,
   technical spec, acceptance criteria, and implementation plan must be
   reviewed before coding.
3. All major decisions are documented in `docs/specs/`, `docs/adr/`,
   `docs/qa/`, or `docs/security/`.
4. Every feature must include tests or a written justification for their
   absence.
5. Pull requests must be small and reviewable. Avoid bundling unrelated
   changes.

See [CLAUDE.md](CLAUDE.md) for the full contribution workflow.

## License

MIT — see [LICENSE](LICENSE) for details.

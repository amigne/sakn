# ADR-004: Health Endpoint Split

## Status
Accepted — 2026-05-21

## Context
The existing `/health` endpoint returns infrastructure status
(`{"status":"ok","checks":{"database":"ok|unavailable","redis":"ok|unavailable"}}`)
without authentication. This leaks internal infrastructure state to any caller
(load balancers, external monitors, attackers). Audit finding M-1 flagged the
lack of security headers on `/health` (fixed in issue #21), but the unrelated
issue of information disclosure via the health response body remained
unaddressed.

## Decision
Split the health endpoint into two:

1. **`GET /health`** — Minimal liveness probe. Returns `{"status":"ok"}` only.
   No database or Redis queries. No authentication. Designed for load-balancer
   and container health checks that run on short intervals (every 1-5 seconds).

2. **`GET /health/full`** — Detailed health status. Returns
   `{"status":"ok","checks":{"database":"ok|unavailable","redis":"ok|unavailable"}}`.
   Protected by a static token passed via the `X-Health-Token` header, compared
   against the `HEALTH_FULL_TOKEN` environment variable. Returns 401 if the
   token is missing or incorrect. Returns 503 if `HEALTH_FULL_TOKEN` is not
   configured (operator must explicitly enable this endpoint).

**Authentication method**: Static token (`X-Health-Token` header) over host-header
binding (`if request.headers["host"] == "backend:8000"`) because:

- Host-header binding breaks when a reverse proxy (Caddy, nginx) sits between
  the monitoring system and the backend — the `Host` header reflects the proxy's
  view, not the actual client.
- A static token works regardless of network topology (direct access, Docker
  internal network, proxied).
- Tokens can be rotated using the same CSPRNG procedure documented in
  `docs/security/secrets-management.md`.
- Token-based auth is simpler to test and debug than host-header rules.

## Consequences
- Load-balancer health checks are faster (no DB/Redis queries per probe).
- Infrastructure status is no longer publicly accessible — the `/health/full`
  endpoint requires a pre-shared token.
- Operators must set `HEALTH_FULL_TOKEN` in `.env` to enable detailed health
  monitoring. If unset, `/health/full` returns 401.
- The Docker Compose healthcheck command (`curl -f localhost:8000/health`) is
  unaffected — it checks the minimal endpoint, which only needs HTTP 200.
- Sprint 1 documentation (`secrets-management.md`, `incident-response.md`)
  examples referencing `{"status":"healthy"}` are corrected to `{"status":"ok"}`
  to match the actual contract.

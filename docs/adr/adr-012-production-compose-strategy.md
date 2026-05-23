# ADR-012: Production Docker Compose Strategy

- **Status:** Accepted
- **Date:** 2026-05-23
- **Deciders:** Sprint 8 post-audit

## Context

The project currently uses Docker Compose profiles (`profiles: [prod]`) to gate
production-only services (caddy, frontend, backend) within a single
`docker-compose.yml` file. Development services are defined in a separate
`docker-compose.dev.yml` overlay.

This creates ambiguity:
- No self-contained production compose file exists.
- `docker compose --profile prod up` is non-obvious syntax.
- Production-specific settings (resource limits, logging drivers) are missing.

## Decision

Create a self-contained `docker-compose.prod.yml` that defines all five
production services (caddy, frontend, backend, postgres, redis) with:

- **No profiles gating** — all services start unconditionally.
- **Resource limits** (`deploy.resources.limits`) on every service.
- **Logging driver** `json-file` with rotation (`max-size: 10m`, `max-file: 3`).
- **Healthchecks with `start_period`** for cold-start tolerance.
- **No dev bind mounts** — only named volumes and read-only config mounts.
- **`restart: unless-stopped`** on all services.

The original `docker-compose.yml` retains the base service definitions without
profiles, usable as a dev base or compose library. `docker-compose.dev.yml`
remains as the development overlay.

## Usage

- **Production:** `docker compose -f docker-compose.prod.yml up -d`
- **Development:** `docker compose -f docker-compose.yml -f docker-compose.dev.yml up`

## Consequences

- Production configuration is self-documenting and auditable in a single file.
- Resource limits prevent noisy-neighbor issues in shared Docker hosts.
- Log rotation prevents disk exhaustion from unbound container logs.
- Breaking: `docker compose --profile prod up` no longer works. Teams must
  migrate to `-f docker-compose.prod.yml`.

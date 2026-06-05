# Implementation Plan — Visitor IP in Top Bar

> **Version:** 1.0
> **Status:** Draft
> **Date:** 2026-06-05
> **References:** `functional-spec.md` §2.4, `ui-spec.md` §7.4, `spec-api-contract.md` §3.9, `docs/qa/acceptance-visitor-ip.md`, `docs/adr/003-proxy-trust-policy.md`

Small, single-PR feature. No new dependency, no DB change, no migration, no ADR (reuses the existing trusted-proxy policy, ADR-003). Implemented on the `dev0.2.0-myip` integration branch.

## Scope

Display the visitor's server-perceived IP in the top bar, immediately left of the language switcher, for all visitors (anonymous + authenticated), backed by a new public read-only endpoint.

## Backend

1. **`GET /auth/whoami`** in `app/api/v1/endpoints/auth.py` (auth router, prefix `/auth`):
   - No auth, no CSRF (read-only GET).
   - Returns `{"ip": request.client.host if request.client else None}`.
   - **Must** use `request.client.host` (already corrected by `TrustedProxyMiddleware`); must **not** read `X-Forwarded-For`/`X-Real-IP` directly.
2. Tests (`tests/integration/`): the 200 shape, anonymous access, trusted-hops derivation (mirror existing proxy-trust tests), hops=0 ignores XFF, `ip: null` fallback, no-CSRF.

## Frontend

3. **API call**: add `whoami()` to a service (e.g., extend `authService.ts` or a small `netService.ts`) → `GET /auth/whoami` → `{ ip: string | null }`. Tolerate failure (return null, no throw surfaced to UI).
4. **`TopBar.tsx`**: fetch on mount; render the IP element **before** the language toggle button (`[IP] [Lang] [Theme] [User]`). Network/globe icon + monospace IP. Click/Enter/Space → copy to clipboard + `common.ip_copied` feedback (~2 s) + `aria-live="polite"`. `title`/aria-label = `common.your_ip`. Hidden `< sm` (640px). Omitted on failure/null.
5. **i18n**: add `common.your_ip`, `common.ip_copied` to `i18n/en.json` and `i18n/fr.json`.
6. Tests: extend `components/layout/__tests__/TopBar.test.tsx` (renders before language toggle, copy behavior, omitted on failure, hidden when narrow). Optional Playwright assertion in an existing layout/topbar spec.

## Out of scope / decided defaults (reviewer may adjust)

- **Click-to-copy** interaction (vs plain static text) — included for engineer convenience.
- **Hidden below 640px** (vs always shown / truncated) — to preserve top-bar space.
- **Fetched once on mount** (no polling, no client cache).
- Endpoint path `/auth/whoami` (vs a dedicated meta router) — chosen for minimal wiring; the route is public despite the `/auth` prefix.

## Verification

```
cd src/backend && .venv/bin/ruff check app/ tests/ && .venv/bin/pytest tests/ -q
cd ../frontend && node_modules/.bin/tsc --noEmit && node_modules/.bin/biome check src/ && node_modules/.bin/vitest run
```

## CHANGELOG

Add under `[Unreleased] → ### Added`: top-bar visitor IP display (`GET /auth/whoami`). No version bump.

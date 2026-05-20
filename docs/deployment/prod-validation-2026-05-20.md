# Production Deployment Validation — 2026-05-20

Issue: [#6](https://github.com/amigne/sakn/issues/6)

## Environment

- Docker 29.5.0 / Compose v5.1.3
- `.env.prod-test` with random credentials (URL-safe)
- Domain: `sakn.local`

## Step 0 — Pre-requisites

`.env.prod-test` created with `openssl rand -base64` credentials. Passwords filtered to URL-safe characters (`tr '+/' '-_'`) to avoid URL parsing issues in `DATABASE_URL`. Added to `.gitignore`.

## Step 1 — Build

```
docker compose --env-file .env.prod-test --profile prod build --no-cache
```

| Image | Size | Status |
|-------|------|--------|
| sakn-backend | 345 MB | OK |
| sakn-frontend | 74.5 MB | OK |
| caddy:2-alpine | (pulled) | OK |

Notes:
- `setcap cap_net_raw+ep /usr/bin/traceroute.db` correct (issue #31 verified)
- Vite chunk size warning (non-blocking)

## Step 2 — Stack Startup

```
docker compose --env-file .env.prod-test --profile prod up -d
```

| Container | Health | Status |
|-----------|--------|--------|
| postgres | healthy | OK |
| redis | healthy | OK |
| backend | healthy | OK (after fix, see below) |
| frontend | healthy | OK (after fix, see below) |
| caddy | (none) | OK |

## Step 3 — Healthchecks

All 5 containers OK after fixes. Backend `/health` returns `{"status":"ok","checks":{"database":"ok","redis":"ok"}}`.

## Step 4 — Functional Tests

### SPA via Caddy
```
curl -k https://sakn.local/
→ <!DOCTYPE html>... SPA served correctly
```

### API via Caddy
```
POST /api/v1/auth/register → "Registration successful"
POST /api/v1/auth/login → Returns user + session
GET /api/v1/tools → Returns 4 tools (ping, traceroute, dns_lookup, ssl_viewer)
```

### WebSocket
- Direct backend: WebSocket upgrade OK, connection established
- Via Caddy HTTPS: Requires valid TLS cert (test limitation, not a bug)
- Caddy route fixed: `/api/v1/tools/*/ws` → `/api/v1/tools/*/stream` (was mismatched)

## Step 5 — Security Headers

```
Strict-Transport-Security: max-age=63072000; includeSubDomains; preload
Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self' ws: wss:; form-action 'self'
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: strict-origin-when-cross-origin
```

All present ✅. Server header removed (`-Server` in Caddy config).

## Step 6 — Fail-Fast Verification

| Variable | Fail-fast | Result |
|----------|-----------|--------|
| SECRET_KEY | `${SECRET_KEY:?}` | "required variable SECRET_KEY is missing a value" ✅ |
| POSTGRES_PASSWORD | `${POSTGRES_PASSWORD:?}` | "required variable POSTGRES_PASSWORD is missing a value" ✅ |
| REDIS_PASSWORD | `${REDIS_PASSWORD:?}` | "required variable REDIS_PASSWORD is missing a value" ✅ |

## Step 7 — Scheduler

- `apscheduler` starts during lifespan without errors
- `cleanup_unverified_accounts` tested manually: executed successfully (0 accounts in test)
- Jobs: log_cleanup (03:00), unverified_account_cleanup (03:30)

## Bugs Found and Fixed

### Bug #1 — `startup.sh` PostgreSQL wait script silently fails
- **Root cause**: `sys.stderr` referenced but `sys` not imported; `2>/dev/null` silenced the `NameError`
- **Impact**: Backend would never start if PostgreSQL wasn't immediately ready
- **Fix**: Added `import sys`, replaced `print(file=sys.stderr)` with `sys.exit(1)`

### Bug #2 — `docker-compose.yml` DATABASE_URL password encoding
- **Root cause**: `POSTGRES_PASSWORD` interpolated directly into URL without URL-encoding
- **Impact**: Passwords containing `/`, `@`, `:`, `%` produce malformed URLs
- **Fix**: Documented as known limitation. Workaround: use URL-safe passwords

### Bug #3 — Caddyfile WebSocket route mismatch
- **Root cause**: Caddy route `/api/v1/tools/*/ws` doesn't match backend route `/{tool_name}/stream`
- **Impact**: Dedicated WS route non-functional; WS falls through to generic `/api/*` proxy
- **Fix**: Changed to `/api/v1/tools/*/stream`

### Bug #4 — Frontend healthcheck IPv6 resolution
- **Root cause**: `wget http://localhost:80/` resolves to IPv6 but nginx binds IPv4 only
- **Impact**: Frontend healthcheck failed (unhealthy), but nginx served correctly
- **Fix**: Changed `localhost` to `127.0.0.1`

## Known Limitations

- SMTP not tested: `smtp.example.com` is a dummy host (email sending fails silently in test)
- WebSocket via Caddy HTTPS not tested: self-signed cert doesn't work with websocket clients
- Scheduler jobs not tested end-to-end: cron timing requires production runtime

## Final State

```
NAME              STATUS
sakn-backend-1    Up (healthy)
sakn-caddy-1      Up
sakn-frontend-1   Up (healthy)
sakn-postgres-1   Up (healthy)
sakn-redis-1      Up (healthy)
```

All 5 containers operational, all tests pass.

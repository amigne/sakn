# Production Deployment Checklist

## Pre-deployment

- [ ] `.env` file contains all required secrets:
  - `POSTGRES_PASSWORD` (strong, random)
  - `REDIS_PASSWORD` (strong, random)
  - `SECRET_KEY` (at least 32 characters, high entropy)
  - `HEALTH_FULL_TOKEN` (optional but recommended, generate with `python -c "import secrets; print(secrets.token_urlsafe(32))"`)
- [ ] `DOMAIN` is set to the production domain name.
- [ ] `ENVIRONMENT=production` is set.
- [ ] `TRUSTED_PROXY_HOPS=1` is set (Caddy is the reverse proxy).
- [ ] `CORS_ORIGINS` is set to the production frontend URL.
- [ ] SMTP credentials are configured if email verification is enabled.
- [ ] DNS A/AAAA records point to the production server.

## Configuration validation

- [ ] `docker compose -f docker-compose.prod.yml config` parses without errors.
- [ ] `docker compose -f docker-compose.prod.yml config --services` lists all 5 services: caddy, frontend, backend, postgres, redis.

## Deployment

```bash
docker compose -f docker-compose.prod.yml up -d
```

## Post-deployment verification

- [ ] All 5 containers are running: `docker compose -f docker-compose.prod.yml ps`
- [ ] All healthchecks pass within 60 seconds:
  ```bash
  docker compose -f docker-compose.prod.yml ps --format json | jq 'select(.Health != "healthy")'
  ```
  (should return no results)
- [ ] HTTPS is working: `curl -sS https://$DOMAIN/health` returns HTTP 200.
- [ ] Backend health endpoint: `curl -sS https://$DOMAIN/health` returns `{"status":"ok"}`.
- [ ] WebSocket upgrade works: verify a tool stream endpoint connects successfully.
- [ ] Resource limits are in effect:
  ```bash
  docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}"
  ```

## Logging

- [ ] Container logs are rotated (max 10 MB per file, 3 files retained).
- [ ] Check disk usage: `du -sh /var/lib/docker/containers/*/`

## Rollback

```bash
docker compose -f docker-compose.prod.yml down
# Then deploy previous version
```

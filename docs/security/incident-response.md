# Incident Response Runbook — SAKN

**Date**: 2026-05-20
**Status**: Living document — update after each incident postmortem.

## 1. When to Use This Runbook

Trigger this runbook when any of the following are suspected or confirmed:

- Credential compromise (user or administrator account)
- Session hijacking
- Unauthorized administrative actions
- Data breach (user data exposure)
- Service compromise (container or host access)
- Denial of service attack
- Discovery of an exploitable security vulnerability
- Secrets leakage (SECRET_KEY, database password, Redis password)

## 2. Contacts and Escalation

Fill in the contact method column per deployment.

| Role | Responsibility | Escalation Trigger | Contact Method |
|------|---------------|--------------------|----------------|
| Application Owner | Accepts risk decisions, authorizes service disruption | Critical severity confirmed | _Fill in_ |
| Infrastructure Operator | Executes runbook procedures, restarts services | Any incident requiring service restart | _Fill in_ |
| Security Point of Contact | Leads investigation, preserves evidence, writes postmortem | Any confirmed security incident | _Fill in_ |

## 3. Severity Classification

| Severity | Criteria | Response Time | Example |
|----------|----------|--------------|---------|
| **Critical** | Active compromise, data exfiltration in progress | Immediate | Admin account takeover, SECRET_KEY leaked |
| **High** | Exploitable vulnerability confirmed, no active exploitation yet | < 4 hours | Default credentials exposed, missing auth on endpoint |
| **Medium** | Information disclosure, limited scope, no direct account access | < 24 hours | Health endpoint leaking version info, verbose error messages |
| **Low** | Hardening opportunity, no direct exploit path | Next sprint | Missing security header, non-default configuration weakness |

## 4. Response Procedures

### 4.1 Invalidate All Sessions

Use when: session token leak suspected, SECRET_KEY rotated, or mass account compromise.

- [ ] **Step 1**: Flush Redis session store.
  ```bash
  docker compose exec redis redis-cli -a "$REDIS_PASSWORD" FLUSHDB
  ```
  Note: `FLUSHDB` removes all keys in the current database (sessions + rate-limit
  counters). Both will repopulate automatically. If Redis is shared with other
  applications, use `SCAN` + `DEL` targeting `session:*` keys instead.

- [ ] **Step 2**: Delete all session rows from PostgreSQL.
  ```bash
  docker compose exec backend python -c "
  import asyncio
  from sqlalchemy import delete
  from app.database import async_session_factory
  from app.models.session import Session

  async def run():
      async with async_session_factory() as db:
          result = await db.execute(delete(Session))
          await db.commit()
          print(f'{result.rowcount} sessions deleted.')

  asyncio.run(run())
  "
  ```

- [ ] **Step 3**: Rotate `SECRET_KEY` (see [Section 4.3](#43-force-secret_key-rotation)).

- [ ] **Step 4**: Restart the backend.
  ```bash
  docker compose restart backend
  ```

- [ ] **Step 5**: Notify users to re-authenticate (if user-facing service).

### 4.2 Revoke an Administrator

Use when: admin account suspected compromised, or administrative access needs
immediate revocation.

#### Method A: Direct database (preferred for immediate response)

```bash
docker compose exec backend python -c "
import asyncio
from sqlalchemy import select, update
from app.database import async_session_factory
from app.models.user import User

async def run():
    async with async_session_factory() as db:
        # Replace with the target admin's email
        target_email = 'admin@example.com'

        result = await db.execute(select(User).where(User.email == target_email))
        user = result.scalar_one_or_none()
        if user is None:
            print(f'User {target_email} not found.')
            return
        if user.role != 'administrator':
            print(f'User {target_email} is not an administrator (current role: {user.role}).')
            return

        user.role = 'authenticated'
        user.status = 'active'
        await db.commit()
        print(f'Administrator {target_email} demoted to authenticated. Session will lose admin privileges on next request.')

asyncio.run(run())
"
```

#### Method B: Admin UI

1. Log in as another administrator.
2. Navigate to **Admin → Users**.
3. Find the target user, click to open detail view.
4. Change **Role** from `administrator` to `authenticated`.
5. Click **Save**.

**Important**: The backend enforces last-admin protection — you cannot demote
or delete the **last remaining** administrator via either method. If you need
to remove the sole admin, first promote another user to administrator.

### 4.3 Force SECRET_KEY Rotation

Use when: SECRET_KEY suspected compromised, or as part of session invalidation.

- [ ] **Step 1**: Generate a new key.
  ```bash
  python -c "import secrets; print(secrets.token_urlsafe(32))"
  ```

- [ ] **Step 2**: Update `SECRET_KEY` in the `.env` file.

- [ ] **Step 3**: Invalidate all sessions (see [Section 4.1](#41-invalidate-all-sessions))
  — old CSRF tokens are bound to the old key context.

- [ ] **Step 4**: Restart the backend.
  ```bash
  docker compose restart backend
  ```

- [ ] **Step 5**: Verify the service is healthy.
  ```bash
  curl -s http://localhost:8000/health
  # Expected: {"status":"healthy"}
  ```

- [ ] **Step 6**: Note that email hashes in existing `SecurityEventLog` rows are
  permanently bound to the old key. Old log entries expire after the configured
  retention period (default 90 days).

### 4.4 Data Breach (User Data Exposure)

Use when: unauthorized access to user data confirmed or strongly suspected.

- [ ] **Step 1 — Contain**: Stop the affected service or disconnect it from the
  network to prevent further exfiltration.
  ```bash
  docker compose stop backend
  ```

- [ ] **Step 2 — Assess scope**: Query recent security events for unusual patterns.
  ```bash
  docker compose exec postgres psql -U sakn -c \
    "SELECT event_type, COUNT(*) FROM security_event_logs
     WHERE created_at > NOW() - INTERVAL '24 hours'
     GROUP BY event_type ORDER BY COUNT(*) DESC;"
  ```

- [ ] **Step 3 — Rotate all secrets**: `SECRET_KEY`, `POSTGRES_PASSWORD`,
  `REDIS_PASSWORD`, `SMTP_PASSWORD`. See
  [Secrets Management](./secrets-management.md) for per-secret procedures.

- [ ] **Step 4 — Invalidate all sessions** (see [Section 4.1](#41-invalidate-all-sessions)).

- [ ] **Step 5 — Notify**: Inform affected users per applicable data breach
  notification requirements (GDPR Art. 33/34, CCPA, etc.).

- [ ] **Step 6 — Preserve evidence**:
  ```bash
  # Dump logs before restarting
  docker compose logs backend  > "incident-backend-$(date -I).log"
  docker compose logs postgres > "incident-postgres-$(date -I).log"

  # Dump security event logs
  docker compose exec postgres pg_dump -U sakn --table=security_event_logs --table=audit_logs \
    > "incident-logs-$(date -I).sql"
  ```

- [ ] **Step 7 — Root cause analysis**: Identify how the breach occurred before
  restoring service. File a postmortem in `docs/security/`.

### 4.5 Service Compromise (Container or Host Access)

Use when: attacker may have gained shell access inside a container or on the
Docker host.

- [ ] **Step 1 — Isolate**: Stop and disconnect the compromised container.
  ```bash
  docker compose stop <service-name>
  docker network disconnect sakn-public <service-name>
  docker network disconnect sakn-internal <service-name>
  ```

- [ ] **Step 2 — Preserve forensic data**:
  ```bash
  docker logs <container> > "incident-container-$(date -I).log"
  docker cp <container>:/app ./forensic-app-copy
  ```

- [ ] **Step 3 — Rotate all secrets**: Assume all secrets accessible to the
  compromised container are compromised. See [Secrets Management](./secrets-management.md).

- [ ] **Step 4 — Rebuild images from clean source**:
  ```bash
  docker compose build --no-cache
  ```

- [ ] **Step 5 — Redeploy**:
  ```bash
  docker compose --profile prod up -d
  ```

- [ ] **Step 6 — Audit**: Review all administrator accounts and active sessions.
  ```bash
  # List all admin accounts
  docker compose exec backend python -c "
  import asyncio
  from sqlalchemy import select
  from app.database import async_session_factory
  from app.models.user import User

  async def run():
      async with async_session_factory() as db:
          result = await db.execute(select(User).where(User.role == 'administrator'))
          for user in result.scalars():
              print(f'{user.email} — status={user.status}')
  asyncio.run(run())
  "
  ```

### 4.6 Denial of Service Attack

Use when: service is unreachable or severely degraded due to request volume.

- [ ] **Step 1 — Identify the source**:
  ```bash
  docker compose logs backend | grep -E "rate_limit|429" | tail -100
  ```

- [ ] **Step 2 — Mitigate**:

  **If single source IP**: Block at Caddy level by adding to the Caddyfile:
  ```caddyfile
  @attacker remote_ip <source-ip>
  abort @attacker
  ```
  Then reload: `docker compose exec caddy caddy reload --config /etc/caddy/Caddyfile`

  **If distributed**: Reduce rate limits via the admin panel:
  - Navigate to **Admin → Rate Limits**.
  - Lower the soft and hard limits for the `visitor` role.
  - Or, temporarily disable visitor tool access: **Admin → Access** → set
    visitor permissions to disallowed for all tools.

- [ ] **Step 3 — Monitor recovery**:
  ```bash
  watch -n 5 'curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health'
  ```

- [ ] **Step 4 — Post-incident**: Document attack patterns and adjust default
  rate limit values in the `RateLimitConfig` table based on observations.

## 5. Post-Incident Checklist

Complete after every incident, regardless of severity:

- [ ] Postmortem written and stored in `docs/security/postmortem-YYYY-MM-DD.md`.
- [ ] Root cause identified and fixed (or tracked as a GitHub issue).
- [ ] Detection gap closed: new monitoring, alert, or log query added.
- [ ] This runbook updated with lessons learned.
- [ ] New ADR created if the fix required an architectural change.
- [ ] Relevant audit findings updated in [audit-2026-05-18.md](./audit-2026-05-18.md).

## 6. References

- [Secrets Management](./secrets-management.md) — rotation procedures for each secret.
- [Security Audit (2026-05-18)](./audit-2026-05-18.md) — 29 findings with severity ratings.
- [Threat Model](./threat-model.md) — threat inventory and residual risks.
- [ADR-003: Proxy Trust Policy](../adr/003-proxy-trust-policy.md) — relevant for service compromise scenarios.

# SECRET_KEY Rotation — SAKN

**Date**: 2026-05-25
**Status**: Living document — update if SECRET_KEY usage expands beyond sessions + email hashing.

## 1. Purpose

`SECRET_KEY` is the application's master secret, used for:

| Use | Code | Impact of rotation |
|-----|------|--------------------|
| Session token HMAC | `security/tokens.py:hash_token()` | All sessions invalidated (users logged out) |
| Email hash in security logs | `auth_service.py:_hash_email_for_log()` | Correlation broken for pre-rotation log entries |
| CSRF token binding | `security/csrf.py` | All CSRF tokens invalidated (forms rejected until page refresh) |

This document provides rotation procedures for both emergency and planned scenarios.

## 2. When to Rotate

| Trigger | Procedure | Downtime |
|---------|-----------|----------|
| **Suspected compromise** (key leaked, exfiltrated, exposed in logs/config) | Hard rotation (§3) immediately | Yes — all users logged out |
| **Periodic rotation** (every 6–12 months, or per audit requirement) | Double-key rotation (§4) | No — users stay logged in |
| **Pre-audit compliance** (rotation mandated by policy) | Double-key rotation (§4) | No |

**Recommended period**: 6 months for low-risk deployments, 3 months if SECRET_KEY
is used in shared infrastructure or CI secrets.

## 3. Hard Rotation (Emergency / Full Invalidation)

Use when the current key is suspected compromised or when all sessions must be
terminated.

### Pre-flight checklist
- [ ] Notify users of planned service disruption (if not emergency).
- [ ] Schedule during low-traffic window (if planned).
- [ ] Ensure ops has database access (for session cleanup verification).

### Procedure

**Step 1 — Generate new key**
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```
Produces a 43-character base64url string with 256 bits of entropy.

**Step 2 — Update `.env`**
```bash
# Replace SECRET_KEY value
SECRET_KEY=<new-key>
```

**Step 3 — Flush Redis sessions**
```bash
docker compose exec redis redis-cli -a "$REDIS_PASSWORD" FLUSHDB
```

**Step 4 — Delete all sessions from PostgreSQL**
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

**Step 5 — Restart backend**
```bash
docker compose restart backend
```

**Step 6 — Verify health**
```bash
curl -s http://localhost:8000/health
# Expected: {"status":"ok"}
```

### Post-rotation state

| Component | State |
|-----------|-------|
| Sessions | All invalidated. All users must re-authenticate. |
| CSRF tokens | All invalidated. Existing pages must be refreshed to obtain new tokens. |
| SecurityEventLog | Pre-rotation `email_hash` values are permanently bound to the old key. New events use the new key — correlation across the rotation boundary is lost. Old entries expire after the configured retention period (default 90 days). |
| Non-session tokens | Password reset and email verification tokens issued before rotation are invalidated. Users must re-request. |

### Rollback

1. Restore old `SECRET_KEY` in `.env`.
2. Restart backend: `docker compose restart backend`.
3. New sessions created under the new key become invalid — users logged in during
   the rotation window must re-authenticate.

## 4. Double-Key Rotation (Planned / Zero-Downtime)

This approach uses an *old key + new key* window to avoid logging users out.

### Pre-requisites

A configuration change is needed to support dual-key operation:

```python
# config.py — add
OLD_SECRET_KEY: str | None = None  # Set during rotation window
```

```python
# security/tokens.py — verify with fallback
def hash_token(token: str) -> str:
    return hmac.new(settings.SECRET_KEY.encode(), token.encode(), hashlib.sha256).hexdigest()

def verify_token(token: str, stored_hash: str) -> bool:
    current = hash_token(token)
    if secrets.compare_digest(current, stored_hash):
        return True
    # Fallback: try old key during rotation window
    if settings.OLD_SECRET_KEY:
        legacy = hmac.new(
            settings.OLD_SECRET_KEY.encode(), token.encode(), hashlib.sha256
        ).hexdigest()
        if secrets.compare_digest(legacy, stored_hash):
            # Silently upgrade to new key
            upgrade_token_hash(token, current)
            return True
    return False
```

The same pattern applies to `_hash_email_for_log()` for email correlation continuity.

> **Note**: Double-key support is **not currently implemented** in the codebase.
> If zero-downtime rotation becomes a requirement, implement the above as a
> separate engineering task. The 30-day migration window pattern used in
> [ADR-007](../adr/007-session-token-hmac-pepper.md) provides the architectural
> precedent.

### Procedure (once double-key is implemented)

1. Set `OLD_SECRET_KEY=<current-key>` and `SECRET_KEY=<new-key>` in `.env`.
2. Restart backend.
3. Wait for the migration window (≥ 24 hours to cover max session lifetime).
4. Monitor logs: confirm zero fallback verifications with the old key.
5. Remove `OLD_SECRET_KEY` from `.env`.
6. Restart backend.

### Fallback: Manual double-key

If implementing code-level double-key is not feasible, a **manual hard rotation
with notification** is the recommended alternative:

1. Schedule a maintenance window.
2. Announce the window to users (if user-facing).
3. Execute hard rotation (§3).
4. Users re-authenticate — blast radius is one login per active user.

## 5. Impact on SecurityEventLog Correlation

### How email hashing works

```python
def _hash_email_for_log(email: str) -> str:
    normalized = email.strip().lower()
    return hmac.new(settings.SECRET_KEY.encode(), normalized.encode(), hashlib.sha256).hexdigest()
```

The hash is `HMAC-SHA256(SECRET_KEY, normalized_email)`. Same email + same key =
same hash (deterministic). Different key = different hash.

### Correlation before and after rotation

```
┌─────────────────────────────────────────────────────┐
│  Old key                           New key          │
│  ────────────────────────────────────────────────   │
│  email_hash: abc123...  ────▶  email_hash: xyz789...│
│                                       ↑             │
│                          Correlation boundary       │
│                          (cross-boundary matching   │
│                           is impossible)            │
└─────────────────────────────────────────────────────┘
```

**Impact**:
- Attack patterns spanning the rotation boundary become invisible to email-based
  correlation.
- IP-based correlation (`source_ip` field) still works across the boundary.
- Acceptable risk: old entries expire after 90-day retention; the gap closes
  naturally.

### Migration of pre-rotation data

If you need to correlate pre-rotation `email_hash` with post-rotation events,
a one-time migration can re-hash old entries with the new key. This requires:

1. The old `SECRET_KEY` to still be available (to compute `HMAC(old_key, email)`
   → reverse lookup is not possible, but you can re-derive).
2. **Actually, this is impossible**: you cannot recover the email from the hash.
   The migration would need access to the original email, which is not stored
   after hashing.

**Bottom line**: cross-rotation email correlation cannot be restored for old
security event log entries. Plan rotations accordingly — use the hard rotation
for emergency only, and prefer the double-key approach for planned rotations.

## 6. Operational Checklist

Before any rotation:

- [ ] Confirm current `SECRET_KEY` value is backed up (secure password manager).
- [ ] Verify database backups are current.
- [ ] Verify Redis is reachable (`docker compose exec redis redis-cli -a "$REDIS_PASSWORD" PING`).
- [ ] Notify stakeholders of rotation window.
- [ ] Test new key generation: `python -c "import secrets; print(secrets.token_urlsafe(32))"`.

After rotation:

- [ ] Confirm `/health` returns `{"status":"ok"}`.
- [ ] Log in with a test account to verify session creation works.
- [ ] Verify a new security event is logged with the new key (`email_hash` populated).
- [ ] Document the rotation in the deployment log: date, reason, key fingerprint
  (`sha256sum` of the new key — **not** the key itself).
- [ ] Securely delete old key from any temporary storage.

## 7. References

- [ADR-007: HMAC-Peppered Session Token Hashing](../adr/007-session-token-hmac-pepper.md)
- [Secrets Management](./secrets-management.md)
- [Incident Response Runbook](./incident-response.md)
- [Threat Model](./threat-model.md) — Section 5.1 (Authentication), Section 5.2 (Sessions)

# ADR-007: HMAC-Peppered Session Token Hashing

## Status
Accepted (migration completed 2026-05-26, ahead of schedule) — legacy SHA-256
fallback removed

## Context
Session tokens are hashed with plain SHA-256 before storage in PostgreSQL and
Redis (`security/tokens.py:hash_token()`). The `SECRET_KEY` (a 32+ byte CSPRNG
value) is not involved in session token hashing. If both DB and Redis are
simultaneously compromised, token hashes have no domain separation or key
material — brute-forcing the 256-bit token space is infeasible with current
compute, but HMAC peppering would add defence-in-depth (audit finding M-3).

## Decision
Replace plain SHA-256 with HMAC-SHA256(SECRET_KEY, token) for all new tokens.

**Migration strategy — coexistence window**:
1. `hash_token()` now uses HMAC-SHA256 (all new tokens use HMAC).
2. `hash_token_legacy()` preserves the old SHA-256 for backward-compatible
   lookups.
3. Session lookup tries HMAC first, falls back to SHA-256 if not found.
4. When a session is found via legacy SHA-256, it is **silently upgraded**:
   the stored `token_hash` in DB and Redis is replaced with the HMAC version.
   The raw session token (cookie) never changes — users are not logged out.

**Non-session tokens** (email verification, password reset):
These are short-lived (≤24h). They switch to HMAC immediately — old tokens
issued before deployment become invalid. Acceptable blast radius: a handful of
users need to re-request verification or password reset.

**Migration window**: originally planned at 30 days (covers the 24h session TTL
with buffer), with cleanup targeted for 2026-06-20.

**Cleanup completed ahead of schedule (2026-05-26, issue #109)**. Rationale for
accelerating from 30 → 5 days:

- SAKN is **not yet deployed in production** at the time of cleanup. The
  population of users with continuously-active sliding sessions predating the
  HMAC deployment (2026-05-21) is empirically zero.
- 24h absolute TTL plus inactivity timeout means the practical legacy-session
  window is already drained for any realistic dev/test usage.
- The "confirmed zero legacy lookups" check from the original plan was not
  instrumented (no metric / log counter on the legacy branch). Waiting the full
  30 days would have provided no additional verifiable safety in the absence of
  that telemetry — pre-prod context makes the gain marginal vs. carrying the
  fallback code surface area longer.
- If SAKN is later deployed to production with this change already in place,
  there is no legacy session population to worry about — HMAC has been the only
  path from day one of prod.

All legacy code removed in commit `<this PR>`:
- `hash_token_legacy()` — deleted
- `is_legacy_hash()` — deleted
- `verify_token()` legacy fallback — removed
- `_resolve_session()` dual-lookup in middleware — simplified to HMAC-only
- `_upgrade_session_hash()` — deleted
- `migrate_session_hash()` in Redis store — deleted
- `session_service.get()` legacy branch — removed
- `test_legacy_session_authenticates_and_upgrades` — removed

## Consequences
- Session token hashes are now keyed with the application's `SECRET_KEY`.
  An attacker who compromises both DB and Redis cannot verify token hashes
  without also obtaining the `SECRET_KEY`.
- Lookup cost is slightly higher: HMAC computation + potentially one SHA-256
  computation per session resolution. Negligible in practice (both are fast).
- `SECRET_KEY` rotation now invalidates all HMAC-hashed sessions (users must
  re-authenticate). This is documented in `docs/security/secrets-management.md`.
- Audit finding M-3 is mitigated.

## Rollback
1. Revert `tokens.py` to plain SHA-256.
2. Restart the backend.
3. Sessions hashed with HMAC become invalid (users re-login). Legacy SHA-256
   hashes in DB remain valid.
4. No database migration needed — code-only revert.

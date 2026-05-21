# ADR-007: HMAC-Peppered Session Token Hashing

## Status
Accepted — 2026-05-21

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

**Migration window**: 30 days (covers the 24h session TTL with buffer).
After 30 days and confirmed zero legacy lookups, remove `hash_token_legacy()`
and the fallback path from `verify_token()`.

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

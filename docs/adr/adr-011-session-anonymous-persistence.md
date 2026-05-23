# ADR-011: Anonymous Session Persistence

- **Status:** Accepted
- **Date:** 2026-05-23
- **Deciders:** Sprint 8 post-audit

## Context

The current `SessionMiddleware` creates ephemeral anonymous session identifiers
(`anon_{uuid7}`) that exist only in `request.state` for the duration of a single
request. These identifiers are not persisted to the database or Redis, and no
session cookie is returned to the client.

This has several drawbacks:
- No audit trail for anonymous visitors (every request gets a new session ID).
- Rate limiting cannot be consistently applied per-session.
- No ability to trace a visitor through conversion (anonymous → authenticated).
- Anonymous visitors cannot have persistent preferences.

## Decision

Persist anonymous sessions in the `sessions` table with `user_id = NULL` and
return a session cookie to the client.

### Implementation

- **Model:** The `Session` model already supports `user_id IS NULL` (column is
  `nullable=True`). No schema migration needed.
- **Service:** `session_service.create()` already accepts `user_id: str | None`
  and guards concurrent-limit enforcement on `if user_id:`. No changes needed.
- **Middleware:** `SessionMiddleware._create_anonymous_session()` creates a
  persisted session via `session_service.create(user_id=None, ...)`, sets a
  `sakn_session` / `__Host-sakn_session` cookie on the response.
- **Fallback:** If the database is unavailable, the middleware falls back to
  the old ephemeral `anon_{uuid7}` behavior.

### Login transition

When an anonymous user logs in, the `/api/v1/auth/login` endpoint creates a
**new** authenticated session and overwrites the session cookie. The old
anonymous session remains in the database but expires naturally after the
session duration (default 24 hours).

## Consequences

- **Positive:** Full audit trail — every request is traceable to a session ID.
- **Positive:** Consistent rate limiting by session ID instead of IP.
- **Positive:** Enables future features such as anonymous preferences and
  visitor-to-user conversion tracking.
- **Negative:** Increased session table volume. A periodic cleanup job for
  expired anonymous sessions will be needed.
- **Negative:** GDPR considerations — anonymous session cookies must be
  disclosed in the privacy policy. Retention is the same as authenticated
  sessions (24 hours by default).

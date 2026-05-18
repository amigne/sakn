# ADR-002: Enumeration Protection

## Status
Accepted — 2026-05-17

## Context
Public user registration endpoints can be abused to enumerate registered emails. An attacker can submit registration forms and observe response differences to determine whether an email address already has an account.

## Decision
All user-facing authentication responses that could leak existence information return uniform messages:
1. **Registration**: duplicate email returns 200 (same as success), not 409. Internal error code `EMAIL_ALREADY_EXISTS` is logged server-side but never sent to the client.
2. **Login**: invalid credentials and non-existent email return identical error (`INVALID_CREDENTIALS` / `errors.invalid_credentials`) with identical timing.
3. **Password reset**: always returns `auth.reset_email_sent` regardless of whether the email exists.

## Consequences
- Attackers cannot enumerate registered emails via registration, login, or password reset.
- Legitimate users who mistype their email on registration will not be notified that the email is already taken — they will simply not receive a verification email for the duplicate registration.
- Server-side logging retains the real error codes for monitoring and debugging.

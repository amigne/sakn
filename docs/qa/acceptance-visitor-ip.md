# Acceptance Criteria — Visitor IP in Top Bar

> **Version:** 1.0
> **Status:** Draft
> **Date:** 2026-06-05
> **Feature:** Display the visitor's server-perceived IP in the top bar, left of the language switcher.
> **References:** `functional-spec.md` §2.4, `ui-spec.md` §7.4, `spec-api-contract.md` §3.9, `docs/adr/003-proxy-trust-policy.md`

---

## 1. Backend — `GET /auth/whoami`

### AC-MYIP-001 — Endpoint returns the client IP
**Given** the backend is running
**When** `GET /api/v1/whoami` is called
**Then** the response is HTTP 200 with `{"ip": "<address>"}` where `<address>` is the request's `request.client.host`.

### AC-MYIP-002 — No authentication required
**Given** no session cookie is sent (anonymous)
**When** `GET /api/v1/whoami` is called
**Then** the response is HTTP 200 (not 401). The same response shape is returned for authenticated sessions.

### AC-MYIP-003 — Trusted-proxy derivation, not raw header
**Given** `TRUSTED_PROXY_HOPS=1` and a request with `X-Forwarded-For: 1.2.3.4, 203.0.113.7`
**When** `GET /api/v1/whoami` is called through one trusted proxy hop
**Then** `ip` is the trusted-proxy-derived client IP (`203.0.113.7`, the entry at `-trusted_hops`), **not** the leftmost client-controlled value (`1.2.3.4`). The endpoint reads only `request.client.host`.

### AC-MYIP-004 — Spoof resistance with hops = 0
**Given** `TRUSTED_PROXY_HOPS=0` and a request carrying an `X-Forwarded-For` header
**When** `GET /api/v1/whoami` is called
**Then** `ip` is the TCP peer address; the `X-Forwarded-For` header is ignored.

### AC-MYIP-005 — IPv6 supported
**Given** a client connecting over IPv6
**When** `GET /api/v1/whoami` is called
**Then** `ip` is the IPv6 address verbatim.

### AC-MYIP-006 — Unknown address → null
**Given** a request scope without a resolvable client address
**When** `GET /api/v1/whoami` is called
**Then** the response is HTTP 200 with `{"ip": null}` (no error).

### AC-MYIP-007 — No CSRF required (GET)
**Given** no `X-CSRF-Token` header
**When** `GET /api/v1/whoami` is called
**Then** the response is HTTP 200 (read-only GET is not CSRF-protected).

---

## 2. Frontend — Top Bar Element

### AC-MYIP-008 — Displayed left of the language switcher
**Given** any authenticated or anonymous visitor on any page with the top bar
**When** the page loads and `whoami` resolves
**Then** the IP element renders immediately to the left of the language toggle. Order is `[IP] [Lang] [Theme] [User]`.

### AC-MYIP-009 — Shows the resolved address
**Given** `GET /api/v1/whoami` returns `{"ip": "203.0.113.7"}`
**When** the top bar renders
**Then** `203.0.113.7` is displayed (monospace), preceded by the network/globe icon.

### AC-MYIP-010 — Click copies to clipboard
**Given** the IP element is displayed and the Clipboard API is available
**When** the user clicks (or presses Enter/Space on) the element
**Then** the IP is written to the clipboard and feedback (`common.ip_copied`) is shown for ~2 s, then reverts.

### AC-MYIP-011 — Tooltip / accessible name
**Given** the IP element
**When** inspected
**Then** its `title` and accessible name come from `common.your_ip`. The copied feedback is announced via `aria-live="polite"`.

### AC-MYIP-012 — Omitted on failure
**Given** `GET /api/v1/whoami` fails (network error or `ip: null`)
**When** the top bar renders
**Then** the IP element is not rendered (no error text, no placeholder). The rest of the top bar is unaffected.

### AC-MYIP-013 — Hidden below `sm` breakpoint
**Given** a viewport width < 640px
**When** the top bar renders
**Then** the IP element is hidden; the language/theme/user controls remain.

### AC-MYIP-014 — Keyboard focus ring
**Given** keyboard navigation
**When** the IP element receives focus
**Then** a visible focus ring is shown and it is reachable in logical tab order (before the language toggle).

### AC-MYIP-015 — i18n keys present
**Given** the keys `common.your_ip` and `common.ip_copied`
**When** the i18n audit runs
**Then** both keys exist in `fr.json` and `en.json`.

---

## 3. Security / Privacy

### AC-MYIP-016 — No secret/PII beyond the visitor's own address
**Given** the feature is in use
**When** monitoring the `whoami` response
**Then** it contains only the requesting client's own IP — no other user's address, no session token, no server internals.

### AC-MYIP-017 — Header not reflected verbatim
**Given** a request with a crafted `X-Forwarded-For` and `TRUSTED_PROXY_HOPS` smaller than the chain length
**When** `GET /api/v1/whoami` is called
**Then** the returned `ip` is the trusted entry (or TCP peer), never an attacker-chosen leftmost value — preventing reflected-value tricks.

---

## 4. Test Status

| Scope | ACs | Status |
|---|---|---|
| Backend endpoint | AC-MYIP-001 → 007, 016, 017 | Pending |
| Frontend top bar | AC-MYIP-008 → 015 | Pending |

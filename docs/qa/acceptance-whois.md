# Acceptance Criteria — WHOIS Lookup

> **Version:** 1.0
> **Status:** Draft — Sprint 0 (pre-implementation)
> **Date:** 2026-06-05
> **Module:** WHOIS Lookup (`whois`)
> **References:** `functional-spec.md` §3.6, `spec-tool-whois.md`, `ui-spec.md` SCR-27 §5.5, ADR-018, `docs/security/review-whois.md`

---

## 1. Backend Contract (Sprint 1)

### AC-WHOIS-001 — Tool registered in `/tools` response

**Given** the backend is running
**When** `GET /tools` is called
**Then** the response includes an entry with `"name": "whois"`, `"backend": true`, `"category": "network"`, and parameters `target` (required) and `server` (optional) as defined in `spec-tool-whois.md` §1.2

### AC-WHOIS-002 — Seed creates `ToolModule` row

**Given** the application boots for the first time after deployment
**When** the seed runs
**Then** a `ToolModule` row exists with `name="whois"`, `enabled=True`

### AC-WHOIS-003 — Seed creates `RoleToolPermission` rows

**Given** the application boots
**When** the seed runs
**Then** `RoleToolPermission` rows exist for `(visitor, whois)`, `(authenticated, whois)`, and `(administrator, whois)`, all with `allowed=True`

### AC-WHOIS-004 — Admin can disable the tool globally

**Given** an admin sets `ToolModule.enabled=false` for `whois`
**When** any user requests `/tools`
**Then** `whois` is absent from the response. Direct navigation to `/whois` shows "Tool not available."

### AC-WHOIS-005 — Admin can revoke per-role permission

**Given** an admin toggles off the `visitor` permission for `whois`
**When** a visitor requests `/tools`
**Then** `whois` is absent from the response

### AC-WHOIS-006 — Tool removed from sidebar when disabled

**Given** a user's effective permission for `whois` is `false`
**When** the sidebar renders
**Then** "WHOIS" is absent from the sidebar (consistent with existing tool gating, `ui-spec.md` §4.3)

### AC-WHOIS-007 — No migration required

**Given** the `whois` deployment
**When** Alembic runs `alembic upgrade head`
**Then** no new migration is generated (no schema change needed — `ToolModule` table is reused)

### AC-WHOIS-008 — `POST /tools/whois/execute` accepts valid params

**Given** a user with permission to use WHOIS
**When** `POST /api/v1/tools/whois/execute` is called with `{"params": {"target": "example.com"}}`
**Then** the response is HTTP 200 (or an appropriate error for the remote server, not a 4xx validation error)

### AC-WHOIS-009 — `target` parameter is required

**Given** the `whois` tool
**When** `POST /api/v1/tools/whois/execute` is called without `target`
**Then** the response is HTTP 422 with `VALIDATION_ERROR`

### AC-WHOIS-010 — `target` length enforced

**Given** the `whois` tool
**When** `POST /api/v1/tools/whois/execute` is called with `target` > 255 characters
**Then** the response is HTTP 422 with `VALIDATION_ERROR`

### AC-WHOIS-011 — `server` parameter is optional

**Given** the `whois` tool
**When** `POST /api/v1/tools/whois/execute` is called with `{"params": {"target": "example.com"}}` (no `server`)
**Then** the tool proceeds with automatic server selection (no validation error)

---

## 2. RDAP Phase (Sprint 1)

### AC-WHOIS-020 — RDAP query succeeds for a domain with RDAP support

**Given** a domain registered in a TLD that supports RDAP (e.g., `example.com` — Verisign operates `rdap.verisign.com`)
**When** a WHOIS lookup is executed for `example.com`
**Then** the response has `protocol: "rdap"`, `domain: "example.com"`, `registrar` is populated, `status` is a non-empty array, and `creation_date` / `expiration_date` are valid ISO 8601 strings

### AC-WHOIS-021 — RDAP query succeeds for a public IP address

**Given** a public IP address (e.g., `8.8.8.8`)
**When** a WHOIS lookup is executed for `8.8.8.8`
**Then** the response has `protocol: "rdap"` and returns IP ownership data (ARIN/RIPE/APNIC/LACNIC/AFRINIC)

### AC-WHOIS-022 — RDAP JSON is parsed into all expected fields

**Given** a successful RDAP response
**When** the response is parsed
**Then** the output includes `domain`, `status`, `registrar`, `name_servers`, `creation_date`, `expiration_date`, `updated_date` — all fields that exist in the RDAP JSON are mapped correctly (nullable if absent in the source)

### AC-WHOIS-023 — RDAP 404 from authoritative server = not found

**Given** a domain that does not exist (`this-domain-definitely-does-not-exist-2026.invalid`)
**When** a WHOIS lookup is executed
**Then** the response has `success: false` and the frontend renders the "Domain not found" message (i18n: `tools.whois.not_found`). The error code is NOT `WHOIS_CONNECTION_FAILED` (the server responded — the domain just doesn't exist).

### AC-WHOIS-024 — RDAP contact fields are `null` when GDPR-redacted

**Given** a domain with GDPR-redacted RDAP contacts
**When** the RDAP response is parsed
**Then** `registrant`, `admin_contact`, and `tech_contact` are `null` (not the string `"[REDACTED]"`). The frontend renders `[REDACTED]` (i18n: `tools.whois.redacted`) for null contact fields.

### AC-WHOIS-025 — RDAP IANA bootstrap query works

**Given** any valid TLD
**When** the RDAP bootstrap query to `https://rdap.iana.org/domain/<tld>` is executed
**Then** the authoritative RDAP server URL is extracted from the JSON response, and the subsequent RDAP query uses this URL (not a hardcoded server)

---

## 3. WHOIS Fallback (Sprint 1)

### AC-WHOIS-030 — WHOIS fallback triggered when RDAP unavailable

**Given** a TLD that does not support RDAP (IANA bootstrap returns 404 or no RDAP entry)
**When** a WHOIS lookup is executed for a domain in that TLD
**Then** the tool falls back to classic WHOIS on port 43, returns `protocol: "whois"`, and `raw_text` contains the WHOIS server response

### AC-WHOIS-031 — WHOIS response includes structured extraction

**Given** a successful WHOIS fallback
**When** the response is parsed
**Then** best-effort structured fields are extracted: `domain`, `registrar`, `creation_date`, `expiration_date`, `status`, `name_servers`. Fields that cannot be parsed are `null`. `raw_text` is always populated.

### AC-WHOIS-032 — IANA WHOIS reference query works

**Given** a TLD whose WHOIS server is not hardcoded
**When** the WHOIS fallback is triggered
**Then** the tool queries `whois.iana.org` on port 43 with `<tld>\r\n`, parses the `whois:` field from the response, and uses that server for the authoritative WHOIS query

### AC-WHOIS-033 — Thin registry returns raw text

**Given** a thin WHOIS registry (e.g., `.com` — Verisign WHOIS)
**When** the WHOIS response is parsed
**Then** some structured fields may be `null` (thin registries return minimal data). `raw_text` contains the complete WHOIS response including the referral to the registrar's WHOIS server.

### AC-WHOIS-034 — WHOIS response truncated when exceeding size cap

**Given** a WHOIS server that returns > 2 MiB of data
**When** the response size exceeds `settings.WHOIS_MAX_RESPONSE_BYTES`
**Then** the connection is closed, the accumulated data is returned with a `truncated: true` flag, and the frontend displays a truncation warning

---

## 4. Custom `server` Override (Sprint 1)

### AC-WHOIS-040 — Custom server → WHOIS only (no RDAP)

**Given** a `server` parameter is provided (e.g., `"whois.arin.net"`)
**When** a WHOIS lookup is executed
**Then** RDAP is **not** attempted. The tool connects directly to the custom server on port 43. The response has `protocol: "whois"`.

### AC-WHOIS-041 — Custom server for IP lookup

**Given** `target: "8.8.8.8"` with `server: "whois.arin.net"`
**When** a WHOIS lookup is executed
**Then** the tool queries `whois.arin.net` on port 43 with `8.8.8.8\r\n`. The response contains ARIN WHOIS data for the 8.8.8.0/24 block.

### AC-WHOIS-042 — Custom server unreachable

**Given** a custom `server` that is unreachable (e.g., `"whois.nonexistent-server.invalid"`)
**When** a WHOIS lookup is executed
**Then** the response is HTTP 502 with `WHOIS_CONNECTION_FAILED` after timeout

---

## 5. SSRF Security (Sprint 1 — Critical)

### AC-WHOIS-050 — Private target IP blocked

**Given** `target: "127.0.0.1"`
**When** a WHOIS lookup is executed
**Then** the response is HTTP 422 with `TARGET_NOT_ALLOWED`. No network connection is attempted.

### AC-WHOIS-051 — Private target hostname blocked

**Given** `target: "localhost"` (resolves to `127.0.0.1`)
**When** a WHOIS lookup is executed
**Then** the response is HTTP 422 with `TARGET_NOT_ALLOWED`. No network connection is attempted.

### AC-WHOIS-052 — Internal target blocked (RFC 1918)

**Given** `target: "192.168.1.1"`
**When** a WHOIS lookup is executed
**Then** the response is HTTP 422 with `TARGET_NOT_ALLOWED`

### AC-WHOIS-053 — Custom `server` private IP blocked

**Given** `target: "example.com"`, `server: "127.0.0.1"`
**When** a WHOIS lookup is executed
**Then** the response is HTTP 422 with `TARGET_NOT_ALLOWED`. The `server` is validated through `filter_target()` before any connection.

### AC-WHOIS-054 — Custom `server` internal hostname blocked

**Given** `target: "example.com"`, `server: "metadata.google.internal"` (resolves to `169.254.169.254`)
**When** a WHOIS lookup is executed
**Then** the response is HTTP 422 with `TARGET_NOT_ALLOWED`

### AC-WHOIS-055 — Docker bridge IP blocked as target

**Given** `target: "172.17.0.2"` (Docker default bridge — covered by `BLOCKED_NETWORKS`)
**When** a WHOIS lookup is executed
**Then** the response is HTTP 422 with `TARGET_NOT_ALLOWED`

### AC-WHOIS-056 — Docker bridge IP blocked as custom server

**Given** `target: "example.com"`, `server: "172.17.0.2"`
**When** a WHOIS lookup is executed
**Then** the response is HTTP 422 with `TARGET_NOT_ALLOWED`

### AC-WHOIS-057 — RDAP redirect to private IP blocked

**Given** an RDAP server that returns a 302 redirect to a private IP (e.g., `Location: http://10.0.0.1/domain/example.com`)
**When** the redirect is intercepted
**Then** the redirect target hostname is resolved and validated through `filter_target()`. The private IP is blocked, the redirect is NOT followed, and the response is HTTP 502 with `WHOIS_CONNECTION_FAILED`.

### AC-WHOIS-058 — IPv6 loopback blocked as target

**Given** `target: "::1"`
**When** a WHOIS lookup is executed
**Then** the response is HTTP 422 with `TARGET_NOT_ALLOWED`

### AC-WHOIS-059 — IPv6 private (ULA) blocked as custom server

**Given** `target: "example.com"`, `server: "fd00::1"` (Unique Local Address)
**When** a WHOIS lookup is executed
**Then** the response is HTTP 422 with `TARGET_NOT_ALLOWED`

---

## 6. Edge Cases (Sprint 1–2)

### AC-WHOIS-060 — Unsupported TLD

**Given** a TLD for which neither RDAP nor WHOIS servers can be discovered (IANA has no entry)
**When** a WHOIS lookup is executed
**Then** the response is HTTP 422 with `WHOIS_UNSUPPORTED_TLD`

### AC-WHOIS-061 — RDAP connection timeout

**Given** an RDAP server that does not respond within the connect timeout (10s)
**When** a WHOIS lookup is executed
**Then** the tool falls back to WHOIS (Phase 2). If WHOIS also fails, returns `WHOIS_CONNECTION_FAILED`.

### AC-WHOIS-062 — WHOIS connection timeout

**Given** a WHOIS server that does not respond within the connect timeout (15s)
**When** a WHOIS lookup is executed (via fallback or custom server)
**Then** the response is HTTP 502 with `WHOIS_CONNECTION_FAILED`

### AC-WHOIS-063 — RDAP read timeout

**Given** an RDAP server that accepts the connection but does not complete the response within 20s
**When** the read timeout expires
**Then** the tool falls back to WHOIS. If WHOIS also fails, returns `WHOIS_CONNECTION_FAILED`.

### AC-WHOIS-064 — Overall execution deadline enforced

**Given** a query that takes longer than 60 seconds (cumulative across all phases)
**When** the deadline is exceeded
**Then** the query is cancelled and the response is HTTP 502 with `WHOIS_CONNECTION_FAILED`

### AC-WHOIS-065 — WHOIS protocol injection prevented

**Given** `target: "example.com\r\nQUIT\r\n"` (injection attempt)
**When** the target is sanitized before being sent over the WHOIS socket
**Then** `\r` and `\n` are stripped. The query sent is `example.com\r\n`. The injection is neutralized.

### AC-WHOIS-066 — Target with only control characters rejected

**Given** `target: "\r\n\r\n"` (all control characters)
**When** the target is sanitized
**Then** the sanitized result is empty. The tool returns a validation error (HTTP 422).

### AC-WHOIS-067 — RDAP redirect loop detection (max 3 redirects)

**Given** an RDAP server that returns a chain of 4+ redirects
**When** the 4th redirect is encountered
**Then** the redirect is NOT followed. The tool falls back to WHOIS or returns `WHOIS_CONNECTION_FAILED`.

### AC-WHOIS-068 — IDN domain (Unicode) accepted

**Given** `target: "xn--xample-9ua.com"` (Punycode) or `target: "éxample.com"` (Unicode)
**When** a WHOIS lookup is executed
**Then** the domain is accepted and processed (Punycode conversion handled automatically for RDAP; WHOIS servers typically accept Punycode)

---

## 7. Timeouts & Resource Limits (Sprint 1–2)

### AC-WHOIS-070 — RDAP connect timeout configurable

**Given** `settings.WHOIS_RDAP_CONNECT_TIMEOUT = 5` (overridden from default 10s)
**When** an RDAP connection is attempted
**Then** the connect timeout is 5 seconds

### AC-WHOIS-071 — WHOIS connect timeout configurable

**Given** `settings.WHOIS_TCP_CONNECT_TIMEOUT = 10` (overridden from default 15s)
**When** a WHOIS connection is attempted
**Then** the connect timeout is 10 seconds

### AC-WHOIS-072 — Response size cap configurable

**Given** `settings.WHOIS_MAX_RESPONSE_BYTES = 1048576` (1 MiB)
**When** a WHOIS response is read
**Then** the cap is 1 MiB (not the default 2 MiB)

### AC-WHOIS-073 — DNS resolution timeout applied

**Given** a target hostname whose DNS resolution takes longer than 10 seconds (global DNS timeout)
**When** `filter_target()` is called
**Then** the resolution is cancelled after 10s and `errors.dns_resolution_failed` is returned

---

## 8. No New Dependencies (Sprint 1)

### AC-WHOIS-080 — No new PyPI packages

**Given** the WHOIS tool implementation
**When** `uv pip list` is compared before and after
**Then** no new packages are added. The tool uses only `httpx` (existing), `asyncio` (stdlib), `json` (stdlib), `re` (stdlib), and `ipaddress` (stdlib).

### AC-WHOIS-081 — No subprocess execution

**Given** any WHOIS query
**When** the tool executes
**Then** no subprocess is spawned (`subprocess.run`, `asyncio.create_subprocess_exec`, etc.). All network I/O is performed via `httpx` and `asyncio.open_connection`.

---

## 9. UI (Sprint 3)

### AC-WHOIS-100 — WHOIS page renders at `/whois`

**Given** the tool is enabled and the user has permission
**When** the user navigates to `/whois`
**Then** the WHOIS Lookup page renders with the Target input, Advanced toggle (collapsed), Start button, and empty output panel

### AC-WHOIS-101 — Start button initiates execution

**Given** a valid `target` is entered
**When** the user clicks "Start" (or presses Enter)
**Then** a `POST /api/v1/tools/whois/execute` request is sent. The Start button becomes disabled with a spinner. The output panel shows the loading state with elapsed time.

### AC-WHOIS-102 — RDAP result displays structured fields

**Given** a successful RDAP response
**When** the result is rendered
**Then** the protocol badge shows "RDAP" (blue). Structured fields are rendered as label: value pairs as specified in `ui-spec.md` §5.5.5. `null` fields are hidden or displayed as `[REDACTED]`. Dates are locale-formatted.

### AC-WHOIS-103 — WHOIS result displays raw text

**Given** a successful WHOIS fallback response
**When** the result is rendered
**Then** the protocol badge shows "WHOIS" (yellow). Structured fields are rendered (best-effort). The raw text block is displayed in a monospace, scrollable container, expanded by default.

### AC-WHOIS-104 — Copy button copies structured + raw text

**Given** a result is displayed
**When** the user clicks "Copy"
**Then** the clipboard contains formatted text: structured fields as `Label: Value` pairs, followed by the raw WHOIS text if present. A "Copied!" confirmation is shown.

### AC-WHOIS-105 — Advanced toggle reveals WHOIS Server field

**Given** the WHOIS page is rendered
**When** the user clicks the "Advanced" toggle
**Then** the `WHOIS Server` field is revealed with the helper text "Leave empty for automatic server selection."

### AC-WHOIS-106 — Domain not found message displayed

**Given** the backend returns `success: false` with `not_found: true`
**When** the response is rendered
**Then** a yellow warning banner displays "Domain not found." (i18n: `tools.whois.not_found`)

### AC-WHOIS-107 — Error banner for unsupported TLD

**Given** the backend returns `WHOIS_UNSUPPORTED_TLD` (422)
**When** the response is rendered
**Then** a red error banner displays "This TLD is not supported by any known WHOIS or RDAP server." The Start button is re-enabled.

### AC-WHOIS-108 — Error banner for connection failure

**Given** the backend returns `WHOIS_CONNECTION_FAILED` (502)
**When** the response is rendered
**Then** a red error banner displays "Could not connect to the remote server." The Start button is re-enabled.

### AC-WHOIS-109 — Truncation warning displayed

**Given** the backend returns `truncated: true`
**When** the response is rendered
**Then** a yellow warning banner displays "The response was truncated because it exceeded the maximum size." The raw text block shows the truncated data.

### AC-WHOIS-110 — Desktop layout (≥ 1024px)

**Given** a viewport width of 1200px
**When** the WHOIS page renders
**Then** the layout is two-panel vertical: Parameters (top) + Output (bottom). The sidebar is expanded.

### AC-WHOIS-111 — Mobile layout (< 768px)

**Given** a viewport width of 375px
**When** the WHOIS page renders
**Then** the layout is single-column stacked. All touch targets (Start button, Copy button, Advanced toggle) are ≥ 44×44px. The raw text block has `max-height: 250px`.

---

## 10. i18n (Sprint 3)

### AC-WHOIS-120 — French locale

**Given** the user's language is `fr`
**When** the WHOIS page renders
**Then** all labels, messages, badges, and error banners are in French. The protocol badges show "RDAP" and "WHOIS" (unchanged — protocol names are not translated). `[REDACTED]` is displayed as `[CONFIDENTIEL]` (i18n: `tools.whois.redacted`).

### AC-WHOIS-121 — English locale

**Given** the user's language is `en`
**When** the WHOIS page renders
**Then** all labels, messages, badges, and error banners are in English. `[REDACTED]` is displayed as `[REDACTED]`.

### AC-WHOIS-122 — All i18n keys present

**Given** the keys listed in `spec-tool-whois.md` §11 and `spec-api-contract.md` §10.3
**When** the i18n key audit runs
**Then** all `tools.whois.*` (26 keys) and `errors.whois_*` (2 keys) exist in both `fr.json` and `en.json`. Total: 28 keys. The 3 UI-state keys added in Sprint 0 (`tools.whois.idle`, `tools.whois.trying_rdap`, `tools.whois.fallback_whois`, for the two-phase loading UX) are registered in `spec-api-contract.md` §10.3; the rest pre-existed. Sprint 3 adds them all to `en.json`/`fr.json`.

---

## 11. Accessibility (Sprint 3+)

### AC-WHOIS-130 — All controls have labels

**Given** the WHOIS page
**When** inspected with a screen reader
**Then** every input (`target`, `server`) has an associated `<label>` element. The Advanced toggle has `aria-expanded`. The `server` field has `aria-describedby` pointing to the helper text.

### AC-WHOIS-131 — Result announced to screen readers

**Given** a screen reader is active
**When** a WHOIS result is rendered
**Then** the output panel's `aria-live="polite"` region announces: "WHOIS lookup complete. Protocol: [RDAP/WHOIS]. Domain: [domain]."

### AC-WHOIS-132 — Error announced assertively

**Given** a screen reader is active
**When** an error is returned (e.g., `WHOIS_UNSUPPORTED_TLD`)
**Then** the error banner's `aria-live="assertive"` region announces the error message immediately

### AC-WHOIS-133 — Keyboard navigation for raw text block

**Given** a WHOIS result with raw text
**When** the user presses Tab
**Then** the raw text block is focusable (`tabindex="0"`) and scrollable via arrow keys

### AC-WHOIS-134 — Focus order is logical

**Given** the WHOIS page (desktop)
**When** the user presses Tab repeatedly
**Then** the focus order is: Target → Advanced toggle → (WHOIS Server if expanded) → Start → Reset → (result area: Copy, then raw text block if present). No focus trap.

---

## 12. Cross-References

| Source | Sections |
|---|---|
| `functional-spec.md` | §3.6 (WHOIS Lookup) |
| `spec-tool-whois.md` | Full technical specification |
| `ui-spec.md` | SCR-27, §5.5 |
| `spec-api-contract.md` | §9 (error codes), §10.3 (i18n keys) |
| `docs/adr/ADR-018-whois-resolution-and-ssrf-policy.md` | Architectural decision |
| `docs/security/review-whois.md` | Security review |
| `app/security/address_filter.py` | `filter_target()` — SSRF defense |

---

## 13. AC Summary

| Category | AC Range | Count |
|---|---|---|
| Backend Contract | AC-WHOIS-001 → 011 | 11 |
| RDAP Phase | AC-WHOIS-020 → 025 | 6 |
| WHOIS Fallback | AC-WHOIS-030 → 034 | 5 |
| Custom Server | AC-WHOIS-040 → 042 | 3 |
| SSRF Security | AC-WHOIS-050 → 059 | 10 |
| Edge Cases | AC-WHOIS-060 → 068 | 9 |
| Timeouts | AC-WHOIS-070 → 073 | 4 |
| No New Deps | AC-WHOIS-080 → 081 | 2 |
| UI | AC-WHOIS-100 → 111 | 12 |
| i18n | AC-WHOIS-120 → 122 | 3 |
| Accessibility | AC-WHOIS-130 → 134 | 5 |
| **Total** | | **70** |

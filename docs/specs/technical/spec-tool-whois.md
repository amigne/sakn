# WHOIS Lookup Tool Specification

> **Version:** 1.0
> **Status:** Draft — Sprint 0 (spec consolidation)
> **Date:** 2026-06-05
> **Module:** WHOIS Lookup (`whois`)
> **References:** `functional-spec.md` §3.6, `spec-tools-instant.md` §5–6, `spec-api-contract.md` §9–10, `ui-spec.md` SCR-27, ADR-018

The WHOIS Lookup is a **backend tool**: the user submits a `target` (domain or IP) and an optional custom `server`, the backend executes a two-phase RDAP/WHOIS query, and returns structured ownership data plus raw text fallback.

---

## 1. Backend Tool Contract

### 1.1 Tool Registration

`WhoisLookupTool` extends `BaseTool` with `backend=True` (the default). It defines its parameters, category, and version via `get_definition()` and implements `execute()` for the backend logic.

### 1.2 `GET /tools` Response

```json
{
  "name": "whois",
  "display_name_key": "tools.whois.name",
  "description_key": "tools.whois.description",
  "category": "network",
  "version": "1.0.0",
  "backend": true,
  "parameters": [
    {
      "name": "target",
      "type": "string",
      "label_key": "tools.whois.param_target_label",
      "description_key": "tools.whois.param_target_desc",
      "required": true,
      "default": null,
      "constraints": {"max_length": 255}
    },
    {
      "name": "server",
      "type": "string",
      "label_key": "tools.whois.param_server_label",
      "description_key": "tools.whois.param_server_desc",
      "required": false,
      "default": null,
      "constraints": {"max_length": 255}
    }
  ]
}
```

### 1.3 `POST /tools/whois/execute`

**Request**:
```json
{
  "params": {
    "target": "example.com",
    "server": null
  }
}
```

**Response** (200 OK — RDAP success):
```json
{
  "tool": "whois",
  "success": true,
  "duration_ms": 345.2,
  "data": {
    "protocol": "rdap",
    "domain": "example.com",
    "status": ["clientDeleteProhibited", "clientTransferProhibited"],
    "registrar": "Example Registrar, Inc.",
    "whois_server": "whois.example-registrar.com",
    "name_servers": ["ns1.example.com", "ns2.example.com"],
    "creation_date": "1995-08-14T04:00:00Z",
    "expiration_date": "2027-08-13T04:00:00Z",
    "updated_date": "2026-01-15T08:30:00Z",
    "registrant": null,
    "admin_contact": null,
    "tech_contact": null,
    "raw_text": null,
    "disclaimer": "For more information on RDAP..."
  }
}
```

**Response** (200 OK — WHOIS fallback):
```json
{
  "tool": "whois",
  "success": true,
  "duration_ms": 1230.5,
  "data": {
    "protocol": "whois",
    "domain": "example.com",
    "status": ["clientDeleteProhibited"],
    "registrar": "Example Registrar, Inc.",
    "whois_server": null,
    "name_servers": ["ns1.example.com"],
    "creation_date": "1995-08-14T04:00:00Z",
    "expiration_date": "2027-08-13T04:00:00Z",
    "updated_date": null,
    "registrant": null,
    "admin_contact": null,
    "tech_contact": null,
    "raw_text": "Domain Name: EXAMPLE.COM\nRegistry Domain ID: ...\n...",
    "disclaimer": null
  }
}
```

All fields except `protocol`, `domain`, and `raw_text` are **nullable** — they are populated only when successfully parsed from the response.

### 1.4 Error Responses

**Unsupported TLD** (422):
```json
{
  "error": {
    "code": "WHOIS_UNSUPPORTED_TLD",
    "message_key": "errors.whois_unsupported_tld",
    "message": "This TLD is not supported by any known WHOIS or RDAP server.",
    "details": null
  }
}
```

**Connection failed** (502):
```json
{
  "error": {
    "code": "WHOIS_CONNECTION_FAILED",
    "message_key": "errors.whois_connection_failed",
    "message": "Could not connect to the remote WHOIS/RDAP server.",
    "details": null
  }
}
```

**Target not allowed** (422 — SSRF block):
```json
{
  "error": {
    "code": "TARGET_NOT_ALLOWED",
    "message_key": "errors.target_not_allowed",
    "message": "Target not allowed.",
    "details": null
  }
}
```

---

## 2. `WhoisLookupTool` Class

### 2.1 Definition

```python
from app.tools.base import BaseTool, ToolCategory, ToolDefinition, ToolParameter


class WhoisLookupTool(BaseTool):
    """WHOIS lookup tool — RDAP-first with WHOIS/43 fallback."""

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="whois",
            display_name_key="tools.whois.name",
            description_key="tools.whois.description",
            category=ToolCategory.NETWORK,
            version="1.0.0",
            backend=True,
            parameters=[
                ToolParameter(
                    name="target",
                    type="string",
                    label_key="tools.whois.param_target_label",
                    description_key="tools.whois.param_target_desc",
                    required=True,
                    default=None,
                    constraints={"max_length": 255},
                ),
                ToolParameter(
                    name="server",
                    type="string",
                    label_key="tools.whois.param_server_label",
                    description_key="tools.whois.param_server_desc",
                    required=False,
                    default=None,
                    constraints={"max_length": 255},
                ),
            ],
        )
```

### 2.2 `execute()` Signature

```python
async def execute(self, params: dict[str, Any], context: ExecutionContext) -> ToolResult:
```

The method is `async` because it performs network I/O (HTTP requests via `httpx`, TCP connections via `asyncio`). The `ExecutionContext` provides the user's role and session for logging/rate-limiting.

---

## 3. Execution Algorithm

### 3.1 Phase 0 — Validation & SSRF Check

1. Validate `target` and `server` parameters (type, max length).
2. If `server` is provided:
   - Validate `server` through `filter_target(server)` → block if private/internal.
   - **Skip RDAP entirely** — go directly to Phase 2 (WHOIS) with the custom server.
3. Validate `target` through `filter_target(target)` → block if private/internal.
4. The validated IP from `filter_target()` is retained for DNS rebinding protection (resolve-then-connect).

### 3.2 Phase 1 — RDAP (HTTP)

1. **Bootstrap**: `GET https://rdap.iana.org/domain/<tld>` or `GET https://rdap.iana.org/ip/<ip>`.
   - Extract the authoritative RDAP server URL from the JSON response.
   - If IANA returns 404 or the TLD/IP has no RDAP entry → fallback to Phase 2.
2. **Authoritative query**: `GET <authoritative_rdap_url>/domain/<domain>` or `/ip/<ip>`.
   - `Accept: application/rdap+json`.
   - Timeout: **10s connect, 20s total read** (from `spec-tools-instant.md` §6).
3. **Redirect handling**: If the authoritative server returns 3xx:
   - Extract the `Location` header.
   - Resolve the redirect target hostname.
   - **Re-validate** through `filter_target()` before following.
   - Follow at most **3 redirects** (prevent redirect loops).
4. **Success**: Parse JSON response → map to structured fields (see §4.1) → return with `protocol: "rdap"`.
5. **Failure** (404, connection error, timeout, non-JSON response, private redirect): → fallback to Phase 2.

### 3.3 Phase 2 — WHOIS Fallback (TCP port 43)

1. **Server discovery** (if no custom `server`):
   - Query `whois.iana.org` on port 43 with `tld\r\n` to get the TLD's authoritative WHOIS server.
   - Parse the response for the `whois:` field (standard IANA WHOIS reference format).
   - If no WHOIS server found → return `WHOIS_UNSUPPORTED_TLD`.
2. **Server validation**: Resolve the WHOIS server hostname and validate through `filter_target()`.
3. **Connection**: `asyncio.open_connection(validated_ip, 43)`.
   - Timeout: **15s connect, 20s total read** (from `spec-tools-instant.md` §6).
4. **Query**: Send `{sanitized_target}\r\n` (control characters stripped, see §3.4).
5. **Read**: Accumulate response data until the server closes the connection.
   - **Size cap**: 2 MiB default (`settings.WHOIS_MAX_RESPONSE_BYTES`, configurable).
   - If the cap is exceeded, close the connection and return truncated data with a warning flag.
6. **Parse**: Best-effort structured extraction (see §4.2). Always include `raw_text`.
7. **Return**: Structured fields + `raw_text`, with `protocol: "whois"`.

### 3.4 Target Sanitization for WHOIS Protocol

Before sending over the TCP socket, the `target` string is sanitized:

```python
import re

def sanitize_whois_target(target: str) -> str:
    """Strip control characters to prevent WHOIS protocol injection."""
    # Remove \r, \n, and all control chars below 0x20 except space (0x20)
    sanitized = re.sub(r'[\x00-\x1f]', '', target)
    if not sanitized.strip():
        raise ValueError("Target is empty after sanitization")
    return sanitized
```

The query sent is always: `f"{sanitized}\r\n"` — exactly one command, one CRLF.

---

## 4. Response Parsing

### 4.1 RDAP JSON → Structured Fields

RDAP responses follow RFC 7483 (JSON Responses). Mapping:

| RDAP JSON path | Output field | Fallback |
|---|---|---|
| `ldhName` or `handle` | `domain` | Input `target` |
| `status[]` | `status` | `[]` |
| `entities[?role=registrar].vcardArray` | `registrar` | `null` |
| `nameservers[].ldhName` | `name_servers` | `[]` |
| `events[?action=registration].eventDate` | `creation_date` | `null` |
| `events[?action=expiration].eventDate` | `expiration_date` | `null` |
| `events[?action=last changed].eventDate` | `updated_date` | `null` |
| `entities[?role=registrant].vcardArray` | `registrant` | `null` — GDPR-redacted → `null` |
| `entities[?role=administrative].vcardArray` | `admin_contact` | `null` — GDPR-redacted → `null` |
| `entities[?role=technical].vcardArray` | `tech_contact` | `null` — GDPR-redacted → `null` |
| `notices[?title=Terms of Service].description` | `disclaimer` | `null` |

**GDPR handling**: When contact entities contain only a "redacted" notice or are absent, the contact fields are `null`. The frontend displays `[REDACTED]` (i18n: `tools.whois.redacted`) for null contact fields. The backend does **not** return the string `"[REDACTED]"` — it returns `null`, and the frontend renders the appropriate label.

**Domain-not-found detection**: RDAP returns HTTP 404 with an error response body. The tool detects this and returns `success=False` with the `not_found` flag rather than falling back to WHOIS (a 404 from the authoritative RDAP server means the domain does not exist, not that RDAP is unsupported).

### 4.2 WHOIS Raw Text → Best-Effort Structured Fields

Classic WHOIS responses are unstructured. The parser uses regex-based extraction for common patterns:

| Pattern | Field | Regex (simplified) |
|---|---|---|
| `Domain Name: VALUE` | `domain` | `(?i)Domain Name:\s*(.+)` |
| `Registrar: VALUE` | `registrar` | `(?i)Registrar:\s*(.+)` |
| `Name Server: VALUE` | `name_servers` | `(?i)Name Server:\s*(.+)` (multi-line) |
| `Creation Date: VALUE` | `creation_date` | `(?i)Creation Date:\s*(.+)` |
| `Registry Expiry Date: VALUE` | `expiration_date` | `(?i)(?:Registry )?Expir\w+ Date:\s*(.+)` |
| `Updated Date: VALUE` | `updated_date` | `(?i)Updated Date:\s*(.+)` |
| `Domain Status: VALUE` | `status` | `(?i)Domain Status:\s*(.+)` (multi-line) |
| `Registrant.*` (multi-line block) | `registrant` | Best-effort block extraction |
| `Admin.*` (multi-line block) | `admin_contact` | Best-effort block extraction |
| `Tech.*` (multi-line block) | `tech_contact` | Best-effort block extraction |

**Design principle**: Parsing is **best-effort**. Fields that cannot be parsed are `null`. The `raw_text` field is **always** populated for WHOIS responses, so the user always has the complete data. The structured fields are a convenience, not a guarantee.

**Thin registry handling** (e.g., `.com`): Thin WHOIS registries return only the domain statuses, nameservers, and dates — no contact data. The parser extracts what it can; the rest is in `raw_text`.

---

## 5. SSRF Integration

### 5.1 Filter Target Usage

Three calls to `filter_target()` per query (typical RDAP + WHOIS path):

| Call | Input | When | Error on block |
|---|---|---|---|
| 1 | `target` parameter | Phase 0 | `TARGET_NOT_ALLOWED` |
| 2 | RDAP authoritative server hostname | Phase 1 (before RDAP `GET`) | `WHOIS_CONNECTION_FAILED` (logged internally as SSRF block) |
| 3 | WHOIS server hostname (auto or custom) | Phase 2 (before TCP connect) | `TARGET_NOT_ALLOWED` if `server` was user-provided; `WHOIS_CONNECTION_FAILED` if auto-discovered |
| 4+ | RDAP redirect target hostname(s) | Phase 1 (before following each 3xx) | `WHOIS_CONNECTION_FAILED` |

### 5.2 Resolve-Then-Connect Pattern

**RDAP (HTTPS) — pin the validated IP WITHOUT breaking TLS.** The connection must go
to the pre-validated IP (DNS-rebinding defense) **while** the URL keeps the **hostname**
so that SNI and certificate verification still apply. Do **not** put the IP in the URL,
do **not** override the `Host` header, and **never** disable `verify`. In `httpx`, pin
the IP via a custom transport whose connection pool resolves the hostname to the
already-validated IP:

```python
# For RDAP (httpx) — IP-pinned but TLS-verified against the hostname.
resolved_ip, block_error = await filter_target(rdap_hostname)
if block_error:
    return ToolResult(success=False, error=block_error)

# Custom transport: keep the hostname in the URL (SNI + cert verification stay on
# `rdap_hostname`) but force the socket to connect to `resolved_ip`. Implemented by
# subclassing httpx.AsyncHTTPTransport / injecting an httpcore pool whose resolver
# returns `resolved_ip` for `rdap_hostname`. verify=True (default) MUST be kept.
transport = IPPinnedTransport(host=rdap_hostname, pinned_ip=resolved_ip)
async with httpx.AsyncClient(transport=transport, verify=True) as client:
    # URL uses the hostname — TLS validates the cert for rdap_hostname.
    response = await client.get(f"https://{rdap_hostname}/domain/{domain}")

# For WHOIS (asyncio) — plain TCP, no TLS, so connect straight to the validated IP.
resolved_ip, block_error = await filter_target(whois_hostname)
if block_error:
    return ToolResult(success=False, error=block_error)
reader, writer = await asyncio.wait_for(
    asyncio.open_connection(resolved_ip, 43),
    timeout=15.0,
)
```

The connection always targets the validated IP (DNS-rebinding defense, ADR-018 §B.5).
For RDAP this is done **without** weakening TLS: the cert is verified against
`rdap_hostname` and SNI carries the hostname. **MUST NOT**: put the IP in the HTTPS
URL, spoof the `Host` header against a mismatched cert, or set `verify=False`. See
`review-whois.md` §2.4. (For WHOIS over plain TCP there is no TLS, so connecting
directly to the IP is correct.)

### 5.3 Usage Model

Follows the same pattern as `ssl_viewer.py:96`:

```python
# Validate target through shared SSRF filter
resolved_ip, block_error = await filter_target(target)
if block_error:
    return ToolResult(success=False, error=block_error)
```

---

## 6. Timeouts & Resource Limits

| Limit | Value | Configurable | Reference |
|---|---|---|---|
| RDAP HTTP connect timeout | 10s | `settings.WHOIS_RDAP_CONNECT_TIMEOUT` | `spec-tools-instant.md` §6 |
| RDAP HTTP read timeout | 20s | `settings.WHOIS_RDAP_READ_TIMEOUT` | `spec-tools-instant.md` §6 |
| WHOIS TCP connect timeout | 15s | `settings.WHOIS_TCP_CONNECT_TIMEOUT` | `spec-tools-instant.md` §6 |
| WHOIS TCP read timeout | 20s | `settings.WHOIS_TCP_READ_TIMEOUT` | `spec-tools-instant.md` §6 |
| WHOIS response size cap | 2 MiB | `settings.WHOIS_MAX_RESPONSE_BYTES` | Security review §2.5 |
| Max RDAP redirects | 3 | Hardcoded | ADR-018 §B.4 |
| DNS resolution timeout | 10s (global DNS timeout) | `settings.SECURITY_DNS_TIMEOUT` | `address_filter.py:140` |
| `target` max length | 255 chars | Hardcoded (same as other tools) | `functional-spec.md` §3.6.2 |
| `server` max length | 255 chars | Hardcoded | `functional-spec.md` §3.6.2 |

### 6.1 Cumulated Timeout Budget

Worst-case query duration (all phases sequential):

| Phase | Step | Max Time |
|---|---|---|
| 0 | `filter_target(target)` + `filter_target(server)` | 10s (DNS) |
| 1 | IANA RDAP bootstrap | 20s |
| 1 | Authoritative RDAP query | 20s |
| — | RDAP fails → fallback | — |
| 2 | IANA WHOIS reference query | 20s |
| 2 | TLD WHOIS server query | 20s |
| **Total worst case** | | **~90s** |

In practice, a fast path (RDAP success) completes in < 1s. A WHOIS fallback without IANA reference (server already known from bootstrap) completes in 2–5s. The worst case is rare.

An **overall execution deadline** of **60 seconds** is enforced at the `execute()` level via `asyncio.wait_for()` to prevent runaway queries. This is a defense-in-depth measure below the HTTP request timeout.

---

## 7. Error Mapping

| Condition | HTTP | Error Code | message_key |
|---|---|---|---|
| Target is private/internal IP | 422 | `TARGET_NOT_ALLOWED` | `errors.target_not_allowed` |
| Custom `server` is private/internal IP | 422 | `TARGET_NOT_ALLOWED` | `errors.target_not_allowed` |
| TLD has no known RDAP or WHOIS server | 422 | `WHOIS_UNSUPPORTED_TLD` | `errors.whois_unsupported_tld` |
| Domain does not exist (RDAP 404) | 200 | (success=False, not_found=True) | `tools.whois.not_found` |
| Cannot connect to RDAP/WHOIS server | 502 | `WHOIS_CONNECTION_FAILED` | `errors.whois_connection_failed` |
| RDAP/WHOIS timeout | 502 | `WHOIS_CONNECTION_FAILED` | `errors.whois_connection_failed` |
| RDAP redirect to private IP | 502 | `WHOIS_CONNECTION_FAILED` | `errors.whois_connection_failed` |
| WHOIS response truncated (size cap) | 200 | (success=True, truncated=True) | (warning in UI) |
| Overall execution deadline exceeded | 502 | `WHOIS_CONNECTION_FAILED` | `errors.whois_connection_failed` |
| Tool disabled / role not allowed | 403 | `TOOL_DISABLED` / `ROLE_NOT_ALLOWED` | (standard error keys) |

---

## 8. Registration & Seed

### 8.1 Registry Registration

In `src/backend/app/main.py`, add:

```python
from app.tools.whois import WhoisLookupTool

# In the registry block:
registry.register(WhoisLookupTool())
```

### 8.2 Seed Behavior

The existing seed loop (in `main.py`) handles `WhoisLookupTool` automatically:
- Creates `ToolModule` row (`name="whois"`, `enabled=True`)
- Creates `RoleToolPermission` rows for `visitor`, `authenticated`, `administrator` with `allowed=True`

### 8.3 No Migration

No Alembic migration is needed. The `ToolModule` and `RoleToolPermission` tables are reused. The seed creates the new rows on first boot after deployment (idempotent — no-op if rows already exist).

### 8.4 Admin Integration

- The tool appears in Admin > Modules with an Enabled toggle.
- Permission matrix (visitor/authenticated/admin) works identically to other tools.
- No status icon (no `has_status` flag).
- No settings gear (no `has_settings` flag — `WHOIS_MAX_RESPONSE_BYTES` and timeouts are configured via environment variables, not the admin UI).

---

## 9. Dependencies

**No new dependencies.** The tool uses:

| Dependency | Usage | Already in project |
|---|---|---|
| `httpx` | Async HTTP client for RDAP requests | Yes (test suite) |
| `asyncio` | Async TCP for WHOIS connections, timeouts, overall deadline | Yes (stdlib) |
| `json` | RDAP JSON response parsing | Yes (stdlib) |
| `re` | WHOIS text parsing, target sanitization | Yes (stdlib) |
| `ipaddress` | IP validation in `filter_target()` | Yes (stdlib) |

---

## 10. Files Touched (Sprint 1 — Backend Contract)

| File | Change |
|---|---|
| `src/backend/app/tools/whois.py` | **New file**: `WhoisLookupTool` class with `get_definition()` and `execute()` |
| `src/backend/app/main.py` | Register `WhoisLookupTool` in the registry |
| `src/backend/app/config.py` | Add WHOIS settings (timeouts, response size cap) |
| `src/backend/app/models/tool_module.py` | No change — schema unchanged |
| `src/frontend/src/...` | **Not touched this sprint** — Sprint 3+ |

---

## 11. i18n Keys (Complete List)

Per `spec-api-contract.md` §10.3. All keys already exist in both `fr.json` and `en.json` (verified against the API contract). **No new keys are needed** — the existing catalog covers all WHOIS UI elements and error states.

```
tools.whois.name
tools.whois.description
tools.whois.param_target_label
tools.whois.param_target_desc
tools.whois.param_server_label
tools.whois.param_server_desc
tools.whois.result_domain
tools.whois.result_status
tools.whois.result_registrar
tools.whois.result_creation_date
tools.whois.result_expiration_date
tools.whois.result_updated_date
tools.whois.result_nameservers
tools.whois.result_registrant
tools.whois.result_admin_contact
tools.whois.result_tech_contact
tools.whois.result_raw_text
tools.whois.result_protocol
tools.whois.protocol_rdap
tools.whois.protocol_whois
tools.whois.not_found
tools.whois.redacted
tools.whois.unsupported_tld

errors.whois_unsupported_tld
errors.whois_connection_failed
```

**Key count**: 24 `tools.whois.*` + 2 `errors.whois_*` = **26 keys total**. All pre-existing in the API contract. No additions needed.

---

## 12. References

| Source | Sections |
|---|---|
| `functional-spec.md` | §3.6 (WHOIS Lookup) |
| `spec-tools-instant.md` | §5 (WHOIS execution strategy), §6 (timeouts) |
| `spec-api-contract.md` | §9 (error codes), §10.3 (i18n keys) |
| `ui-spec.md` | SCR-27, §5 (output display) |
| `docs/adr/ADR-018-whois-resolution-and-ssrf-policy.md` | RDAP/WHOIS strategy, SSRF policy, dependency decision |
| `docs/security/review-whois.md` | Security review |
| `app/security/address_filter.py` | `filter_target()` — shared SSRF defense |
| `app/tools/ssl_viewer.py:96` | SSRF filter usage pattern |
| `app/tools/base.py` | `BaseTool`, `ToolDefinition`, `ToolParameter`, `ToolCategory` |
| `app/main.py:90-147` | Registry + seed pattern |

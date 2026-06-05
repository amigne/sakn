# ADR-018: WHOIS Resolution Strategy and SSRF Policy

## Status

Proposed — 2026-06-05 (Sprint 0 / spec consolidation)

## Context

SAKN's WHOIS tool (SCR-27) queries domain and IP ownership information. Two protocols exist for this purpose:

1. **RDAP** (Registration Data Access Protocol) — HTTP-based, JSON responses, standardized by IETF (RFC 7480-7485). Provides structured data. Adoption is growing but incomplete: many TLDs and IP registries still lack RDAP support.
2. **Classic WHOIS** (port 43) — Legacy TCP protocol, plain-text responses, no standard format. Universal coverage but unstructured output.

The tool must work for **any** domain or IP the user queries, regardless of registry support. It must also allow power users to specify a custom WHOIS server (bypassing automatic server selection).

Additionally, the tool makes **outbound network connections** to arbitrary third-party servers determined by user input. This creates a **Server-Side Request Forgery (SSRF)** risk: an attacker could use the WHOIS tool as a proxy to scan internal networks or access internal services.

SAKN already has a shared SSRF defense in `app/security/address_filter.py` (`filter_target()`), used by Ping, Traceroute, DNS Lookup, and TLS/SSL Viewer. The WHOIS tool must integrate with this same defense.

## Decision

### Part A: RDAP-First with WHOIS Fallback

**Decision**: The WHOIS tool implements a two-phase protocol strategy:

1. **Phase 1 — RDAP** (attempted first):
   - Query IANA's RDAP bootstrap service (`https://rdap.iana.org/`) to discover the authoritative RDAP server for the target TLD or IP range.
   - Send an HTTP `GET` to the authoritative RDAP server.
   - Parse the JSON response into structured fields.
   - **If RDAP succeeds** (HTTP 200 with valid JSON): return structured data with `protocol: "rdap"`.

2. **Phase 2 — WHOIS fallback** (only if RDAP fails):
   - Determine the appropriate WHOIS server: IANA's WHOIS reference for the TLD, or the user-supplied custom server.
   - Open a TCP connection to port 43, send `domain\r\n`, read the response until the server closes the connection.
   - Return the raw text plus best-effort structured extraction, with `protocol: "whois"`.

3. **Custom `server` override**: When the user provides a `server` parameter, **RDAP is skipped entirely**. The tool connects directly to the custom server on port 43 (classic WHOIS only). This respects the user's explicit intent — if they specify a WHOIS server, they want WHOIS.

**Rationale**:
- RDAP is the modern standard (IETF RFCs). It provides structured, machine-readable data that maps cleanly to the tool's output schema. When available, it produces a better user experience.
- RDAP adoption is incomplete. Many ccTLDs and some gTLDs still lack RDAP. A WHOIS fallback ensures universal coverage.
- The two-phase approach matches the behavior of modern WHOIS clients (e.g., `whois` CLI from ICANN, web-based WHOIS tools). Users expect this.
- The custom `server` override with RDAP-skip gives power users direct control while keeping the default path modern.

**Alternatives considered and rejected**:

| Alternative | Rationale for rejection |
|---|---|
| **WHOIS-only** (no RDAP) | Loses structured data for RDAP-supporting TLDs. Worse UX (raw text for all queries). Ignores industry direction. |
| **RDAP-only** (no WHOIS fallback) | Incomplete coverage — many TLDs have no RDAP. Would require a hardcoded allow-list of RDAP-capable TLDs, which is a maintenance burden. |
| **Parallel RDAP + WHOIS** | Wastes resources. Both protocols query the same underlying registry data. Parallel execution doubles network calls and remote server load for no benefit. |
| **WHOIS-first with RDAP fallback** | Wrong priority. RDAP is the modern protocol; WHOIS is the legacy fallback. Reversing the order would produce raw text for RDAP-capable TLDs when structured data is available. |
| **Separate "RDAP Lookup" and "WHOIS Lookup" tools** | Unnecessary UX complexity. Users don't care about the protocol — they want ownership information. A single tool with a protocol indicator is simpler. |

### Part B: SSRF Policy

**Decision**: The WHOIS tool reuses the existing shared SSRF defense (`filter_target()` from `app/security/address_filter.py`) and extends it with WHOIS-specific protections.

**Rules**:

1. **`target` validation**: The `target` parameter is validated through `filter_target()` before any network connection. If the target is an IP address, it is checked against the blocklist directly. If it is a hostname, it is resolved and each resolved IP is checked.

2. **`server` validation** (custom WHOIS server): When the user provides a custom `server`, its hostname is resolved and checked through `filter_target()` **before** opening the TCP connection. Private/internal WHOIS servers are blocked. This prevents an attacker from specifying `server=127.0.0.1` or `server=internal-service.local` to probe internal networks.

3. **Auto-discovered RDAP/WHOIS servers**: Servers discovered via IANA bootstrap are **also** validated through `filter_target()` before connection. While IANA references legitimate public servers, an attacker controlling DNS could poison resolution. Defense-in-depth: validate every host, even "trusted" ones.

4. **RDAP HTTP redirects**: If an RDAP server responds with a 3xx redirect, the redirect target hostname is resolved and **re-validated** through `filter_target()` before following. This prevents an open-redirect chain from reaching internal IPs.

5. **Resolve-then-connect** (DNS rebinding prevention): For every connection, the hostname is resolved to IP(s) first, the IP(s) are validated through the blocklist, and **then** the connection is opened to the validated IP. This closes the DNS rebinding window: even if the DNS response changes between validation and connection (rebinding attack), the tool connects to the IP it validated, not a fresh DNS result.

6. **No raw IP in RDAP URL path**: The RDAP URL path is constructed from the sanitized domain or IP string. The target is not interpolated directly into the URL without validation (httpx handles URL encoding).

7. **No user-controlled protocol or port**: The protocol (HTTP for RDAP, plain TCP for WHOIS) and port (443 for RDAP, 43 for WHOIS) are fixed. The user cannot specify arbitrary ports or protocols via the `server` parameter — only a hostname or IP.

**Rationale**:
- Reusing `filter_target()` avoids duplicating the blocklist logic and ensures consistent security policy across all tools.
- The hostname resolution step for custom `server` is critical: without it, an attacker could specify `server=127.0.0.1` and reach local services.
- RDAP redirect validation is necessary because IANA bootstrap servers redirect to registry-operated servers. An attacker controlling a malicious registry or exploiting an open redirect could redirect to internal IPs.
- The resolve-then-connect pattern is the standard defense against DNS rebinding (TOCTOU on DNS). SAKN already uses this pattern in `filter_target()` — the returned `resolved_ip` is the validated address used for the connection.

**Alternatives considered and rejected**:

| Alternative | Rationale for rejection |
|---|---|
| **Allowlist of known WHOIS/RDAP servers only** | Incomplete and high-maintenance. There are hundreds of TLD WHOIS servers and dozens of RDAP servers. An allowlist would need constant updates as registries change servers. |
| **No `server` parameter (remove custom server)** | Loss of power-user functionality. Network engineers routinely query specific WHOIS servers (e.g., `whois.arin.net` for IP lookups). Removing this would make the tool less useful for the target audience. |
| **Separate SSRF filter for WHOIS** | Code duplication. The shared `filter_target()` already covers all known private/internal ranges. |
| **SOCKS proxy for outbound WHOIS connections** | Over-engineering. Adds deployment complexity (proxy must be configured, maintained, monitored). The resolve-then-connect pattern provides equivalent protection at lower cost. |

### Part C: No New Dependencies

**Decision**: The WHOIS tool uses **only** the standard library (`asyncio`) and `httpx`, which is already a project dependency (used by the test suite and other modules). No new PyPI packages are introduced.

- **HTTP client**: `httpx` (already in `pyproject.toml`). Handles RDAP requests with timeout support, redirect following, and proper TLS.
- **Async I/O**: `asyncio` (stdlib). Used for the WHOIS TCP connection (open_connection, read with timeout).
- **WHOIS parsing**: Implemented in-app (~100–150 lines). Parses key-value lines (`Key: Value`) and multi-line blocks from classic WHOIS responses. No external WHOIS parsing library is needed — the parsing is best-effort and the raw text is always available.
- **JSON parsing**: `json` (stdlib). RDAP responses are JSON.

**Rationale**:
- Avoids supply-chain risk from a niche WHOIS parsing library.
- Classic WHOIS parsing is straightforward (key-value extraction). A dedicated library would add a dependency for ~100 lines of parsing code.
- `httpx` is already trusted and audited as part of the project's dependency chain.
- `asyncio` is the standard async framework used by FastAPI and the rest of the backend.

**Alternatives considered and rejected**:

| Alternative | Rationale for rejection |
|---|---|
| **`python-whois`** (PyPI) | Adds a new dependency for functionality that can be implemented in ~100 lines. The library has irregular maintenance and pulls in transitive dependencies. |
| **`whois` CLI subprocess** | Violates the project's preference for library-based execution (DNS uses `dnspython`, TLS uses `ssl`+`socket`, not subprocesses). Subprocess WHOIS would require installing the system `whois` package in the Docker image and would be harder to timeout/control. |
| **`aiohttp`** (alternative HTTP client) | Adds a second async HTTP library. `httpx` is already in the project and supports both sync and async usage. |
| **`requests`** (sync HTTP) | Would block the async event loop. `httpx` provides an async client compatible with FastAPI's async execution model. |

## Consequences

### Positive
- **Universal coverage**: RDAP-first with WHOIS fallback ensures the tool works for every TLD and IP registry, past and present.
- **Structured data when available**: RDAP responses are machine-readable JSON — no parsing ambiguity.
- **Power user control**: Custom `server` parameter gives network engineers the flexibility they expect.
- **Consistent security**: Reuses the proven `filter_target()` defense. No new security perimeter to audit.
- **No new attack surface from dependencies**: Using existing `httpx` + stdlib avoids supply-chain risk.

### Negative
- **Two code paths to maintain**: RDAP parsing and WHOIS parsing are separate implementations. RDAP parsing is straightforward (JSON → dict mapping) but adds ~80 lines. WHOIS parsing is best-effort and inherently fragile due to the lack of a standard format.
- **Best-effort WHOIS parsing is imperfect**: Classic WHOIS responses vary wildly between registries. Structured extraction will miss fields or misparse some responses. The raw text fallback ensures the user always has the full data.
- **RDAP bootstrap latency**: The IANA bootstrap query adds one extra HTTP round-trip (~100-300 ms) before the actual RDAP query. This is acceptable for an on-demand tool (not a high-throughput API).
- **Double DNS resolution**: Both the IANA bootstrap hostname and the authoritative RDAP server hostname must be resolved. Each resolution goes through `filter_target()`, adding latency. Acceptable for the same reason.

### Neutral
- The two-phase strategy may evolve as RDAP adoption grows. If RDAP reaches near-universal coverage, the WHOIS fallback could become opt-in (a "Force WHOIS" checkbox rather than automatic fallback). This is a future consideration, not part of the current implementation.

## References

- `functional-spec.md` §3.6 — WHOIS functional requirements
- `docs/specs/technical/spec-tools-instant.md` §5–6 — WHOIS technical outline and timeouts
- `docs/specs/technical/spec-api-contract.md` §9–10 — Error codes and i18n keys
- `app/security/address_filter.py` — Shared SSRF filter (`filter_target()`)
- `app/tools/ssl_viewer.py:96` — Usage pattern for `filter_target()`
- RFC 7480-7485 — RDAP protocol suite
- RFC 3912 — WHOIS protocol specification

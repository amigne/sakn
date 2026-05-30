# Functional Specification — SAKN (Swiss Army Knife for Network Engineers)

> **Version:** 3.0 — New modules (MAC OUI, WHOIS, Secret Generator)
> **Status:** Draft
> **Date:** 2026-05-21

Defines **what** the application does: user roles, tool capabilities, business rules, and constraints. For **how** it is built, see `docs/specs/technical/`. For **how** it looks, see `docs/specs/ui-spec.md`.

---

## 1. Introduction

### 1.1 Product Vision

SAKN is a web application providing a unified interface for network diagnostic and information tools: Ping, Traceroute, DNS Lookup, TLS/SSL Certificate Viewer, MAC OUI Lookup, WHOIS, and a Secret Generator. It replaces the need to install and switch between separate CLI tools and utilities.

### 1.2 Target Users

Network engineers, system administrators, DevOps practitioners, IT support staff, security engineers.

### 1.3 Guiding Principles

- Tools must behave predictably and match CLI counterparts where applicable.
- Security filtering must be strict: internal/private addresses must never be reachable.
- Rate limiting must protect the platform without blocking legitimate usage.
- The application must be operable in English and French.
- The application must support locale-sensitive date, number, and unit formatting.
- The application must support light, dark, and system-preference display modes.

---

## 2. User Roles

### 2.1 Role Definitions

| Role | Identifier | Authenticated | Email Verified | Admin |
|---|---|---|---|---|
| Visitor | `visitor` | No | N/A | No |
| Authenticated User | `authenticated` | Yes | Yes | No |
| Administrator | `administrator` | Yes | Yes | Yes |

### 2.2 Role Hierarchy

Administrators inherit all capabilities of Authenticated Users. Authenticated Users do not inherit Visitor capabilities (sets are independent by design).

### 2.3 Anonymous Access

Visitors can use any tool explicitly enabled for the `visitor` role via the access rights configuration. Default: **deny** if no configuration exists.

---

## 3. Tools

For execution protocols (WebSocket, HTTP, subprocess sandboxing), see `spec-tools-live.md` and `spec-tools-instant.md`. For output display formats, see `docs/specs/ui-spec.md` §5.

### 3.1 Ping

#### 3.1.1 Description

Send ICMP echo requests to a target host and display round-trip statistics.

#### 3.1.2 Input Parameters

| Parameter | Type | Default | Constraints |
|---|---|---|---|
| Target | string (hostname or IP) | (required) | Must pass address validation and security filter. |
| Count | integer | 4 | 0 to 100. 0 = unlimited until Max Duration or user stops. |
| Timeout | integer (seconds) | 10 | 1 to 60. |
| Packet Size | integer (bytes) | 56 | 8 to 65507. |
| DF Bit | boolean | false | Set Don't Fragment flag. |
| DSCP/ToS | integer | 0 | 0 to 63. |
| Max Duration | integer (seconds) | 30 | Whichever limit (count or duration) is reached first ends the execution. No cross-constraint with count. |

#### 3.1.3 Behaviour Rules

- MUST use raw ICMP when the backend has the required capabilities. If ICMP is unavailable, return a permission-denied error — never silently fall back to an alternative protocol.
- Each packet MUST respect the configured timeout. No response within timeout → packet recorded as lost.
- Max Duration is a hard stop: no new packets sent after expiry. In-flight packets at expiry are allowed to complete.
- DF Bit set → MUST prevent IP fragmentation. Path MTU lower than packet size → drop packet and report error.

#### 3.1.4 Edge Cases

- Target resolves to multiple IPs: ping the first address (standard ping behavior).
- IPv4/IPv6 mix: prefer IPv6 unless user explicitly selects IPv4.
- ICMP disabled at OS level: clear error message.
- All packets lost: summary shows 100% loss, no RTT statistics.

### 3.2 Traceroute

#### 3.2.1 Description

Discover the network path to a target host by sending probes with increasing TTL.

#### 3.2.2 Input Parameters

| Parameter | Type | Default | Constraints |
|---|---|---|---|
| Target | string (hostname or IP) | (required) | Must pass address validation and security filter. |
| Protocol | enum | UDP | UDP, ICMP, TCP. |
| Port | integer | 33434 | 1 to 65535. Used for UDP and TCP modes only. |
| Probes per Hop | integer | 3 | 1 to 10. |
| Timeout | integer (seconds) | 1 | 1 to 30. |
| Max Distance | integer (hops) | 30 | 1 to 64. |
| DNS Resolution | boolean | true | Resolve IP addresses of each hop to hostnames. |

#### 3.2.3 Behaviour Rules

- Three probes per hop with the same TTL.
- **UDP mode**: destination port incremented by 1 per probe (standard behavior). Starting port = user-specified.
- **ICMP mode**: ICMP echo requests with increasing TTL. Port parameter ignored.
- **TCP mode**: TCP SYN packets with increasing TTL. Specified port used for all probes.
- ICMP Time Exceeded received → record hop with source IP of that message.
- No response within timeout → record hop as `*`.
- Destination responds (Echo Reply for ICMP, SYN-ACK for TCP, Port Unreachable for UDP) → trace complete.
- Max Distance is a hard stop.

#### 3.2.4 Edge Cases

- Target resolves to multiple IPs: first address used.
- Routing changes between probes: display all distinct IPs observed per hop.
- Firewall blocks ICMP Time Exceeded: continue probing up to Max Distance even with `*` responses.
- Looping route: no loop detection in MVP (see §6 OQ-002).
- Destination behind NAT: final hop may show private IP. Expected, do not filter.

### 3.3 DNS Lookup

#### 3.3.1 Description

Query DNS records for a domain name using configurable record types and nameservers.

#### 3.3.2 Input Parameters

| Parameter | Type | Default | Constraints |
|---|---|---|---|
| Domain | string | (required) | Valid domain name or IP address (for PTR). Max 255 characters. |
| Record Type | enum (multi-select) | A | A, AAAA, CNAME, MX, NS, TXT, SRV, SOA, PTR, CAA. One or more. |
| DNS Server | string | System default | Predefined list (8.8.8.8, 1.1.1.1, 9.9.9.9) + custom entry. Must be a valid IP address. |
| Recursive CNAME Resolution | boolean | true | Follow CNAME chain to terminal record. |

#### 3.3.3 Behaviour Rules

- Each selected record type queried independently. Results grouped by type.
- **Recursive CNAME enabled**: follow CNAME chain until A/AAAA record or loop detected (same target twice in chain). Max chain depth: 10.
- **Recursive CNAME disabled**: return raw CNAME record(s) without following.
- Custom DNS server must be a valid IPv4 or IPv6 address. Hostnames NOT accepted.
- A "Copy to clipboard" button MUST be available for displayed results.

#### 3.3.4 Edge Cases

- Domain does not exist: NXDOMAIN error.
- No records of requested type: empty result with message.
- DNS server unreachable or timeout: timeout error.
- PTR query with no reverse record: "no PTR record found."
- Internationalized domain names (IDN): accept Unicode. Punycode conversion is handled automatically by dnspython.

### 3.4 TLS/SSL Certificate Viewer

#### 3.4.1 Description

Connect to an HTTPS server and display the TLS certificate chain with detailed properties.

#### 3.4.2 Input Parameters

| Parameter | Type | Default | Constraints |
|---|---|---|---|
| URL | string | (required) | Valid URL (https://) or hostname. Accepts IP or DNS hostname. Port extracted from URL (default 443 for https). |
| SNI | string | Same as URL hostname | Server Name Indication. Must be a valid hostname. |

#### 3.4.3 Behaviour Rules

- MUST connect using any SSL/TLS version.
- Connection using TLS < 1.2 or SSL → clear warning displayed ("connection is not secure").
- Full certificate chain displayed, even if some certs are untrusted.
- Certificate chain validated against system CA store.
- Server requires client certificate → connection refused, error returned.
- Server uses IP as hostname (not target) → hostname mismatch reported as validation error.
- Tool checks certificate revocation status via OCSP with CRL fallback (cached 24h).
- A "Copy to clipboard" button MUST be available for displayed results.

#### 3.4.4 Edge Cases

- Expired certificate: displayed with clear validation error. All fields remain visible.
- Self-signed certificate: displayed with validation error (untrusted root). Chain = single certificate.
- Missing intermediate: display chain as sent by server. Report incompleteness.
- Connection refused or timeout: clear error, no certificate data displayed.
- TLS < 1.2 or SSL: connection succeeds, warning displayed.
- Wildcard certificate: SANs include wildcard entries (e.g., `*.example.com`). Display as-is.

### 3.5 MAC OUI Lookup

#### 3.5.1 Description

Extract MAC addresses and OUI prefixes from arbitrary text, then look up the vendor/manufacturer in a local database populated daily from the official IEEE OUI files.

#### 3.5.2 Input Parameters

| Parameter | Type | Default | Constraints |
|---|---|---|---|
| Text | string (textarea) | (required) | Max 50 000 characters. Accepts any text. |

The user can paste raw output from network equipment: ARP tables, CAM tables, `show mac address-table`, etc. SAKN extracts all valid MAC addresses and OUI prefixes automatically.

#### 3.5.3 Supported MAC/OUI Formats

| Format | Example | Notes |
|---|---|---|
| Colon-separated pairs | `00:11:22:33:44:55` | Most common |
| Hyphen-separated pairs | `00-11-22-33-44-55` | Windows-style |
| Dot-separated quads | `0011.2233.4455` | Cisco-style |
| No separator | `001122334455` | Bare hex |
| OUI only | `00:11:22` or `001122` | First 3 bytes |

All separators can be mixed in the input text. The extraction is case-insensitive.

#### 3.5.4 Behaviour Rules

- Valid MAC/OUI patterns are extracted from the input text via regex. Non-matching text is ignored.
- Extracted prefixes are deduplicated before database lookup.
- Each OUI is looked up against the 3 IEEE databases: MA-L (24-bit), MA-M (28-bit), MA-S (36-bit).
- If a MAC address matches multiple OUI sizes (e.g., a 28-bit prefix that is also covered by a 24-bit prefix), the most specific match (longest prefix) is returned.
- The OUI database is populated daily from the 3 official IEEE files:
  - `http://standards-oui.ieee.org/oui/oui.txt` (MA-L, 24-bit)
  - `http://standards-oui.ieee.org/oui28/mam.txt` (MA-M, 28-bit)
  - `http://standards-oui.ieee.org/oui36/oui36.txt` (MA-S, 36-bit)
- Organization changes are tracked historically: when an OUI changes organization name or address between two daily syncs, the change is recorded with a timestamp.
- A "Copy to clipboard" button MUST be available for displayed results.

#### 3.5.5 Edge Cases

- No valid MAC/OUI found in input → empty result with message.
- Input exceeds 50 000 characters → truncation warning.
- OUI not yet in database (newly assigned) → "Unknown vendor" with the extracted prefix.
- OUI has history of changes → expandable section showing previous organization names and dates.
- IEEE files temporarily unavailable during daily sync → keep previous data, log warning, retry next day.
- Duplicate OUIs in input → deduplicated, one result row per OUI.

### 3.6 WHOIS Lookup

#### 3.6.1 Description

Query domain or IP ownership information using RDAP (Registration Data Access Protocol) with automatic fallback to classic WHOIS (port 43) when RDAP is unavailable.

#### 3.6.2 Input Parameters

| Parameter | Type | Default | Constraints |
|---|---|---|---|
| Target | string | (required) | Valid domain name or IP address. Max 255 characters. |
| WHOIS Server | string | Automatic | Optional. Custom WHOIS server hostname or IP. Overrides automatic server selection. |

#### 3.6.3 Behaviour Rules

- RDAP is attempted first (HTTP `GET` to the appropriate RDAP bootstrap server).
- If the TLD or IP registry does not support RDAP (HTTP 404, timeout, or connection refused), fall back to classic WHOIS on port 43.
- Classic WHOIS response is returned as structured fields when possible, plus the raw text.
- The protocol used (RDAP or WHOIS) is indicated in the result.
- A "Copy to clipboard" button MUST be available for displayed results.

#### 3.6.4 Edge Cases

- Domain does not exist: "Domain not found."
- IP address is private/internal: blocked by the same network address filter used by other tools (see §5.1 of `spec-backend.md`).
- WHOIS server unreachable or timeout: timeout error after 15s.
- TLD with no known WHOIS or RDAP server: unsupported TLD error.
- Rate-limited by remote WHOIS server: error with "try again later" message.
- Thin WHOIS registry (e.g., `.com`): the raw text response is displayed. Structured data extraction is best-effort.
- GDPR-redacted contact fields: displayed as "[REDACTED]" — this is the expected output for most domains.

### 3.7 Secret Generator

#### 3.7.1 Description

Generate cryptographically secure secrets directly in the browser. Three generation modes: human-readable passwords, URL-safe tokens (à la Python `secrets.token_urlsafe()`), and raw hexadecimal secrets. No backend execution — all generation happens client-side.

#### 3.7.2 Input Parameters

**Mode selection** (user chooses one of three):

| Mode | Description | Equivalent CLI |
|---|---|---|
| Password | Character-based password with configurable charsets | — |
| Token (URL-safe) | Base64url-encoded random bytes | `python -c "import secrets; print(secrets.token_urlsafe(N))"` |
| Hex | Raw hexadecimal random bytes | `openssl rand -hex N` |

**Password mode parameters:**

| Parameter | Type | Default | Constraints |
|---|---|---|---|
| Length | integer | 20 | 8 to 128 |
| Uppercase (A-Z) | boolean | true | At least one character set must be enabled |
| Lowercase (a-z) | boolean | true | |
| Digits (0-9) | boolean | true | |
| Symbols (!@#...) | boolean | true | |

**Token (URL-safe) mode parameters:**

| Parameter | Type | Default | Constraints |
|---|---|---|---|
| Length | integer (chars) | 43 | 16 to 256. Each character encodes 6 bits (base64url, charset size = 64). |

Entropy = `length * 6` bits. Default 43 chars → 258 bits. Equivalent to Python `secrets.token_urlsafe(32)`.

**Hex mode parameters:**

| Parameter | Type | Default | Constraints |
|---|---|---|---|
| Length | integer (chars) | 64 | 16 to 512. Each character encodes 4 bits (hexadecimal, charset size = 16). |

Entropy = `length * 4` bits. Default 64 chars → 256 bits. Equivalent to `openssl rand -hex 32`.

#### 3.7.3 Behaviour Rules

- Uses `crypto.getRandomValues()` (Web Crypto API) for CSPRNG — never `Math.random()`.
- The primary parameter in all 3 modes is the **output length in characters**. Entropy in bits is displayed alongside: `"N caractères (X bits)"`.
- **Password mode**: uniform distribution via rejection sampling to avoid modulo bias. At least one character set must be enabled.
- **Token mode**: generates `ceil(length * 6 / 8)` random bytes, encodes in base64url (RFC 4648 §5, `-` and `_`, no `=` padding). The output length may be 1 char shorter than requested if the byte count doesn't align exactly — in which case the actual length and bit count are displayed.
- **Hex mode**: generates `ceil(length / 2)` random bytes, encodes as lowercase hexadecimal. Output length is always even (each byte = 2 hex chars); odd requested lengths are rounded up and the actual length is displayed.
- Generated secret is displayed in a read-only monospace field.
- A "Copy to clipboard" button copies the secret. The clipboard is auto-cleared after 30 seconds.
- A "Regenerate" button generates a new secret with the same parameters.
- No secret is ever sent to the backend — generation is 100% client-side.
- A visual strength indicator (weak/fair/strong/very strong) is displayed based on entropy thresholds.

#### 3.7.4 Edge Cases

- Password mode: length = 8 with only digits → weak (8 chars, ~26 bits), red indicator.
- Password mode: length = 128 with all sets → very strong (128 chars, ~832 bits), green indicator.
- Token mode: length = 43 → 43 chars, 258 bits entropy.
- Hex mode: length = 64 → 64 chars, 256 bits entropy.
- Clipboard API unavailable (old browser, HTTP origin) → "Copy" button hidden, user must select and copy manually.
- JavaScript disabled → tool unusable (server-rendered fallback message).

---

## 4. Authentication and Account Management

For implementation details (session storage, CSRF, password hashing), see `spec-backend.md`. For API request/response schemas, see `spec-api-contract.md`.

### 4.1 Registration

- Register with email + password.
- Password: 8-128 chars, 1 uppercase, 1 lowercase, 1 digit. Common/leaked passwords rejected (zxcvbn, entropy ≥ 30 bits).
- Email verification: link sent upon registration, expires after 24h. Unverified accounts = "pending", cannot use tools.
- Unverified account not verified within 7 days → auto-deleted.
- Duplicate email: "If the email is valid, a verification link has been sent." (enumeration protection).

### 4.2 Login

- Login with email + password.
- Brute force protection:
  - 5 consecutive failures → locked for 5 min
  - 10 → 15 min
  - 15 → 45 min
  - 20+ → 90 min (renewed every subsequent 5 failures)
  - Counter resets on successful login.
  - Error message: "Account temporarily unavailable. Try again later."
- Session: 24h sliding expiration (admin-configurable). Max 10 concurrent sessions per user (admin-configurable).
- Users can view and revoke active sessions.

### 4.3 Email Verification

- Verification link contains a unique token, valid for 24 hours.
- Resend available after 60s cooldown. Max 5 resends per 24h.
- Expired token: user can request a new one.

### 4.4 Password Reset

- Request by providing email. Response: "If the email is registered, a reset link has been sent."
- Reset link valid for 1 hour.
- After successful reset, all active sessions (except current) are terminated.
- Rate limit: 3 requests per email per 24h.

### 4.5 User Preferences

- Language: `en` | `fr` (default: `en`).
- Display mode: `light` | `dark` | `system` (default: `system`).
- Locale: e.g., `en-US`, `fr-FR` (default: browser `navigator.language`). Controls date/number/unit formatting, separate from language.
- Preferences persisted and applied across sessions.

### 4.6 Account Deletion

- Requires current password confirmation.
- Immediate and irreversible.
- Preferences: DELETED. Logs: ANONYMIZED (user references removed).

---

## 5. Baseline Rate Limit Values

The full rate limiting system is specified in `spec-backend.md` §6. These are the default values defined by the functional spec:

| Role | Global Soft | Global Hard | Tool Soft | Tool Hard |
|---|---|---|---|---|
| Visitor (session) | 1 req/sec | 200 req/hr | no limit | no limit |
| Visitor (IP) | 5 req/sec | 500 req/hr | no limit | no limit |
| Authenticated User | 1 req/sec | 500 req/hr | no limit | no limit |
| Administrator | no limit | 3600 req/hr | no limit | no limit |

Key rule: per-tool limits can only tighten global limits (must be ≤ global for the same role).

---

## 6. Excluded from Scope & Open Questions

### 6.1 Explicitly Out of Scope (MVP)

IP/subnet calculator, VirusTotal integration, dashboards, public REST API, Electron desktop app, native mobile app, social login/OAuth, MFA, team accounts, saved tool history, real-time collaboration, automated scheduling, performance monitoring.

### 6.2 Resolved Open Questions

| ID | Question | Decision |
|---|---|---|
| OQ-001 | IPv4 vs IPv6 preference | Prefer IPv6. No toggle in MVP. |
| OQ-002 | Traceroute loop detection | Defer to post-MVP. |
| OQ-003 | TCP Ping | ICMP-only for MVP. |
| OQ-004 | EDNS Client Subnet | Defer. |
| OQ-005 | Certificate revocation checking | Implemented: OCSP with CRL fallback (24h disk cache). |
| OQ-006 | DNSSEC validation | Defer. Display AD flag if available. |
| OQ-007 | Password complexity | 8-128 chars, upper+lower+digit + zxcvbn. No special char. |
| OQ-008 | Timing attack protection | Monitor for MVP. |
| OQ-009 | Visitor rate limiting | Both session + IP checks. |
| OQ-010 | Session storage | Persistent Redis. |
| OQ-011 | Super-admin role | None. Bootstrap via CLI. |
| OQ-014 | Locale formatting | Separate from language preference. |
| OQ-015 | RTL support | Design from start with CSS logical properties. |
| OQ-020 | Concurrent execution | Frontend prevents; backend allows. |

---

## 7. Assumptions and Constraints

### 7.1 Assumptions

1. **ICMP availability**: Server has CAP_NET_RAW or equivalent. If unavailable, Ping returns error (no silent fallback).
2. **Backend DNS resolution**: Uses system-configured resolvers unless overridden by custom DNS server parameter.
3. **TLS handshake**: Backend can perform TLS handshakes without persistent connections.
4. **Outbound network access**: Server has outbound internet access on ports 53 (DNS), 80/443 (TLS), and full port range for Ping/Traceroute.
5. **Docker capabilities**: Container configured with NET_RAW, NET_ADMIN, and network access.
6. **IDN support**: Unicode domain names converted to Punycode before queries.
7. **Log retention**: 90 days sufficient for MVP.

### 7.2 Constraints

1. Email + password authentication only (no social login, OAuth, SSO).
2. No file downloads (CSV, JSON export) in MVP.
3. No saved tool history for users. Only admins view execution logs.
4. Single language per session (no mixed-language pages).
5. WebSocket real-time output mandatory for Ping and Traceroute.
6. Tool concurrency prevented by frontend design, not backend enforcement.
7. RTL support designed from the start (CSS logical properties).

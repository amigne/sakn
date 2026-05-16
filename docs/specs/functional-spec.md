# Functional Specification — SAKN (Swiss Army Knife for Network Engineers)

> **Version:** 2.0 — Condensed
> **Status:** Draft
> **Date:** 2026-05-14

Defines **what** the application does: user roles, tool capabilities, business rules, and constraints. For **how** it is built, see `docs/specs/technical/`. For **how** it looks, see `docs/specs/ui-spec.md`.

---

## 1. Introduction

### 1.1 Product Vision

SAKN is a web application providing a unified interface for network diagnostic tools: Ping, Traceroute, DNS Lookup, and TLS/SSL Certificate Viewer. It replaces the need to install and switch between separate CLI tools.

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
| Count | integer | optional, unlimited | 0 to 100. 0 or empty = unlimited until Max Duration or user stops. |
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

Whois, MAC OUI lookup, IP/subnet calculator, VirusTotal integration, dashboards, public REST API, Electron desktop app, native mobile app, social login/OAuth, MFA, team accounts, saved tool history, real-time collaboration, automated scheduling, performance monitoring.

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

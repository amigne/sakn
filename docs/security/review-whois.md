# Security Review — WHOIS Lookup Tool

> **Version:** 1.0
> **Status:** Draft — Sprint 0 (pre-implementation)
> **Date:** 2026-06-05
> **Module:** WHOIS Lookup (`whois`)
> **References:** `functional-spec.md` §3.6, `spec-tool-whois.md`, ADR-018, `app/security/address_filter.py`

Pre-implementation security review of the WHOIS Lookup tool (SCR-27). This review identifies threats, evaluates mitigations, and documents the residual attack surface before any code is written.

---

## 1. Threat Model

### 1.1 Assets

| Asset | Sensitivity | Impact of compromise |
|---|---|---|
| Backend server network access | High | SSRF could expose internal services, cloud metadata endpoints, or enable lateral movement |
| Outbound bandwidth | Medium | Abuse as a reflection amplifier or proxy |
| User input confidentiality | Low | WHOIS queries are public by nature (domains/IPs are not secrets) |
| Server file system / memory | Medium | Large responses could exhaust memory; file writes could leak data |

### 1.2 Threat Actors

| Actor | Motivation | Capability |
|---|---|---|
| External attacker (unauthenticated) | SSRF probe, network scanning, DoS | Can send crafted `target` and `server` parameters |
| Authenticated user | Same as above, plus rate-limit bypass via multiple accounts | Has legitimate access; may attempt to abuse tool for internal scanning |
| Malicious registry/DNS | Supply-chain attack via compromised RDAP/WHOIS server | Could serve malicious redirects or oversized responses |

### 1.3 Attack Vectors

| ID | Vector | Severity | Likelihood |
|---|---|---|---|
| AV-1 | **SSRF via `target` parameter** — attacker provides `target=127.0.0.1` or `target=internal-service.local` | Critical | High |
| AV-2 | **SSRF via `server` parameter** — attacker provides `server=127.0.0.1` or `server=169.254.169.254` (cloud metadata) | Critical | High |
| AV-3 | **SSRF via RDAP HTTP redirect** — legitimate RDAP server returns 302 to internal IP | High | Low |
| AV-4 | **SSRF via DNS rebinding** — attacker-controlled domain resolves to public IP initially, then to private IP on subsequent resolution | High | Low |
| AV-5 | **Response size exhaustion** — remote WHOIS server returns multi-megabyte response, consuming server memory | Medium | Medium |
| AV-6 | **WHOIS protocol injection** — attacker provides `target=example.com\r\nQUIT\r\n` to inject WHOIS commands | Medium | Medium |
| AV-7 | **Amplification / proxy abuse** — attacker uses SAKN to flood a third-party WHOIS server | Low | Low |
| AV-8 | **Information disclosure via error messages** — error details reveal internal network topology or server configuration | Low | Low |
| AV-9 | **RDAP response parsing DoS** — deeply nested or maliciously crafted JSON exhausts CPU/memory during parsing | Medium | Low |
| AV-10 | **TDAP bootstrap cache poisoning** — attacker poisons DNS for `rdap.iana.org` to redirect RDAP queries through a malicious intermediary | Medium | Very Low |

---

## 2. Mitigations

### 2.1 SSRF via `target` Parameter (AV-1)

**Mitigation**: The `target` parameter is validated through `filter_target()` (`app/security/address_filter.py`) before any network connection.

- If `target` is an IP: checked directly against `BLOCKED_NETWORKS` (covers `127.0.0.0/8`, `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `169.254.0.0/16`, `::1/128`, `fc00::/7`, etc.).
- If `target` is a hostname: resolved via DNS, and **each** resolved IP is checked against `BLOCKED_NETWORKS`.
- Covers Docker bridge networks (`172.17.0.0/16`, `172.18.0.0/16`), cloud metadata endpoints (`169.254.0.0/16`), and all RFC 1918 private ranges.

**Residual risk**: **Low**. The blocklist is comprehensive and shared across all tools. Bypass requires a zero-day in Python's `ipaddress` module or a new private range not covered by the blocklist.

### 2.2 SSRF via `server` Parameter (AV-2)

**Mitigation**: The `server` parameter (custom WHOIS server) is validated through the **same** `filter_target()` before opening the TCP connection.

- Hostname is resolved, each IP is checked.
- Direct IP (e.g., `127.0.0.1`) is blocked.
- Internal hostnames (e.g., `metadata.google.internal`) are blocked as soon as they resolve to private IPs.

**Rationale**: This is the most critical WHOIS-specific SSRF mitigation. Without it, an attacker could specify `server=127.0.0.1` and reach any local service on port 43, or `server=169.254.169.254` to hit cloud metadata APIs (if the cloud provider's metadata service responds on port 43 — unlikely but defense-in-depth).

**Residual risk**: **Low**. Same filter, same blocklist. The only additional risk is that a custom server on a public IP could itself be a malicious proxy — but that requires the attacker to control a public IP, which is outside SAKN's threat model.

### 2.3 SSRF via RDAP HTTP Redirect (AV-3)

**Mitigation**: Every HTTP redirect (3xx) received during an RDAP query is intercepted. The redirect target's hostname is extracted, resolved, and **re-validated** through `filter_target()` before following.

- If the redirect target resolves to a private IP, the redirect is **not followed** and the query fails with `WHOIS_CONNECTION_FAILED`.
- This is implemented as a custom `httpx` event hook or manual redirect handling (not `follow_redirects=True` with default behavior).

**Rationale**: IANA bootstrap redirects to registry-operated RDAP servers (e.g., `rdap.verisign.com`). A compromised or malicious registry could redirect to an internal IP. Re-validation closes this vector.

**Residual risk**: **Very Low**. Requires a compromised IANA bootstrap server or a compromised registry RDAP server — both are high-effort, targeted attacks.

### 2.4 SSRF via DNS Rebinding (AV-4)

**Mitigation**: The resolve-then-connect pattern: resolve hostname → validate IP(s) → connect to validated IP. The validated IP is used directly for the connection, not the hostname.

- For RDAP: the `httpx` transport is configured with a custom resolver that returns the pre-validated IP.
- For WHOIS: `asyncio.open_connection(validated_ip, 43)` — the IP, not the hostname, is passed to `open_connection`.

**Rationale**: DNS rebinding relies on the time-of-check/time-of-use (TOCTOU) gap between validation (DNS resolves to public IP) and connection (DNS now resolves to private IP). By resolving once and connecting to the validated IP, the TOCTOU window is eliminated.

**Residual risk**: **Very Low**. The only remaining rebinding vector is within the `filter_target()` resolution itself (CNAME chain walking), which is protected by its own TOCTOU hardening (see `address_filter.py:74-130`).

### 2.5 Response Size Exhaustion (AV-5)

**Mitigation**: A **response size cap** is enforced on WHOIS TCP reads.

- Default cap: **2 MiB** (configurable via `settings.WHOIS_MAX_RESPONSE_BYTES`).
- Implemented as a byte counter in the read loop: after each `read()` chunk, the total is checked. If it exceeds the cap, the connection is closed and the accumulated data is returned with a truncation warning.
- RDAP responses are capped by `httpx`'s default streaming limits (and the JSON parser's input size check).

**Rationale**: Some WHOIS servers return excessively large responses (e.g., `.com` thin registry referrals can include lists of hundreds of registrars). 2 MiB accommodates legitimate large responses while preventing memory exhaustion. The cap is configurable so operators can adjust for their environment.

**Residual risk**: **Low**. A 2 MiB cap is generous for WHOIS data. Memory exhaustion would require the cap to be disabled or set to an extreme value.

### 2.6 WHOIS Protocol Injection (AV-6)

**Mitigation**: The `target` string is **sanitized before being sent over the WHOIS socket**.

- The target is stripped of `\r` and `\n` characters (and any other control characters below 0x20 except space).
- The sanitized target is validated to ensure it is not empty after stripping.
- The WHOIS query sent on the socket is always: `{sanitized_target}\r\n` — exactly one command, exactly one CRLF terminator.

**Rationale**: WHOIS is a line-based text protocol. An attacker could inject `target=example.com\r\nQUIT\r\n` to terminate the session early or inject additional WHOIS commands. Sanitization prevents this. This is standard practice for WHOIS clients.

**Residual risk**: **Very Low**. Control-character stripping eliminates the injection vector. Even if a novel encoding bypasses the strip, WHOIS servers typically ignore unknown commands (they return the requested domain's data or an error).

### 2.7 Amplification / Proxy Abuse (AV-7)

**Mitigation**: Standard rate limiting applies (visitor: 200 req/h, authenticated: 500 req/h). Additionally, the tool's execution time (RDAP: 20s max, WHOIS: 20s max) bounds the amplification window.

**Residual risk**: **Low**. An attacker would need many IPs or accounts to generate meaningful traffic to a third-party WHOIS server. The rate limits make SAKN an unattractive amplification vector compared to open DNS resolvers or NTP servers.

### 2.8 Information Disclosure via Errors (AV-8)

**Mitigation**: Error responses use the standard error envelope with `message_key` values (i18n). Internal details (resolved IP addresses, WHOIS server hostnames, exact connection errors) are logged server-side but **not** returned to the client.

- `WHOIS_UNSUPPORTED_TLD` (422): "This TLD is not supported by any known WHOIS or RDAP server." Does not reveal which servers were attempted.
- `WHOIS_CONNECTION_FAILED` (502): "Could not connect to the remote WHOIS/RDAP server." Does not reveal the IP or connection error details.
- `TARGET_NOT_ALLOWED` (422): Standard security filter error. Does not reveal why the target was blocked.

**Residual risk**: **Very Low**. Error messages are generic and i18n-based. Detailed error information is logged, not exposed.

### 2.9 RDAP JSON Parsing DoS (AV-9)

**Mitigation**: RDAP responses are parsed with `json.loads()` from the Python stdlib, which has no known DoS vulnerabilities for typical response sizes (RDAP responses are typically < 100 KB). The `httpx` response is fully read before parsing (no streaming JSON parser needed).

**Residual risk**: **Very Low**. Python's `json` module is well-tested. The response size cap (via httpx's timeout and the tool's overall execution deadline) prevents unbounded input.

### 2.10 RDAP Bootstrap Cache Poisoning (AV-10)

**Mitigation**: The RDAP bootstrap query to `rdap.iana.org` uses HTTPS (TLS). DNS resolution for `rdap.iana.org` goes through the system resolver, which is assumed to be trustworthy (same assumption as all other SAKN tools).

**Residual risk**: **Very Low**. Poisoning `rdap.iana.org` requires compromising IANA's DNS or the server's DNS resolver — both are high-effort attacks outside SAKN's threat model. HTTPS provides an additional layer (certificate validation).

---

## 3. Attack Surface Summary

### 3.1 New Network Connections

| Connection | Destination | Port | Protocol | Trigger |
|---|---|---|---|---|
| IANA RDAP bootstrap | `rdap.iana.org` | 443 | HTTPS | Every WHOIS query (RDAP attempt) |
| Authoritative RDAP server | Registry-operated (e.g., `rdap.verisign.com`) | 443 | HTTPS | After IANA bootstrap redirect |
| IANA WHOIS reference | `whois.iana.org` | 43 | TCP | WHOIS fallback (to discover TLD WHOIS server) |
| TLD WHOIS server | Registry-operated (e.g., `whois.verisign-grs.com`) | 43 | TCP | WHOIS fallback |
| Custom WHOIS server | User-supplied | 43 | TCP | When `server` parameter provided |

All connections are outbound. No new listening ports are opened.

### 3.2 Inputs Under Attacker Control

| Input | Validation | Risk after mitigation |
|---|---|---|
| `target` (domain or IP) | `filter_target()` → IP blocklist + DNS resolution | Low |
| `server` (custom WHOIS server) | `filter_target()` → IP blocklist + DNS resolution | Low |
| RDAP redirect target (indirect) | `filter_target()` re-validation before following | Very Low |

### 3.3 Trusted External Services

| Service | Trust Level | Justification |
|---|---|---|
| IANA RDAP bootstrap (`rdap.iana.org`) | High | Operated by ICANN/IANA. HTTPS with certificate validation. |
| IANA WHOIS reference (`whois.iana.org`) | Medium | Operated by ICANN/IANA. Plain TCP (no TLS for WHOIS). Query is read-only. |
| Registry RDAP/WHOIS servers | Low | Operated by individual registries. Treated as untrusted — responses are validated, redirects are re-checked, size is capped. |

### 3.4 Comparison with Existing Tools

| Property | WHOIS | TLS/SSL Viewer | DNS Lookup |
|---|---|---|---|
| Outbound connections | 2–4 per query (bootstrap + authoritative, RDAP + WHOIS fallback) | 1 per query (TLS handshake) | 1 per query (DNS) |
| Connection target controlled by | User input (`target`, `server`) | User input (`url`) | User input (`domain`, `resolver`) |
| SSRF filter | `filter_target()` on target, server, RDAP redirects | `filter_target()` on target | `filter_target()` on target |
| Response size risk | Medium (WHOIS can be large) | Low (TLS handshake only) | Low (DNS responses bounded) |
| Protocol injection risk | Medium (WHOIS text protocol) | None (binary TLS) | None (binary DNS via dnspython) |

The WHOIS tool has a slightly larger attack surface than existing tools due to: (a) the two-phase protocol requiring multiple connections, (b) the text-based WHOIS protocol with injection risk, and (c) potentially large responses. All three are adequately mitigated.

---

## 4. Security Checklist for Implementation

- [ ] `target` is validated through `filter_target()` before any connection (AV-1)
- [ ] `server` is validated through `filter_target()` before WHOIS connection (AV-2)
- [ ] RDAP HTTP redirects are intercepted and re-validated through `filter_target()` (AV-3)
- [ ] Connections use the validated IP, not the hostname (resolve-then-connect) (AV-4)
- [ ] WHOIS TCP response size cap is enforced (default 2 MiB) (AV-5)
- [ ] `target` is sanitized — `\r` and `\n` stripped — before being sent over the WHOIS socket (AV-6)
- [ ] Rate limiting is applied (inherited from global/tool defaults) (AV-7)
- [ ] Error responses use generic i18n keys, not internal details (AV-8)
- [ ] RDAP JSON response is parsed with stdlib `json.loads()` (AV-9)
- [ ] RDAP bootstrap uses HTTPS with certificate validation (AV-10)
- [ ] All timeouts are enforced: RDAP 10s connect / 20s read, WHOIS 15s connect / 20s read
- [ ] No new dependencies introduced (verify with `uv pip list` diff)
- [ ] No new Alembic migration generated (verify with `alembic check`)

---

## 5. Recommendations

1. **Accept** the WHOIS tool implementation with the mitigations described above.
2. The SSRF risk is the primary concern and is adequately addressed by reusing `filter_target()` with the additional `server` and RDAP-redirect validation.
3. The WHOIS protocol injection risk is low-severity and fully mitigated by control-character sanitization.
4. The response size cap (2 MiB) should be configurable via `settings.WHOIS_MAX_RESPONSE_BYTES` to accommodate operators with different memory constraints.
5. Post-implementation: a penetration test should specifically target the RDAP redirect chain (AV-3) and DNS rebinding (AV-4) vectors to verify the mitigations.

---

## 6. References

| Source | Section |
|---|---|
| `functional-spec.md` | §3.6 (WHOIS Lookup) |
| `docs/specs/technical/spec-tool-whois.md` | Full technical specification |
| `docs/specs/technical/spec-tools-instant.md` | §5–6 (WHOIS strategy, timeouts) |
| `docs/adr/ADR-018-whois-resolution-and-ssrf-policy.md` | SSRF policy decision |
| `app/security/address_filter.py` | `filter_target()` implementation |
| `app/tools/ssl_viewer.py:96` | SSRF filter usage pattern |
| `docs/security/threat-model.md` | Project-wide threat model |

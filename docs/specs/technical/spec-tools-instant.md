# Instant Tools Specification — DNS Lookup & TLS/SSL Viewer

> **Version:** 4.0 — Added MAC OUI and WHOIS
> **Status:** Draft
> **Date:** 2026-05-21

HTTP request/response tools. Load with `spec-common.md`, `spec-backend.md`, and `spec-api-contract.md`.

---

## 1. HTTP Execution

### 1.1 Request

`POST /api/v1/tools/{tool_name}/execute`

```json
{
  "params": {
    "target": "example.com",
    ...
  }
}
```

### 1.2 Response (200 OK)

```json
{
  "tool": "dns_lookup",
  "success": true,
  "duration_ms": 235.1,
  "data": { ... }
}
```

### 1.3 Error Response (4xx/5xx)

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

## 2. DNS Lookup

### 2.1 Execution Strategy

`dnspython` library. No subprocess needed. Full control over record types, custom resolvers, EDNS, CNAME chain following.

### 2.2 Parameters

- `target`: hostname to resolve.
- `record_type`: A, AAAA, MX, TXT, NS, CNAME, SOA, etc.
- `resolver`: DNS server IP (optional, uses system default if empty).
- `recursive_cname`: boolean, default `true`. Follow CNAME chain until final record.

### 2.3 Result Data

Structured output with: queried hostname, record type, answer records (each with type, value, TTL), optional CNAME chain, optional authority/additional sections.

### 2.4 CNAME Behavior

When `recursive_cname: true`, each resolved address in the CNAME chain is independently checked against the network blocklist.

---

## 3. TLS/SSL Certificate Viewer

### 3.1 Execution Strategy

Python `ssl` + `socket` + `cryptography` libraries. Direct TLS handshake, full certificate chain retrieval, validation against system CA store. No subprocess needed.

### 3.2 Parameters

- `url`: single URL field (not separate target + port). Port extracted from URL (default 443 for `https://`). Accepts numeric IP, hostname, or full URL.
- Forms: `example.com`, `192.168.1.1`, `https://example.com:8443`.

### 3.3 Result Data

Structured output with:
- Certificate chain (each cert: subject, issuer, validity period, SAN, key algorithm/size, signature algorithm, fingerprint).
- Trust chain validation (against system CA store).
- TLS version negotiated.
- Cipher suite negotiated.

### 3.4 Version Handling

Connect with any SSL/TLS version the server offers. If connection uses TLS < 1.2 or SSL, include a clear warning in the result. The tool does NOT enforce a minimum version.

### 3.5 Revocation

The tool checks revocation via OCSP (leaf + intermediates) with automatic CRL fallback (24h disk cache) when OCSP is unavailable. Revoked leaf certificates force `chain_valid = false`.

---

## 4. MAC OUI Lookup

### 4.1 Execution Strategy

Local database lookup (no external API call at execution time). The backend parses the input text, extracts MAC/OUI patterns via regex, deduplicates, and queries the `mac_oui` table.

The database is populated via a daily scheduled task (APScheduler) that downloads and parses the 3 official IEEE OUI files.

### 4.2 Parameters

- `text`: raw text (string, max 50 000 chars). Accepts any text; valid MAC/OUI patterns are extracted automatically.

### 4.3 Result Data

Structured output with:
- `results`: array of `{oui, organization, address, oui_type, first_seen, last_seen}`
  - `oui`: the extracted OUI prefix (uppercase, colon-separated, e.g., `00:11:22`)
  - `organization`: vendor/manufacturer name
  - `address`: organization address as registered with IEEE
  - `oui_type`: `MA-L`, `MA-M`, or `MA-S`
  - `first_seen`: date the OUI was first seen in IEEE files by SAKN
  - `last_seen`: date the OUI was last confirmed in IEEE files
- `history`: array of `{oui, previous_organization, new_organization, change_type, changed_at}`, empty if no changes. Change types: `name_change`, `address_change`, `revoked`, `reassigned`.
- `parse_stats`: `{total_input_chars, mac_oui_count, unique_oui_count}`

### 4.4 Pattern Extraction

The regex extracts MAC addresses and OUI prefixes in these formats from arbitrary text:
- Colon-separated: `00:11:22:33:44:55` or `00:11:22`
- Hyphen-separated: `00-11-22-33-44-55` or `00-11-22`
- Dot-separated (Cisco): `0011.2233.4455` or `0011.22`
- Bare hex: `001122334455` or `001122`

The extraction regex matches hex pairs separated by `:`, `-`, `.`, or run together (even-length hex strings of 6–12 characters). Non-matching text is ignored. Case-insensitive.

### 4.5 OUI Database Sync

- **Schedule**: daily via APScheduler (configurable time, default 03:00 UTC).
- **Sources**:
  - `http://standards-oui.ieee.org/oui/oui.txt` (MA-L)
  - `http://standards-oui.ieee.org/oui28/mam.txt` (MA-M)
  - `http://standards-oui.ieee.org/oui36/oui36.txt` (MA-S)
- **Process**:
  1. Download each file.
  2. Parse entries: `OUI (hex) \t Organization \t Address`.
  3. For each parsed OUI: if it exists with the same org/address → update `last_seen`. If org or address changed → insert `MacOuiHistory` row, then update. If new → insert.
  4. Any OUI not seen in this sync → mark `last_seen` = previous value (no deletion — historical entries retained for forensic value).
- **Error handling**: if a file download fails, log warning, skip that file, keep existing data. Three consecutive daily failures → admin alert.

---

## 5. WHOIS Lookup

### 5.1 Execution Strategy

Two-phase protocol: RDAP (HTTP) attempted first, with automatic fallback to classic WHOIS (TCP port 43).

- **RDAP**: HTTP `GET` to the RDAP bootstrap server for the target TLD or IP registry.
  - Domain: `https://<tld>.rdap.org/domain/<domain>` or IANA bootstrap redirect.
  - IP: `https://rdap.arin.net/ip/<ip>` (or RIPE/APNIC/LACNIC/AFRINIC based on IANA allocation).
  - Response is JSON, parsed into structured fields.
- **WHOIS (fallback)**: TCP connection to the WHOIS server (IANA-referenced or custom), send `domain\r\n`, read response until connection closed.
  - Response is raw text, displayed as-is plus best-effort structured extraction.
  - WHOIS server determined by IANA TLD reference; custom server overrides.

### 5.2 Parameters

- `target`: domain or IP address (string, required).
- `server`: custom WHOIS server hostname or IP (string, optional). Overrides automatic server selection. Ignored for RDAP phase.

### 5.3 Result Data

Structured output (fields present when available):
- `protocol`: `rdap` or `whois`
- `domain`: queried domain
- `status`: array of domain status codes
- `registrar`: registrar name
- `whois_server`: WHOIS server hostname
- `name_servers`: array of nameserver hostnames
- `creation_date`, `expiration_date`, `updated_date`: ISO 8601
- `registrant`, `admin_contact`, `tech_contact`: contact objects (fields redacted as per GDPR — may be `null` or `[REDACTED]`)
- `raw_text`: raw WHOIS response (only for classic WHOIS fallback)
- `disclaimer`: RDAP legal disclaimer text (if any)

### 5.4 Server Selection

1. RDAP bootstrap: query `https://rdap.iana.org/domain/<tld>` or `https://rdap.iana.org/ip/<ip>` for the authoritative RDAP server URL.
2. If RDAP returns 404 or connection error → fallback to WHOIS. IANA WHOIS server reference obtained from `whois.iana.org` for the TLD.
3. If a custom `server` parameter is provided, skip automatic RDAP/WHOIS server selection and connect directly to the custom server on port 43 (WHOIS only — RDAP is skipped when a custom server is specified).

---

## 6. Timeout & Resource Limits

| Tool | Mechanism | Default | Maximum |
|---|---|---|---|
| DNS Lookup | timeout per query via `dnspython` | 5s | 30s |
| TLS/SSL Viewer | socket timeout for connect + handshake | 10s | 30s |
| MAC OUI Lookup | DB query + regex extraction | — | 5s |
| WHOIS (RDAP) | HTTP request timeout | 10s | 20s |
| WHOIS (classic) | TCP connect + read timeout | 15s | 20s |

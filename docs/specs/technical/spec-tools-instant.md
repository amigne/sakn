# Instant Tools Specification — DNS Lookup & TLS/SSL Viewer

> **Version:** 3.0 — Extracted from technical-spec v2.0
> **Status:** Draft
> **Date:** 2026-05-14

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

The tool does NOT check OCSP/CRL. The result explicitly states that certificate revocation status was not checked.

---

## 4. Timeout & Resource Limits

| Tool | Mechanism | Default | Maximum |
|---|---|---|---|
| DNS Lookup | timeout per query via `dnspython` | 5s | 30s |
| TLS/SSL Viewer | socket timeout for connect + handshake | 10s | 30s |

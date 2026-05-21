# ADR-009: WebSocket Origin Header Enforcement

## Status

Accepted — 2026-05-21

## Context

The WebSocket endpoint `/api/v1/tools/{tool_name}/stream` performs CSWSH (Cross-Site WebSocket Hijacking) protection by validating the `Origin` header against the `CORS_ORIGINS` allowlist. Currently, if the `Origin` header is absent — as it is for non-browser HTTP clients such as `curl`, `wget`, or programmatic WebSocket libraries — the request is allowed. This is the "lax" (allow-by-default) configuration.

**Threat model:** An attacker who can trick a browser into initiating a WebSocket connection to the SAKN backend (e.g., via a malicious webpage) will have the browser automatically attach the session cookie. Without Origin validation, the server would accept the connection and the attacker could use the victim's session to execute tools. Modern browsers send the `Origin` header on WebSocket connections, so CSWSH is primarily a browser concern. However, non-browser clients that omit `Origin` could also be exploited as unwitting attack proxies if the server accepts connections without origin checks.

**The problem with the lax default:** A `curl` or `wget` invocation reaching the WebSocket endpoint from an attacker-controlled context (e.g., a compromised CI runner or a server-side SSRF) would bypass origin validation entirely and be accepted with only session-based auth. This expands the attack surface beyond browser-based CSWSH.

## Options Considered

### (a) Strict — absent Origin → reject

Reject all WebSocket connections that lack an `Origin` header with close code 4003.

- **Pros:** Maximum security. No non-browser client can connect without an origin.
- **Cons:** Breaks legitimate non-browser WebSocket clients (CLI tools, monitoring scripts, integration tests). Users with programmatic access would need to manually set an `Origin` header matching `CORS_ORIGINS`.

### (b) Lax — absent Origin → allow (status quo)

Allow connections without an `Origin` header, trusting only session-based authentication.

- **Pros:** Compatible with all clients. No configuration needed.
- **Cons:** Vulnerable to non-browser proxy attacks. Any client that can reach the endpoint can attempt to authenticate with stolen/brute-forced session tokens.

### (c) Configurable — `WS_REQUIRE_ORIGIN` flag

Introduce a boolean configuration flag `WS_REQUIRE_ORIGIN` that controls whether absent-Origin requests are accepted or rejected.

- **Pros:** Flexible. Development environments keep lax mode for ease of testing. Production environments enable strict mode. Deployers choose based on their threat model.
- **Cons:** Requires operators to set the flag. Default affects security posture.

## Decision

**Option (c): Configurable flag `WS_REQUIRE_ORIGIN`.**

- **Default:** `False` (lax, backward-compatible). Existing deployments are unaffected.
- **Production recommendation:** Set `WS_REQUIRE_ORIGIN=True` to enforce that all WebSocket connections carry a valid `Origin` header matching `CORS_ORIGINS`.
- **Close code on rejection:** `4003` (`WS_CLOSE_INVALID_ORIGIN`).

The flag is defined in `app/config.py`:

```python
WS_REQUIRE_ORIGIN: bool = False  # set true in production for CSWSH protection
```

The check in `_is_allowed_origin` (tools.py) becomes:

```python
if not origin:
    return not settings.WS_REQUIRE_ORIGIN
```

## Consequences

- **Non-browser clients in production:** Operators who enable `WS_REQUIRE_ORIGIN=True` must ensure any programmatic WebSocket clients include an `Origin` header set to a value in `CORS_ORIGINS`. This is trivially done in most HTTP libraries (e.g., `--header "Origin: https://my.sakn.instance"` with curl).
- **Monitoring/health checks:** Internal health checks that connect via WebSocket must include an `Origin` header or be exempted (future enhancement: allowlist of trusted IPs that bypass origin checks).
- **No breaking change:** Default of `False` means no existing setup breaks. The recommendation is documented here and in the deployment guide.

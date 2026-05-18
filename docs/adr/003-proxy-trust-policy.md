# ADR-003: Proxy Trust Policy

## Status

Accepted — 2026-05-18

## Context

The application is deployed behind a reverse proxy (Caddy in the reference deployment, but also Traefik, Nginx, or any other HTTP-aware reverse proxy in alternative deployments). The proxy terminates TLS and forwards requests to the backend over plain HTTP on an internal Docker network.

Two pieces of information from the original client must be propagated to the backend, otherwise security-sensitive features misbehave:

1. **Original scheme** (`http` vs `https`). Required by `request.url.scheme` to set the `Secure` flag and the `__Host-` prefix on session and CSRF cookies (cf. `app/api/v1/endpoints/auth.py:125,151`, `app/middleware/session.py:118`, `app/api/v1/endpoints/sessions.py:68`). Without it, cookies are emitted without `Secure`, defeating the cookie-hardening intent of the security audit finding C-2.
2. **Original client IP**. Required for IP-based rate limiting (`app/api/v1/endpoints/auth.py:91,113`, `app/middleware/rate_limit.py:82`) and for `source_ip` in `SecurityEventLog` and `ToolExecutionLog`. Without it, all traffic appears to originate from the reverse proxy and IP-based controls are ineffective.

Both are conveyed via `X-Forwarded-Proto` and `X-Forwarded-For` headers added by the reverse proxy.

### Why the obvious solutions are unacceptable

**Uvicorn's built-in `ProxyHeadersMiddleware` with `FORWARDED_ALLOW_IPS=*`** trusts both headers from any source. With this setting, an attacker reaching the backend (directly or by spoofing `X-Forwarded-For` if the upstream proxy appends rather than overwrites) can:
- inject an arbitrary client IP, bypassing IP-based rate limits on `/auth/login` and `/auth/register` (audit finding M-8 becomes worse, not better);
- poison `SecurityEventLog` with attacker-controlled IPs, destroying forensic traceability.

**Relying on reverse-proxy defaults to strip `X-Forwarded-For`**. Caddy v2.7+ does this; Traefik, Nginx, HAProxy, AWS ALB, GCP HTTPS LB each have their own defaults and quirks. The application's security guarantees would then depend on the choice and version of the proxy — an unstable foundation that breaks the moment a different proxy is deployed.

**Restricting `FORWARDED_ALLOW_IPS` to a fixed subnet** (e.g. the Docker bridge) requires hard-coding network ranges that vary between deployments (compose default vs. swarm vs. Kubernetes vs. bare-metal). Not portable.

## Decision

Implement a **proxy-agnostic** trust policy as an in-application ASGI middleware (`TrustedProxyMiddleware`):

1. **Configurable trusted-hop count**, expressed via the env var `TRUSTED_PROXY_HOPS` (integer, default `0`):
   - `0` → no proxy in front; forwarded headers are ignored, the TCP peer is the client.
   - `1` → one reverse proxy in front (Caddy/Traefik/Nginx).
   - `N` → N proxies in front (e.g. CDN + ingress).

2. **`X-Forwarded-Proto`**: when `TRUSTED_PROXY_HOPS > 0`, the rightmost value (only `http`/`https` accepted) sets `scope["scheme"]`. For WebSocket, `http` → `ws`, `https` → `wss`.

3. **`X-Forwarded-For`**: when `TRUSTED_PROXY_HOPS > 0`, the application parses the comma-separated list and takes the entry at position `-TRUSTED_PROXY_HOPS` (counting from the right). This is the IP that the immediate trusted proxy observed, which by construction cannot be spoofed by an external client — every well-behaved reverse proxy appends to the right.

4. **Uvicorn's built-in proxy headers handling is disabled** by launching with `--no-proxy-headers`. This avoids two middleware mutating the same scope fields with potentially conflicting policies.

5. The middleware runs **before** `RequestIDMiddleware` / `SessionMiddleware` / `RateLimitMiddleware`, so all downstream code sees the corrected `scope["scheme"]` and `scope["client"]`.

## Consequences

### Security
- IP spoofing via `X-Forwarded-For` is structurally impossible from outside the trust boundary, regardless of the upstream proxy's behavior. The rightmost-N approach is the same pattern used by Rails (`ActionDispatch::RemoteIp`), Django (when configured per the docs), Laravel (`TrustProxies`), ASP.NET Core (`ForwardedHeadersOptions`).
- `Secure` and `__Host-` cookies activate correctly behind any HTTPS-terminating proxy.
- An attacker on the same internal Docker network bypassing the proxy can still spoof `X-Forwarded-For`, since no proxy added an entry. The mitigation is at the network layer (network isolation, see Operational Notes).

### Portability
- Application behavior is identical behind Caddy, Traefik, Nginx, HAProxy, or any other RFC 7239-respecting proxy. Only `TRUSTED_PROXY_HOPS` changes per deployment.
- No coupling to a specific proxy version or default policy.

### Operational
- Operators must declare `TRUSTED_PROXY_HOPS` correctly in the deployment env file. Misconfiguration is detectable: a value too low yields the proxy's IP as `source_ip`; a value too high yields the TCP peer's IP (typically the immediate proxy). Both are non-exploitable but visible in logs.
- The default value `0` is fail-safe: in absence of explicit configuration, the app uses the TCP peer as the client (i.e. behaves as if directly exposed). The `docker-compose.yml` shipped with the prod profile sets `TRUSTED_PROXY_HOPS=1` since it ships Caddy as the single hop.

### Tests
- Unit tests in `src/backend/tests/unit/test_proxy_trust.py` cover the six canonical cases (no hops, single hop, multi-hop, spoofing attempt, scheme propagation, WebSocket scheme).

## Operational Notes

For belt-and-suspenders defense against an attacker that has already obtained lateral access to the internal Docker network:

- Place the backend on its own Docker network (`sakn-app`) and connect only the reverse proxy to it. The frontend, postgres and redis containers stay on their existing networks. This way, any container other than the reverse proxy cannot reach `backend:8000` directly. *(Out of scope for this ADR; tracked separately.)*

## Related

- Security audit 2026-05-18 finding C-2 (`docs/security/audit-2026-05-18.md`)
- Issue #9 — `[CRITIQUE] Caddy n'écoute qu'en HTTP, aucune configuration TLS/HTTPS`
- Backend specification §5.6 (`docs/specs/technical/spec-backend.md`)

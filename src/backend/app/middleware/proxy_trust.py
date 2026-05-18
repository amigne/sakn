"""
Proxy-agnostic trust policy for X-Forwarded-* headers.

Replaces uvicorn's built-in ProxyHeadersMiddleware (which must be disabled with
--no-proxy-headers) so the application enforces its own policy independent of
the choice and version of the upstream reverse proxy.

See docs/adr/003-proxy-trust-policy.md for the design rationale.
"""
from typing import Iterable

from starlette.types import ASGIApp, Receive, Scope, Send


class TrustedProxyMiddleware:
    """Honor X-Forwarded-Proto and X-Forwarded-For according to TRUSTED_PROXY_HOPS.

    - trusted_hops == 0 → headers ignored; TCP peer is the client.
    - trusted_hops >= 1 → rightmost X-Forwarded-Proto sets scope["scheme"];
      X-Forwarded-For entry at index -trusted_hops becomes the client IP.

    The Nth-from-right pattern is anti-spoofing by construction: a well-behaved
    reverse proxy always appends its peer's address to the right of the chain.
    Anything to the left can be client-controlled and must not be trusted.
    """

    def __init__(self, app: ASGIApp, trusted_hops: int = 0) -> None:
        self.app = app
        self.trusted_hops = max(0, trusted_hops)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] in ("http", "websocket") and self.trusted_hops > 0:
            headers: Iterable[tuple[bytes, bytes]] = scope.get("headers") or []
            proto_raw = b""
            xff_raw = b""
            for k, v in headers:
                if k == b"x-forwarded-proto":
                    proto_raw = v
                elif k == b"x-forwarded-for":
                    xff_raw = v

            # Scheme: take the rightmost value of X-Forwarded-Proto.
            if proto_raw:
                proto = proto_raw.decode("ascii", "ignore").split(",")[-1].strip().lower()
                if proto in ("http", "https"):
                    if scope["type"] == "websocket":
                        scope["scheme"] = "wss" if proto == "https" else "ws"
                    else:
                        scope["scheme"] = proto

            # Client IP: take the entry at -trusted_hops in the X-Forwarded-For list.
            if xff_raw:
                hops = [h.strip() for h in xff_raw.decode("latin-1").split(",") if h.strip()]
                if len(hops) >= self.trusted_hops:
                    client_ip = hops[-self.trusted_hops]
                    existing_port = scope["client"][1] if scope.get("client") else 0
                    scope["client"] = (client_ip, existing_port)

        await self.app(scope, receive, send)

"""Tests for the TrustedProxyMiddleware (ADR-003)."""
from __future__ import annotations

import pytest

from app.middleware.proxy_trust import TrustedProxyMiddleware


class _FakeApp:
    def __init__(self) -> None:
        self.captured: dict | None = None

    async def __call__(self, scope, receive, send):
        self.captured = {
            "scheme": scope.get("scheme"),
            "client": scope.get("client"),
        }


def _http_scope(client=("198.51.100.1", 54321), headers=None, scheme="http"):
    return {
        "type": "http",
        "scheme": scheme,
        "client": client,
        "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or [])],
    }


def _ws_scope(client=("198.51.100.1", 0), headers=None, scheme="ws"):
    return {
        "type": "websocket",
        "scheme": scheme,
        "client": client,
        "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or [])],
    }


async def _send(*args, **kwargs):
    return None


async def _receive():
    return {"type": "http.request"}


@pytest.mark.asyncio
async def test_no_hops_ignores_headers():
    inner = _FakeApp()
    mw = TrustedProxyMiddleware(inner, trusted_hops=0)
    scope = _http_scope(headers=[
        ("X-Forwarded-Proto", "https"),
        ("X-Forwarded-For", "1.2.3.4"),
    ])
    await mw(scope, _receive, _send)
    assert inner.captured == {"scheme": "http", "client": ("198.51.100.1", 54321)}


@pytest.mark.asyncio
async def test_single_hop_takes_rightmost_xff():
    inner = _FakeApp()
    mw = TrustedProxyMiddleware(inner, trusted_hops=1)
    scope = _http_scope(headers=[
        ("X-Forwarded-Proto", "https"),
        ("X-Forwarded-For", "203.0.113.7"),
    ])
    await mw(scope, _receive, _send)
    assert inner.captured["scheme"] == "https"
    assert inner.captured["client"][0] == "203.0.113.7"


@pytest.mark.asyncio
async def test_single_hop_ignores_spoofed_leftmost():
    """Attacker prepends a fake IP; the proxy appends the real one to the right."""
    inner = _FakeApp()
    mw = TrustedProxyMiddleware(inner, trusted_hops=1)
    scope = _http_scope(headers=[
        ("X-Forwarded-For", "1.2.3.4, 203.0.113.7"),
    ])
    await mw(scope, _receive, _send)
    assert inner.captured["client"][0] == "203.0.113.7"


@pytest.mark.asyncio
async def test_two_hops_takes_second_from_right():
    """CDN + ingress: trust the CDN's view of the client (entry -2)."""
    inner = _FakeApp()
    mw = TrustedProxyMiddleware(inner, trusted_hops=2)
    scope = _http_scope(headers=[
        ("X-Forwarded-For", "203.0.113.7, 10.0.0.5, 10.0.0.1"),
    ])
    await mw(scope, _receive, _send)
    assert inner.captured["client"][0] == "10.0.0.5"


@pytest.mark.asyncio
async def test_websocket_https_maps_to_wss():
    inner = _FakeApp()
    mw = TrustedProxyMiddleware(inner, trusted_hops=1)
    scope = _ws_scope(headers=[("X-Forwarded-Proto", "https")])
    await mw(scope, _receive, _send)
    assert inner.captured["scheme"] == "wss"


@pytest.mark.asyncio
async def test_invalid_proto_value_ignored():
    inner = _FakeApp()
    mw = TrustedProxyMiddleware(inner, trusted_hops=1)
    scope = _http_scope(headers=[("X-Forwarded-Proto", "javascript")])
    await mw(scope, _receive, _send)
    assert inner.captured["scheme"] == "http"


@pytest.mark.asyncio
async def test_xff_shorter_than_trusted_hops_falls_back_to_peer():
    """If the chain is shorter than expected (misconfig), keep TCP peer."""
    inner = _FakeApp()
    mw = TrustedProxyMiddleware(inner, trusted_hops=3)
    scope = _http_scope(headers=[("X-Forwarded-For", "1.2.3.4")])
    await mw(scope, _receive, _send)
    assert inner.captured["client"] == ("198.51.100.1", 54321)

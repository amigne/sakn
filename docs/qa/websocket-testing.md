# WebSocket testing — Starlette TestClient limitation

## Problem

Starlette's `TestClient` does not expose the WebSocket close code sent by the
server **before** `websocket.accept()`. When the server calls
`await websocket.close(code=4XXX)` prior to accepting, the TestClient always
reports close code `1000` — the RFC 6455 normal closure code — regardless of
the actual code the server sent.

This is a known Starlette limitation: the TestClient's WebSocket session
implicitly accepts the connection before the server-side accept/reject logic
runs, so any close frame sent pre-accept is consumed internally and the
application-level close code is discarded.

## Impact on SAKN

SAKN's WebSocket endpoint (`tool_stream`) performs several checks **before**
calling `await websocket.accept()`:

- Origin validation (CSWSH protection, ADR-009) → close code 4003
- Database availability → close code 4503
- Rate limiting → close code 4029
- Session/permission validation → close code 4003

All of these close codes are **pre-accept** and therefore invisible to
Starlette's TestClient.

## Solution

Instead of using `TestClient.websocket_connect()`, tests call
`tool_stream(ws, tool_name)` directly with a **mock WebSocket**
(`unittest.mock.AsyncMock`). The mock's `close()` method records the
`code` and `reason` keyword arguments, allowing assertions on the exact
close code the server intended to send.

This is implemented in:
- `tests/integration/test_websocket.py` — all WebSocket fail-closed tests

## Alternative (if end-to-end WS testing is needed)

To test the full WebSocket handshake path (including Starlette's routing
and middleware), use `httpx.AsyncClient` with the ASGI transport instead of
Starlette's TestClient. `httpx` exposes close events correctly, but this
approach is heavier and may not be needed given the mock-based coverage.

## References

- Starlette TestClient source: `starlette/testclient.py` (`WebSocketTestSession`)
- SAKN ADR-009: WebSocket origin enforcement
- Issues: #43 (DB exception fail-closed), #60 (DB unavailable), #61 (rate limit), #46 (origin validation)

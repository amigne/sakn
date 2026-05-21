# Live Tools Specification — Ping & Traceroute

> **Version:** 3.0 — Extracted from technical-spec v2.0
> **Status:** Draft
> **Date:** 2026-05-14

WebSocket-based continuous tools. Load with `spec-common.md`, `spec-backend.md`, and `spec-api-contract.md`.

---

## 1. WebSocket Protocol

### 1.1 Endpoint & Auth

`/api/v1/tools/{tool_name}/stream` — WSS in production (Caddy terminates TLS), WS direct to Uvicorn in dev. Authenticated via session cookie on connect. Server treats disconnection as implicit cancel.

### 1.2 Message Types

| Direction | Type | Purpose |
|---|---|---|
| Client → Server | `start` | Launch execution with tool-specific params |
| Client → Server | `cancel` | User stops execution |
| Server → Client | `result` | Incremental partial result (1 packet or 1 hop) |
| Server → Client | `notice` | Non-blocking info (e.g., "IPv6 unavailable, falling back to IPv4") |
| Server → Client | `complete` | Execution finished with aggregated summary |
| Server → Client | `error` | Blocking error before or during execution |

### 1.3 Common Patterns

- All messages carry `{"type": "<type>", ...}`.
- `result` carries a sequence identifier (`seq` for Ping, `hop` for Traceroute).
- Each `result.data` has a `status` field: `ok`, `timeout`, or `error` (with `error_type`).
- `notice` and `error` carry `message_key` + `message` for i18n.
- `complete` carries `summary` + `duration_ms` + `terminated_by` (`completed`, `user`, `max_duration`, `error`).
- `cancel` (empty body) triggers `complete` with `"terminated_by": "user"` and partial results accumulated so far.

### 1.4 Connection Lifecycle

Client connects → authenticated via session cookie → sends `start` → server streams `result`/`notice` → optional client `cancel` → server sends `complete` → client closes. Server treats disconnect as implicit cancel.

### 1.5 Connection Rejection Codes

The server may close the WebSocket before accepting the handshake. The following close codes (RFC 6455 §7.4.2, application range 4000–4999) are defined in `src/backend/app/api/v1/endpoints/ws_codes.py`:

| Constant | Code | Semantics | Trigger |
|---|---|---|---|
| `WS_CLOSE_INVALID_ORIGIN` | 4003 | Origin header not in CORS_ORIGINS allowlist | CSWSH check fails |
| `WS_CLOSE_PERMISSION_DENIED` | 4003 | Access denied (tool disabled, role not allowed) | Permission check fails |
| `WS_CLOSE_UNKNOWN_TOOL` | 4004 | Tool name not recognized | Unknown tool in WS path |
| `WS_CLOSE_RATE_LIMITED` | 4029 | Rate limit exceeded | Visitor/authenticated hard limit hit |
| `WS_CLOSE_INVALID_SESSION` | 4401 | Session invalid or expired (reserved) | — |
| `WS_CLOSE_DB_UNAVAILABLE` | 4503 | Database unavailable for authorization | `is_db_available()` returns False |

---

## 2. Ping

### 2.1 Execution Strategy

System `ping` command via subprocess, output streamed per-packet over WebSocket.

### 2.2 Start Message

```json
{
  "type": "start",
  "params": {
    "target": "8.8.8.8",
    "count": 4,
    "timeout": 10,
    "packet_size": 56,
    "df_bit": false,
    "dscp": 0,
    "max_duration": 30
  }
}
```

**Params**: `target` (IP, pre-resolved by security filter), `count` (optional, default unlimited = 0 = runs until max_duration or user stops), `timeout` (per-packet, seconds), `packet_size` (bytes), `df_bit` (don't fragment), `dscp` (traffic class), `max_duration` (hard stop, seconds).

### 2.3 Result Message

```json
{
  "type": "result",
  "seq": 1,
  "data": {
    "status": "ok",
    "rtt_ms": 12.3,
    "ttl": 54,
    "bytes": 64
  }
}
```

**Status variants**:
- `ok`: `rtt_ms`, `ttl`, `bytes` present.
- `timeout`: only `status` field.
- `error`: `status` + `error_type` (`destination_unreachable`, `ttl_exceeded`, `source_quench`, `redirect`, `unknown`) + `from_ip`.

### 2.4 Complete Message

```json
{
  "type": "complete",
  "data": {
    "summary": {
      "transmitted": 4,
      "received": 3,
      "lost": 1,
      "loss_pct": 25.0,
      "rtt_min_ms": 11.8,
      "rtt_avg_ms": 12.4,
      "rtt_max_ms": 13.1,
      "rtt_stddev_ms": 0.5
    },
    "duration_ms": 3125.0,
    "terminated_by": "completed"
  }
}
```

---

## 3. Traceroute

### 3.1 Execution Strategy

System `traceroute` command via subprocess, output streamed per-hop over WebSocket. Supports UDP, ICMP, and TCP modes.

### 3.2 Start Message

```json
{
  "type": "start",
  "params": {
    "target": "8.8.8.8",
    "protocol": "udp",
    "port": 33434,
    "probes_per_hop": 3,
    "timeout": 5,
    "max_distance": 30,
    "dns_resolution": true
  }
}
```

**Params**: `target` (IP, pre-resolved), `protocol` (udp/icmp/tcp), `port`, `probes_per_hop`, `timeout` (per-probe, seconds), `max_distance` (max hops), `dns_resolution` (resolve IPs to hostnames).

### 3.3 Result Message (standard hop)

```json
{
  "type": "result",
  "hop": 1,
  "data": {
    "ip": "192.168.1.1",
    "hostname": "router.home",
    "probes": [
      {"rtt_ms": 2.3, "status": "ok"},
      {"rtt_ms": 2.1, "status": "ok"},
      {"rtt_ms": 2.5, "status": "ok"}
    ]
  }
}
```

`hostname` is `null` when `dns_resolution` is `false` or resolution fails.

### 3.4 Result Variants

**Timeouts** (partial or full): `rtt_ms: null`, `status: "timeout"`. Hop with all timeouts → `ip: null`, `hostname: null`.

**Multipath routing**:
```json
{
  "type": "result",
  "hop": 4,
  "data": {
    "multipath": true,
    "paths": [
      {
        "ip": "142.251.37.1",
        "hostname": null,
        "probes": [{"rtt_ms": 15.2, "status": "ok"}, {"rtt_ms": null, "status": "timeout"}]
      },
      {
        "ip": "142.251.37.2",
        "hostname": null,
        "probes": [{"rtt_ms": 16.1, "status": "ok"}]
      }
    ]
  }
}
```

**Destination reached**: `"reached": true` in hop data.

### 3.5 Complete Message

```json
{
  "type": "complete",
  "data": {
    "summary": {
      "hops_probed": 8,
      "destination_reached": true,
      "total_time_ms": 4521.0
    },
    "terminated_by": "completed"
  }
}
```

---

## 4. Subprocess Sandboxing

### 4.1 Isolation Rules

1. **Timeout**: hard timeout = `max_duration + 10s`. Subprocess killed `SIGTERM` then `SIGKILL`.
2. **Process group**: subprocesses in separate process group → clean termination of children.
3. **Resource limits**: CPU time, address space, file descriptors via `prlimit` or Python `resource`.
4. **User**: runs as `nobody` (or dedicated `sakn-exec` user), minimum capabilities.
5. **Output**: only stdout captured and exposed. Stderr logged but not returned to user.
6. **No shell**: `subprocess.Popen` with list arguments, NEVER `shell=True`. All params as separate list items.

### 4.2 Command Injection Prevention

- Target IP validated via `ipaddress.ip_address()` before subprocess.
- Hostnames resolved by app (via `dnspython`), IP passed to subprocess (NOT hostname).
- Numeric params validated as integers within acceptable ranges.
- Under no circumstances is user input interpolated into a shell command string.

### 4.3 Privilege Model

| Capability | Required By | Grant Method |
|---|---|---|
| `CAP_NET_RAW` | Ping (ICMP), Traceroute (raw sockets) | `setcap` on binaries + Docker `cap_add: NET_RAW` |
| `CAP_NET_ADMIN` | Traceroute (some ICMP modes) | Docker `cap_add: NET_ADMIN` |

**Principle**: minimum capabilities. NOT `--privileged`, NOT root. Python backend as `uid=1000`. `setcap cap_net_raw+ep` on `/usr/bin/ping` and `/usr/sbin/traceroute` at image build time.

### 4.4 Timeout & Resource Limits

| Tool | Mechanism | Default | Maximum |
|---|---|---|---|
| Ping | per-packet `timeout` + `max_duration` hard stop | 10s / 30s total | 60s per-packet |
| Traceroute | per-probe `timeout` × probes | 5s per-probe, 30 hops = 450s max | 30s per-probe, 64 hops |

All subprocesses: wall-clock timeout via `asyncio.wait_for()` at `max_duration + 30s`.

### 4.5 Concurrency

Multiple tool executions per user allowed. Each is an independent asyncio task. Rate limiting counters accumulate across concurrent executions.

### 4.6 WebSocket Cleanup

On disconnect: `SIGTERM` to subprocess, 5s grace period for final results, then `SIGKILL`. WebSocket connections tracked in memory; idle connections (>2× max_duration) cleaned up periodically. Heartbeat/ping frames detect dead connections.

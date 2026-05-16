import asyncio
import logging
import time
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from app.tools.ping import PingTool
from app.tools.network.executor import SubprocessExecutor
from app.security.address_filter import filter_target

logger = logging.getLogger(__name__)

# Ping sends packets 1 second apart (default interval)
PING_INTERVAL = 1.0


async def handle_ping_stream(websocket: WebSocket, session_id: str, user_id: str | None, source_ip: str) -> None:
    tool = PingTool(executor=SubprocessExecutor(hard_timeout=90.0))
    process: asyncio.subprocess.Process | None = None

    try:
        raw = await websocket.receive_json()
        if raw.get("type") != "start":
            await websocket.send_json({"type": "error", "message_key": "errors.invalid_params", "message": "Expected 'start' message"})
            return

        params = raw.get("params", {})
        try:
            validated = tool.validate_params(params)
        except ValueError as e:
            await websocket.send_json({"type": "error", "message_key": "errors.invalid_params", "message": str(e)})
            return

        resolved_ip, block_error = await filter_target(validated["target"])
        if block_error:
            await websocket.send_json({
                "type": "error",
                "message_key": block_error,
                "message": "Target not allowed" if "not_allowed" in block_error else "DNS resolution failed",
            })
            return

        args = PingTool._build_args(resolved_ip, validated)
        count = validated.get("count", 4)
        per_packet_timeout = validated.get("timeout", 10)
        max_duration = validated.get("max_duration", 30)
        hard_timeout = max_duration  # no buffer — exact deadline

        start = time.monotonic()
        process = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        results_by_seq: dict[int, dict[str, Any]] = {}
        received_seqs: set[int] = set()
        cancelled = False
        stdout_parts: list[str] = []

        async def read_stdout():
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                decoded = line.decode("utf-8", errors="replace").strip()
                if not decoded:
                    continue
                stdout_parts.append(decoded)
                if decoded.startswith("PING") or decoded.startswith("---"):
                    continue
                parsed = PingTool._parse_output(decoded)
                if parsed:
                    item = parsed[0]
                    if item.get("status") == "error":
                        # Local error (e.g. Message too long) — send as notice
                        await websocket.send_json({
                            "type": "notice",
                            "message_key": "notices.ping_local_error",
                            "message": item.get("message", "Local error"),
                        })
                        continue
                    item_seq = item.get("seq")
                    if item_seq is None:
                        # Seq-less timeout — assign next available
                        item_seq = max(results_by_seq.keys(), default=0) + 1
                        item["seq"] = item_seq
                    results_by_seq[item_seq] = item
                    received_seqs.add(item_seq)
                    await websocket.send_json({
                        "type": "result",
                        "seq": item_seq,
                        "data": item,
                    })

        async def read_stderr():
            while True:
                line = await process.stderr.readline()
                if not line:
                    break
                decoded = line.decode("utf-8", errors="replace").strip()
                if decoded:
                    logger.info("ping stderr: %s", decoded[:500])
                    # Forward local errors as notices so the user sees them
                    if "ping:" in decoded:
                        await websocket.send_json({
                            "type": "notice",
                            "message_key": "notices.ping_local_error",
                            "message": decoded,
                        })

        async def listen_cancel():
            nonlocal cancelled
            try:
                while True:
                    msg = await websocket.receive_json()
                    if msg.get("type") == "cancel":
                        cancelled = True
                        if process.returncode is None:
                            process.terminate()
                        return
            except Exception:
                pass

        async def watch_timeouts():
            """Emit timeout results in real-time when per-packet timeout expires."""
            if count <= 0:
                return  # Unlimited mode: can't predict seq numbers

            while process.returncode is None and not cancelled:
                now = time.monotonic()
                for seq in range(1, count + 1):
                    if seq in received_seqs:
                        continue
                    packet_send_time = start + (seq - 1) * PING_INTERVAL
                    timeout_at = packet_send_time + per_packet_timeout
                    if now >= timeout_at:
                        timeout_entry = {"status": "timeout", "seq": seq}
                        results_by_seq[seq] = timeout_entry
                        received_seqs.add(seq)
                        await websocket.send_json({
                            "type": "result",
                            "seq": seq,
                            "data": timeout_entry,
                        })
                await asyncio.sleep(0.3)

        read_task = asyncio.create_task(read_stdout())
        stderr_task = asyncio.create_task(read_stderr())
        cancel_task = asyncio.create_task(listen_cancel())
        timeout_watch_task = asyncio.create_task(watch_timeouts())

        try:
            await asyncio.wait_for(process.wait(), timeout=hard_timeout)
            timed_out = False
        except asyncio.TimeoutError:
            timed_out = True
            if process.returncode is None:
                process.kill()
            await process.wait()

        cancel_task.cancel()
        timeout_watch_task.cancel()
        await read_task
        await stderr_task

        # Parse statistics block from full stdout for accurate summary counts
        full_stdout = "\n".join(stdout_parts)
        parsed_summary = PingTool._parse_summary(full_stdout)

        real_transmitted = parsed_summary.get("transmitted", 0)
        use_count = real_transmitted if real_transmitted > 0 else (count if count > 0 else max(results_by_seq.keys(), default=0))

        # When max_duration killed the process, cap at packets physically sendable
        if timed_out and max_duration > 0:
            max_possible = int(max_duration / PING_INTERVAL)  # exclude last packet sent at deadline (no chance to reply)
            use_count = min(use_count, max_possible)

        # Fill in any remaining missing seqs as timeouts
        if use_count > 0:
            for s in range(1, use_count + 1):
                if s not in received_seqs:
                    results_by_seq[s] = {"status": "timeout", "seq": s}
                    await websocket.send_json({
                        "type": "result",
                        "seq": s,
                        "data": {"status": "timeout", "seq": s},
                    })

        terminated_by = "max_duration" if timed_out else ("user" if cancelled else "completed")
        duration_ms = (time.monotonic() - start) * 1000

        if real_transmitted > 0 and not timed_out:
            rtts = [r["rtt_ms"] for r in results_by_seq.values() if r.get("rtt_ms") is not None and r.get("status") == "ok"]
            summary = {
                "transmitted": parsed_summary["transmitted"],
                "received": parsed_summary["received"],
                "lost": parsed_summary["lost"],
                "loss_pct": parsed_summary["loss_pct"],
                "rtt_min_ms": round(min(rtts), 1) if rtts else None,
                "rtt_avg_ms": round(sum(rtts) / len(rtts), 1) if rtts else None,
                "rtt_max_ms": round(max(rtts), 1) if rtts else None,
                "rtt_mdev_ms": round(_stddev(rtts), 1) if len(rtts) >= 2 else None,
            }
        else:
            summary = _build_summary(results_by_seq, use_count)

        await websocket.send_json({
            "type": "complete",
            "data": {
                "summary": summary,
                "duration_ms": duration_ms,
                "terminated_by": terminated_by,
            },
        })

    except WebSocketDisconnect:
        if process and process.returncode is None:
            process.kill()
    except Exception:
        logger.exception("ping_ws error")
        try:
            await websocket.send_json({
                "type": "error",
                "message_key": "errors.internal_error",
                "message": "An unexpected error occurred",
            })
        except Exception:
            pass
    finally:
        if process and process.returncode is None:
            try:
                process.kill()
            except Exception:
                pass


def _stddev(values: list[float]) -> float:
    """Population standard deviation."""
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((x - mean) ** 2 for x in values) / len(values)
    return variance ** 0.5


def _build_summary(results_by_seq: dict[int, dict[str, Any]], expected_count: int) -> dict[str, Any]:
    transmitted = max(expected_count, max(results_by_seq.keys(), default=0))
    received = sum(1 for r in results_by_seq.values() if r.get("status") == "ok")
    lost = transmitted - received
    loss_pct = round((lost / transmitted * 100), 1) if transmitted > 0 else 0.0
    rtts = [r["rtt_ms"] for r in results_by_seq.values() if r.get("rtt_ms") is not None and r.get("status") == "ok"]

    return {
        "transmitted": transmitted,
        "received": received,
        "lost": lost,
        "loss_pct": loss_pct,
        "rtt_min_ms": round(min(rtts), 1) if rtts else None,
        "rtt_avg_ms": round(sum(rtts) / len(rtts), 1) if rtts else None,
        "rtt_max_ms": round(max(rtts), 1) if rtts else None,
        "rtt_mdev_ms": round(_stddev(rtts), 1) if len(rtts) >= 2 else None,
    }

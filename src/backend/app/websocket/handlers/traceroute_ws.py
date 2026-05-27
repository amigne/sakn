import asyncio
import contextlib
import logging
import time
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.database import async_session_factory
from app.models.preferences import GlobalSetting
from app.security.address_filter import filter_target, is_ip_blocked
from app.tools.network.executor import SubprocessExecutor
from app.tools.traceroute import (
    HEADER_RE,
    HOP_LINE_RE,
    TracerouteTool,
    _parse_probes_from_tokens,
)

logger = logging.getLogger(__name__)

# Max per-hop timeout budget: probes_per_hop * timeout + margin
PER_HOP_MAX_WAIT_FACTOR = 2.0


def mask_private_hops(data: dict[str, Any], show_private: bool) -> dict[str, Any]:
    """Mask private IP addresses in a traceroute hop, respecting the show_private setting.

    When show_private is False and all paths in a multipath hop are private,
    the hop is collapsed to a regular hop and probes from all paths are merged
    into a single top-level probes array.
    """
    if show_private:
        return data

    if data.get("multipath"):
        masked_paths = []
        for path in data.get("paths", []):
            pip = path.get("ip")
            if pip and is_ip_blocked(pip):
                masked_paths.append({**path, "ip": "[hidden]", "hostname": None})
            else:
                masked_paths.append(path)
        data["paths"] = masked_paths
        if all(p["ip"] == "[hidden]" for p in masked_paths):
            data["multipath"] = False
            data["ip"] = "[hidden]"
            data["hostname"] = None
            data["probes"] = [probe for path in masked_paths for probe in path.get("probes", [])]
            data.pop("paths", None)
        return data

    if data.get("ip") and is_ip_blocked(data["ip"]):
        data["ip"] = "[hidden]"
        data["hostname"] = None
    return data


async def _log_tool_exec(
    tool_name: str, params: dict, result: str, duration_ms: int,
    error_msg: str | None, user_id: str | None, session_id: str, source_ip: str,
) -> None:
    try:
        from app.database import async_session_factory, is_db_available
        if not is_db_available():
            return
        import app.services.log_service as log_svc
        async with async_session_factory() as db:
            await log_svc.create_tool_execution_log(
                db, user_id=user_id, session_id=session_id, source_ip=source_ip,
                tool_name=tool_name, parameters=params, result=result,
                duration_ms=duration_ms, error_message=error_msg,
            )
            await db.commit()
    except Exception:
        logger.exception("Failed to log WS tool execution")


async def handle_traceroute_stream(
    websocket: WebSocket,
    session_id: str,
    user_id: str | None,
    source_ip: str,
) -> None:
    tool = TracerouteTool(executor=SubprocessExecutor(hard_timeout=600.0))
    process: asyncio.subprocess.Process | None = None

    try:
        raw = await websocket.receive_json()
        if raw.get("type") != "start":
            await websocket.send_json({
                "type": "error",
                "message_key": "errors.invalid_params",
                "message": "Expected 'start' message",
            })
            return

        params = raw.get("params", {})
        try:
            validated = tool.validate_params(params)
        except ValueError as e:
            await websocket.send_json({
                "type": "error",
                "message_key": "errors.invalid_params",
                "message": str(e),
            })
            return

        resolved_ip, block_error = await filter_target(validated["target"])
        if block_error:
            await websocket.send_json({
                "type": "error",
                "message_key": block_error,
                "message": "Target not allowed" if "not_allowed" in block_error else "DNS resolution failed",
            })
            return

        # Read module setting: whether to show private IPs in hops
        show_private = True
        try:
            async with async_session_factory() as db:
                row = await db.execute(
                    select(GlobalSetting).where(GlobalSetting.key == "module.traceroute.show_private_hops")
                )
                setting = row.scalar_one_or_none()
                if setting is not None:
                    show_private = setting.value.lower() not in ("false", "0", "no", "off")
        except Exception:
            pass

        def _mask_private(data: dict[str, Any]) -> dict[str, Any]:
            return mask_private_hops(data, show_private)

        args = TracerouteTool._build_args(resolved_ip, validated)
        max_distance = validated.get("max_distance", 30)
        timeout = validated.get("timeout", 1)
        probes_per_hop = validated.get("probes_per_hop", 3)
        # Hard timeout: max_distance * timeout * probes + generous margin
        hard_timeout = max_distance * timeout * probes_per_hop + 60

        start = time.monotonic()
        process = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        cancelled = False
        hops_sent = 0
        destination_reached = False
        stdout_parts: list[str] = []

        # Buffer for multipath continuation lines
        current_hop_lines: list[str] = []
        current_hop_num: int | None = None
        current_hop_probe_count: int = 0

        async def flush_current_hop():
            nonlocal current_hop_num, current_hop_lines, hops_sent, destination_reached, current_hop_probe_count
            if current_hop_num is not None and current_hop_lines:
                hop_data = TracerouteTool._parse_hop_group(current_hop_num, current_hop_lines)
                data = hop_data["data"]
                data = _mask_private(data)

                # Detect destination reached: the resolved target IP appears
                # as one of the responding IPs in this hop
                if not destination_reached:
                    if data.get("ip") == resolved_ip:
                        data["reached"] = True
                        destination_reached = True
                    elif data.get("multipath"):
                        for path in data.get("paths", []):
                            if path.get("ip") == resolved_ip:
                                data["reached"] = True
                                destination_reached = True
                                break

                await websocket.send_json({
                    "type": "result",
                    "hop": current_hop_num,
                    "data": data,
                })
                hops_sent = current_hop_num

            current_hop_num = None
            current_hop_lines = []
            current_hop_probe_count = 0

        async def read_stdout():
            nonlocal current_hop_num, current_hop_lines, current_hop_probe_count
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                decoded = line.decode("utf-8", errors="replace").strip()
                if not decoded:
                    continue
                stdout_parts.append(decoded)

                if HEADER_RE.match(decoded):
                    continue

                m = HOP_LINE_RE.match(decoded)
                if m:
                    # New hop: flush the previous one
                    await flush_current_hop()
                    current_hop_num = int(m.group(1))
                    current_hop_lines = [m.group(2)]
                    current_hop_probe_count = len(_parse_probes_from_tokens(m.group(2).split()))
                elif current_hop_num is not None:
                    # Continuation line (multipath)
                    current_hop_lines.append(decoded)
                    current_hop_probe_count += len(_parse_probes_from_tokens(decoded.split()))

                # Flush as soon as we have all expected probes for this hop
                if current_hop_num is not None and current_hop_probe_count >= probes_per_hop:
                    await flush_current_hop()

        async def read_stderr():
            while True:
                line = await process.stderr.readline()
                if not line:
                    break
                decoded = line.decode("utf-8", errors="replace").strip()
                if decoded:
                    logger.info("traceroute stderr: %s", decoded[:500])

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

        read_task = asyncio.create_task(read_stdout())
        stderr_task = asyncio.create_task(read_stderr())
        cancel_task = asyncio.create_task(listen_cancel())

        try:
            await asyncio.wait_for(process.wait(), timeout=hard_timeout)
            timed_out = False
        except TimeoutError:
            timed_out = True
            if process.returncode is None:
                process.kill()
            await process.wait()

        cancel_task.cancel()
        await read_task
        await stderr_task

        # Flush any remaining buffered hop
        await flush_current_hop()

        terminated_by = (
            "max_duration" if timed_out else ("user" if cancelled else "completed")
        )
        duration_ms = (time.monotonic() - start) * 1000

        await websocket.send_json({
            "type": "complete",
            "data": {
                "summary": {
                    "hops_probed": hops_sent,
                    "destination_reached": destination_reached,
                    "total_time_ms": round(duration_ms, 1),
                },
                "duration_ms": round(duration_ms, 1),
                "terminated_by": terminated_by,
            },
        })

        result = "success" if terminated_by == "completed" else "partial"
        await _log_tool_exec("traceroute", validated, result, round(duration_ms), None,
                             user_id, session_id, source_ip)

    except WebSocketDisconnect:
        await _log_tool_exec("traceroute", params, "partial", 0,
                             "Cancelled by user", user_id, session_id, source_ip)
        if process and process.returncode is None:
            process.kill()
    except Exception as e:
        logger.exception("traceroute_ws error")
        await _log_tool_exec("traceroute", params, "failure", 0, str(e),
                             user_id, session_id, source_ip)
        with contextlib.suppress(Exception):
            await websocket.send_json({
                "type": "error",
                "message_key": "errors.internal_error",
                "message": "An unexpected error occurred",
            })
    finally:
        if process and process.returncode is None:
            with contextlib.suppress(Exception):
                process.kill()

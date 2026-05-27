import logging
import re
import time
from typing import Any

from app.security.address_filter import filter_target
from app.tools.base import BaseTool, ExecutionContext, ToolCategory, ToolDefinition, ToolParameter, ToolResult
from app.tools.network.executor import SubprocessExecutor

logger = logging.getLogger(__name__)

PING_LINE_RE = re.compile(
    r"(\d+) bytes from ([\d\.a-f:]+):\s+icmp_seq=(\d+)\s+ttl=(\d+)\s+time=([\d\.]+)\s*ms"
)

TIMEOUT_RE = re.compile(r"no answer yet for icmp_seq=(\d+)")

LOCAL_ERROR_RE = re.compile(r"ping:\s+(.+)$")

SUMMARY_RE = re.compile(
    r"(\d+) packets transmitted,\s+(\d+) received.*?(\d+)% packet loss.*?time\s+(\d+)ms",
    re.DOTALL,
)

RTT_STATS_RE = re.compile(
    r"rtt min/avg/max/mdev\s*=\s*([\d\.]+)/([\d\.]+)/([\d\.]+)/([\d\.]+)\s*ms"
)

STATISTICS_SEPARATOR = "---"


class PingTool(BaseTool):
    def __init__(self, executor: SubprocessExecutor | None = None):
        self._executor = executor or SubprocessExecutor(hard_timeout=90.0)

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="ping",
            display_name_key="tools.ping.name",
            description_key="tools.ping.description",
            category=ToolCategory.NETWORK,
            version="1.0.0",
            parameters=[
                ToolParameter(
                    name="target",
                    type="string",
                    label_key="tools.ping.param_target_label",
                    description_key="tools.ping.param_target_desc",
                    required=True,
                    constraints={"max_length": 255},
                ),
                ToolParameter(
                    name="count",
                    type="integer",
                    label_key="tools.ping.param_count_label",
                    description_key="tools.ping.param_count_desc",
                    default=4,
                    constraints={"min": 0, "max": 100},
                ),
                ToolParameter(
                    name="timeout",
                    type="integer",
                    label_key="tools.ping.param_timeout_label",
                    description_key="tools.ping.param_timeout_desc",
                    default=10,
                    constraints={"min": 1, "max": 60},
                ),
                ToolParameter(
                    name="packet_size",
                    type="integer",
                    label_key="tools.ping.param_packet_size_label",
                    description_key="tools.ping.param_packet_size_desc",
                    default=56,
                    constraints={"min": 8, "max": 65507},
                ),
                ToolParameter(
                    name="df_bit",
                    type="boolean",
                    label_key="tools.ping.param_df_bit_label",
                    description_key="tools.ping.param_df_bit_desc",
                    default=False,
                ),
                ToolParameter(
                    name="dscp",
                    type="integer",
                    label_key="tools.ping.param_dscp_label",
                    description_key="tools.ping.param_dscp_desc",
                    default=0,
                    constraints={"min": 0, "max": 63},
                ),
                ToolParameter(
                    name="max_duration",
                    type="integer",
                    label_key="tools.ping.param_max_duration_label",
                    description_key="tools.ping.param_max_duration_desc",
                    default=30,
                    constraints={"min": 1, "max": 300},
                ),
            ],
            requires_privileges=["NET_RAW"],
        )

    def validate_params(self, params: dict[str, Any]) -> dict[str, Any]:
        target = params.get("target", "").strip()
        if not target:
            raise ValueError("Target is required")

        count = int(params.get("count", 4))
        if count < 0 or count > 100:
            raise ValueError("Count must be 0-100")

        timeout = int(params.get("timeout", 10))
        if timeout < 1 or timeout > 60:
            raise ValueError("Timeout must be 1-60")

        packet_size = int(params.get("packet_size", 56))
        if packet_size < 8 or packet_size > 65507:
            raise ValueError("Packet size must be 8-65507")

        dscp = int(params.get("dscp", 0))
        if dscp < 0 or dscp > 63:
            raise ValueError("DSCP must be 0-63")

        max_duration = int(params.get("max_duration", 30))
        if max_duration < 1 or max_duration > 300:
            raise ValueError("Max duration must be 1-300")

        return {
            "target": target,
            "count": count,
            "timeout": timeout,
            "packet_size": packet_size,
            "df_bit": bool(params.get("df_bit", False)),
            "dscp": dscp,
            "max_duration": max_duration,
        }

    async def execute(self, params: dict[str, Any], context: ExecutionContext) -> ToolResult:
        validated = self.validate_params(params)
        resolved_ip, block_error = await filter_target(validated["target"])
        if block_error:
            return ToolResult(success=False, error=block_error)

        args = self._build_args(resolved_ip, validated)

        start = time.monotonic()
        result = await self._executor.run(args, timeout=validated["max_duration"] + 10)
        duration_ms = (time.monotonic() - start) * 1000

        if result.timed_out:
            return ToolResult(success=False, error="errors.timeout", duration_ms=duration_ms)

        lines = self._parse_output(result.stdout)
        summary = self._parse_summary(result.stdout)

        return ToolResult(
            success=result.exit_code == 0 or len(lines) > 0,
            data={
                "lines": lines,
                "summary": summary,
                "raw_stdout": result.stdout,
            },
            duration_ms=duration_ms,
        )

    @staticmethod
    def _build_args(target_ip: str, params: dict[str, Any]) -> list[str]:
        args = ["ping"]
        count = params.get("count", 4)
        timeout = params.get("timeout", 10)
        packet_size = params.get("packet_size", 56)
        df_bit = params.get("df_bit", False)
        dscp = params.get("dscp", 0)
        max_duration = params.get("max_duration", 30)

        if count > 0:
            args.extend(["-c", str(count)])
        args.extend(["-W", str(timeout)])
        args.extend(["-s", str(packet_size)])
        if df_bit:
            args.extend(["-M", "do"])
        if dscp > 0:
            # DSCP uses bits 2-7 of the TOS byte → shift left by 2
            args.extend(["-Q", str(dscp << 2)])
        if max_duration > 0 and count == 0:
            # -w deadline only for unlimited count; with -c, count controls iterations
            args.extend(["-w", str(max_duration)])
        args.append(target_ip)
        return args

    @staticmethod
    def _parse_output(stdout: str) -> list[dict[str, Any]]:
        lines = []
        for line in stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            if line.startswith("PING"):
                continue
            if line.startswith(STATISTICS_SEPARATOR):
                break
            m = PING_LINE_RE.match(line)
            if m:
                lines.append({
                    "bytes": int(m.group(1)),
                    "from": m.group(2),
                    "seq": int(m.group(3)),
                    "ttl": int(m.group(4)),
                    "rtt_ms": float(m.group(5)),
                    "status": "ok",
                })
            else:
                tm = TIMEOUT_RE.search(line)
                if tm:
                    lines.append({"status": "timeout", "seq": int(tm.group(1))})
                elif erm := LOCAL_ERROR_RE.search(line):
                    lines.append({"status": "error", "error_type": "local_error", "message": erm.group(1)})
                elif "timeout" in line.lower() or "unreachable" in line.lower():
                    lines.append({"status": "timeout"})
        return lines

    @staticmethod
    def _parse_summary(stdout: str) -> dict[str, Any]:
        sm = SUMMARY_RE.search(stdout)
        if not sm:
            return {"transmitted": 0, "received": 0, "lost": 0, "loss_pct": 0.0}
        transmitted = int(sm.group(1))
        received = int(sm.group(2))
        loss_pct = float(sm.group(3))
        lost = transmitted - received

        rtts = [r.group(1, 2, 3, 4) for r in RTT_STATS_RE.finditer(stdout)]
        if rtts:
            r = rtts[0]
            return {
                "transmitted": transmitted,
                "received": received,
                "lost": lost,
                "loss_pct": loss_pct,
                "rtt_min_ms": float(r[0]),
                "rtt_avg_ms": float(r[1]),
                "rtt_max_ms": float(r[2]),
                "rtt_mdev_ms": float(r[3]),
            }

        return {
            "transmitted": transmitted,
            "received": received,
            "lost": lost,
            "loss_pct": loss_pct,
            "rtt_min_ms": None,
            "rtt_avg_ms": None,
            "rtt_max_ms": None,
            "rtt_mdev_ms": None,
        }

    def get_result_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "lines": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "bytes": {"type": "integer"},
                            "from": {"type": "string"},
                            "seq": {"type": "integer"},
                            "ttl": {"type": "integer"},
                            "rtt_ms": {"type": "number"},
                            "status": {"type": "string", "enum": ["ok", "timeout"]},
                        },
                    },
                },
                "summary": {
                    "type": "object",
                    "properties": {
                        "transmitted": {"type": "integer"},
                        "received": {"type": "integer"},
                        "lost": {"type": "integer"},
                        "loss_pct": {"type": "number"},
                        "rtt_min_ms": {"type": "number"},
                        "rtt_avg_ms": {"type": "number"},
                        "rtt_max_ms": {"type": "number"},
                        "rtt_mdev_ms": {"type": "number"},
                    },
                },
            },
        }

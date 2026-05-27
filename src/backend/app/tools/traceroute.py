import logging
import re
import time
from ipaddress import ip_address
from typing import Any

from app.security.address_filter import filter_target
from app.tools.base import BaseTool, ExecutionContext, ToolCategory, ToolDefinition, ToolParameter, ToolResult
from app.tools.network.executor import SubprocessExecutor

logger = logging.getLogger(__name__)

HOP_LINE_RE = re.compile(r"^\s*(\d+)\s+(.*)")
HEADER_RE = re.compile(r"traceroute\s+to\s+")


def _is_ip(s: str) -> bool:
    try:
        ip_address(s)
        return True
    except ValueError:
        return False


def _parse_probes_from_tokens(tokens: list[str]) -> list[dict[str, Any]]:
    """Parse probe measurements from a tokenized hop line segment.

    Handles both output formats:
      - IP (hostname) rtt ms  (no-DNS or inetutils style)
      - hostname (IP) rtt ms  (DNS-resolution style)
    """
    probes: list[dict[str, Any]] = []
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if t == "*":
            probes.append({"rtt_ms": None, "status": "timeout"})
            i += 1
        elif _is_ip(t):
            # IP (...) rtt or IP rtt
            i += 1
            if i < len(tokens) and tokens[i].startswith("(") and tokens[i].endswith(")"):
                i += 1
        elif i + 1 < len(tokens) and tokens[i + 1].startswith("(") and tokens[i + 1].endswith(")"):
            # hostname (IP) rtt
            i += 2
        else:
            try:
                rtt = float(t)
                if i + 1 < len(tokens) and tokens[i + 1] == "ms":
                    probes.append({"rtt_ms": rtt, "status": "ok"})
                    i += 2
                else:
                    probes.append({"rtt_ms": rtt, "status": "ok"})
                    i += 1
            except ValueError:
                i += 1
    return probes


def _extract_ip_hostname_map(tokens: list[str]) -> dict[str, str | None]:
    """Build a mapping of IP -> hostname from token stream.

    Handles both: ``IP (hostname)`` and ``hostname (IP)``.
    """
    mapping: dict[str, str | None] = {}
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if t == "*":
            i += 1
        elif _is_ip(t):
            ip = t
            hostname = None
            i += 1
            if i < len(tokens) and tokens[i].startswith("(") and tokens[i].endswith(")"):
                hostname = tokens[i][1:-1]
                i += 1
            if ip not in mapping:
                mapping[ip] = hostname
        elif i + 1 < len(tokens) and tokens[i + 1].startswith("(") and tokens[i + 1].endswith(")"):
            # hostname (IP) — IP is in the parentheses
            inner = tokens[i + 1][1:-1]
            if _is_ip(inner) and inner not in mapping:
                mapping[inner] = t
            i += 2
        else:
            try:
                float(t)
                i += 1
                if i < len(tokens) and tokens[i] == "ms":
                    i += 1
            except ValueError:
                i += 1
    return mapping


def _group_probes_by_ip(
    tokens: list[str],
    probes: list[dict[str, Any]],
    ip_map: dict[str, str | None],
) -> list[dict[str, Any]]:
    """Group probes by the responding IP for multipath detection."""
    if not ip_map:
        return []

    ip_list = list(ip_map.keys())
    if len(ip_list) <= 1:
        return []

    # Determine which IP each probe belongs to by walking tokens
    ip_assignment: list[str | None] = [None] * len(probes)
    i = 0
    probe_idx = 0
    current_ip: str | None = None
    while i < len(tokens) and probe_idx < len(probes):
        t = tokens[i]
        if _is_ip(t):
            current_ip = t
            i += 1
            if i < len(tokens) and tokens[i].startswith("(") and tokens[i].endswith(")"):
                i += 1
        elif t == "*":
            if current_ip:
                ip_assignment[probe_idx] = current_ip
            probe_idx += 1
            i += 1
        else:
            try:
                float(t)
                if current_ip:
                    ip_assignment[probe_idx] = current_ip
                probe_idx += 1
                i += 1
                if i < len(tokens) and tokens[i] == "ms":
                    i += 1
            except ValueError:
                i += 1

    paths_map: dict[str, list[dict[str, Any]]] = {}
    for idx, probe in enumerate(probes):
        assigned = ip_assignment[idx] if idx < len(ip_assignment) else None
        ip_key = assigned or (ip_list[0] if ip_list else "unknown")
        if ip_key not in paths_map:
            paths_map[ip_key] = []
        paths_map[ip_key].append(probe)

    return [
        {"ip": ip, "hostname": ip_map.get(ip), "probes": prbs}
        for ip, prbs in paths_map.items()
    ]


class TracerouteTool(BaseTool):
    def __init__(self, executor: SubprocessExecutor | None = None):
        self._executor = executor or SubprocessExecutor(hard_timeout=600.0)

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="traceroute",
            display_name_key="tools.traceroute.name",
            description_key="tools.traceroute.description",
            category=ToolCategory.NETWORK,
            version="1.0.0",
            parameters=[
                ToolParameter(
                    name="target",
                    type="string",
                    label_key="tools.traceroute.param_target_label",
                    description_key="tools.traceroute.param_target_desc",
                    required=True,
                    constraints={"max_length": 255},
                ),
                ToolParameter(
                    name="protocol",
                    type="enum",
                    label_key="tools.traceroute.param_protocol_label",
                    description_key="tools.traceroute.param_protocol_desc",
                    default="udp",
                    constraints={"options": ["udp", "icmp", "tcp"]},
                ),
                ToolParameter(
                    name="port",
                    type="integer",
                    label_key="tools.traceroute.param_port_label",
                    description_key="tools.traceroute.param_port_desc",
                    default=33434,
                    constraints={"min": 1, "max": 65535},
                ),
                ToolParameter(
                    name="probes_per_hop",
                    type="integer",
                    label_key="tools.traceroute.param_probes_label",
                    description_key="tools.traceroute.param_probes_desc",
                    default=3,
                    constraints={"min": 1, "max": 10},
                ),
                ToolParameter(
                    name="timeout",
                    type="integer",
                    label_key="tools.traceroute.param_timeout_label",
                    description_key="tools.traceroute.param_timeout_desc",
                    default=1,
                    constraints={"min": 1, "max": 30},
                ),
                ToolParameter(
                    name="max_distance",
                    type="integer",
                    label_key="tools.traceroute.param_max_distance_label",
                    description_key="tools.traceroute.param_max_distance_desc",
                    default=30,
                    constraints={"min": 1, "max": 64},
                ),
                ToolParameter(
                    name="dns_resolution",
                    type="boolean",
                    label_key="tools.traceroute.param_dns_resolution_label",
                    description_key="tools.traceroute.param_dns_resolution_desc",
                    default=True,
                ),
            ],
            requires_privileges=["NET_RAW"],
        )

    def validate_params(self, params: dict[str, Any]) -> dict[str, Any]:
        target = params.get("target", "").strip()
        if not target:
            raise ValueError("Target is required")

        protocol = params.get("protocol", "udp")
        if protocol not in ("udp", "icmp", "tcp"):
            raise ValueError("Protocol must be udp, icmp, or tcp")

        port = int(params.get("port", 33434))
        if port < 1 or port > 65535:
            raise ValueError("Port must be 1-65535")

        probes_per_hop = int(params.get("probes_per_hop", 3))
        if probes_per_hop < 1 or probes_per_hop > 10:
            raise ValueError("Probes per hop must be 1-10")

        timeout = int(params.get("timeout", 1))
        if timeout < 1 or timeout > 30:
            raise ValueError("Timeout must be 1-30")

        max_distance = int(params.get("max_distance", 30))
        if max_distance < 1 or max_distance > 64:
            raise ValueError("Max distance must be 1-64")

        return {
            "target": target,
            "protocol": protocol,
            "port": port,
            "probes_per_hop": probes_per_hop,
            "timeout": timeout,
            "max_distance": max_distance,
            "dns_resolution": bool(params.get("dns_resolution", True)),
        }

    async def execute(self, params: dict[str, Any], context: ExecutionContext) -> ToolResult:
        validated = self.validate_params(params)
        resolved_ip, block_error = await filter_target(validated["target"])
        if block_error:
            return ToolResult(success=False, error=block_error)

        args = self._build_args(resolved_ip, validated)

        start = time.monotonic()
        max_duration = validated["max_distance"] * validated["timeout"] * validated["probes_per_hop"] + 30
        result = await self._executor.run(args, timeout=max_duration)
        duration_ms = (time.monotonic() - start) * 1000

        if result.timed_out:
            return ToolResult(success=False, error="errors.timeout", duration_ms=duration_ms)

        hops = self._parse_output(result.stdout)

        return ToolResult(
            success=result.exit_code == 0 or len(hops) > 0,
            data={
                "hops": hops,
                "raw_stdout": result.stdout,
            },
            duration_ms=duration_ms,
        )

    @staticmethod
    def _build_args(target_ip: str, params: dict[str, Any]) -> list[str]:
        args = ["traceroute"]
        protocol = params.get("protocol", "udp")
        probes = params.get("probes_per_hop", 3)
        timeout = params.get("timeout", 5)
        max_distance = params.get("max_distance", 30)
        dns_resolution = params.get("dns_resolution", True)
        port = params.get("port", 33434)

        if not dns_resolution:
            args.append("-n")

        args.extend(["-q", str(probes)])
        args.extend(["-w", str(timeout)])
        args.extend(["-m", str(max_distance)])

        if protocol == "icmp":
            args.append("-I")
        elif protocol == "tcp":
            args.extend(["-T", "-p", str(port)])
        else:
            args.extend(["-p", str(port)])

        args.append(target_ip)
        return args

    @staticmethod
    def _parse_output(stdout: str) -> list[dict[str, Any]]:
        hops: list[dict[str, Any]] = []
        lines = stdout.splitlines()

        current_hop_lines: list[str] = []
        current_hop_num: int | None = None

        def flush_hop():
            nonlocal current_hop_num, current_hop_lines
            if current_hop_num is not None and current_hop_lines:
                hop_data = TracerouteTool._parse_hop_group(current_hop_num, current_hop_lines)
                hops.append(hop_data)
            current_hop_num = None
            current_hop_lines = []

        for line in lines:
            line = line.strip()
            if not line:
                continue
            if HEADER_RE.match(line):
                continue

            m = HOP_LINE_RE.match(line)
            if m:
                flush_hop()
                current_hop_num = int(m.group(1))
                current_hop_lines = [m.group(2)]
            elif current_hop_num is not None:
                current_hop_lines.append(line)

        flush_hop()
        return hops

    @staticmethod
    def _parse_hop_group(hop_num: int, line_segments: list[str]) -> dict[str, Any]:
        all_tokens: list[str] = []
        all_probes: list[dict[str, Any]] = []
        all_ip_map: dict[str, str | None] = {}

        for segment in line_segments:
            tokens = segment.strip().split()
            all_tokens.extend(tokens)
            probes = _parse_probes_from_tokens(tokens)
            ip_map = _extract_ip_hostname_map(tokens)
            all_probes.extend(probes)
            all_ip_map.update(ip_map)

        ip_list = list(all_ip_map.keys())

        # Multipath: multiple distinct IPs responded
        if len(ip_list) > 1:
            paths = _group_probes_by_ip(all_tokens, all_probes, all_ip_map)
            return {
                "hop": hop_num,
                "data": {
                    "multipath": True,
                    "paths": paths,
                    "reached": False,
                },
            }

        if ip_list:
            primary_ip = ip_list[0]
            return {
                "hop": hop_num,
                "data": {
                    "ip": primary_ip,
                    "hostname": all_ip_map.get(primary_ip),
                    "probes": all_probes,
                    "reached": False,
                },
            }

        # All timeouts
        return {
            "hop": hop_num,
            "data": {
                "ip": None,
                "hostname": None,
                "probes": all_probes if all_probes else [{"rtt_ms": None, "status": "timeout"}] * 3,
                "reached": False,
            },
        }

    def get_result_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "hops": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "hop": {"type": "integer"},
                            "data": {
                                "type": "object",
                                "properties": {
                                    "ip": {"type": "string"},
                                    "hostname": {"type": "string"},
                                    "probes": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "rtt_ms": {"type": "number"},
                                                "status": {"type": "string", "enum": ["ok", "timeout"]},
                                            },
                                        },
                                    },
                                    "multipath": {"type": "boolean"},
                                    "paths": {"type": "array"},
                                    "reached": {"type": "boolean"},
                                },
                            },
                        },
                    },
                },
            },
        }

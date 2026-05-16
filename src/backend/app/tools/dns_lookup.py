import logging
import time
from typing import Any

import dns.flags
import dns.rdatatype
import dns.resolver

from app.config import settings
from app.security.address_filter import is_ip_blocked, resolve_hostname
from app.tools.base import BaseTool, ExecutionContext, ToolCategory, ToolDefinition, ToolParameter, ToolResult

logger = logging.getLogger(__name__)

MAX_CNAME_DEPTH = 10

VALID_RECORD_TYPES = {"A", "AAAA", "CNAME", "MX", "NS", "TXT", "SRV", "SOA", "PTR", "CAA"}


def _rrset_type_name(rrset: Any) -> str:
    """Return the DNS type name for an RRset's rdtype."""
    try:
        return dns.rdatatype.to_text(rrset.rdtype)
    except Exception:
        return "?"


def _merge_rrsets(
    into: dict[str, list[dict[str, Any]]],
    rrsets: list[Any],
) -> dict[str, list[dict[str, Any]]]:
    """Merge RRset items into the *into* dict, keyed by type name."""
    for rrset in rrsets:
        rt = _rrset_type_name(rrset)
        if rt not in into:
            into[rt] = []
        for item in rrset:
            into[rt].append({
                "type": rt,
                "value": str(item),
                "ttl": rrset.ttl,
                "owner": str(rrset.name).rstrip("."),
            })
    return into


class DnsLookupTool(BaseTool):
    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="dns_lookup",
            display_name_key="tools.dns_lookup.name",
            description_key="tools.dns_lookup.description",
            category=ToolCategory.DNS,
            version="1.0.0",
            parameters=[
                ToolParameter(
                    name="target",
                    type="string",
                    label_key="tools.dns_lookup.param_target_label",
                    description_key="tools.dns_lookup.param_target_desc",
                    required=True,
                    constraints={"max_length": 255},
                ),
                ToolParameter(
                    name="record_types",
                    type="string",
                    label_key="tools.dns_lookup.param_record_types_label",
                    description_key="tools.dns_lookup.param_record_types_desc",
                    default=["A"],
                ),
                ToolParameter(
                    name="resolver",
                    type="string",
                    label_key="tools.dns_lookup.param_resolver_label",
                    description_key="tools.dns_lookup.param_resolver_desc",
                    default="",
                ),
                ToolParameter(
                    name="recursive_cname",
                    type="boolean",
                    label_key="tools.dns_lookup.param_recursive_cname_label",
                    description_key="tools.dns_lookup.param_recursive_cname_desc",
                    default=True,
                ),
            ],
        )

    def validate_params(self, params: dict[str, Any]) -> dict[str, Any]:
        target = (params.get("target") or params.get("domain") or "").strip()
        if not target:
            raise ValueError("Target domain is required")
        if len(target) > 255:
            raise ValueError("Domain exceeds 255 characters")

        # Normalize IDN to Punycode so the domain key matches DNS record owners.
        try:
            target = target.encode("idna").decode()
        except (UnicodeError, ValueError):
            raise ValueError("Invalid domain name")

        record_types = params.get("record_types", ["A"])
        if isinstance(record_types, str):
            record_types = [record_types]
        record_types = [rt.upper() for rt in record_types]
        invalid = [rt for rt in record_types if rt not in VALID_RECORD_TYPES]
        if invalid:
            raise ValueError(f"Invalid record types: {', '.join(invalid)}")

        resolver_ip = (params.get("resolver") or "").strip()
        if resolver_ip == "__system__":
            resolver_ip = ""

        recursive_cname = bool(params.get("recursive_cname", True))

        return {
            "target": target,
            "record_types": record_types,
            "resolver": resolver_ip,
            "recursive_cname": recursive_cname,
        }

    async def execute(self, params: dict[str, Any], context: ExecutionContext) -> ToolResult:
        validated = self.validate_params(params)
        target = validated["target"]
        record_types = validated["record_types"]
        resolver_ip = validated["resolver"]
        recursive_cname = validated["recursive_cname"]

        # Security filter: resolve target through trusted resolver, check for blocked IPs
        block_error = await self._security_check(target)
        if block_error:
            return ToolResult(success=False, error=block_error)

        start = time.monotonic()

        try:
            records: dict[str, list[dict[str, Any]]] = {}
            authority: dict[str, list[dict[str, Any]]] = {}
            additional: dict[str, list[dict[str, Any]]] = {}
            dnssec_ad_flag = False
            cname_chain: list[str] | None = None
            cname_blocked: dict[str, bool] = {}

            for rt in record_types:
                try:
                    # Fresh resolver per type — isolates slow queries so they
                    # don't consume the shared lifetime budget.
                    resolver_obj = self._make_resolver(resolver_ip)
                    answers = resolver_obj.resolve(target, rt)
                    rdtype = dns.rdatatype.from_text(rt)
                    rrset_records: list[dict[str, Any]] = []
                    for rrset in answers.response.answer:
                        if rrset.rdtype != rdtype:
                            continue
                        owner = str(rrset.name).rstrip(".")
                        for item in rrset:
                            rrset_records.append({
                                "type": rt,
                                "value": str(item),
                                "ttl": rrset.ttl,
                                "owner": owner,
                            })
                    records[rt] = rrset_records

                    # DNSSEC: record whether the AD flag was set on this response
                    if answers.response.flags & dns.flags.AD:
                        dnssec_ad_flag = True

                    # Collect authority and additional sections
                    authority = _merge_rrsets(authority, answers.response.authority)
                    additional = _merge_rrsets(additional, answers.response.additional)
                except dns.resolver.NoAnswer:
                    records[rt] = []
                except dns.resolver.NXDOMAIN:
                    duration_ms = (time.monotonic() - start) * 1000
                    return ToolResult(
                        success=False,
                        error="errors.nxdomain",
                        data={"domain": target},
                        duration_ms=duration_ms,
                    )
                except dns.exception.Timeout:
                    logger.warning("DNS timeout for %s/%s", target, rt)
                    records[rt] = []
                except Exception as e:
                    logger.warning("DNS query error for %s/%s: %s", target, rt, e)
                    records[rt] = []

            # CNAME chain following: resolve all record types for each hop
            cname_records: dict[str, dict[str, list[dict[str, Any]]]] = {}
            if recursive_cname and "CNAME" in records and records["CNAME"]:
                chain, cname_records, blocked = await self._follow_cname_chain(
                    target, resolver_ip, record_types
                )
                cname_chain = chain
                cname_blocked = blocked

            duration_ms = (time.monotonic() - start) * 1000

            return ToolResult(
                success=True,
                data={
                    "domain": target,
                    "records": records,
                    "authority": authority if authority else None,
                    "additional": additional if additional else None,
                    "dnssec_ad_flag": dnssec_ad_flag,
                    "cname_chain": cname_chain,
                    "cname_records": cname_records if cname_records else None,
                },
                duration_ms=duration_ms,
            )

        except dns.exception.Timeout:
            duration_ms = (time.monotonic() - start) * 1000
            logger.warning("DNS resolver lifetime expired for %s, returning partial results", target)
            has_any = any(v for v in records.values())
            return ToolResult(
                success=has_any,
                error=None if has_any else "errors.dns_timeout",
                data={"domain": target, "records": records, "cname_chain": cname_chain, "cname_records": None},
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = (time.monotonic() - start) * 1000
            logger.exception("DNS lookup failed for %s", target)
            return ToolResult(success=False, error=str(e), duration_ms=duration_ms)

    async def _security_check(self, target: str) -> str | None:
        """Check if the target domain resolves to blocked IPs via trusted resolver."""
        ips = await resolve_hostname(target)
        if not ips:
            return None  # Allow NXDOMAIN — it's a valid DNS query result, not a security issue
        for ip_str in ips:
            if is_ip_blocked(ip_str):
                logger.warning("DNS target %s resolved to blocked IP %s", target, ip_str)
                return "errors.target_not_allowed"
        return None

    # Workaround: DNS4EU public resolvers (86.54.11.x) are known to
    # respond slowly or not at all to certain record types (e.g. CNAME).
    # Use a shorter timeout so a single slow query doesn't block the user.
    _DNS4EU_IPS = frozenset({"86.54.11.1", "86.54.11.11", "86.54.11.12", "86.54.11.13", "86.54.11.100"})

    @classmethod
    def _make_resolver(cls, resolver_ip: str) -> dns.resolver.Resolver:
        resolver_obj = dns.resolver.Resolver()
        if resolver_ip:
            resolver_obj.nameservers = [resolver_ip]
        if resolver_ip in cls._DNS4EU_IPS:
            resolver_obj.timeout = 3
            resolver_obj.lifetime = 5  # 3s timeout + buffer
        else:
            resolver_obj.timeout = 5
            resolver_obj.lifetime = 8  # 5s timeout + buffer
        # Enable EDNS with DNSSEC OK flag so resolvers return the AD flag
        resolver_obj.use_edns(0, dns.flags.DO, 1232)
        return resolver_obj

    async def _follow_cname_chain(
        self,
        target: str,
        resolver_ip: str,
        record_types: list[str],
    ) -> tuple[list[str], dict[str, dict[str, list[dict[str, Any]]]], dict[str, bool]]:
        """Follow CNAME chain starting from target, checking each hop's IPs against blocklist.

        For each CNAME hop, resolves all requested record types.

        Returns (chain, cname_records, blocked) where cname_records maps each hop domain
        to its records grouped by type.
        """
        chain: list[str] = [target]
        cname_records: dict[str, dict[str, list[dict[str, Any]]]] = {}
        blocked: dict[str, bool] = {}
        seen: set[str] = {target.lower()}
        current = target

        for _ in range(MAX_CNAME_DEPTH):
            try:
                resolver_obj = self._make_resolver(resolver_ip)
                answers = resolver_obj.resolve(current, "CNAME")
                if not answers.response.answer:
                    break
                first_rrset = answers.response.answer[0]
                cname_items = list(first_rrset)
                if not cname_items:
                    break
                next_hop = str(cname_items[0]).rstrip(".")
                if next_hop.lower() in seen:
                    break  # Loop detected
                seen.add(next_hop.lower())
                chain.append(next_hop)

                # Security check: resolve this CNAME hop and check IPs against blocklist
                hop_ips = await resolve_hostname(next_hop)
                blocked[next_hop] = any(is_ip_blocked(ip) for ip in hop_ips)

                # Resolve all requested record types for this CNAME hop.
                # Only keep records that actually belong to this hop (owner == next_hop).
                hop_records: dict[str, list[dict[str, Any]]] = {}
                hop_owner = next_hop.rstrip(".")
                for rt in record_types:
                    try:
                        hop_resolver = self._make_resolver(resolver_ip)
                        rt_answers = hop_resolver.resolve(next_hop, rt)
                        rdtype = dns.rdatatype.from_text(rt)
                        items: list[dict[str, Any]] = []
                        for rrset in rt_answers.response.answer:
                            if rrset.rdtype != rdtype:
                                continue
                            owner = str(rrset.name).rstrip(".")
                            if owner != hop_owner:
                                continue
                            for item in rrset:
                                items.append({"type": rt, "value": str(item), "ttl": rrset.ttl, "owner": owner})
                        hop_records[rt] = items
                    except dns.resolver.NoAnswer:
                        hop_records[rt] = []
                    except Exception:
                        hop_records[rt] = []
                cname_records[next_hop] = hop_records

                current = next_hop
            except dns.resolver.NoAnswer:
                break
            except dns.resolver.NXDOMAIN:
                break
            except Exception:
                break

        return chain, cname_records, blocked

    def get_result_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "domain": {"type": "string"},
                "dnssec_ad_flag": {"type": "boolean"},
                "authority": {
                    "type": "object",
                    "additionalProperties": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "type": {"type": "string"},
                                "value": {"type": "string"},
                                "ttl": {"type": "integer"},
                                "owner": {"type": "string"},
                            },
                        },
                    },
                },
                "additional": {
                    "type": "object",
                    "additionalProperties": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "type": {"type": "string"},
                                "value": {"type": "string"},
                                "ttl": {"type": "integer"},
                                "owner": {"type": "string"},
                            },
                        },
                    },
                },
                "records": {
                    "type": "object",
                    "additionalProperties": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "type": {"type": "string"},
                                "value": {"type": "string"},
                                "ttl": {"type": "integer"},
                                "owner": {"type": "string"},
                            },
                        },
                    },
                },
                "cname_chain": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "cname_records": {
                    "type": "object",
                    "additionalProperties": {
                        "type": "object",
                        "additionalProperties": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "type": {"type": "string"},
                                    "value": {"type": "string"},
                                    "ttl": {"type": "integer"},
                                },
                            },
                        },
                    },
                },
            },
        }

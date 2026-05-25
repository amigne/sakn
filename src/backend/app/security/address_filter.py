from ipaddress import ip_address, ip_network
import logging
import dns.name
import dns.resolver
from app.config import settings

logger = logging.getLogger(__name__)

BLOCKED_NETWORKS = [
    # IPv4
    ip_network("0.0.0.0/8"),
    ip_network("10.0.0.0/8"),
    ip_network("100.64.0.0/10"),
    ip_network("127.0.0.0/8"),
    ip_network("169.254.0.0/16"),
    ip_network("172.16.0.0/12"),
    ip_network("172.17.0.0/16"),
    ip_network("172.18.0.0/16"),
    ip_network("192.0.2.0/24"),
    ip_network("192.168.0.0/16"),
    ip_network("198.18.0.0/15"),
    ip_network("198.51.100.0/24"),
    ip_network("203.0.113.0/24"),
    ip_network("224.0.0.0/4"),
    ip_network("240.0.0.0/4"),
    ip_network("255.255.255.255/32"),
    # IPv6
    ip_network("::1/128"),
    ip_network("::ffff:0:0/96"),
    ip_network("fc00::/7"),
    ip_network("fe80::/10"),
    ip_network("ff00::/8"),
]

CNAME_MAX_HOPS = 16


def is_ip_blocked(target_ip: str) -> bool:
    """Check if an IP address is in the blocked networks list."""
    try:
        ip = ip_address(target_ip)
    except ValueError:
        return True
    for net in BLOCKED_NETWORKS:
        if ip in net:
            return True
    return False


def _make_resolver(resolver_ip: str) -> dns.resolver.Resolver:
    r = dns.resolver.Resolver()
    r.nameservers = [resolver_ip]
    r.timeout = 3
    r.lifetime = 5
    return r


def _check_ips(ips: list[str], context: str) -> list[str] | None:
    """Return ips if all pass the blocklist, None if any is blocked."""
    for ip_str in ips:
        if is_ip_blocked(ip_str):
            logger.warning("Blocked IP %s at %s", ip_str, context)
            return None
    return ips


def _canonical_name(name: str) -> str:
    """Normalize a DNS name to its canonical wire-format representation, then
    back to lowercase text without the trailing dot (RFC 4343 case-insensitivity)."""
    return dns.name.from_text(name).to_text(omit_final_dot=True).lower()


async def resolve_hostname(hostname: str, resolver_ip: str | None = None) -> list[str]:
    """Resolve hostname to IPs, walking the CNAME chain and checking each hop.

    Walks CNAME intermediates manually to detect chains that pass through
    internal hostnames.  At each hop we resolve A (then AAAA) records and
    verify every IP against the blocklist, continuing to the next hop when
    the current name is an alias.
    """
    resolver_ip = resolver_ip or settings.SECURITY_DNS_RESOLVER
    resolver = _make_resolver(resolver_ip)
    current = _canonical_name(hostname)
    seen = {current}

    for _ in range(CNAME_MAX_HOPS):
        # ── A records ──────────────────────────────────────────
        try:
            answer = resolver.resolve(current, "A", raise_on_no_answer=False)
            a_ips = [str(r) for r in answer.rrset] if answer.rrset else []
            if a_ips:
                result = _check_ips(a_ips, f"CNAME chain hop: {current}")
                return result if result is not None else []
        except dns.resolver.NXDOMAIN:
            return []
        except Exception:
            pass  # try AAAA / CNAME below

        # ── AAAA records ───────────────────────────────────────
        try:
            answer = resolver.resolve(current, "AAAA", raise_on_no_answer=False)
            aaaa_ips = [str(r) for r in answer.rrset] if answer.rrset else []
            if aaaa_ips:
                result = _check_ips(aaaa_ips, f"CNAME chain hop: {current}")
                return result if result is not None else []
        except dns.resolver.NXDOMAIN:
            return []
        except Exception:
            pass

        # ── CNAME alias → next hop ─────────────────────────────
        try:
            answer = resolver.resolve(current, "CNAME", raise_on_no_answer=False)
            if answer.rrset:
                target_canonical = _canonical_name(str(answer.rrset[0].target))
                if target_canonical in seen:
                    logger.warning("CNAME loop detected: %s → %s", current, target_canonical)
                    return []
                seen.add(target_canonical)
                current = target_canonical
                continue
        except dns.resolver.NXDOMAIN:
            return []
        except Exception:
            pass

        return []  # no A, no AAAA, no CNAME — unresolvable

    logger.warning("CNAME chain exceeded max hops (%d) for %s", CNAME_MAX_HOPS, hostname)
    return []


async def filter_target(target: str) -> tuple[str, str | None]:
    """Validate and filter a target (hostname or IP).

    Returns:
        (resolved_ip, error_message_key) — one is always None.
    """
    # Try to parse as IP first
    try:
        ip = ip_address(target)
        ip_str = str(ip)
        if is_ip_blocked(ip_str):
            return "", "errors.target_not_allowed"
        return ip_str, None
    except ValueError:
        pass

    # Try to resolve as hostname
    ips = await resolve_hostname(target)
    if not ips:
        return "", "errors.dns_resolution_failed"

    # Check each resolved IP
    for ip_str in ips:
        if is_ip_blocked(ip_str):
            return "", "errors.target_not_allowed"

    return ips[0], None

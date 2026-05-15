from ipaddress import ip_address, ip_network
import logging
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


async def resolve_hostname(hostname: str, resolver_ip: str | None = None) -> list[str]:
    """Resolve hostname to IPs using a specific DNS resolver."""
    resolver_ip = resolver_ip or settings.SECURITY_DNS_RESOLVER
    resolver_obj = dns.resolver.Resolver()
    resolver_obj.nameservers = [resolver_ip]
    resolver_obj.timeout = 3
    resolver_obj.lifetime = 5

    try:
        answers = resolver_obj.resolve(hostname, "A")
        return [str(r) for r in answers]
    except dns.resolver.NXDOMAIN:
        return []
    except Exception:
        try:
            answers = resolver_obj.resolve(hostname, "AAAA")
            return [str(r) for r in answers]
        except Exception:
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

from unittest.mock import MagicMock, patch

import dns.name
import dns.resolver
import pytest

from app.security.address_filter import (
    is_ip_blocked,
    filter_target,
    resolve_hostname,
    BLOCKED_NETWORKS,
    CNAME_MAX_HOPS,
)

# ── Mock helpers for DNS resolver ────────────────────────────────────────────


def _make_answer(rrset_items):
    """Build a mock dns.resolver.Answer with an rrset of records."""
    answer = MagicMock()
    answer.rrset = rrset_items if rrset_items else None
    return answer


def _a_record(ip):
    """A mock A/AAAA record that stringifies to the given IP."""
    r = MagicMock()
    r.__str__ = MagicMock(return_value=ip)
    return r


def _cname_record(target):
    """A mock CNAME record whose .target stringifies to `target`."""
    r = MagicMock()
    name = dns.name.from_text(target)
    r.target = name
    return r


def _empty_answer():
    """A mock answer with no rrset (NXDOMAIN-like but not raised)."""
    return _make_answer(None)


def _resolver_from_map(response_map):
    """Return a mock resolver whose .resolve(name, rdtype, **kw) looks up
    (name, rdtype) in *response_map*.  Keys are ``(name.lower(), rdtype)``.
    Values can be a mock answer, an exception to raise, or ``None`` for an
    empty rrset.
    """
    def _resolve(name, rdtype, raise_on_no_answer=False):
        key = (str(name).lower(), rdtype)
        value = response_map.get(key)
        if isinstance(value, Exception):
            raise value
        if value is None:
            return _empty_answer()
        return value

    resolver = MagicMock()
    resolver.resolve = _resolve
    return resolver


class TestIsIPBlocked:
    @pytest.mark.parametrize("ip", [
        "127.0.0.1",
        "127.255.255.255",
        "10.0.0.1",
        "10.255.255.255",
        "192.168.1.1",
        "192.168.255.255",
        "172.16.0.1",
        "172.31.255.255",
        "0.0.0.0",
        "224.0.0.1",
        "240.0.0.1",
        "255.255.255.255",
        "169.254.1.1",
        "100.64.0.1",
        "172.17.0.1",
        "172.18.0.1",
        "192.0.2.1",
        "198.51.100.1",
        "203.0.113.1",
        "::1",
        "fc00::1",
        "fe80::1",
        "ff00::1",
    ])
    def test_blocked_ips(self, ip):
        assert is_ip_blocked(ip) is True, f"{ip} should be blocked"

    @pytest.mark.parametrize("ip", [
        "8.8.8.8",
        "1.1.1.1",
        "93.184.216.34",
        "208.67.222.222",
        "2001:4860:4860::8888",
        "2606:4700:4700::1111",
    ])
    def test_allowed_ips(self, ip):
        assert is_ip_blocked(ip) is False, f"{ip} should be allowed"

    def test_invalid_ip_is_blocked(self):
        assert is_ip_blocked("not-an-ip") is True


@pytest.mark.asyncio
async def test_filter_target_ip_direct():
    ip, error = await filter_target("8.8.8.8")
    assert ip == "8.8.8.8"
    assert error is None


@pytest.mark.asyncio
async def test_filter_target_private_ip():
    ip, error = await filter_target("127.0.0.1")
    assert ip == ""
    assert error == "errors.target_not_allowed"


@pytest.mark.asyncio
async def test_filter_target_loopback_ipv6():
    ip, error = await filter_target("::1")
    assert ip == ""
    assert error == "errors.target_not_allowed"


@pytest.mark.asyncio
async def test_filter_target_invalid():
    ip, error = await filter_target("not_a_valid_target_!!!")
    assert ip == ""
    assert error is not None


def test_blocked_networks_count():
    assert len(BLOCKED_NETWORKS) > 15


class TestResolveHostname:
    """Issue #66: CNAME chain walking with blocklist enforcement per hop."""

    @pytest.mark.asyncio
    async def test_cname_chain_to_public_ip_returns_ips(self):
        """CNAME alias → public IP: the resolved IPs are returned."""
        response_map = {
            ("alias.example.com", "A"): _empty_answer(),
            ("alias.example.com", "AAAA"): _empty_answer(),
            ("alias.example.com", "CNAME"): _make_answer(
                [_cname_record("real.example.com")]
            ),
            ("real.example.com", "A"): _make_answer([_a_record("8.8.8.8")]),
        }
        with patch(
            "app.security.address_filter._make_resolver",
            return_value=_resolver_from_map(response_map),
        ):
            result = await resolve_hostname("alias.example.com")
            assert result == ["8.8.8.8"]

    @pytest.mark.asyncio
    async def test_cname_chain_to_private_ip_returns_empty(self):
        """CNAME alias → RFC1918 IP: blocked → returns empty list."""
        response_map = {
            ("alias.example.com", "A"): _empty_answer(),
            ("alias.example.com", "AAAA"): _empty_answer(),
            ("alias.example.com", "CNAME"): _make_answer(
                [_cname_record("internal.example.com")]
            ),
            ("internal.example.com", "A"): _make_answer(
                [_a_record("192.168.1.1")]
            ),
        }
        with patch(
            "app.security.address_filter._make_resolver",
            return_value=_resolver_from_map(response_map),
        ):
            result = await resolve_hostname("alias.example.com")
            assert result == []

    @pytest.mark.asyncio
    async def test_cname_loop_detection_returns_empty(self):
        """a → b → a returns empty list when a CNAME loop is detected."""
        response_map = {
            ("a.example.com", "A"): _empty_answer(),
            ("a.example.com", "AAAA"): _empty_answer(),
            ("a.example.com", "CNAME"): _make_answer(
                [_cname_record("b.example.com")]
            ),
            ("b.example.com", "A"): _empty_answer(),
            ("b.example.com", "AAAA"): _empty_answer(),
            ("b.example.com", "CNAME"): _make_answer(
                [_cname_record("a.example.com")]
            ),
        }
        with patch(
            "app.security.address_filter._make_resolver",
            return_value=_resolver_from_map(response_map),
        ):
            result = await resolve_hostname("a.example.com")
            assert result == []

    @pytest.mark.asyncio
    async def test_nxdomain_mid_chain_returns_empty(self):
        """NXDOMAIN at any hop returns empty."""
        response_map = {
            ("alias.example.com", "A"): _empty_answer(),
            ("alias.example.com", "AAAA"): _empty_answer(),
            ("alias.example.com", "CNAME"): _make_answer(
                [_cname_record("missing.example.com")]
            ),
            ("missing.example.com", "A"): dns.resolver.NXDOMAIN(),
        }
        with patch(
            "app.security.address_filter._make_resolver",
            return_value=_resolver_from_map(response_map),
        ):
            result = await resolve_hostname("alias.example.com")
            assert result == []

    @pytest.mark.asyncio
    async def test_max_hops_exceeded_returns_empty(self):
        """Chain longer than CNAME_MAX_HOPS returns empty."""
        # Build a chain: hop0 → hop1 → hop2 → ... → hop{CNAME_MAX_HOPS}
        response_map = {}
        for i in range(CNAME_MAX_HOPS):
            current = f"hop{i}.example.com"
            next_hop = f"hop{i + 1}.example.com"
            response_map[(current, "A")] = _empty_answer()
            response_map[(current, "AAAA")] = _empty_answer()
            response_map[(current, "CNAME")] = _make_answer(
                [_cname_record(next_hop)]
            )
        # The last hop has no records → unresolvable (returns [] before max hops check)
        # So we need one more hop with a CNAME to actually exceed max
        last = f"hop{CNAME_MAX_HOPS}.example.com"
        response_map[(last, "A")] = _empty_answer()
        response_map[(last, "AAAA")] = _empty_answer()
        response_map[(last, "CNAME")] = _make_answer(
            [_cname_record(f"hop{CNAME_MAX_HOPS + 1}.example.com")]
        )

        with patch(
            "app.security.address_filter._make_resolver",
            return_value=_resolver_from_map(response_map),
        ):
            result = await resolve_hostname("hop0.example.com")
            assert result == []

    @pytest.mark.asyncio
    async def test_cname_loop_case_insensitive_two_hops(self):
        """evil.com → Evil.com → detected at hop 2, not hop 3 (issue #68)."""
        response_map = {
            ("evil.com", "A"): _empty_answer(),
            ("evil.com", "AAAA"): _empty_answer(),
            ("evil.com", "CNAME"): _make_answer(
                [_cname_record("Evil.com")]  # different case
            ),
            # Evil.com canonicalizes to evil.com which is already in seen
        }
        with patch(
            "app.security.address_filter._make_resolver",
            return_value=_resolver_from_map(response_map),
        ):
            result = await resolve_hostname("evil.com")
            assert result == []

    @pytest.mark.asyncio
    async def test_cname_loop_case_insensitive_multi_case(self):
        """Chain with 3+ case variants of the same name → detected."""
        response_map = {
            ("evil.com", "A"): _empty_answer(),
            ("evil.com", "AAAA"): _empty_answer(),
            ("evil.com", "CNAME"): _make_answer(
                [_cname_record("EVIL.com")]  # first variant
            ),
            # EVIL.com normalizes to evil.com → loop detected at hop 1
        }
        with patch(
            "app.security.address_filter._make_resolver",
            return_value=_resolver_from_map(response_map),
        ):
            result = await resolve_hostname("evil.com")
            assert result == []

    @pytest.mark.asyncio
    async def test_cname_normal_resolution_unaffected_by_canonicalization(self):
        """foo.com → bar.com → 1.2.3.4 continues without being flagged as loop."""
        response_map = {
            ("foo.com", "A"): _empty_answer(),
            ("foo.com", "AAAA"): _empty_answer(),
            ("foo.com", "CNAME"): _make_answer(
                [_cname_record("bar.com")]
            ),
            ("bar.com", "A"): _make_answer([_a_record("1.2.3.4")]),
        }
        with patch(
            "app.security.address_filter._make_resolver",
            return_value=_resolver_from_map(response_map),
        ):
            result = await resolve_hostname("foo.com")
            assert result == ["1.2.3.4"]

    @pytest.mark.asyncio
    async def test_malformed_hostname_returns_empty(self):
        """Malformed inputs (.., .foo, oversized labels) must not crash — return []."""
        for bad in ["..", ".foo", "foo..bar", "a" * 64 + ".com"]:
            result = await resolve_hostname(bad)
            assert result == [], f"expected [] for {bad!r}, got {result!r}"

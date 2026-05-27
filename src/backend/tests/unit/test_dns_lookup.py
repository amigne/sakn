from unittest.mock import AsyncMock, MagicMock, patch

import dns.rdatatype
import pytest

from app.constants.roles import ROLE_AUTHENTICATED
from app.tools.base import ExecutionContext
from app.tools.dns_lookup import DnsLookupTool


@pytest.fixture
def ctx():
    return ExecutionContext(
        user_id="user-1",
        session_id="session-1",
        source_ip="192.0.2.1",
        role=ROLE_AUTHENTICATED,
        request_id="req-1",
    )


@pytest.fixture
def tool():
    return DnsLookupTool()


def _make_rdata(value: str) -> MagicMock:
    """Create a mock rdata item that stringifies to the given value."""
    r = MagicMock()
    r.__str__ = lambda s, v=value: v
    return r


def _make_rrset(rdtype_name: str, ttl: int, *rdata_values: str) -> MagicMock:
    """Create a mock RRset with TTL, rdtype, and rdata items."""
    items = [_make_rdata(v) for v in rdata_values]
    rrset = MagicMock()
    rrset.ttl = ttl
    rrset.rdtype = dns.rdatatype.from_text(rdtype_name)
    rrset.__iter__ = lambda s, arr=items: iter(arr)
    return rrset


def _make_answer(*rrsets: MagicMock) -> MagicMock:
    """Create a mock Answer with response.answer set to the given RRsets."""
    answer = MagicMock()
    answer.response.answer = list(rrsets)
    return answer


class TestDnsLookupValidation:
    def test_validates_minimal_params(self, tool):
        result = tool.validate_params({"target": "example.com"})
        assert result["target"] == "example.com"
        assert result["record_types"] == ["A"]
        assert result["resolver"] == ""
        assert result["recursive_cname"] is True

    def test_accepts_domain_alias(self, tool):
        result = tool.validate_params({"domain": "example.com"})
        assert result["target"] == "example.com"

    def test_prefers_target_over_domain(self, tool):
        result = tool.validate_params({"target": "foo.com", "domain": "bar.com"})
        assert result["target"] == "foo.com"

    def test_rejects_empty_target(self, tool):
        with pytest.raises(ValueError, match="Target domain is required"):
            tool.validate_params({"target": ""})

    def test_rejects_overlong_domain(self, tool):
        with pytest.raises(ValueError, match="exceeds 255"):
            tool.validate_params({"target": "a" * 256 + ".com"})

    def test_normalizes_record_types_to_uppercase(self, tool):
        result = tool.validate_params({"target": "example.com", "record_types": ["a", "Mx", "Txt"]})
        assert result["record_types"] == ["A", "MX", "TXT"]

    def test_rejects_invalid_record_types(self, tool):
        with pytest.raises(ValueError, match="Invalid record types"):
            tool.validate_params({"target": "example.com", "record_types": ["A", "BOGUS"]})

    def test_strips_system_resolver(self, tool):
        result = tool.validate_params({"target": "example.com", "resolver": "__system__"})
        assert result["resolver"] == ""

    def test_recursive_cname_defaults_true(self, tool):
        result = tool.validate_params({"target": "example.com"})
        assert result["recursive_cname"] is True

    def test_recursive_cname_explicit_false(self, tool):
        result = tool.validate_params({"target": "example.com", "recursive_cname": False})
        assert result["recursive_cname"] is False


class TestDnsLookupExecute:
    @pytest.mark.asyncio
    async def test_blocks_target_resolving_to_private_ip(self, tool, ctx):
        with patch("app.tools.dns_lookup.resolve_hostname", new_callable=AsyncMock) as mock_resolve:
            mock_resolve.return_value = ["192.168.1.1"]
            result = await tool.execute({"target": "internal.local"}, ctx)
            assert result.success is False
            assert result.error == "errors.target_not_allowed"

    @pytest.mark.asyncio
    async def test_allows_target_resolving_to_public_ip(self, tool, ctx):
        with patch("app.tools.dns_lookup.resolve_hostname", new_callable=AsyncMock) as mock_resolve:
            mock_resolve.return_value = ["93.184.216.34"]
            with patch.object(DnsLookupTool, "_make_resolver") as mock_make:
                mock_resolver = MagicMock()
                mock_resolver.resolve.return_value = _make_answer()
                mock_make.return_value = mock_resolver
                result = await tool.execute({"target": "example.com", "record_types": ["A"]}, ctx)
                assert result.success is True
                assert result.data["domain"] == "example.com"

    @pytest.mark.asyncio
    async def test_allows_nxdomain(self, tool, ctx):
        """NXDOMAIN from security filter should not block — it's a valid DNS scenario."""
        with patch("app.tools.dns_lookup.resolve_hostname", new_callable=AsyncMock) as mock_resolve:
            mock_resolve.return_value = []
            with patch.object(DnsLookupTool, "_make_resolver") as mock_make:
                import dns.resolver
                mock_resolver = MagicMock()
                mock_resolver.resolve.side_effect = dns.resolver.NXDOMAIN()
                mock_make.return_value = mock_resolver
                result = await tool.execute({"target": "nonexistent.example"}, ctx)
                assert result.success is False
                assert result.error == "errors.nxdomain"

    @pytest.mark.asyncio
    async def test_returns_records_grouped_by_type(self, tool, ctx):
        with patch("app.tools.dns_lookup.resolve_hostname", new_callable=AsyncMock) as mock_resolve:
            mock_resolve.return_value = ["93.184.216.34"]
            with patch.object(DnsLookupTool, "_make_resolver") as mock_make:
                mock_resolver = MagicMock()

                def fake_resolve(name, rdtype):
                    if rdtype == "A":
                        return _make_answer(_make_rrset("A", 300, "93.184.216.34"))
                    elif rdtype == "MX":
                        return _make_answer(_make_rrset("MX", 3600, "10 mail.example.com."))
                    else:
                        return _make_answer()

                mock_resolver.resolve.side_effect = fake_resolve
                mock_make.return_value = mock_resolver

                result = await tool.execute(
                    {"target": "example.com", "record_types": ["A", "MX"]}, ctx
                )
                assert result.success is True
                assert "A" in result.data["records"]
                assert "MX" in result.data["records"]
                assert result.data["records"]["A"][0]["value"] == "93.184.216.34"
                assert result.data["records"]["A"][0]["ttl"] == 300
                assert result.data["records"]["MX"][0]["value"] == "10 mail.example.com."
                assert result.data["records"]["MX"][0]["ttl"] == 3600

    @pytest.mark.asyncio
    async def test_cname_chain_following(self, tool, ctx):
        with patch("app.tools.dns_lookup.resolve_hostname", new_callable=AsyncMock) as mock_resolve:
            mock_resolve.return_value = ["93.184.216.34"]
            with patch.object(DnsLookupTool, "_make_resolver") as mock_make:
                mock_resolver = MagicMock()

                def fake_resolve(name, rdtype):
                    if rdtype == "CNAME" and name == "example.com":
                        return _make_answer(_make_rrset("CNAME", 300, "www.example.com."))
                    elif rdtype == "CNAME" and name == "www.example.com":
                        raise __import__("dns.resolver").resolver.NoAnswer()
                    else:
                        return _make_answer()

                mock_resolver.resolve.side_effect = fake_resolve
                mock_make.return_value = mock_resolver

                result = await tool.execute(
                    {"target": "example.com", "record_types": ["CNAME"], "recursive_cname": True},
                    ctx,
                )
                assert result.success is True
                assert result.data["cname_chain"] is not None
                assert len(result.data["cname_chain"]) == 2
                assert "www.example.com" in result.data["cname_chain"]

    @pytest.mark.asyncio
    async def test_cname_chain_loop_detection(self, tool, ctx):
        with patch("app.tools.dns_lookup.resolve_hostname", new_callable=AsyncMock) as mock_resolve:
            mock_resolve.return_value = ["93.184.216.34"]
            with patch.object(DnsLookupTool, "_make_resolver") as mock_make:
                mock_resolver = MagicMock()

                def fake_resolve(name, rdtype):
                    if rdtype == "CNAME":
                        if name == "example.com":
                            return _make_answer(_make_rrset("CNAME", 300, "www.example.com."))
                        else:
                            return _make_answer(_make_rrset("CNAME", 300, "example.com."))
                    return _make_answer()

                mock_resolver.resolve.side_effect = fake_resolve
                mock_make.return_value = mock_resolver

                result = await tool.execute(
                    {"target": "example.com", "record_types": ["CNAME"], "recursive_cname": True},
                    ctx,
                )
                assert result.success is True
                assert len(result.data["cname_chain"]) == 2

    @pytest.mark.asyncio
    async def test_cname_hop_blocked_address_check(self, tool, ctx):
        """Each CNAME hop's resolved IPs are checked against the blocklist."""
        with patch("app.tools.dns_lookup.resolve_hostname", new_callable=AsyncMock) as mock_resolve:
            mock_resolve.side_effect = [
                ["93.184.216.34"],
                ["192.168.1.1"],
            ]

            with patch.object(DnsLookupTool, "_make_resolver") as mock_make:
                mock_resolver = MagicMock()

                def fake_resolve(name, rdtype):
                    if rdtype == "CNAME" and name == "example.com":
                        return _make_answer(_make_rrset("CNAME", 300, "internal.example.com."))
                    raise __import__("dns.resolver").resolver.NoAnswer()

                mock_resolver.resolve.side_effect = fake_resolve
                mock_make.return_value = mock_resolver

                result = await tool.execute(
                    {"target": "example.com", "record_types": ["CNAME"], "recursive_cname": True},
                    ctx,
                )
                assert result.success is True
                assert result.data["cname_chain"] is not None

    @pytest.mark.asyncio
    async def test_no_cname_chain_when_disabled(self, tool, ctx):
        with patch("app.tools.dns_lookup.resolve_hostname", new_callable=AsyncMock) as mock_resolve:
            mock_resolve.return_value = ["93.184.216.34"]
            with patch.object(DnsLookupTool, "_make_resolver") as mock_make:
                mock_resolver = MagicMock()

                def fake_resolve(name, rdtype):
                    if rdtype == "CNAME":
                        return _make_answer(_make_rrset("CNAME", 300, "www.example.com."))
                    return _make_answer()

                mock_resolver.resolve.side_effect = fake_resolve
                mock_make.return_value = mock_resolver

                result = await tool.execute(
                    {"target": "example.com", "record_types": ["CNAME"], "recursive_cname": False},
                    ctx,
                )
                assert result.success is True
                assert result.data["cname_chain"] is None

    @pytest.mark.asyncio
    async def test_dns_timeout_per_type_graceful(self, tool, ctx):
        """A per-record-type timeout should be treated as empty, not fatal."""
        with patch("app.tools.dns_lookup.resolve_hostname", new_callable=AsyncMock) as mock_resolve:
            mock_resolve.return_value = ["93.184.216.34"]
            with patch.object(DnsLookupTool, "_make_resolver") as mock_make:
                import dns.exception
                mock_resolver = MagicMock()
                mock_resolver.resolve.side_effect = dns.exception.Timeout()
                mock_make.return_value = mock_resolver
                result = await tool.execute({"target": "example.com", "record_types": ["A"]}, ctx)
                # Per-type timeout → empty records, not a failure
                assert result.success is True
                assert result.data["records"]["A"] == []

    @pytest.mark.asyncio
    async def test_custom_resolver_configured(self, tool, ctx):
        with patch("app.tools.dns_lookup.resolve_hostname", new_callable=AsyncMock) as mock_resolve:
            mock_resolve.return_value = ["93.184.216.34"]
            with patch("app.tools.dns_lookup.dns.resolver.Resolver") as MockResolver:
                mock_instance = MagicMock()
                mock_instance.resolve.return_value = _make_answer()
                MockResolver.return_value = mock_instance

                await tool.execute(
                    {"target": "example.com", "resolver": "8.8.8.8", "record_types": ["A"]}, ctx
                )
                assert mock_instance.nameservers == ["8.8.8.8"]
                assert mock_instance.timeout == 5
                assert mock_instance.lifetime == 8

    @pytest.mark.asyncio
    async def test_multiple_rdata_in_rrset(self, tool, ctx):
        """An RRset with multiple items should produce multiple records."""
        with patch("app.tools.dns_lookup.resolve_hostname", new_callable=AsyncMock) as mock_resolve:
            mock_resolve.return_value = ["93.184.216.34"]
            with patch.object(DnsLookupTool, "_make_resolver") as mock_make:
                mock_resolver = MagicMock()
                mock_resolver.resolve.return_value = _make_answer(
                    _make_rrset("A", 300, "93.184.216.34", "93.184.216.35")
                )
                mock_make.return_value = mock_resolver

                result = await tool.execute(
                    {"target": "example.com", "record_types": ["A"]}, ctx
                )
                assert result.success is True
                assert len(result.data["records"]["A"]) == 2
                assert result.data["records"]["A"][0]["value"] == "93.184.216.34"
                assert result.data["records"]["A"][1]["value"] == "93.184.216.35"


class TestDnsLookupDefinition:
    def test_definition_metadata(self, tool):
        d = tool.get_definition()
        assert d.name == "dns_lookup"
        assert d.category.value == "dns"
        assert len(d.parameters) == 4


class TestDnsLookupMakeResolver:
    def test_system_default_resolver(self, tool):
        resolver = tool._make_resolver("")
        assert resolver.nameservers != []

    def test_custom_resolver(self, tool):
        resolver = tool._make_resolver("8.8.8.8")
        assert resolver.nameservers == ["8.8.8.8"]

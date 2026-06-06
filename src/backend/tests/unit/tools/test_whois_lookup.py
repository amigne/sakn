"""Unit tests for WhoisLookupTool — definition, validation, SSRF, RDAP parsing.

All network calls are mocked. No real outbound connections.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.tools.base import ToolCategory
from app.tools.whois_lookup import (
    WhoisLookupTool,
    _extract_iana_rdap_servers,
    _extract_tld,
    _is_gdpr_redacted,
    _parse_rdap_response,
    _pin_resolution,
)

# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def tool() -> WhoisLookupTool:
    return WhoisLookupTool()


# ── Sample RDAP fixtures ─────────────────────────────────────────────────────


@pytest.fixture
def iana_bootstrap_response() -> dict:
    """Simulated IANA RDAP bootstrap response for .com (Verisign)."""
    return {
        "services": [
            [
                ["com", "net"],
                ["https://rdap.verisign.com/com/v1/"],
            ]
        ],
        "description": "RDAP bootstrap for domain registries",
    }


@pytest.fixture
def iana_bootstrap_ip_response() -> dict:
    """Simulated IANA RDAP bootstrap response for 8.0.0.0/8 (ARIN)."""
    return {
        "services": [
            [
                ["8.0.0.0/8"],
                ["https://rdap.arin.net/registry/"],
            ]
        ],
    }


@pytest.fixture
def iana_bootstrap_empty() -> dict:
    """Simulated IANA response with no services."""
    return {"services": []}


@pytest.fixture
def rdap_domain_response() -> dict:
    """Simulated authoritative RDAP domain response (RFC 7483)."""
    return {
        "objectClassName": "domain",
        "ldhName": "EXAMPLE.COM",
        "handle": "2336799_DOMAIN_COM-VRSN",
        "status": [
            "client delete prohibited",
            "client transfer prohibited",
            "client update prohibited",
        ],
        "entities": [
            {
                "objectClassName": "entity",
                "handle": "123",
                "roles": ["registrar"],
                "vcardArray": [
                    "vcard",
                    [
                        ["version", {}, "text", "4.0"],
                        ["fn", {}, "text", "Example Registrar, Inc."],
                        ["org", {}, "text", "Example Registrar, Inc."],
                    ],
                ],
            },
            {
                "objectClassName": "entity",
                "handle": "456",
                "roles": ["registrant"],
                "vcardArray": [
                    "vcard",
                    [
                        ["version", {}, "text", "4.0"],
                        ["fn", {}, "text", "Redacted for Privacy"],
                    ],
                ],
                "remarks": [
                    {
                        "title": "REDACTED FOR PRIVACY",
                        "description": ["Some of the data in this object has been removed."],
                    }
                ],
            },
            {
                "objectClassName": "entity",
                "handle": "789",
                "roles": ["administrative"],
                "vcardArray": ["vcard", []],
            },
            {
                "objectClassName": "entity",
                "handle": "101",
                "roles": ["technical"],
                "vcardArray": [
                    "vcard",
                    [
                        ["version", {}, "text", "4.0"],
                        ["fn", {}, "text", "Tech Admin"],
                        ["email", {}, "text", "tech@example.com"],
                    ],
                ],
            },
        ],
        "nameservers": [
            {"objectClassName": "nameserver", "ldhName": "NS1.EXAMPLE.COM"},
            {"objectClassName": "nameserver", "ldhName": "NS2.EXAMPLE.COM"},
        ],
        "events": [
            {
                "eventAction": "registration",
                "eventDate": "1995-08-14T04:00:00Z",
            },
            {
                "eventAction": "expiration",
                "eventDate": "2027-08-13T04:00:00Z",
            },
            {
                "eventAction": "last changed",
                "eventDate": "2026-01-15T08:30:00Z",
            },
        ],
        "notices": [
            {
                "title": "Terms of Service",
                "description": [
                    "By submitting this query, you agree to abide by this policy."
                ],
            }
        ],
    }


@pytest.fixture
def rdap_ip_response() -> dict:
    """Simulated RDAP IP response (ARIN-style)."""
    return {
        "objectClassName": "ip network",
        "handle": "NET-8-0-0-0-1",
        "startAddress": "8.8.8.0",
        "endAddress": "8.8.8.255",
        "entities": [
            {
                "objectClassName": "entity",
                "handle": "GOGL",
                "roles": ["registrant"],
                "vcardArray": [
                    "vcard",
                    [
                        ["version", {}, "text", "4.0"],
                        ["fn", {}, "text", "Google LLC"],
                        ["org", {}, "text", "Google LLC"],
                    ],
                ],
            }
        ],
        "events": [
            {"eventAction": "registration", "eventDate": "2014-03-14T00:00:00Z"},
            {"eventAction": "last changed", "eventDate": "2015-08-01T00:00:00Z"},
        ],
        "status": ["active"],
    }


@pytest.fixture
def rdap_redacted_response() -> dict:
    """RDAP response where ALL contacts are GDPR-redacted."""
    return {
        "objectClassName": "domain",
        "ldhName": "REDACTED-DOMAIN.EU",
        "status": ["active"],
        "entities": [
            {
                "roles": ["registrant"],
                "vcardArray": ["vcard", []],
                "remarks": [
                    {"description": ["GDPR redacted — personal data protected"]}
                ],
            },
            {
                "roles": ["administrative"],
                "vcardArray": ["vcard", []],
            },
            {
                "roles": ["technical"],
                "vcardArray": ["vcard", []],
            },
        ],
        "nameservers": [],
        "events": [],
    }


# ── Module-level helpers ─────────────────────────────────────────────────────


class TestExtractTld:
    def test_simple_tld(self):
        assert _extract_tld("example.com") == "com"

    def test_subdomain(self):
        assert _extract_tld("sub.example.org") == "org"

    def test_cctld(self):
        # .co.uk → uk is 2 chars, co is ≤ 3 → both treated as TLD
        assert _extract_tld("example.co.uk") == "co.uk"

    def test_single_label(self):
        assert _extract_tld("localhost") == "localhost"

    def test_idn_punycode(self):
        assert _extract_tld("xn--xample-9ua.com") == "com"


class TestExtractIanaRdapServers:
    def test_extracts_servers(self, iana_bootstrap_response):
        servers = _extract_iana_rdap_servers(iana_bootstrap_response)
        assert servers == ["https://rdap.verisign.com/com/v1/"]

    def test_empty_services(self, iana_bootstrap_empty):
        servers = _extract_iana_rdap_servers(iana_bootstrap_empty)
        assert servers == []

    def test_no_services_key(self):
        servers = _extract_iana_rdap_servers({})
        assert servers == []


class TestIsGdprRedacted:
    def test_redacted_by_remark(self):
        entity = {"remarks": [{"description": ["GDPR redacted — personal data"]}]}
        assert _is_gdpr_redacted({"fn": "John"}, entity) is True

    def test_not_redacted_with_data(self):
        entity = {}
        assert _is_gdpr_redacted({"fn": "John Doe", "org": "ACME"}, entity) is False

    def test_empty_vcard_is_redacted(self):
        assert _is_gdpr_redacted(None, {}) is True
        assert _is_gdpr_redacted({}, {}) is True

    def test_redacted_fn_value(self):
        assert _is_gdpr_redacted({"fn": "Redacted for Privacy"}, {}) is True


# ── RDAP parsing ─────────────────────────────────────────────────────────────


class TestParseRdapResponse:
    def test_domain_success(self, rdap_domain_response):
        result = _parse_rdap_response(rdap_domain_response, "example.com")
        assert result["protocol"] == "rdap"
        assert result["domain"] == "EXAMPLE.COM"
        assert len(result["status"]) == 3
        assert result["registrar"] == "Example Registrar, Inc."
        assert result["name_servers"] == ["ns1.example.com", "ns2.example.com"]
        assert result["creation_date"] == "1995-08-14T04:00:00Z"
        assert result["expiration_date"] == "2027-08-13T04:00:00Z"
        assert result["updated_date"] == "2026-01-15T08:30:00Z"
        assert result["raw_text"] is None
        assert result["disclaimer"] is not None
        assert "abide" in result["disclaimer"]

    def test_gdpr_contacts_null(self, rdap_domain_response):
        result = _parse_rdap_response(rdap_domain_response, "example.com")
        # Registrant is GDPR-redacted → null
        assert result["registrant"] is None
        # Admin has empty vcard → null
        assert result["admin_contact"] is None
        # Tech has real data → not null
        assert result["tech_contact"] is not None
        assert result["tech_contact"]["fn"] == "Tech Admin"

    def test_ip_response(self, rdap_ip_response):
        result = _parse_rdap_response(rdap_ip_response, "8.8.8.8")
        assert result["protocol"] == "rdap"
        assert result["domain"] == "NET-8-0-0-0-1"  # handle
        assert result["registrant"] is not None
        assert result["registrant"]["org"] == "Google LLC"
        assert result["creation_date"] == "2014-03-14T00:00:00Z"

    def test_all_contacts_redacted(self, rdap_redacted_response):
        result = _parse_rdap_response(rdap_redacted_response, "redacted-domain.eu")
        assert result["registrant"] is None
        assert result["admin_contact"] is None
        assert result["tech_contact"] is None

    def test_missing_fields_default(self):
        minimal = {"ldhName": "minimal.com"}
        result = _parse_rdap_response(minimal, "minimal.com")
        assert result["status"] == []
        assert result["registrar"] is None
        assert result["name_servers"] == []
        assert result["creation_date"] is None
        assert result["expiration_date"] is None
        assert result["updated_date"] is None
        assert result["disclaimer"] is None

    def test_fallback_to_target_domain(self):
        result = _parse_rdap_response({}, "fallback.com")
        assert result["domain"] == "fallback.com"


# ── get_definition ───────────────────────────────────────────────────────────


class TestGetDefinition:
    def test_name(self, tool):
        d = tool.get_definition()
        assert d.name == "whois"

    def test_category(self, tool):
        d = tool.get_definition()
        assert d.category == ToolCategory.NETWORK

    def test_version(self, tool):
        d = tool.get_definition()
        assert d.version == "1.0.0"

    def test_backend(self, tool):
        d = tool.get_definition()
        assert d.backend is True

    def test_params_target(self, tool):
        d = tool.get_definition()
        target_param = next(p for p in d.parameters if p.name == "target")
        assert target_param.type == "string"
        assert target_param.required is True
        assert target_param.constraints["max_length"] == 255

    def test_params_server(self, tool):
        d = tool.get_definition()
        server_param = next(p for p in d.parameters if p.name == "server")
        assert server_param.type == "string"
        assert server_param.required is False

    def test_param_count(self, tool):
        d = tool.get_definition()
        assert len(d.parameters) == 2


# ── validate_params ─────────────────────────────────────────────────────────


class TestValidateParams:
    def test_valid_target(self, tool):
        result = tool.validate_params({"target": "example.com"})
        assert result["target"] == "example.com"
        assert result["server"] is None
        assert result["is_ip"] is False

    def test_valid_target_ip(self, tool):
        result = tool.validate_params({"target": "8.8.8.8"})
        assert result["target"] == "8.8.8.8"
        assert result["is_ip"] is True

    def test_target_stripped(self, tool):
        result = tool.validate_params({"target": "  example.com  "})
        assert result["target"] == "example.com"

    def test_target_required(self, tool):
        with pytest.raises(ValueError, match="Target is required"):
            tool.validate_params({"target": ""})

    def test_target_missing(self, tool):
        with pytest.raises(ValueError, match="Target is required"):
            tool.validate_params({})

    def test_target_max_length(self, tool):
        long_target = "a" * 256 + ".com"
        with pytest.raises(ValueError, match="Target exceeds 255"):
            tool.validate_params({"target": long_target})

    def test_target_exactly_255(self, tool):
        target = "a" * 251 + ".com"  # 255 chars
        result = tool.validate_params({"target": target})
        assert len(result["target"]) == 255

    def test_server_optional(self, tool):
        result = tool.validate_params({"target": "example.com"})
        assert result["server"] is None

    def test_server_provided(self, tool):
        result = tool.validate_params(
            {"target": "example.com", "server": "whois.arin.net"}
        )
        assert result["server"] == "whois.arin.net"

    def test_server_max_length(self, tool):
        long_server = "a" * 256 + ".net"
        with pytest.raises(ValueError, match="Server exceeds 255"):
            tool.validate_params(
                {"target": "example.com", "server": long_server}
            )

    def test_ipv6_target(self, tool):
        result = tool.validate_params({"target": "2001:4860:4860::8888"})
        assert result["is_ip"] is True


# ── SSRF validation ──────────────────────────────────────────────────────────


def _mock_filter_target_ok(return_ip: str = "93.184.216.34"):
    """Helper: create a mock for filter_target that returns success."""

    async def mock_filter(target: str) -> tuple[str, str | None]:
        return return_ip, None

    return mock_filter


def _mock_filter_target_blocked():
    """Helper: create a mock for filter_target that returns blocked."""

    async def mock_filter(target: str) -> tuple[str, str | None]:
        return "", "errors.target_not_allowed"

    return mock_filter


class TestSsrfValidation:
    @pytest.mark.asyncio
    async def test_private_target_ip_blocked(self, tool):
        with patch(
            "app.tools.whois_lookup.filter_target",
            _mock_filter_target_blocked(),
        ):
            result = await tool.execute(
                {"target": "127.0.0.1"},
                MagicMock(),
            )
        assert result.success is False
        assert result.error == "errors.target_not_allowed"

    @pytest.mark.asyncio
    async def test_private_target_hostname_blocked(self, tool):
        with patch(
            "app.tools.whois_lookup.filter_target",
            _mock_filter_target_blocked(),
        ):
            result = await tool.execute(
                {"target": "localhost"},
                MagicMock(),
            )
        assert result.success is False
        assert result.error == "errors.target_not_allowed"

    @pytest.mark.asyncio
    async def test_rfc1918_blocked(self, tool):
        with patch(
            "app.tools.whois_lookup.filter_target",
            _mock_filter_target_blocked(),
        ):
            result = await tool.execute(
                {"target": "192.168.1.1"},
                MagicMock(),
            )
        assert result.success is False
        assert result.error == "errors.target_not_allowed"

    @pytest.mark.asyncio
    async def test_private_server_blocked(self, tool):
        """When a custom server resolves to a private IP, it should be blocked."""
        # First call: target is ok → returns IP
        # Second call: server is blocked
        call_count = 0

        async def selective_filter(target: str) -> tuple[str, str | None]:
            nonlocal call_count
            call_count += 1
            if call_count == 1:  # target
                return "93.184.216.34", None
            return "", "errors.target_not_allowed"  # server blocked

        with patch("app.tools.whois_lookup.filter_target", selective_filter):
            result = await tool.execute(
                {"target": "example.com", "server": "127.0.0.1"},
                MagicMock(),
            )
        assert result.success is False
        assert result.error == "errors.target_not_allowed"

    @pytest.mark.asyncio
    async def test_ipv6_loopback_blocked(self, tool):
        with patch(
            "app.tools.whois_lookup.filter_target",
            _mock_filter_target_blocked(),
        ):
            result = await tool.execute(
                {"target": "::1"},
                MagicMock(),
            )
        assert result.success is False
        assert result.error == "errors.target_not_allowed"

    @pytest.mark.asyncio
    async def test_ipv6_ula_blocked(self, tool):
        with patch(
            "app.tools.whois_lookup.filter_target",
            _mock_filter_target_blocked(),
        ):
            result = await tool.execute(
                {"target": "fd00::1"},
                MagicMock(),
            )
        assert result.success is False
        assert result.error == "errors.target_not_allowed"


# ── RDAP execution (with mocked HTTP) ────────────────────────────────────────


class TestRdapExecution:
    @pytest.mark.asyncio
    async def test_rdap_domain_success(self, tool, rdap_domain_response):
        """Full RDAP flow: IANA bootstrap → authoritative query → success."""
        iana_json = {
            "services": [
                [["com"], ["https://rdap.verisign.com/com/v1/"]]
            ]
        }

        call_count = 0

        async def mock_rdap_get(url: str) -> dict | None:
            nonlocal call_count
            call_count += 1
            if "iana" in url:
                return iana_json
            return rdap_domain_response

        async def mock_filter(target: str) -> tuple[str, str | None]:
            return "1.2.3.4", None

        with patch(
            "app.tools.whois_lookup.filter_target", mock_filter
        ), patch.object(
            tool, "_rdap_get", mock_rdap_get
        ):
            result = await tool.execute(
                {"target": "example.com"},
                MagicMock(),
            )

        assert result.success is True
        assert result.data["protocol"] == "rdap"
        assert result.data["domain"] == "EXAMPLE.COM"
        assert result.data["registrar"] == "Example Registrar, Inc."
        assert len(result.data["name_servers"]) == 2

    @pytest.mark.asyncio
    async def test_rdap_iana_404(self, tool):
        """IANA bootstrap returns 404 → WHOIS_UNSUPPORTED_TLD."""

        async def mock_rdap_get(url: str) -> dict | None:
            return None  # IANA returns nothing (404 / no data)

        async def mock_filter(target: str) -> tuple[str, str | None]:
            return "1.2.3.4", None

        with patch(
            "app.tools.whois_lookup.filter_target", mock_filter
        ), patch.object(
            tool, "_rdap_get", mock_rdap_get
        ):
            result = await tool.execute(
                {"target": "unknown-tld.xyz"},
                MagicMock(),
            )

        assert result.success is False
        assert result.error == "errors.whois_unsupported_tld"

    @pytest.mark.asyncio
    async def test_rdap_not_found_at_authoritative(self, tool):
        """Authoritative RDAP returns 404 → not_found."""
        import httpx

        call_count = 0

        async def mock_rdap_get(url: str) -> dict | None:
            nonlocal call_count
            call_count += 1
            if call_count == 1:  # IANA bootstrap
                return {
                    "services": [[["com"], ["https://rdap.verisign.com/com/v1/"]]]
                }
            else:
                # Simulate 404 from authoritative server
                mock_resp = MagicMock()
                mock_resp.status_code = 404
                mock_req = MagicMock()
                raise httpx.HTTPStatusError(
                    "Not Found",
                    request=mock_req,
                    response=mock_resp,
                )

        async def mock_filter(target: str) -> tuple[str, str | None]:
            return "1.2.3.4", None

        with patch(
            "app.tools.whois_lookup.filter_target", mock_filter
        ), patch.object(
            tool, "_rdap_get", mock_rdap_get
        ):
            result = await tool.execute(
                {"target": "nonexistent-domain-2026.com"},
                MagicMock(),
            )

        assert result.success is False
        assert result.error == "tools.whois.not_found"

    @pytest.mark.asyncio
    async def test_rdap_connect_timeout(self, tool):
        """RDAP connection timeout → WHOIS_CONNECTION_FAILED."""
        import httpx

        async def mock_rdap_get(url: str) -> dict | None:
            raise httpx.ConnectTimeout("Connection timed out")

        async def mock_filter(target: str) -> tuple[str, str | None]:
            return "1.2.3.4", None

        with patch(
            "app.tools.whois_lookup.filter_target", mock_filter
        ), patch.object(
            tool, "_rdap_get", mock_rdap_get
        ):
            result = await tool.execute(
                {"target": "example.com"},
                MagicMock(),
            )

        assert result.success is False
        assert result.error == "errors.whois_connection_failed"

    @pytest.mark.asyncio
    async def test_custom_server_skips_rdap(self, tool):
        """When server is provided, RDAP is skipped → WHOIS_UNSUPPORTED_TLD."""
        async def mock_filter(target: str) -> tuple[str, str | None]:
            return "1.2.3.4", None

        with patch("app.tools.whois_lookup.filter_target", mock_filter):
            result = await tool.execute(
                {"target": "example.com", "server": "whois.arin.net"},
                MagicMock(),
            )

        # Sprint 1: custom server not yet supported → WHOIS_UNSUPPORTED_TLD
        # Sprint 2 will handle this with WHOIS/43 connection
        assert result.success is False
        assert result.error == "errors.whois_unsupported_tld"

    @pytest.mark.asyncio
    async def test_execution_deadline_exceeded(self, tool):
        """Overall 60s deadline triggers TimeoutError → WHOIS_CONNECTION_FAILED."""
        import asyncio as real_asyncio

        async def mock_rdap_get(url: str) -> dict | None:
            await real_asyncio.sleep(999)
            return {}

        async def mock_filter(target: str) -> tuple[str, str | None]:
            return "1.2.3.4", None

        import app.tools.whois_lookup as wl_mod

        original = wl_mod.settings.WHOIS_EXECUTION_DEADLINE
        wl_mod.settings.WHOIS_EXECUTION_DEADLINE = 0.1
        try:
            with patch(
                "app.tools.whois_lookup.filter_target", mock_filter
            ), patch.object(
                tool, "_rdap_get", mock_rdap_get
            ):
                result = await tool.execute(
                    {"target": "example.com"},
                    MagicMock(),
                )
        finally:
            wl_mod.settings.WHOIS_EXECUTION_DEADLINE = original

        assert result.success is False
        assert result.error == "errors.whois_connection_failed"


# ── RDAP redirect handling ───────────────────────────────────────────────────


class TestRdapRedirectHandling:
    @pytest.mark.asyncio
    async def test_redirect_to_private_ip_blocked(self, tool):
        """RDAP redirect to a private IP should be blocked."""
        call_count = 0

        async def mock_rdap_get(url: str) -> dict | None:
            nonlocal call_count
            call_count += 1
            if call_count == 1:  # IANA bootstrap
                return {
                    "services": [[["com"], ["https://rdap.example.com/domain/"]]]
                }
            else:
                # Simulate a redirect to private IP — _rdap_get would see
                # the redirect, resolve the target, find it blocked, and return None
                return None

        # Block internal hosts; allow everything else (RDAP hosts + target).
        blocked_hosts = {"10.0.0.1", "internal.local"}

        async def mock_filter(target: str) -> tuple[str, str | None]:
            if target in blocked_hosts:
                return "", "errors.target_not_allowed"
            return "1.2.3.4", None

        with patch(
            "app.tools.whois_lookup.filter_target", mock_filter
        ), patch.object(
            tool, "_rdap_get", mock_rdap_get
        ):
            result = await tool.execute(
                {"target": "example.com"},
                MagicMock(),
            )

        # The first auth server returns None (redirect blocked),
        # so we get WHOIS_CONNECTION_FAILED
        assert result.success is False
        assert result.error == "errors.whois_connection_failed"

    @pytest.mark.asyncio
    async def test_redirect_limit_exceeded(self, tool):
        """RDAP hôte autoritaire injoignable après plusieurs tentatives → échec."""
        import httpx

        call_count = 0

        async def mock_rdap_get(url: str) -> dict | None:
            nonlocal call_count
            call_count += 1
            if call_count == 1:  # IANA bootstrap
                return {
                    "services": [
                        [["com"], [
                            "https://rdap1.example.com/",
                            "https://rdap2.example.com/",
                            "https://rdap3.example.com/",
                        ]]
                    ]
                }
            # All authoritative servers fail
            raise httpx.ConnectTimeout("Connection timed out")

        async def mock_filter(target: str) -> tuple[str, str | None]:
            return "1.2.3.4", None

        with patch(
            "app.tools.whois_lookup.filter_target", mock_filter
        ), patch.object(
            tool, "_rdap_get", mock_rdap_get
        ):
            result = await tool.execute(
                {"target": "example.com"},
                MagicMock(),
            )

        # All auth servers failed → connection error
        assert result.success is False
        assert result.error == "errors.whois_connection_failed"


# ── RDAP _rdap_get: real per-hop SSRF validation + IP pinning (S1/S3/S5) ─────


class TestRdapGetPerHopSecurity:
    """Exercise the real _rdap_get transport loop (not a mock) via MockTransport.

    These tests cover the redirect SSRF/pinning path that the higher-level
    tests bypass by mocking _rdap_get wholesale.
    """

    @pytest.mark.asyncio
    async def test_followed_redirect_is_validated_and_pinned(
        self, tool, monkeypatch
    ):
        """Each followed redirect re-validates AND IP-pins the new host (S1)."""
        import contextlib as _ctx

        import httpx

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.host == "rdap1.example.com":
                return httpx.Response(
                    302,
                    headers={
                        "Location": "https://rdap2.example.com/domain/example.com"
                    },
                )
            return httpx.Response(200, json={"ldhName": "EXAMPLE.COM"})

        validated: list[str] = []

        async def mock_filter(target: str) -> tuple[str, str | None]:
            validated.append(target)
            return "1.2.3.4", None

        pinned: list[tuple[str, str]] = []

        @_ctx.asynccontextmanager
        async def fake_pin(host: str, ip: str):
            pinned.append((host, ip))
            yield

        monkeypatch.setattr("app.tools.whois_lookup.filter_target", mock_filter)
        monkeypatch.setattr("app.tools.whois_lookup._pin_resolution", fake_pin)

        result = await tool._rdap_get(
            "https://rdap1.example.com/domain/example.com",
            transport=httpx.MockTransport(handler),
        )

        assert result == {"ldhName": "EXAMPLE.COM"}
        # Both the initial host and the redirect target were validated AND pinned
        # immediately before connecting — no fresh DNS at connect time.
        assert "rdap1.example.com" in validated
        assert "rdap2.example.com" in validated
        assert ("rdap1.example.com", "1.2.3.4") in pinned
        assert ("rdap2.example.com", "1.2.3.4") in pinned

    @pytest.mark.asyncio
    async def test_redirect_to_blocked_host_is_not_connected(
        self, tool, monkeypatch
    ):
        """A redirect to an SSRF-blocked host is refused before connecting (S1)."""
        import httpx

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.host == "rdap1.example.com":
                return httpx.Response(
                    302,
                    headers={"Location": "https://internal.evil/domain/x"},
                )
            raise AssertionError("must not connect to a blocked redirect host")

        async def mock_filter(target: str) -> tuple[str, str | None]:
            if target == "internal.evil":
                return "", "errors.target_not_allowed"
            return "1.2.3.4", None

        monkeypatch.setattr("app.tools.whois_lookup.filter_target", mock_filter)

        result = await tool._rdap_get(
            "https://rdap1.example.com/domain/x",
            transport=httpx.MockTransport(handler),
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_non_https_redirect_is_refused(self, tool, monkeypatch):
        """A redirect that downgrades to http:// is refused (S5)."""
        import httpx

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.scheme == "https":
                return httpx.Response(
                    302,
                    headers={"Location": "http://rdap2.example.com/domain/x"},
                )
            raise AssertionError("must not follow an http:// downgrade")

        async def mock_filter(target: str) -> tuple[str, str | None]:
            return "1.2.3.4", None

        monkeypatch.setattr("app.tools.whois_lookup.filter_target", mock_filter)

        result = await tool._rdap_get(
            "https://rdap1.example.com/domain/x",
            transport=httpx.MockTransport(handler),
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_oversize_response_is_capped(self, tool, monkeypatch):
        """An over-cap RDAP body returns None instead of buffering unbounded (S3)."""
        import httpx

        big = b'{"x":"' + b"a" * (3 * 1024 * 1024) + b'"}'

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=big)

        async def mock_filter(target: str) -> tuple[str, str | None]:
            return "1.2.3.4", None

        monkeypatch.setattr("app.tools.whois_lookup.filter_target", mock_filter)

        result = await tool._rdap_get(
            "https://rdap1.example.com/domain/x",
            transport=httpx.MockTransport(handler),
        )
        assert result is None


# ── IP pinning context manager ───────────────────────────────────────────────


class TestPinResolution:
    @pytest.mark.asyncio
    async def test_pin_resolution_patches_getaddrinfo(self):
        """_pin_resolution patches loop.getaddrinfo for the pinned host."""
        import asyncio as _asyncio

        loop = _asyncio.get_running_loop()

        host = "example.com"
        pinned_ip = "93.184.216.34"

        async with _pin_resolution(host, pinned_ip):
            # Pinned host should resolve to the pinned IP
            pinned_results = await loop.getaddrinfo(host, 443)
            # The result should contain the pinned IP
            assert any(pinned_ip in str(addr) for *_, addr in pinned_results)

        # After context exit, resolution should work normally again
        restored_results = await loop.getaddrinfo("localhost", 80)
        assert len(restored_results) > 0

    @pytest.mark.asyncio
    async def test_pin_resolution_forwards_other_hosts(self):
        """Non-pinned hosts should still resolve normally."""
        host = "example.com"
        pinned_ip = "93.184.216.34"

        async with _pin_resolution(host, pinned_ip):
            # Resolving localhost (unpinned) should still work
            result = await __import__("asyncio").get_running_loop().getaddrinfo(
                "localhost", 80
            )
            assert result is not None
            assert len(result) > 0
            # It resolves normally (we don't care about the actual IP, just that it doesn't crash)
            assert result is not None
            assert len(result) > 0


# ── Validation error handling ────────────────────────────────────────────────


class TestValidationErrors:
    @pytest.mark.asyncio
    async def test_empty_target_returns_error(self, tool):
        result = await tool.execute({"target": ""}, MagicMock())
        assert result.success is False
        assert result.error == "Target is required"

    @pytest.mark.asyncio
    async def test_overlong_target_returns_error(self, tool):
        result = await tool.execute({"target": "a" * 300}, MagicMock())
        assert result.success is False
        assert "255" in result.error

    @pytest.mark.asyncio
    async def test_overlong_server_returns_error(self, tool):
        result = await tool.execute(
            {"target": "example.com", "server": "a" * 300},
            MagicMock(),
        )
        assert result.success is False
        assert "255" in result.error


# ── get_result_schema ────────────────────────────────────────────────────────


class TestResultSchema:
    def test_has_expected_fields(self, tool):
        schema = tool.get_result_schema()
        props = schema["properties"]
        assert props["protocol"]["enum"] == ["rdap", "whois"]
        assert props["domain"]["type"] == "string"
        assert "registrar" in props
        assert "name_servers" in props
        assert "creation_date" in props
        assert "expiration_date" in props
        assert "updated_date" in props
        assert "registrant" in props
        assert "admin_contact" in props
        assert "tech_contact" in props
        assert "raw_text" in props
        assert "disclaimer" in props

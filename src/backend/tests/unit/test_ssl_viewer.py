from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

from app.constants.roles import ROLE_AUTHENTICATED
from app.tools.base import ExecutionContext
from app.tools.ssl_viewer import SslViewerTool, _hostname_matches, _normalize_key_algorithm


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
    return SslViewerTool()


def _fake_leaf_cert():
    """Create a minimal fake certificate for testing."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = datetime.now(tz=UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(
            x509.Name(
                [
                    x509.NameAttribute(NameOID.COMMON_NAME, "example.com"),
                    x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Example Org"),
                ]
            )
        )
        .issuer_name(
            x509.Name(
                [
                    x509.NameAttribute(NameOID.COMMON_NAME, "Example CA"),
                ]
            )
        )
        .not_valid_before(now - timedelta(days=30))
        .not_valid_after(now + timedelta(days=335))
        .serial_number(12345)
        .public_key(key.public_key())
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName("example.com"), x509.DNSName("www.example.com")]),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    return cert.public_bytes(serialization.Encoding.DER)


def _fake_ca_cert():
    """Create a minimal fake CA certificate for testing."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = datetime.now(tz=UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(
            x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Example CA")])
        )
        .issuer_name(
            x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Example CA")])
        )
        .not_valid_before(now - timedelta(days=365))
        .not_valid_after(now + timedelta(days=3650))
        .serial_number(67890)
        .public_key(key.public_key())
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .sign(key, hashes.SHA256())
    )
    return cert.public_bytes(serialization.Encoding.DER)


def _mock_connect_permissive(leaf_der=None, intermediates=None, tls="TLSv1.3", cipher="TLS_AES_256_GCM_SHA384"):
    def _connect(hostname, port, sni):
        return (leaf_der or _fake_leaf_cert(), intermediates or [], tls, cipher)

    return _connect


def _mock_connect_validated(should_fail=False):
    def _connect(hostname, port, sni):
        if should_fail:
            import ssl
            raise ssl.SSLCertVerificationError("certificate verify failed")
        return None

    return _connect


class TestSslViewerValidation:
    def test_minimal_params(self, tool):
        result = tool.validate_params({"url": "example.com"})
        assert result["hostname"] == "example.com"
        assert result["port"] == 443
        assert result["sni"] == ""

    def test_url_with_scheme(self, tool):
        result = tool.validate_params({"url": "https://example.com:8443"})
        assert result["hostname"] == "example.com"
        assert result["port"] == 8443

    def test_url_ip(self, tool):
        result = tool.validate_params({"url": "1.2.3.4"})
        assert result["hostname"] == "1.2.3.4"
        assert result["port"] == 443

    def test_empty_url(self, tool):
        with pytest.raises(ValueError, match="URL is required"):
            tool.validate_params({"url": ""})

    def test_overlong_url(self, tool):
        with pytest.raises(ValueError, match="exceeds 2048"):
            tool.validate_params({"url": "https://" + "a" * 2048 + ".com"})

    def test_accepts_target_alias(self, tool):
        result = tool.validate_params({"target": "example.com"})
        assert result["hostname"] == "example.com"

    def test_sni_override(self, tool):
        result = tool.validate_params({"url": "example.com", "sni": "sni.example.com"})
        assert result["sni"] == "sni.example.com"


class TestSslViewerExecute:
    @pytest.mark.asyncio
    async def test_blocks_private_ip(self, tool, ctx):
        with patch("app.tools.ssl_viewer.filter_target") as mock_filter:
            mock_filter.return_value = ("", "errors.target_not_allowed")
            result = await tool.execute({"url": "192.168.1.1"}, ctx)
            assert result.success is False
            assert result.error == "errors.target_not_allowed"

    @pytest.mark.asyncio
    async def test_successful_connection(self, tool, ctx):
        leaf = _fake_leaf_cert()
        with patch("app.tools.ssl_viewer.filter_target") as mock_filter:
            mock_filter.return_value = ("93.184.216.34", None)
            with patch("app.tools.ssl_viewer.asyncio.to_thread") as mock_thread:
                mock_thread.side_effect = [
                    (leaf, [], "TLSv1.3", "TLS_AES_256_GCM_SHA384"),  # permissive
                    None,  # validated
                ]
                result = await tool.execute({"url": "example.com"}, ctx)

        assert result.success is True
        assert result.data["tls_version"] == "TLSv1.3"
        assert result.data["cipher_suite"] == "TLS_AES_256_GCM_SHA384"
        assert result.data["chain_valid"] is True
        assert len(result.data["certificates"]) > 0
        cert0 = result.data["certificates"][0]
        assert cert0["subject"] == "CN=example.com"
        assert not cert0["is_expired"]
        assert not cert0["is_self_signed"]
        assert "revocation status was not checked" in result.data["warnings"][-1]["message"]

    @pytest.mark.asyncio
    async def test_chain_invalid_on_verification_error(self, tool, ctx):
        leaf = _fake_leaf_cert()
        import ssl as ssl_mod

        with patch("app.tools.ssl_viewer.filter_target") as mock_filter:
            mock_filter.return_value = ("93.184.216.34", None)
            with patch("app.tools.ssl_viewer.asyncio.to_thread") as mock_thread:
                mock_thread.side_effect = [
                    (leaf, [], "TLSv1.2", "ECDHE-RSA-AES128-GCM-SHA256"),  # permissive
                    ssl_mod.SSLCertVerificationError("verify failed"),  # validated fails
                ]
                result = await tool.execute({"url": "example.com"}, ctx)

        assert result.success is True
        assert result.data["chain_valid"] is False
        assert any("not trusted" in w["message"] for w in result.data["warnings"])

    @pytest.mark.asyncio
    async def test_tls_warning_for_old_version(self, tool, ctx):
        leaf = _fake_leaf_cert()
        with patch("app.tools.ssl_viewer.filter_target") as mock_filter:
            mock_filter.return_value = ("93.184.216.34", None)
            with patch("app.tools.ssl_viewer.asyncio.to_thread") as mock_thread:
                mock_thread.side_effect = [
                    (leaf, [], "TLSv1.0", "RC4-SHA"),  # TLS 1.0 — weak
                    None,  # validated
                ]
                result = await tool.execute({"url": "example.com"}, ctx)

        assert result.success is True
        assert any("outdated" in w["message"] for w in result.data["warnings"])

    @pytest.mark.asyncio
    async def test_ssl_error_handling(self, tool, ctx):
        import ssl as ssl_mod

        with patch("app.tools.ssl_viewer.filter_target") as mock_filter:
            mock_filter.return_value = ("93.184.216.34", None)
            with patch("app.tools.ssl_viewer.asyncio.to_thread") as mock_thread:
                mock_thread.side_effect = ssl_mod.SSLError("handshake failed")
                result = await tool.execute({"url": "example.com"}, ctx)

        assert result.success is False
        assert "handshake" in result.error.lower()

    @pytest.mark.asyncio
    async def test_timeout_handling(self, tool, ctx):

        with patch("app.tools.ssl_viewer.filter_target") as mock_filter:
            mock_filter.return_value = ("93.184.216.34", None)
            with patch("app.tools.ssl_viewer.asyncio.to_thread") as mock_thread:
                # Python's socket.timeout is a built-in exception
                mock_thread.side_effect = TimeoutError("timed out")
                result = await tool.execute({"url": "example.com"}, ctx)

        assert result.success is False
        assert result.error == "errors.timeout"

    @pytest.mark.asyncio
    async def test_connection_refused(self, tool, ctx):
        with patch("app.tools.ssl_viewer.filter_target") as mock_filter:
            mock_filter.return_value = ("93.184.216.34", None)
            with patch("app.tools.ssl_viewer.asyncio.to_thread") as mock_thread:
                mock_thread.side_effect = ConnectionRefusedError("refused")
                result = await tool.execute({"url": "example.com"}, ctx)

        assert result.success is False
        assert result.error == "errors.connection_refused"

    @pytest.mark.asyncio
    async def test_self_signed_ca_is_not_flagged(self, tool, ctx):
        """A self-signed CA certificate is normal (root CA) — not an issue."""
        ca = _fake_ca_cert()  # self-signed CA (BasicConstraints: ca=True)
        with patch("app.tools.ssl_viewer.filter_target") as mock_filter:
            mock_filter.return_value = ("93.184.216.34", None)
            with patch("app.tools.ssl_viewer.asyncio.to_thread") as mock_thread:
                mock_thread.side_effect = [
                    (ca, [], "TLSv1.3", "TLS_AES_256_GCM_SHA384"),
                    None,
                ]
                result = await tool.execute({"url": "example.com"}, ctx)

        assert result.success is True
        cert = result.data["certificates"][0]
        assert cert["is_self_signed"] is False  # CA self-signed → normal

    @pytest.mark.asyncio
    async def test_self_signed_end_entity_is_flagged(self, tool, ctx):
        """A self-signed end-entity cert (not a CA) is suspicious."""
        leaf = _fake_leaf_cert()  # end-entity (no BasicConstraints), issuer=Example CA
        with patch("app.tools.ssl_viewer.filter_target") as mock_filter:
            mock_filter.return_value = ("93.184.216.34", None)
            with patch("app.tools.ssl_viewer.asyncio.to_thread") as mock_thread:
                mock_thread.side_effect = [
                    (leaf, [], "TLSv1.3", "TLS_AES_256_GCM_SHA384"),
                    None,
                ]
                result = await tool.execute({"url": "example.com"}, ctx)

        assert result.success is True
        cert = result.data["certificates"][0]
        # End-entity cert with different issuer → not self-signed
        assert cert["is_self_signed"] is False

    @pytest.mark.asyncio
    async def test_wildcard_san_matching(self, tool, ctx):
        leaf = _fake_leaf_cert()
        with patch("app.tools.ssl_viewer.filter_target") as mock_filter:
            mock_filter.return_value = ("93.184.216.34", None)
            with patch("app.tools.ssl_viewer.asyncio.to_thread") as mock_thread:
                mock_thread.side_effect = [
                    (leaf, [], "TLSv1.3", "TLS_AES_256_GCM_SHA384"),
                    None,
                ]
                result = await tool.execute({"url": "example.com", "sni": "www.example.com"}, ctx)

        assert result.success is True
        cert = result.data["certificates"][0]
        # example.com should match via SAN
        assert not cert["name_mismatch"]

    @pytest.mark.asyncio
    async def test_name_mismatch_detected(self, tool, ctx):
        leaf = _fake_leaf_cert()  # cert is for example.com
        with patch("app.tools.ssl_viewer.filter_target") as mock_filter:
            mock_filter.return_value = ("93.184.216.34", None)
            with patch("app.tools.ssl_viewer.asyncio.to_thread") as mock_thread:
                mock_thread.side_effect = [
                    (leaf, [], "TLSv1.3", "TLS_AES_256_GCM_SHA384"),
                    None,
                ]
                result = await tool.execute({"url": "totally-different.com"}, ctx)

        assert result.success is True
        cert = result.data["certificates"][0]
        assert cert["name_mismatch"] is True


class TestSslViewerDefinition:
    def test_definition_metadata(self, tool):
        d = tool.get_definition()
        assert d.name == "ssl_viewer"
        assert d.category.value == "security"
        assert len(d.parameters) == 2


class TestParseUrl:
    def test_bare_hostname(self, tool):
        hostname, port = tool._parse_url("example.com")
        assert hostname == "example.com"
        assert port == 443

    def test_https_url_with_port(self, tool):
        hostname, port = tool._parse_url("https://example.com:8443")
        assert hostname == "example.com"
        assert port == 8443

    def test_http_url_default_port(self, tool):
        hostname, port = tool._parse_url("http://example.com")
        assert hostname == "example.com"
        assert port == 80

    def test_ip_address(self, tool):
        hostname, port = tool._parse_url("1.2.3.4")
        assert hostname == "1.2.3.4"
        assert port == 443


class TestTlsWeakDetection:
    def test_tls_1_0_is_weak(self, tool):
        assert tool._is_tls_weak("TLSv1.0") is True

    def test_tls_1_1_is_weak(self, tool):
        assert tool._is_tls_weak("TLSv1.1") is True

    def test_ssl_v3_is_weak(self, tool):
        assert tool._is_tls_weak("SSLv3") is True

    def test_tls_1_2_not_weak(self, tool):
        assert tool._is_tls_weak("TLSv1.2") is False

    def test_tls_1_3_not_weak(self, tool):
        assert tool._is_tls_weak("TLSv1.3") is False


class TestHostnameMatching:
    def test_exact_match(self):
        assert _hostname_matches("example.com", ["example.com"], "example.com") is True

    def test_wildcard_match(self):
        assert _hostname_matches("sub.example.com", ["*.example.com"], "") is True

    def test_wildcard_no_match(self):
        assert _hostname_matches("example.com", ["*.example.com"], "") is False

    def test_mismatch(self):
        assert _hostname_matches("foo.com", ["bar.com"], "bar.com") is False

    def test_case_insensitive(self):
        assert _hostname_matches("EXAMPLE.COM", ["example.com"], "") is True

    def test_cn_fallback(self):
        assert _hostname_matches("example.com", [], "example.com") is True

    def test_wildcard_subdomain_multiple_levels(self):
        # *.example.com matches only ONE label, not two
        assert _hostname_matches("deep.sub.example.com", ["*.example.com"], "") is False


class TestNormalizeKeyAlgorithm:
    def test_rsa(self):
        assert _normalize_key_algorithm("RSA") == "RSA"

    def test_elliptic_curve(self):
        assert _normalize_key_algorithm("EllipticCurve") == "EC"

    def test_ed25519(self):
        assert _normalize_key_algorithm("Ed25519") == "Ed25519"

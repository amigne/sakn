import asyncio
import logging
import re
import socket
import ssl
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from cryptography import x509
from cryptography.x509.oid import ExtensionOID, NameOID
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import dsa, ec, rsa

from app.security.address_filter import filter_target
from app.tools.base import BaseTool, ExecutionContext, ToolCategory, ToolDefinition, ToolParameter, ToolResult

logger = logging.getLogger(__name__)

TLS_VERSION_WARNING_PATTERN = re.compile(r"(SSL|TLS\s*v?1\.[01])", re.IGNORECASE)

# Key algorithms considered weak
WEAK_KEY_SIZES: dict[type, int] = {
    rsa.RSAPublicKey: 2048,
    dsa.DSAPublicKey: 2048,
    ec.EllipticCurvePublicKey: 256,
}


class SslViewerTool(BaseTool):
    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="ssl_viewer",
            display_name_key="tools.ssl_viewer.name",
            description_key="tools.ssl_viewer.description",
            category=ToolCategory.SECURITY,
            version="1.0.0",
            parameters=[
                ToolParameter(
                    name="url",
                    type="string",
                    label_key="tools.ssl_viewer.param_url_label",
                    description_key="tools.ssl_viewer.param_url_desc",
                    required=True,
                    constraints={"max_length": 2048},
                ),
                ToolParameter(
                    name="sni",
                    type="string",
                    label_key="tools.ssl_viewer.param_sni_label",
                    description_key="tools.ssl_viewer.param_sni_desc",
                    default="",
                ),
            ],
        )

    def validate_params(self, params: dict[str, Any]) -> dict[str, Any]:
        url = (params.get("url") or params.get("target") or "").strip()
        if not url:
            raise ValueError("URL is required")
        if len(url) > 2048:
            raise ValueError("URL exceeds 2048 characters")

        hostname, port = self._parse_url(url)

        sni = (params.get("sni") or "").strip()

        return {
            "url": url,
            "hostname": hostname,
            "port": port,
            "sni": sni,
        }

    async def execute(self, params: dict[str, Any], context: ExecutionContext) -> ToolResult:
        validated = self.validate_params(params)
        hostname = validated["hostname"]
        port = validated["port"]
        sni = validated["sni"] or hostname

        # Security filter: check target against blocklist
        resolved_ip, block_error = await filter_target(hostname)
        if block_error:
            return ToolResult(success=False, error=block_error)

        start = time.monotonic()
        warnings: list[str] = []
        chain_valid = False
        certificates: list[dict[str, Any]] = []
        tls_version = ""
        cipher_suite = ""

        # Step 1: Permissive connection to get certificate data and connection info
        try:
            leaf_der, intermediates_der, tls_version, cipher_suite = await asyncio.to_thread(
                self._connect_permissive, hostname, port, sni
            )
        except ssl.SSLError as e:
            duration_ms = (time.monotonic() - start) * 1000
            return ToolResult(success=False, error=f"SSL error: {e}", duration_ms=duration_ms)
        except socket.timeout:
            duration_ms = (time.monotonic() - start) * 1000
            return ToolResult(success=False, error="errors.timeout", duration_ms=duration_ms)
        except ConnectionRefusedError:
            duration_ms = (time.monotonic() - start) * 1000
            return ToolResult(success=False, error="errors.connection_refused", duration_ms=duration_ms)
        except OSError as e:
            duration_ms = (time.monotonic() - start) * 1000
            return ToolResult(success=False, error=f"Connection failed: {e}", duration_ms=duration_ms)

        # Step 2: Try validating connection for chain trust check
        try:
            await asyncio.to_thread(self._connect_validated, hostname, port, sni)
            chain_valid = True
        except (ssl.SSLCertVerificationError, ssl.SSLError):
            chain_valid = False
        except Exception:
            pass  # Non-certificate error, don't override chain_valid

        # Step 3: Parse all certificates
        all_ders = [leaf_der] + intermediates_der
        for der_data in all_ders:
            try:
                cert = x509.load_der_x509_certificate(der_data)
                certinfo = self._parse_cert(cert, hostname)
                certificates.append(certinfo)
            except Exception as e:
                logger.warning("Failed to parse certificate: %s", e)

        # Step 4: Build warnings
        if tls_version and self._is_tls_weak(tls_version):
            warnings.append("Connection is not secure: TLS version is outdated (less than TLS 1.2).")
        if not chain_valid:
            warnings.append("Certificate chain is not trusted by the system CA store.")

        warnings.append("Certificate revocation status was not checked.")

        duration_ms = (time.monotonic() - start) * 1000

        return ToolResult(
            success=True,
            data={
                "url": f"{hostname}:{port}",
                "tls_version": tls_version,
                "cipher_suite": cipher_suite,
                "certificates": certificates,
                "chain_valid": chain_valid,
                "warnings": warnings,
            },
            duration_ms=duration_ms,
        )

    @staticmethod
    def _parse_url(url: str) -> tuple[str, int]:
        """Extract hostname and port from a URL or hostname string."""
        url = url.strip()
        # Handle bare hostname (no scheme)
        if "://" not in url:
            url = "https://" + url

        parsed = urlparse(url)
        hostname = parsed.hostname or parsed.path or url
        port = parsed.port

        if port is None:
            port = 443 if parsed.scheme == "https" else 80

        return hostname, port

    @staticmethod
    def _connect_permissive(hostname: str, port: int, sni: str) -> tuple[bytes, list[bytes], str, str]:
        """Connect with certificate verification disabled to retrieve cert data."""
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        with socket.create_connection((hostname, port), timeout=10) as sock:
            with ctx.wrap_socket(sock, server_hostname=sni) as ssock:
                tls_version = ssock.version() or "Unknown"
                cipher_info = ssock.cipher() or (None, None, None)
                cipher_suite = cipher_info[0] or "Unknown"
                leaf_der = ssock.getpeercert(binary_form=True)

                # Try to get intermediates
                intermediates: list[bytes] = []
                try:
                    extra_chain = ctx.get_ca_certs()
                    if extra_chain:
                        for entry in extra_chain:
                            if "binary" in entry:
                                intermediates.append(entry["binary"])
                except Exception:
                    pass

        return leaf_der, intermediates, tls_version, cipher_suite

    @staticmethod
    def _connect_validated(hostname: str, port: int, sni: str) -> None:
        """Connect with full certificate validation to check chain trust."""
        ctx = ssl.create_default_context()
        ctx.check_hostname = True
        ctx.verify_mode = ssl.CERT_REQUIRED

        with socket.create_connection((hostname, port), timeout=10) as sock:
            with ctx.wrap_socket(sock, server_hostname=sni):
                pass  # Handshake succeeded → chain is valid

    @staticmethod
    def _is_tls_weak(tls_version: str) -> bool:
        return bool(TLS_VERSION_WARNING_PATTERN.match(tls_version))

    @staticmethod
    def _parse_cert(cert: x509.Certificate, hostname: str) -> dict[str, Any]:
        """Extract structured info from a certificate."""
        # Subject / Issuer
        subject = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
        subject_cn = subject[0].value if subject else "Unknown"

        issuer = cert.issuer.get_attributes_for_oid(NameOID.COMMON_NAME)
        issuer_cn = issuer[0].value if issuer else "Unknown"

        # Subject Alternative Names
        sans: list[str] = []
        try:
            san_ext = cert.extensions.get_extension_for_oid(ExtensionOID.SUBJECT_ALTERNATIVE_NAME)
            sans = san_ext.value.get_values_for_type(x509.DNSName)
        except x509.ExtensionNotFound:
            pass

        # Key info
        public_key = cert.public_key()
        key_algorithm = type(public_key).__name__.replace("PublicKey", "")
        key_size = public_key.key_size

        # Signature algorithm
        sig_algo = cert.signature_algorithm_oid._name if cert.signature_algorithm_oid else "Unknown"

        # Fingerprints
        fingerprint_sha256 = cert.fingerprint(hashes.SHA256()).hex(":")
        fingerprint_sha1 = cert.fingerprint(hashes.SHA1()).hex(":")

        # Extended Key Usage
        ekus: list[str] = []
        try:
            eku_ext = cert.extensions.get_extension_for_oid(ExtensionOID.EXTENDED_KEY_USAGE)
            for eku in eku_ext.value:
                ekus.append(eku.dotted_string if hasattr(eku, "dotted_string") else str(eku))
        except x509.ExtensionNotFound:
            pass

        # Validity
        now = datetime.now(tz=timezone.utc)
        is_expired = now > cert.not_valid_after_utc

        # Self-signed
        is_self_signed = cert.issuer == cert.subject

        # Hostname match check (leaf cert only)
        name_mismatch = False
        if hostname:
            name_mismatch = not _hostname_matches(hostname, sans, subject_cn)

        # Weak key check
        is_weak_key = False
        for key_cls, min_size in WEAK_KEY_SIZES.items():
            if isinstance(public_key, key_cls) and key_size < min_size:
                is_weak_key = True
                break

        return {
            "subject": f"CN={subject_cn}",
            "issuer": f"CN={issuer_cn}",
            "valid_from": cert.not_valid_before_utc.isoformat(),
            "valid_until": cert.not_valid_after_utc.isoformat(),
            "sans": sans,
            "key_algorithm": _normalize_key_algorithm(key_algorithm),
            "key_size": key_size,
            "signature_algorithm": sig_algo,
            "fingerprint_sha256": fingerprint_sha256,
            "fingerprint_sha1": fingerprint_sha1,
            "extended_key_usage": ekus,
            "is_expired": is_expired,
            "is_self_signed": is_self_signed,
            "name_mismatch": name_mismatch,
            "is_weak_key": is_weak_key,
        }

    def get_result_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "tls_version": {"type": "string"},
                "cipher_suite": {"type": "string"},
                "certificates": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "subject": {"type": "string"},
                            "issuer": {"type": "string"},
                            "valid_from": {"type": "string"},
                            "valid_until": {"type": "string"},
                            "sans": {"type": "array", "items": {"type": "string"}},
                            "key_algorithm": {"type": "string"},
                            "key_size": {"type": "integer"},
                            "signature_algorithm": {"type": "string"},
                            "fingerprint_sha256": {"type": "string"},
                            "fingerprint_sha1": {"type": "string"},
                            "extended_key_usage": {"type": "array", "items": {"type": "string"}},
                            "is_expired": {"type": "boolean"},
                            "is_self_signed": {"type": "boolean"},
                            "name_mismatch": {"type": "boolean"},
                            "is_weak_key": {"type": "boolean"},
                        },
                    },
                },
                "chain_valid": {"type": "boolean"},
                "warnings": {"type": "array", "items": {"type": "string"}},
            },
        }


def _hostname_matches(hostname: str, sans: list[str], subject_cn: str) -> bool:
    """Check if hostname matches SANs or CN."""
    hostname_lower = hostname.lower().rstrip(".")
    for san in sans:
        pattern = san.lower().rstrip(".")
        if pattern.startswith("*."):
            suffix = pattern[1:]  # includes the dot
            # Wildcard matches exactly one label; no dots in the matched part
            if hostname_lower.endswith(suffix) and "." not in hostname_lower[:-len(suffix)]:
                return True
        elif hostname_lower == pattern:
            return True
    cn = subject_cn.lower().rstrip(".")
    if hostname_lower == cn:
        return True
    return False


def _normalize_key_algorithm(algo: str) -> str:
    """Normalize key algorithm names for display."""
    mapping = {
        "RSA": "RSA",
        "EllipticCurve": "EC",
        "EC": "EC",
        "DSA": "DSA",
        "Ed25519": "Ed25519",
        "Ed448": "Ed448",
    }
    return mapping.get(algo, algo)

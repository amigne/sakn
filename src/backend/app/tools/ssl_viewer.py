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
from cryptography.hazmat.primitives.serialization import Encoding
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
        for idx, der_data in enumerate(all_ders):
            try:
                cert = x509.load_der_x509_certificate(der_data)
                certinfo = self._parse_cert(cert, hostname, is_leaf=(idx == 0))
                is_last = (idx == len(all_ders) - 1)
                is_self_signed = cert.subject == cert.issuer

                # Trust status for self-signed roots
                if is_self_signed and is_last:
                    certinfo["is_trusted_root"] = self._check_in_trust_store(der_data)
                    certinfo["is_untrusted"] = not certinfo["is_trusted_root"]
                    certinfo["missing_issuer"] = False
                    certinfo["missing_issuer_name"] = None
                elif not is_self_signed and is_last and not chain_valid:
                    # Chain invalid and the last cert is not self-signed →
                    # its issuer (the root) is missing from both the chain
                    # and the system trust store.
                    certinfo["is_trusted_root"] = False
                    certinfo["is_untrusted"] = False
                    certinfo["missing_issuer"] = True
                    icn = [a.value for a in cert.issuer.get_attributes_for_oid(NameOID.COMMON_NAME)]
                    certinfo["missing_issuer_name"] = f"CN={icn[0]}" if icn else "Unknown"
                else:
                    certinfo["is_trusted_root"] = False
                    certinfo["is_untrusted"] = False
                    certinfo["missing_issuer"] = False
                    certinfo["missing_issuer_name"] = None

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

                # Full certificate chain (leaf + intermediates)
                try:
                    full_chain: list[bytes] = ssock.get_unverified_chain()
                except Exception:
                    full_chain = [ssock.getpeercert(binary_form=True)]

                leaf_der = full_chain[0] if full_chain else ssock.getpeercert(binary_form=True)
                intermediates = full_chain[1:] if len(full_chain) > 1 else []

                # If the last cert is not self-signed, try to find its issuer
                # (the root CA) in the system trust store and append it.
                if intermediates:
                    last_der = intermediates[-1]
                else:
                    last_der = leaf_der
                root_der = SslViewerTool._find_root_in_store(last_der)
                if root_der is not None:
                    intermediates = intermediates + [root_der]

        return leaf_der, intermediates, tls_version, cipher_suite

    @classmethod
    def _load_system_ca_certs(cls) -> list[x509.Certificate]:
        """Load and cache all certificates from the system CA store."""
        cache = getattr(cls, "_system_ca_certs_cache", None)
        if cache is not None:
            return cache

        import os
        import hashlib

        pem_files: list[str] = []
        verify_paths = ssl.get_default_verify_paths()

        for candidate in (verify_paths.cafile, verify_paths.openssl_cafile):
            if candidate and os.path.isfile(candidate):
                pem_files.append(candidate)
                break

        if not pem_files:
            capath = verify_paths.capath or verify_paths.openssl_capath
            if capath and os.path.isdir(capath):
                for fn in sorted(os.listdir(capath)):
                    fp = os.path.join(capath, fn)
                    if os.path.isfile(fp) and fn.endswith(".pem"):
                        pem_files.append(fp)

        certs: list[x509.Certificate] = []
        seen: set[str] = set()
        for fp in pem_files:
            try:
                with open(fp, "rb") as f:
                    raw = f.read()
                for ca in x509.load_pem_x509_certificates(raw):
                    digest = hashlib.sha256(ca.public_bytes(Encoding.DER)).hexdigest()
                    if digest not in seen:
                        seen.add(digest)
                        certs.append(ca)
            except Exception:
                continue

        cls._system_ca_certs_cache = certs
        return certs

    @classmethod
    def _check_in_trust_store(cls, cert_der: bytes) -> bool:
        """Return True if *cert_der* is a root certificate present in the system CA store."""
        try:
            cert = x509.load_der_x509_certificate(cert_der)
        except Exception:
            return False

        for ca in cls._load_system_ca_certs():
            if ca.subject == cert.subject:
                return True
        return False

    @classmethod
    def _find_root_in_store(cls, cert_der: bytes) -> bytes | None:
        """If *cert_der* is not self-signed, look up its issuer in the system CA store."""
        try:
            cert = x509.load_der_x509_certificate(cert_der)
        except Exception:
            return None

        # Already a root (self-signed) — nothing to add.
        if cert.issuer == cert.subject:
            return None

        for ca in cls._load_system_ca_certs():
            if ca.subject == cert.issuer:
                return ca.public_bytes(Encoding.DER)

        return None

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
    def _load_trusted_fingerprints() -> set[str]:
        """Return SHA-256 fingerprints of all certificates in the system CA store."""
        fps: set[str] = set()
        try:
            ctx = ssl.create_default_context()
            for entry in ctx.get_ca_certs():
                der = entry.get("binary")
                if der:
                    cert = x509.load_der_x509_certificate(der)
                    fps.add(cert.fingerprint(hashes.SHA256()).hex(":"))
        except Exception:
            pass
        return fps

    @staticmethod
    def _parse_cert(cert: x509.Certificate, hostname: str, *, is_leaf: bool = False) -> dict[str, Any]:
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

        # Is this a CA certificate? (BasicConstraints: CA=True)
        is_ca = False
        try:
            bc_ext = cert.extensions.get_extension_for_oid(ExtensionOID.BASIC_CONSTRAINTS)
            is_ca = bc_ext.value.ca or False
        except x509.ExtensionNotFound:
            pass

        # Self-signed: normal for root/intermediate CAs, suspicious for end-entity certs.
        is_self_signed = cert.issuer == cert.subject
        if is_ca and is_self_signed:
            # A self-signed CA is a root — not an issue by itself.
            # Its trust comes from the system CA store, checked via chain_valid.
            is_self_signed = False

        # Hostname match check — only applies to the leaf (end-entity) certificate.
        # Intermediate and root CA certs are not expected to carry the server's hostname.
        name_mismatch = False
        if is_leaf and hostname:
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
                            "is_untrusted": {"type": "boolean"},
                            "is_trusted_root": {"type": "boolean"},
                            "missing_issuer": {"type": "boolean"},
                            "missing_issuer_name": {"type": "string"},
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

import asyncio
import http.client
import logging
import re
import socket
import ssl
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from cryptography import x509
from cryptography.x509 import ocsp
from cryptography.x509.oid import AuthorityInformationAccessOID, ExtensionOID, NameOID
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.serialization import Encoding
from cryptography.hazmat.primitives.asymmetric import dsa, ec, rsa

# CRL cache directory — one file per URL hash, refreshed daily.
_CRL_CACHE_DIR = "/tmp/sakn-crl-cache"

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
                certinfo["revocation_status"] = ""
                certinfo["revocation_detail"] = ""

                certificates.append(certinfo)
            except Exception as e:
                logger.warning("Failed to parse certificate: %s", e)

        # Step 4: Revocation check for every cert in the chain (OCSP → CRL fallback)
        leaf_revoked = False
        for idx in range(len(all_ders)):
            if idx + 1 >= len(all_ders):
                # Last cert (root) — can't check revocation against itself
                if idx < len(certificates):
                    certificates[idx]["revocation_status"] = ""
                    certificates[idx]["revocation_detail"] = ""
                continue

            status, detail = self._check_revocation(all_ders[idx], all_ders[idx + 1])
            if status == "unknown":
                status, detail = self._check_crl(all_ders[idx])

            if idx < len(certificates):
                certificates[idx]["revocation_status"] = status
                certificates[idx]["revocation_detail"] = detail

            if status == "revoked" and idx == 0:
                leaf_revoked = True

        # A revoked leaf certificate invalidates the entire chain.
        if leaf_revoked:
            chain_valid = False

        # Step 5: Build warnings (each is {message, variant: "error"|"warning"})
        if tls_version and self._is_tls_weak(tls_version):
            warnings.append({"message": "Connection is not secure: TLS version is outdated (less than TLS 1.2).", "variant": "warning"})
        if leaf_revoked:
            c0 = certificates[0] if certificates else {}
            warnings.append({"message": f"Certificate is revoked: {c0.get('revocation_detail', '')}", "variant": "error"})
            # When revoked, the chain-trusted message is redundant — skip it.
        elif not chain_valid:
            warnings.append({"message": "Certificate chain is not trusted by the system CA store.", "variant": "error"})
        if not leaf_revoked and certificates and not certificates[0].get("revocation_status"):
            warnings.append({"message": "Certificate revocation status was not checked.", "variant": "warning"})

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

    # ── OCSP Revocation Checking ────────────────────────────────────

    @staticmethod
    def _get_ocsp_url(cert: x509.Certificate) -> str | None:
        """Extract the OCSP responder URL from a certificate's AIA extension."""
        try:
            aia = cert.extensions.get_extension_for_oid(ExtensionOID.AUTHORITY_INFORMATION_ACCESS)
            for desc in aia.value:
                if desc.access_method == AuthorityInformationAccessOID.OCSP:
                    return desc.access_location.value
        except x509.ExtensionNotFound:
            pass
        return None

    @staticmethod
    def _check_revocation(leaf_der: bytes, issuer_der: bytes) -> tuple[str, str]:
        """Check certificate revocation via OCSP.

        Returns (status, detail) where status is 'good', 'revoked', or 'unknown'.
        """
        try:
            leaf = x509.load_der_x509_certificate(leaf_der)
            issuer = x509.load_der_x509_certificate(issuer_der)
        except Exception:
            return "unknown", "Failed to parse certificate data"

        # Find OCSP URL: leaf AIA → issuer AIA → derived from caIssuers
        ocsp_url = (
            SslViewerTool._get_ocsp_url(leaf)
            or SslViewerTool._get_ocsp_url(issuer)
            or SslViewerTool._derive_ocsp_url(leaf, issuer)
        )
        if not ocsp_url:
            return "unknown", "No OCSP responder URL found"

        try:
            # Build OCSP request
            builder = ocsp.OCSPRequestBuilder()
            builder = builder.add_certificate(leaf, issuer, hashes.SHA256())
            ocsp_req = builder.build()

            # Send to OCSP responder
            parsed = urlparse(ocsp_url)
            conn = http.client.HTTPConnection(parsed.hostname, parsed.port or 80, timeout=5)
            conn.request(
                "POST",
                parsed.path or "/",
                body=ocsp_req.public_bytes(Encoding.DER),
                headers={
                    "Content-Type": "application/ocsp-request",
                    "Accept": "application/ocsp-response",
                    "Host": parsed.hostname or "",
                },
            )
            resp = conn.getresponse()
            resp_data = resp.read()
            conn.close()

            ocsp_resp = ocsp.load_der_ocsp_response(resp_data)
            if ocsp_resp.response_status != ocsp.OCSPResponseStatus.SUCCESSFUL:
                return "unknown", f"OCSP responder error: {ocsp_resp.response_status.name}"

            if ocsp_resp.certificate_status == ocsp.OCSPCertStatus.GOOD:
                return "good", "Certificate is not revoked"
            elif ocsp_resp.certificate_status == ocsp.OCSPCertStatus.REVOKED:
                when = ""
                try:
                    when = f" at {ocsp_resp.revocation_time.isoformat()}"
                except Exception:
                    pass
                return "revoked", f"Certificate revoked{when}"
            else:
                return "unknown", "OCSP status: unknown"
        except OSError:
            return "unknown", "OCSP responder unreachable"
        except Exception:
            return "unknown", "OCSP check failed"

    @classmethod
    def _check_crl(cls, leaf_der: bytes) -> tuple[str, str]:
        """Check certificate revocation via CRL distribution points (cached)."""
        try:
            leaf = x509.load_der_x509_certificate(leaf_der)
        except Exception:
            return "unknown", "Failed to parse certificate"

        crl_urls: list[str] = []
        try:
            crl_dp = leaf.extensions.get_extension_for_oid(ExtensionOID.CRL_DISTRIBUTION_POINTS)
            for dp in crl_dp.value:
                if dp.full_name:
                    for name in dp.full_name:
                        crl_urls.append(name.value)
        except x509.ExtensionNotFound:
            pass

        if not crl_urls:
            return "unknown", "No CRL distribution points in certificate"

        for crl_url in crl_urls:
            crl_der = cls._fetch_crl_cached(crl_url)
            if crl_der is None:
                continue
            try:
                crl = x509.load_der_x509_crl(crl_der)
                for revoked in crl:
                    if revoked.serial_number == leaf.serial_number:
                        when = ""
                        try:
                            when = f" at {revoked.revocation_date_utc.isoformat()}"
                        except Exception:
                            pass
                        return "revoked", f"Certificate revoked{when}"
                return "good", "Certificate is not revoked (CRL)"
            except Exception:
                continue

        return "unknown", "CRL check failed"

    @classmethod
    def _fetch_crl_cached(cls, crl_url: str) -> bytes | None:
        """Fetch a CRL, caching the result on disk for 24 hours."""
        import hashlib
        import os

        os.makedirs(_CRL_CACHE_DIR, exist_ok=True)
        cache_key = hashlib.sha256(crl_url.encode()).hexdigest()[:32]
        cache_path = os.path.join(_CRL_CACHE_DIR, cache_key)

        # Return cached data if fresh enough (< 24h)
        if os.path.isfile(cache_path):
            age = time.time() - os.path.getmtime(cache_path)
            if age < 86400:  # 24 hours
                try:
                    with open(cache_path, "rb") as f:
                        return f.read()
                except Exception:
                    pass

        # Download and cache
        try:
            parsed = urlparse(crl_url)
            conn = http.client.HTTPConnection(
                parsed.hostname, parsed.port or 80, timeout=10
            )
            conn.request("GET", parsed.path or "/")
            resp = conn.getresponse()
            if resp.status != 200:
                conn.close()
                return None
            data = resp.read()
            conn.close()

            # Validate it's a CRL before caching
            x509.load_der_x509_crl(data)

            with open(cache_path, "wb") as f:
                f.write(data)
            return data
        except Exception:
            return None

    @staticmethod
    def _derive_ocsp_url(leaf: x509.Certificate, issuer: x509.Certificate) -> str | None:
        """Try to derive the OCSP URL from the caIssuers URL (Let's Encrypt convention)."""
        try:
            aia = leaf.extensions.get_extension_for_oid(ExtensionOID.AUTHORITY_INFORMATION_ACCESS)
        except x509.ExtensionNotFound:
            try:
                aia = issuer.extensions.get_extension_for_oid(ExtensionOID.AUTHORITY_INFORMATION_ACCESS)
            except x509.ExtensionNotFound:
                return None

        ca_issuers_url = None
        for desc in aia.value:
            if desc.access_method == AuthorityInformationAccessOID.CA_ISSUERS:
                ca_issuers_url = desc.access_location.value
                break

        if not ca_issuers_url:
            return None

        # Let's Encrypt pattern: {name}.i.lencr.org → {name}.o.lencr.org
        if ".i.lencr.org" in ca_issuers_url:
            return ca_issuers_url.replace(".i.lencr.org", ".o.lencr.org")

        return None

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
        subject_cn_attrs = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
        subject_cn = subject_cn_attrs[0].value if subject_cn_attrs else "Unknown"

        # The Subject is completely empty (no RDNs at all).
        empty_subject = len(cert.subject) == 0

        # Subject has attributes but no Common Name.  Valid per RFC 6125
        # when SANs are present, but unusual — flag as a warning.
        no_common_name = not empty_subject and len(subject_cn_attrs) == 0

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

        # Serial number (hex string)
        serial_number = f"{cert.serial_number:X}"

        # Key Usage
        key_usage: list[str] = []
        try:
            ku = cert.extensions.get_extension_for_oid(ExtensionOID.KEY_USAGE).value
            for attr in (
                "digital_signature", "content_commitment", "key_encipherment",
                "data_encipherment", "key_agreement", "key_cert_sign", "crl_sign",
            ):
                try:
                    if getattr(ku, attr, False):
                        key_usage.append(attr)
                except Exception:
                    pass
            # encipher_only / decipher_only only meaningful when key_agreement is set
            try:
                if ku.key_agreement:
                    if ku.encipher_only:
                        key_usage.append("encipher_only")
                    if ku.decipher_only:
                        key_usage.append("decipher_only")
            except Exception:
                pass
        except x509.ExtensionNotFound:
            pass

        # Basic Constraints detail
        bc_path_length: int | None = None
        try:
            bc = cert.extensions.get_extension_for_oid(ExtensionOID.BASIC_CONSTRAINTS)
            bc_path_length = bc.value.path_length
        except x509.ExtensionNotFound:
            pass

        # Authority Information Access
        aia_entries: list[dict[str, str]] = []
        try:
            aia = cert.extensions.get_extension_for_oid(ExtensionOID.AUTHORITY_INFORMATION_ACCESS)
            for desc in aia.value:
                aia_entries.append({
                    "method": "OCSP" if desc.access_method == AuthorityInformationAccessOID.OCSP
                              else "caIssuers" if desc.access_method == AuthorityInformationAccessOID.CA_ISSUERS
                              else desc.access_method.dotted_string,
                    "url": desc.access_location.value,
                })
        except x509.ExtensionNotFound:
            pass

        # CRL Distribution Points
        crl_urls: list[str] = []
        try:
            crl_dp = cert.extensions.get_extension_for_oid(ExtensionOID.CRL_DISTRIBUTION_POINTS)
            for dp in crl_dp.value:
                if dp.full_name:
                    for name in dp.full_name:
                        crl_urls.append(name.value)
        except x509.ExtensionNotFound:
            pass

        # Subject / Authority Key Identifiers
        ski_hex = ""
        try:
            ski = cert.extensions.get_extension_for_oid(ExtensionOID.SUBJECT_KEY_IDENTIFIER)
            ski_hex = ski.value.digest.hex(":")
        except x509.ExtensionNotFound:
            pass

        aki_hex = ""
        try:
            aki = cert.extensions.get_extension_for_oid(ExtensionOID.AUTHORITY_KEY_IDENTIFIER)
            aki_hex = aki.value.key_identifier.hex(":") if aki.value.key_identifier else ""
        except x509.ExtensionNotFound:
            pass

        # Certificate Policies
        policy_oids: list[str] = []
        try:
            cp = cert.extensions.get_extension_for_oid(ExtensionOID.CERTIFICATE_POLICIES)
            for pi in cp.value:
                policy_oids.append(pi.policy_identifier.dotted_string)
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

        if empty_subject:
            subject_label = "Empty Subject"
        elif no_common_name:
            subject_label = cert.subject.rfc4514_string()
        else:
            subject_label = f"CN={subject_cn}"

        return {
            "subject": subject_label,
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
            "no_common_name": no_common_name,
            "empty_subject": empty_subject,
            "serial_number": serial_number,
            "key_usage": key_usage,
            "is_ca": is_ca,
            "bc_path_length": bc_path_length,
            "aia_entries": aia_entries,
            "crl_urls": crl_urls,
            "ski": ski_hex,
            "aki": aki_hex,
            "policy_oids": policy_oids,
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
                            "no_common_name": {"type": "boolean"},
                            "empty_subject": {"type": "boolean"},
                            "revocation_status": {"type": "string"},
                            "revocation_detail": {"type": "string"},
                            "serial_number": {"type": "string"},
                            "key_usage": {"type": "array", "items": {"type": "string"}},
                            "is_ca": {"type": "boolean"},
                            "bc_path_length": {"type": "integer"},
                            "aia_entries": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "method": {"type": "string"},
                                        "url": {"type": "string"},
                                    },
                                },
                            },
                            "crl_urls": {"type": "array", "items": {"type": "string"}},
                            "ski": {"type": "string"},
                            "aki": {"type": "string"},
                            "policy_oids": {"type": "array", "items": {"type": "string"}},
                        },
                    },
                },
                "chain_valid": {"type": "boolean"},
                "warnings": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "message": {"type": "string"},
                            "variant": {"type": "string", "enum": ["error", "warning"]},
                        },
                    },
                },
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

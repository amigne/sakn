"""WHOIS lookup tool — RDAP-first with WHOIS/43 fallback (Sprint 2).

Sprint 1 implements the RDAP phase and the complete SSRF/validation foundation.
When RDAP fails, the tool returns WHOIS_UNSUPPORTED_TLD or WHOIS_CONNECTION_FAILED
with a clean extension point for the Sprint 2 WHOIS/43 fallback.

References:
  - spec-tool-whois.md §1–6
  - ADR-018 (RDAP/WHOIS strategy, SSRF policy)
  - app/security/address_filter.py (filter_target)
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import time
from ipaddress import ip_address
from typing import Any
from urllib.parse import quote, urlparse

import httpx

from app.config import settings
from app.security.address_filter import filter_target
from app.tools.base import (
    BaseTool,
    ExecutionContext,
    ToolCategory,
    ToolDefinition,
    ToolParameter,
    ToolResult,
)

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

IANA_RDAP_BOOTSTRAP = "https://rdap.iana.org"
MAX_RDAP_REDIRECTS = 3


# ── IP pinning (resolve-then-connect, DNS-rebinding defence) ─────────────────


@contextlib.asynccontextmanager
async def _pin_resolution(host: str, ip: str):
    """Temporarily pin DNS resolution for *host* to *ip* on the running event loop.

    This implements the resolve-then-connect pattern required by ADR-018 §B.5:
    the connection goes to the pre-validated IP while the URL keeps the hostname,
    so TLS SNI and certificate verification still apply.

    Used for RDAP (HTTPS) connections.  For plain TCP (WHOIS/43, Sprint 2),
    ``asyncio.open_connection(ip, 43)`` suffices.
    """
    loop = asyncio.get_running_loop()
    original = loop.getaddrinfo

    async def patched(hostname, *args, **kwargs):
        if hostname == host:
            return await original(ip, *args, **kwargs)
        return await original(hostname, *args, **kwargs)

    loop.getaddrinfo = patched  # type: ignore[method-assign]
    try:
        yield
    finally:
        loop.getaddrinfo = original  # type: ignore[method-assign]


# ── RDAP response parsing ────────────────────────────────────────────────────


def _parse_rdap_response(data: dict[str, Any], target: str) -> dict[str, Any]:
    """Parse an RDAP JSON response into structured WHOIS fields.

    Mapping per spec-tool-whois.md §4.1 (RFC 7483).
    All fields except ``protocol`` and ``domain`` are nullable.
    """
    # Domain name
    domain = data.get("ldhName") or data.get("handle") or target

    # Status
    status: list[str] = data.get("status", [])

    # Registrar — first entity with role=registrar
    registrar: str | None = None
    whois_server: str | None = None
    registrant: dict[str, Any] | None = None
    admin_contact: dict[str, Any] | None = None
    tech_contact: dict[str, Any] | None = None

    for entity in data.get("entities", []):
        role = _normalise_role(entity.get("roles", []))
        vcard = _extract_vcard(entity.get("vcardArray"))

        if role == "registrar":
            registrar = _vcard_org_name(vcard)
        elif role == "registrant":
            registrant = vcard if not _is_gdpr_redacted(vcard, entity) else None
        elif role == "administrative":
            admin_contact = vcard if not _is_gdpr_redacted(vcard, entity) else None
        elif role == "technical":
            tech_contact = vcard if not _is_gdpr_redacted(vcard, entity) else None

    # Name servers
    name_servers: list[str] = []
    for ns in data.get("nameservers", []):
        ldh = ns.get("ldhName")
        if ldh:
            name_servers.append(ldh.lower())

    # Events → dates
    creation_date: str | None = None
    expiration_date: str | None = None
    updated_date: str | None = None

    for event in data.get("events", []):
        action = event.get("eventAction", "")
        date_str = event.get("eventDate", "")
        if action == "registration":
            creation_date = date_str or None
        elif action == "expiration":
            expiration_date = date_str or None
        elif action in ("last changed", "last update of RDAP database"):
            updated_date = date_str or None

    # Disclaimer from notices
    disclaimer: str | None = None
    for notice in data.get("notices", []):
        title = notice.get("title", "")
        if "terms" in title.lower() or "copyright" in title.lower():
            desc = notice.get("description", [])
            if isinstance(desc, list) and desc:
                disclaimer = " ".join(desc)
                break

    return {
        "protocol": "rdap",
        "domain": domain,
        "status": status,
        "registrar": registrar,
        "whois_server": whois_server,
        "name_servers": name_servers,
        "creation_date": creation_date,
        "expiration_date": expiration_date,
        "updated_date": updated_date,
        "registrant": registrant,
        "admin_contact": admin_contact,
        "tech_contact": tech_contact,
        "raw_text": None,
        "disclaimer": disclaimer,
    }


def _normalise_role(roles: list[str]) -> str | None:
    """Map RDAP entity roles to our canonical role keys."""
    role_map = {
        "registrar": "registrar",
        "registrant": "registrant",
        "administrative": "administrative",
        "admin": "administrative",
        "technical": "technical",
        "tech": "technical",
    }
    for r in roles:
        mapped = role_map.get(r.lower())
        if mapped:
            return mapped
    return None


def _extract_vcard(vcard_array: list[Any] | None) -> dict[str, Any] | None:
    """Extract a simplified dict from an RDAP jCard (RFC 7095) vcardArray.

    Returns a dict with keys like ``fn``, ``org``, ``email``, ``tel``, ``adr``,
    or ``None`` if the vcard is missing or empty.
    """
    if not vcard_array or not isinstance(vcard_array, list):
        return None

    # jCard structure: ["vcard", [["property", {}, "text", "value"], ...]]
    if len(vcard_array) < 2:
        return None
    props = vcard_array[1]
    if not isinstance(props, list):
        return None

    result: dict[str, Any] = {}
    for prop in props:
        if not isinstance(prop, list) or len(prop) < 4:
            continue
        name = prop[0].lower() if isinstance(prop[0], str) else ""
        value = prop[3] if len(prop) > 3 else ""

        if name == "fn":
            result["fn"] = str(value).strip() if value else None
        elif name == "org":
            # org value is an array of strings
            if isinstance(value, list):
                result["org"] = " ".join(str(v) for v in value if v).strip() or None
            else:
                result["org"] = str(value).strip() if value else None
        elif name == "email":
            result["email"] = str(value).strip() if value else None
        elif name == "tel":
            result["tel"] = str(value).strip() if value else None
        elif name == "adr":
            # adr value is an array: [pobox, ext, street, locality, region, code, country]
            if isinstance(value, list):
                parts = [str(v) for v in value if v]
                result["adr"] = ", ".join(parts) if parts else None
        elif name == "role":
            result["role"] = str(value).strip() if value else None

    # If we got nothing useful, return None
    if not any(v for v in result.values() if v):
        return None
    return result


def _vcard_org_name(vcard: dict[str, Any] | None) -> str | None:
    """Extract the best organisation name from a simplified vcard dict."""
    if not vcard:
        return None
    return vcard.get("org") or vcard.get("fn") or None


def _is_gdpr_redacted(vcard: dict[str, Any] | None, entity: dict[str, Any]) -> bool:
    """Heuristic: is this RDAP entity GDPR-redacted?

    Returns True if the contact data is unavailable due to privacy redaction.
    """
    # If the vcard is empty or only contains a "role" field like "Redacted",
    # consider it redacted.
    if not vcard:
        return True

    # Check for explicit redaction notices
    for remark in entity.get("remarks", []):
        desc = " ".join(remark.get("description", []))
        if any(
            keyword in desc.lower()
            for keyword in ("redacted", "gdpr", "personal data", "protected")
        ):
            return True

    # If the vcard has an fn that is just "Redacted" or similar
    fn = vcard.get("fn", "")
    if isinstance(fn, str) and fn.lower() in ("redacted", "redacted for privacy"):
        return True

    # If we have a meaningful name or org, consider it not redacted
    return not (vcard.get("fn") or vcard.get("org"))


# ── Helpers ──────────────────────────────────────────────────────────────────


def _extract_tld(domain: str) -> str:
    """Extract the TLD from a domain name.

    Examples:
        example.com → com
        sub.example.co.uk → co.uk   (best-effort — the last two labels)
        com → com
    """
    domain = domain.lower().strip().rstrip(".")
    parts = domain.split(".")
    if len(parts) == 1:
        return parts[0]
    # For ccTLDs, the "public suffix" may be two labels (e.g., co.uk).
    # We use a simple heuristic: if the last label is 2 chars (ccTLD),
    # and the second-to-last is ≤ 3 chars, treat both as TLD.
    # This is a pragmatic approximation — a proper Public Suffix List parser
    # would be overkill for Sprint 1.
    if len(parts[-1]) == 2 and len(parts) >= 2 and len(parts[-2]) <= 3:
        return ".".join(parts[-2:])
    return parts[-1]


def _build_rdap_url(base_url: str, target: str, is_ip: bool) -> str:
    """Build the full RDAP query URL for a target.

    The ``target`` is percent-encoded into the path so that it cannot break out
    of the ``/domain/`` segment or inject query/fragment components into the URL
    (defense-in-depth — the target is already SSRF-validated and DNS-resolvable,
    but a domain may contain characters that are special in a URL path).
    IP targets are left untouched: they are strictly validated by
    ``ipaddress.ip_address`` upstream and may legitimately contain ``:`` (IPv6).
    """
    base = base_url.rstrip("/")
    if is_ip:
        return f"{base}/ip/{target}"
    return f"{base}/domain/{quote(target, safe='')}"


# ── WhoisLookupTool ──────────────────────────────────────────────────────────


class WhoisLookupTool(BaseTool):
    """WHOIS lookup tool — RDAP-first with WHOIS/43 fallback (Sprint 2).

    Sprint 1 scope:
    - RDAP phase: IANA bootstrap → authoritative query → JSON parsing
    - SSRF foundation: filter_target on every outbound host
    - Clean extension point for WHOIS/43 fallback (Sprint 2)

    Metadata flags (consumed by main.py seed logic for ToolModule row).
    """

    has_settings: bool = False
    has_status: bool = False

    # ── Definition ───────────────────────────────────────────────────────

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="whois",
            display_name_key="tools.whois.name",
            description_key="tools.whois.description",
            category=ToolCategory.NETWORK,
            version="1.0.0",
            backend=True,
            parameters=[
                ToolParameter(
                    name="target",
                    type="string",
                    label_key="tools.whois.param_target_label",
                    description_key="tools.whois.param_target_desc",
                    required=True,
                    constraints={"max_length": 255},
                ),
                ToolParameter(
                    name="server",
                    type="string",
                    label_key="tools.whois.param_server_label",
                    description_key="tools.whois.param_server_desc",
                    required=False,
                    constraints={"max_length": 255},
                ),
            ],
        )

    # ── Validation ───────────────────────────────────────────────────────

    def validate_params(self, params: dict[str, Any]) -> dict[str, Any]:
        target = (params.get("target") or "").strip()
        if not target:
            raise ValueError("Target is required")
        if len(target) > 255:
            raise ValueError("Target exceeds 255 characters")

        server = (params.get("server") or "").strip() or None
        if server and len(server) > 255:
            raise ValueError("Server exceeds 255 characters")

        # Determine if target is an IP address
        is_ip = False
        try:
            ip_address(target)
            is_ip = True
        except ValueError:
            pass

        return {
            "target": target,
            "server": server,
            "is_ip": is_ip,
        }

    # ── Execute ──────────────────────────────────────────────────────────

    async def execute(self, params: dict[str, Any], context: ExecutionContext) -> ToolResult:
        """Execute a WHOIS lookup for *target*.

        Phase 0: SSRF validation of target + optional server.
        Phase 1: RDAP bootstrap + authoritative query.
        On failure: return appropriate error for Sprint 2 WHOIS fallback hook.
        """
        try:
            validated = self.validate_params(params)
        except ValueError as exc:
            return ToolResult(success=False, error=str(exc))

        start = time.monotonic()

        try:
            result = await asyncio.wait_for(
                self._execute_inner(validated),
                timeout=settings.WHOIS_EXECUTION_DEADLINE,
            )
        except TimeoutError:
            duration_ms = (time.monotonic() - start) * 1000
            logger.warning(
                "WHOIS execution deadline exceeded for target=%s",
                validated["target"],
            )
            return ToolResult(
                success=False,
                error="errors.whois_connection_failed",
                duration_ms=duration_ms,
            )

        # Ensure duration_ms is set
        if result.duration_ms == 0.0:
            result.duration_ms = (time.monotonic() - start) * 1000

        return result

    async def _execute_inner(self, validated: dict[str, Any]) -> ToolResult:
        """Core execution logic (wrapped by the 60s deadline in execute())."""
        target: str = validated["target"]
        server: str | None = validated["server"]
        is_ip: bool = validated["is_ip"]

        # ── Phase 0: SSRF validation ──────────────────────────────────

        # Validate target through shared SSRF filter
        resolved_target_ip, block_error = await filter_target(target)
        if block_error:
            return ToolResult(success=False, error=block_error)

        # If a custom server is provided, validate it too
        if server:
            _, server_block_error = await filter_target(server)
            if server_block_error:
                return ToolResult(success=False, error=server_block_error)
            # Custom server → skip RDAP, go to WHOIS fallback (Sprint 2)
            return ToolResult(
                success=False,
                error="errors.whois_unsupported_tld",
            )

        # ── Phase 1: RDAP ─────────────────────────────────────────────

        rdap_result = await self._execute_rdap(target, is_ip)
        if rdap_result is not None:
            return rdap_result

        # ── Fallback extension point (Sprint 2: WHOIS/43) ─────────────
        # RDAP failed — Sprint 2 will insert WHOIS/43 fallback here.
        return ToolResult(
            success=False,
            error="errors.whois_connection_failed",
        )

    # ── RDAP client ─────────────────────────────────────────────────────

    async def _execute_rdap(self, target: str, is_ip: bool) -> ToolResult | None:
        """Execute the RDAP phase: IANA bootstrap → authoritative query.

        Returns:
            ToolResult on success or definitive failure,
            None if the caller should attempt the WHOIS fallback (Sprint 2).
        """
        # Determine TLD (for domains) or just use the target (for IPs)
        tld = target if is_ip else _extract_tld(target)

        # ── Step 1: IANA bootstrap ────────────────────────────────────
        # Early SSRF gate so a blocked bootstrap host maps to CONNECTION_FAILED
        # rather than UNSUPPORTED_TLD (which is what a None bootstrap means).
        # The authoritative resolve-then-connect pin happens inside _rdap_get.
        iana_host = "rdap.iana.org"
        _, block_error = await filter_target(iana_host)
        if block_error:
            logger.warning("RDAP IANA bootstrap blocked: %s", block_error)
            return ToolResult(
                success=False,
                error="errors.whois_connection_failed",
            )

        bootstrap_url = _build_rdap_url(IANA_RDAP_BOOTSTRAP, tld, is_ip)
        try:
            iana_data = await self._rdap_get(bootstrap_url)
        except Exception as exc:
            logger.warning("RDAP IANA bootstrap failed for %s: %s", target, exc)
            return None  # Sprint 2: WHOIS fallback

        if iana_data is None:
            # IANA returned 404 or had no RDAP entry for this TLD/IP
            logger.info("No RDAP entry at IANA for %s", tld)
            return ToolResult(
                success=False,
                error="errors.whois_unsupported_tld",
            )

        # Extract authoritative RDAP server URL
        auth_servers = _extract_iana_rdap_servers(iana_data)
        if not auth_servers:
            logger.info("No RDAP servers in IANA bootstrap for %s", tld)
            return ToolResult(
                success=False,
                error="errors.whois_unsupported_tld",
            )

        # ── Step 2: Authoritative RDAP query ──────────────────────────
        # Try each authoritative server in order
        last_error: str | None = None
        for auth_url in auth_servers:
            parsed = urlparse(auth_url)
            auth_host = parsed.hostname
            if not auth_host:
                continue

            # SSRF: early gate on the authoritative server hostname. The
            # resolve-then-connect pin (and per-redirect re-validation) is
            # enforced inside _rdap_get for every hop.
            _, auth_block_error = await filter_target(auth_host)
            if auth_block_error:
                logger.warning(
                    "RDAP authoritative server %s blocked: %s",
                    auth_host,
                    auth_block_error,
                )
                last_error = auth_block_error
                continue

            query_url = _build_rdap_url(auth_url, target, is_ip)
            try:
                rdap_data = await self._rdap_get(query_url)
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 404:
                    # Domain not found at authoritative server
                    return ToolResult(
                        success=False,
                        error="tools.whois.not_found",
                        data={"domain": target, "protocol": "rdap"},
                    )
                last_error = "errors.whois_connection_failed"
                continue
            except Exception as exc:
                logger.warning(
                    "RDAP authoritative query failed for %s at %s: %s",
                    target,
                    auth_host,
                    exc,
                )
                last_error = "errors.whois_connection_failed"
                continue

            if rdap_data is None:
                last_error = "errors.whois_connection_failed"
                continue

            # Success — parse and return
            result_data = _parse_rdap_response(rdap_data, target)
            return ToolResult(success=True, data=result_data)

        # All authoritative servers failed
        if last_error:
            return ToolResult(success=False, error=last_error)
        return None  # Sprint 2: WHOIS fallback

    # ── RDAP HTTP request with redirect validation ──────────────────────

    async def _rdap_get(
        self,
        url: str,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> dict[str, Any] | None:
        """Perform an RDAP HTTP GET with SSRF-safe, IP-pinned redirect handling.

        Security model (ADR-018 §B.4/§B.5):

        - **Every** hop (the initial request and each redirect) is independently
          SSRF-validated through ``filter_target()`` **and** IP-pinned via
          ``_pin_resolution()`` immediately before the connection. This closes
          the DNS-rebinding/TOCTOU gap on redirect targets — a redirect host is
          never connected to on a freshly (and possibly attacker-controlled)
          resolved IP.
        - Only ``https`` URLs are followed; a hostless or non-HTTPS hop is
          refused (no plaintext downgrade, no ``file://``/``gopher://``…).
        - Redirects are never auto-followed (``follow_redirects=False``); max
          ``MAX_RDAP_REDIRECTS`` hops, with loop detection.
        - The response body is streamed and capped at
          ``settings.WHOIS_MAX_RESPONSE_BYTES`` to bound memory against a hostile
          or compromised RDAP server.
        - Timeouts from settings: connect=WHOIS_RDAP_CONNECT_TIMEOUT,
          read=WHOIS_RDAP_READ_TIMEOUT.

        ``transport`` is an optional injection point for tests.

        Returns parsed JSON dict, or None on non-JSON / oversize / blocked or
        non-HTTPS redirect. Raises ``httpx.HTTPStatusError`` on 404 (caller maps
        it to ``not_found``) and on other non-2xx statuses (caller retries the
        next authoritative server).
        """
        seen_urls: set[str] = set()
        current_url = url

        timeout = httpx.Timeout(
            connect=settings.WHOIS_RDAP_CONNECT_TIMEOUT,
            read=settings.WHOIS_RDAP_READ_TIMEOUT,
            write=10.0,
            pool=5.0,
        )

        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=False,
            verify=True,
            transport=transport,
            headers={"Accept": "application/rdap+json, application/json"},
        ) as client:
            for _ in range(MAX_RDAP_REDIRECTS + 1):  # +1 for the initial request
                if current_url in seen_urls:
                    logger.warning("RDAP redirect loop detected: %s", current_url)
                    return None
                seen_urls.add(current_url)

                # ── Per-hop SSRF validation + IP pin ──────────────────
                parsed = urlparse(current_url)
                hop_host = parsed.hostname
                if parsed.scheme != "https" or not hop_host:
                    logger.warning(
                        "RDAP refused non-HTTPS or hostless URL: %s", current_url
                    )
                    return None

                pinned_ip, block_error = await filter_target(hop_host)
                if block_error:
                    logger.warning("RDAP hop %s blocked (SSRF)", hop_host)
                    return None

                async with _pin_resolution(hop_host, pinned_ip):
                    response = await self._stream_hop(client, current_url)

                status = response.status_code

                # Handle redirects — validated + pinned on the next iteration.
                if status in (301, 302, 303, 307, 308):
                    location = response.headers.get("Location", "")
                    if not location:
                        return None
                    # Resolve relative redirects against the current URL so the
                    # scheme/host checks above see an absolute target.
                    current_url = str(httpx.URL(current_url).join(location))
                    continue

                # 404 → domain not found (raise so caller can distinguish from
                # connection failures)
                if status == 404:
                    raise httpx.HTTPStatusError(
                        "Not Found",
                        request=response.request,
                        response=response,
                    )

                # 200 → success
                if status == 200:
                    return self._decode_body(response, current_url)

                # Other status codes → failure
                logger.warning(
                    "RDAP unexpected status %d from %s",
                    status,
                    current_url,
                )
                # Raise to trigger retry on next auth server
                response.raise_for_status()

        # Exceeded max redirects
        logger.warning("RDAP exceeded max redirects (%d)", MAX_RDAP_REDIRECTS)
        return None

    async def _stream_hop(
        self, client: httpx.AsyncClient, url: str
    ) -> httpx.Response:
        """GET *url*, reading the body under the size cap.

        The body is streamed and accumulated up to ``WHOIS_MAX_RESPONSE_BYTES``;
        once the cap is exceeded the read stops and the (truncated) content is
        attached so the caller's JSON decode fails cleanly rather than buffering
        an unbounded body. Headers/status are always available.
        """
        cap = settings.WHOIS_MAX_RESPONSE_BYTES
        async with client.stream("GET", url) as response:
            if response.status_code in (301, 302, 303, 307, 308, 404):
                # No body needed for redirects; 404 is signalled via status.
                return response
            body = bytearray()
            async for chunk in response.aiter_bytes():
                body.extend(chunk)
                if len(body) > cap:
                    logger.warning(
                        "RDAP response exceeded %d-byte cap from %s", cap, url
                    )
                    break
            response._content = bytes(body)
            return response

    @staticmethod
    def _decode_body(response: httpx.Response, url: str) -> dict[str, Any] | None:
        """Decode a capped RDAP body as JSON, or None if invalid/oversize."""
        if len(response.content) > settings.WHOIS_MAX_RESPONSE_BYTES:
            return None
        try:
            return json.loads(response.content)
        except (json.JSONDecodeError, UnicodeDecodeError):
            logger.warning("RDAP response is not valid JSON from %s", url)
            return None

    # ── Result schema ───────────────────────────────────────────────────

    def get_result_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "protocol": {"type": "string", "enum": ["rdap", "whois"]},
                "domain": {"type": "string"},
                "status": {"type": "array", "items": {"type": "string"}},
                "registrar": {"type": ["string", "null"]},
                "whois_server": {"type": ["string", "null"]},
                "name_servers": {"type": "array", "items": {"type": "string"}},
                "creation_date": {"type": ["string", "null"]},
                "expiration_date": {"type": ["string", "null"]},
                "updated_date": {"type": ["string", "null"]},
                "registrant": {"type": ["object", "null"]},
                "admin_contact": {"type": ["object", "null"]},
                "tech_contact": {"type": ["object", "null"]},
                "raw_text": {"type": ["string", "null"]},
                "disclaimer": {"type": ["string", "null"]},
            },
        }


# ── IANA bootstrap helpers ───────────────────────────────────────────────────


def _extract_iana_rdap_servers(data: dict[str, Any]) -> list[str]:
    """Extract authoritative RDAP server URLs from an IANA bootstrap response.

    IANA bootstrap responses contain a ``services`` array. Each service entry
    is a list of ``[tld_list, url_list]`` where the first element describes
    the covered TLDs/IP ranges and the second lists the RDAP server URLs.
    """
    servers: list[str] = []
    for service in data.get("services", []):
        if not isinstance(service, list) or len(service) < 2:
            continue
        # service[0] is the TLD/IP list, service[1] is the server URL(s)
        urls = service[1]
        if isinstance(urls, list):
            servers.extend(str(u) for u in urls)
    return servers

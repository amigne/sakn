"""Integration tests for the WHOIS API endpoint.

Uses the TestClient with mocked HTTP transports. No real network calls.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.constants.roles import ROLE_ADMINISTRATOR, ROLE_AUTHENTICATED, ROLE_VISITOR
from app.models.tool_module import RoleToolPermission, ToolModule

# ── Helpers ──────────────────────────────────────────────────────────────────


async def _seed_whois_tool(db) -> str:
    """Create a ToolModule row for whois and return its ID. Idempotent."""
    row = await db.execute(
        select(ToolModule).where(ToolModule.name == "whois")
    )
    existing = row.scalar_one_or_none()
    if existing is not None:
        return existing.id

    module = ToolModule(
        name="whois",
        display_name_key="tools.whois.name",
        description_key="tools.whois.description",
        enabled=True,
        version="1.0.0",
    )
    db.add(module)
    await db.flush()
    return module.id


async def _seed_whois_permissions(db, tool_id: str) -> None:
    """Create RoleToolPermission rows for all roles. Idempotent."""
    for role in [ROLE_VISITOR, ROLE_AUTHENTICATED, ROLE_ADMINISTRATOR]:
        row = await db.execute(
            select(RoleToolPermission).where(
                RoleToolPermission.role == role,
                RoleToolPermission.tool_id == tool_id,
            )
        )
        if row.scalar_one_or_none() is None:
            db.add(RoleToolPermission(role=role, tool_id=tool_id, allowed=True))
    await db.flush()


# ── Tool listing and seed ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_whois_listing_and_seed(client: AsyncClient):
    """AC-WHOIS-001/002/003: WHOIS is listed and seeded correctly."""
    from app.database import async_session_factory

    # Seed the tool module and permissions
    async with async_session_factory() as db:
        tool_id = await _seed_whois_tool(db)
        await _seed_whois_permissions(db, tool_id)
        await db.commit()

    # AC-WHOIS-001: GET /tools includes whois
    response = await client.get("/api/v1/tools")
    assert response.status_code == 200
    data = response.json()
    tools = {t["name"]: t for t in data.get("tools", [])}
    assert "whois" in tools, f"whois not in tools list: {list(tools.keys())}"

    whois = tools["whois"]
    assert whois["category"] == "network"
    assert whois["backend"] is True
    assert whois["version"] == "1.0.0"

    params = {p["name"]: p for p in whois.get("parameters", [])}
    assert params["target"]["required"] is True
    assert params["target"]["constraints"]["max_length"] == 255
    assert params["server"]["required"] is False

    # AC-WHOIS-002: ToolModule row exists
    async with async_session_factory() as db:
        row = await db.execute(
            select(ToolModule).where(ToolModule.name == "whois")
        )
        module = row.scalar_one_or_none()
        assert module is not None
        assert module.enabled is True

    # AC-WHOIS-003: RoleToolPermission rows exist
    async with async_session_factory() as db:
        tool_row = await db.execute(
            select(ToolModule.id).where(ToolModule.name == "whois")
        )
        tid = tool_row.scalar_one_or_none()
        for role in [ROLE_VISITOR, ROLE_AUTHENTICATED, ROLE_ADMINISTRATOR]:
            perm_row = await db.execute(
                select(RoleToolPermission).where(
                    RoleToolPermission.role == role,
                    RoleToolPermission.tool_id == tid,
                )
            )
            perm = perm_row.scalar_one_or_none()
            assert perm is not None, f"Missing permission for {role}"
            assert perm.allowed is True


# ── Tool execution (combined to avoid rate limit accumulation) ───────────────


@pytest.mark.asyncio
async def test_whois_execute_rdap_success(client: AsyncClient):
    """AC-WHOIS-020: RDAP query succeeds with structured data."""
    from app.database import async_session_factory

    async with async_session_factory() as db:
        tool_id = await _seed_whois_tool(db)
        await _seed_whois_permissions(db, tool_id)
        await db.commit()

    # Get the tool instance from the registry to mock its _rdap_get method

    # Build a mock tool and temporarily replace it in the registry
    async def mock_filter(target: str) -> tuple[str, str | None]:
        return "1.2.3.4", None

    # The RDAP JSON that the mock should return
    iana_json = {
        "services": [[["com"], ["https://rdap.verisign.com/com/v1/"]]]
    }
    rdap_json = {
        "ldhName": "EXAMPLE.COM",
        "status": ["client delete prohibited"],
        "entities": [
            {
                "roles": ["registrar"],
                "vcardArray": [
                    "vcard",
                    [["fn", {}, "text", "Example Registrar, Inc."]],
                ],
            }
        ],
        "nameservers": [
            {"ldhName": "NS1.EXAMPLE.COM"},
            {"ldhName": "NS2.EXAMPLE.COM"},
        ],
        "events": [
            {"eventAction": "registration", "eventDate": "1995-08-14T04:00:00Z"},
            {"eventAction": "expiration", "eventDate": "2027-08-13T04:00:00Z"},
        ],
        "notices": [
            {"title": "Terms of Service", "description": ["Test disclaimer."]}
        ],
    }

    # Patch the httpx.AsyncClient constructor to return a mock. _rdap_get streams
    # the body via client.stream(...) + aiter_bytes(), so the mock mirrors that.
    import json as _json

    class MockResponse:
        def __init__(self, status_code, json_data):
            self.status_code = status_code
            self._json_data = json_data
            self.content = _json.dumps(json_data).encode()
            self.headers = {}
            self.request = MagicMock()

        async def aiter_bytes(self):
            yield self.content

        def json(self):
            return self._json_data

        def raise_for_status(self):
            if self.status_code >= 400:
                import httpx
                raise httpx.HTTPStatusError(
                    f"HTTP {self.status_code}",
                    request=MagicMock(),
                    response=self,
                )

    class MockStream:
        def __init__(self, response):
            self._response = response

        async def __aenter__(self):
            return self._response

        async def __aexit__(self, *args):
            pass

    class MockClient:
        """Mock httpx.AsyncClient that works as an async context manager."""

        def __init__(self, **kwargs):
            self._call_count = 0

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        def stream(self, method, url, **kwargs):
            self._call_count += 1
            data = iana_json if "iana" in str(url) else rdap_json
            return MockStream(MockResponse(200, data))

    import httpx

    with patch(
        "app.tools.whois_lookup.filter_target", mock_filter
    ), patch.object(
        httpx, "AsyncClient", MockClient
    ):
        response = await client.post(
            "/api/v1/tools/whois/execute",
            json={"target": "example.com"},
        )

    assert response.status_code == 200
    data = response.json()
    result = data["result"]
    assert result["success"] is True, f"Expected success, got: {result}"
    assert result["data"]["protocol"] == "rdap"
    assert result["data"]["domain"] == "EXAMPLE.COM"
    assert result["data"]["registrar"] == "Example Registrar, Inc."
    assert "duration_ms" in result


@pytest.mark.asyncio
async def test_whois_execute_errors(client: AsyncClient):
    """AC-WHOIS-009/010/050: Validation and SSRF error handling."""
    from app.database import async_session_factory

    async with async_session_factory() as db:
        tool_id = await _seed_whois_tool(db)
        await _seed_whois_permissions(db, tool_id)
        await db.commit()

    from app.redis.rate_limit_store import RateLimitResult

    async def mock_check_limit(*args, **kwargs):
        return RateLimitResult(
            allowed=True, soft_count=0, hard_count=0,
            soft_limit=200, hard_limit=3600,
            soft_window_s=3600, hard_window_s=3600,
            retry_after=0, limit_type="none",
        )

    with patch("app.middleware.rate_limit.check_tool_rate_limit", mock_check_limit):
        # AC-WHOIS-009: Missing target → tool returns success=False
        response = await client.post(
            "/api/v1/tools/whois/execute",
            json={},
        )
    assert response.status_code == 200
    data = response.json()
    assert data["result"]["success"] is False
    assert "Target is required" in data["result"]["error"]

    with patch("app.middleware.rate_limit.check_tool_rate_limit", mock_check_limit):
        # AC-WHOIS-010: Target too long → tool returns success=False
        long_target = "a" * 256 + ".com"
        response = await client.post(
            "/api/v1/tools/whois/execute",
            json={"target": long_target},
        )
    assert response.status_code == 200
    data = response.json()
    assert data["result"]["success"] is False

    with patch("app.middleware.rate_limit.check_tool_rate_limit", mock_check_limit):
        # AC-WHOIS-050: Private target SSRF blocked
        async def mock_blocked_filter(target: str) -> tuple[str, str | None]:
            return "", "errors.target_not_allowed"

        with patch("app.tools.whois_lookup.filter_target", mock_blocked_filter):
            response = await client.post(
                "/api/v1/tools/whois/execute",
                json={"target": "127.0.0.1"},
            )
    assert response.status_code == 200
    data = response.json()
    assert data["result"]["success"] is False
    assert data["result"]["error"] == "errors.target_not_allowed"


# ── Available for role ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_whois_available_for_role(client: AsyncClient):
    """WHOIS should be available for visitor role after seeding."""
    from app.database import async_session_factory

    async with async_session_factory() as db:
        tool_id = await _seed_whois_tool(db)
        await _seed_whois_permissions(db, tool_id)
        await db.commit()

    from app.redis.rate_limit_store import RateLimitResult

    async def mock_check_limit(*args, **kwargs):
        return RateLimitResult(
            allowed=True, soft_count=0, hard_count=0,
            soft_limit=200, hard_limit=3600,
            soft_window_s=3600, hard_window_s=3600,
            retry_after=0, limit_type="none",
        )

    with patch("app.middleware.rate_limit.check_tool_rate_limit", mock_check_limit):
        response = await client.get("/api/v1/tools/available-for/visitor")
    assert response.status_code == 200
    data = response.json()
    assert "whois" in data["tools"]


# ── No subprocess check ──────────────────────────────────────────────────────


def test_no_subprocess_in_whois():
    """AC-WHOIS-081: No subprocess usage in WHOIS tool."""
    import ast

    with open("app/tools/whois_lookup.py") as f:
        source = f.read()

    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name != "subprocess", "subprocess import found"
        elif isinstance(node, ast.ImportFrom):
            assert node.module != "subprocess", "subprocess import found"
            for alias in node.names:
                assert "subprocess" not in str(alias.name), "subprocess reference found"

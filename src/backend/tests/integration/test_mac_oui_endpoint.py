"""Integration tests for POST /api/v1/tools/mac_oui/execute."""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.roles import ROLE_VISITOR
from app.models.base import new_uuid7
from app.models.mac_oui import MacOui
from app.models.mac_oui_history import MacOuiHistory
from app.models.tool_module import RoleToolPermission, ToolModule
from app.redis.rate_limit_store import get_rate_limiter

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _clear_rate_limits():
    """Clear in-memory rate limit counters between tests."""
    get_rate_limiter().clear_for_tests()
    yield


@pytest_asyncio.fixture(autouse=True)
async def _cleanup_committed_data(_engine):
    """Clean up any committed data after each test.

    Because these integration tests call ``db_session.commit()`` to make
    seeded data visible to the endpoint's separate session, we must
    explicitly delete that data afterward so it doesn't pollute other tests.
    """
    from sqlalchemy.ext.asyncio import async_sessionmaker

    yield
    session_factory = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as db, db.begin():
        await db.execute(delete(MacOuiHistory.__table__))
        await db.execute(delete(MacOui.__table__))
        # Also delete the tool module row so other tests can create fresh ones
        await db.execute(
            delete(RoleToolPermission.__table__).where(
                RoleToolPermission.tool_id.in_(
                    select(ToolModule.id).where(ToolModule.name == "mac_oui")
                )
            )
        )
        await db.execute(
            delete(ToolModule.__table__).where(ToolModule.name == "mac_oui")
        )


# ---------------------------------------------------------------------------
# Idempotent seed helpers — use db_session, commit at end
# ---------------------------------------------------------------------------


async def _seed_tool(db: AsyncSession) -> ToolModule:
    """Ensure the mac_oui tool exists, enabled, with visitor permission."""
    row = await db.execute(
        select(ToolModule).where(ToolModule.name == "mac_oui")
    )
    tool = row.scalar_one_or_none()
    if tool is None:
        tool = ToolModule(
            id=new_uuid7(),
            name="mac_oui",
            display_name_key="tools.mac_oui.name",
            description_key="tools.mac_oui.description",
            enabled=True,
            version="1.0.0",
            has_settings=True,
            has_status=True,
        )
        db.add(tool)
        await db.flush()
    else:
        tool.enabled = True

    perm_row = await db.execute(
        select(RoleToolPermission).where(
            RoleToolPermission.role == ROLE_VISITOR,
            RoleToolPermission.tool_id == tool.id,
        )
    )
    perm = perm_row.scalar_one_or_none()
    if perm is None:
        db.add(RoleToolPermission(
            id=new_uuid7(), role=ROLE_VISITOR, tool_id=tool.id, allowed=True,
        ))
    else:
        perm.allowed = True
    await db.flush()
    return tool


async def _seed_mac_oui_data(db: AsyncSession) -> None:
    """Insert the standard MacOui test dataset (idempotent — clears first)."""
    # Clear any existing data from prior tests
    await db.execute(delete(MacOuiHistory.__table__))
    await db.execute(delete(MacOui.__table__))
    await db.flush()

    from tests.fixtures.mac_oui_seed import seed_mac_oui_test_data
    await seed_mac_oui_test_data(db)


# ---------------------------------------------------------------------------
# 200 OK cases
# ---------------------------------------------------------------------------


class TestValidRequests:
    async def test_post_valid_returns_200(self, client: AsyncClient, db_session: AsyncSession):
        """Covers AC-MAC-OUI-028 — valid JSON, all entries valid → 200 OK."""
        await _seed_tool(db_session)
        await _seed_mac_oui_data(db_session)
        await db_session.commit()

        response = await client.post(
            "/api/v1/tools/mac_oui/execute",
            json={"ouis": ["001122", "112233445566"]},
        )

        assert response.status_code == 200
        data = response.json()
        result = data["result"]
        assert result["success"] is True
        assert len(result["data"]["results"]) == 2
        assert result["data"]["rejected"] == []
        assert result["data"]["parse_stats"]["total_inputs"] == 2
        assert result["data"]["parse_stats"]["valid"] == 2
        assert result["data"]["parse_stats"]["rejected"] == 0
        assert result["data"]["parse_stats"]["unique"] == 2

    async def test_post_invalid_entry_returns_200_with_rejected(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Covers AC-MAC-OUI-029 — valid JSON, one invalid entry → 200 with rejected[]."""
        await _seed_tool(db_session)
        await _seed_mac_oui_data(db_session)
        await db_session.commit()

        response = await client.post(
            "/api/v1/tools/mac_oui/execute",
            json={"ouis": ["001122", "test"]},
        )

        assert response.status_code == 200
        data = response.json()
        result = data["result"]
        assert result["success"] is True
        assert len(result["data"]["results"]) == 1
        assert len(result["data"]["rejected"]) == 1
        assert result["data"]["rejected"][0]["index"] == 2
        assert result["data"]["rejected"][0]["reason"] == "non_hex_characters"

    async def test_post_empty_list_returns_200_empty(self, client: AsyncClient, db_session: AsyncSession):
        """Covers AC-MAC-OUI-035 — empty ouis list → 200 OK with empty results."""
        await _seed_tool(db_session)
        await db_session.commit()

        response = await client.post(
            "/api/v1/tools/mac_oui/execute",
            json={"ouis": []},
        )

        assert response.status_code == 200
        data = response.json()
        result = data["result"]
        assert result["success"] is True
        assert result["data"]["results"] == []
        assert result["data"]["rejected"] == []
        assert result["data"]["parse_stats"]["total_inputs"] == 0


# ---------------------------------------------------------------------------
# 422 cases
# ---------------------------------------------------------------------------


class Test422Errors:
    async def test_post_malformed_json_returns_422(self, client: AsyncClient, db_session: AsyncSession):
        """Covers AC-MAC-OUI-030 — malformed JSON body → 422."""
        await _seed_tool(db_session)
        await db_session.commit()

        response = await client.post(
            "/api/v1/tools/mac_oui/execute",
            content=b"not json",
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 422

    async def test_post_missing_ouis_field_returns_422(self, client: AsyncClient, db_session: AsyncSession):
        """Covers AC-MAC-OUI-031 — missing 'ouis' field → 422."""
        await _seed_tool(db_session)
        await db_session.commit()

        response = await client.post(
            "/api/v1/tools/mac_oui/execute",
            json={},
        )

        assert response.status_code == 422
        data = response.json()
        assert data["error"]["code"] == "VALIDATION_ERROR"

    async def test_post_ouis_not_array_returns_422(self, client: AsyncClient, db_session: AsyncSession):
        """Covers AC-MAC-OUI-032 — 'ouis' is not an array → 422."""
        await _seed_tool(db_session)
        await db_session.commit()

        response = await client.post(
            "/api/v1/tools/mac_oui/execute",
            json={"ouis": "001122"},
        )

        assert response.status_code == 422
        data = response.json()
        assert data["error"]["code"] == "VALIDATION_ERROR"

    async def test_post_ouis_contains_non_string_returns_422(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """'ouis' array contains non-string item → 422."""
        await _seed_tool(db_session)
        await db_session.commit()

        response = await client.post(
            "/api/v1/tools/mac_oui/execute",
            json={"ouis": ["001122", 12345]},
        )

        assert response.status_code == 422
        data = response.json()
        assert data["error"]["code"] == "VALIDATION_ERROR"

    async def test_post_batch_too_large_returns_422(self, client: AsyncClient, db_session: AsyncSession):
        """Covers AC-MAC-OUI-036 — batch exceeds max size → 422 with MAC_OUI_TOO_MANY_INPUTS."""
        await _seed_tool(db_session)
        await db_session.commit()

        large_batch = [f"{i:06X}" for i in range(2001)]
        response = await client.post(
            "/api/v1/tools/mac_oui/execute",
            json={"ouis": large_batch},
        )

        assert response.status_code == 422
        data = response.json()
        assert data["error"]["code"] == "MAC_OUI_TOO_MANY_INPUTS"
        assert data["error"]["message_key"] == "errors.mac_oui_too_many_inputs"
        # Covers #345 — details.max must be populated for i18n interpolation
        assert data["error"]["details"] == {"max": 2000}


# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------


class TestSecurity:
    async def test_post_xss_payload_sanitized_in_response(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Covers AC-MAC-OUI-037 — XSS payload → rejected.sample is harmless."""
        await _seed_tool(db_session)
        await db_session.commit()

        response = await client.post(
            "/api/v1/tools/mac_oui/execute",
            json={"ouis": ["<script>alert(1)</script>"]},
        )

        assert response.status_code == 200
        data = response.json()
        sample = data["result"]["data"]["rejected"][0]["sample"]
        for char in ("<", ">", "(", ")", ";", '"', "'"):
            assert char not in sample, f"Unsafe char '{char}' found in sample: {sample!r}"

    async def test_post_redos_payload_bounded(self, client: AsyncClient, db_session: AsyncSession):
        """Pathological payload of 50k chars → response < 1 s (no ReDoS)."""
        await _seed_tool(db_session)
        await db_session.commit()

        import time

        payload = "A" * 50000
        start = time.monotonic()
        response = await client.post(
            "/api/v1/tools/mac_oui/execute",
            json={"ouis": [payload]},
        )
        elapsed = time.monotonic() - start

        assert response.status_code == 200
        assert elapsed < 1.0, f"Response took {elapsed:.2f}s — possible ReDoS"


# ---------------------------------------------------------------------------
# Response structure
# ---------------------------------------------------------------------------


class TestResponseStructure:
    async def test_post_history_in_response(self, client: AsyncClient, db_session: AsyncSession):
        """Covers AC-MAC-OUI-063 — history always present, empty if no history."""
        await _seed_tool(db_session)
        await _seed_mac_oui_data(db_session)
        await db_session.commit()

        response = await client.post(
            "/api/v1/tools/mac_oui/execute",
            json={"ouis": ["001122", "AABBCC"]},
        )

        assert response.status_code == 200
        results = response.json()["result"]["data"]["results"]
        cisco = [r for r in results if r["input"] == "001122"][0]
        assert cisco["history"] == []
        vlancorp = [r for r in results if r["input"] == "AABBCC"][0]
        assert len(vlancorp["history"]) > 0
        assert "change_type" in vlancorp["history"][0]
        assert "detected_at" in vlancorp["history"][0]

    async def test_oui_display_in_response(self, client: AsyncClient, db_session: AsyncSession):
        """Response includes correctly formatted oui_display fields."""
        await _seed_tool(db_session)
        await _seed_mac_oui_data(db_session)
        await db_session.commit()

        response = await client.post(
            "/api/v1/tools/mac_oui/execute",
            json={"ouis": ["001122", "0011223", "8C1F64100"]},
        )

        assert response.status_code == 200
        results = response.json()["result"]["data"]["results"]
        displays = {r["oui_display"] for r in results}
        assert "00:11:22" in displays  # MA-L
        assert "00:11:22:3_" in displays  # MA-M fallback
        assert "8C:1F:64:10:0_" in displays  # MA-S

    async def test_parse_stats_structure(self, client: AsyncClient, db_session: AsyncSession):
        """Covers AC-MAC-OUI-059 — parse_stats structure is correct."""
        await _seed_tool(db_session)
        await _seed_mac_oui_data(db_session)
        await db_session.commit()

        response = await client.post(
            "/api/v1/tools/mac_oui/execute",
            json={"ouis": ["001122", "001122", "deadbeef"]},
        )

        assert response.status_code == 200
        stats = response.json()["result"]["data"]["parse_stats"]
        assert stats["total_inputs"] == 3
        assert stats["valid"] == 2
        assert stats["rejected"] == 1
        assert stats["unique"] == 1

    async def test_ambiguous_flag_in_response(self, client: AsyncClient, db_session: AsyncSession):
        """24-bit OUI with MA-M extensions → ambiguous_extends_ma_m=true."""
        await _seed_tool(db_session)
        await _seed_mac_oui_data(db_session)
        await db_session.commit()

        response = await client.post(
            "/api/v1/tools/mac_oui/execute",
            json={"ouis": ["8C1F64"]},
        )

        assert response.status_code == 200
        results = response.json()["result"]["data"]["results"]
        assert len(results) == 1
        assert results[0]["ambiguous_extends_ma_m"] is True


# ---------------------------------------------------------------------------
# RBAC
# ---------------------------------------------------------------------------


class TestRbac:
    async def test_post_unauthenticated_403_when_disabled(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """When visitor permission is revoked → 403."""
        # Seed tool with visitor permission DISABLED from the start
        tool = await _seed_tool(db_session)
        # Override: set visitor permission to False before committing
        perm_row = await db_session.execute(
            select(RoleToolPermission).where(
                RoleToolPermission.role == ROLE_VISITOR,
                RoleToolPermission.tool_id == tool.id,
            )
        )
        perm = perm_row.scalar_one()
        perm.allowed = False
        await db_session.commit()

        response = await client.post(
            "/api/v1/tools/mac_oui/execute",
            json={"ouis": ["001122"]},
        )

        assert response.status_code == 403

    async def test_post_tool_disabled_returns_403(self, client: AsyncClient, db_session: AsyncSession):
        """When tool is globally disabled → 403."""
        tool = await _seed_tool(db_session)
        # Disable the tool before committing
        tool.enabled = False
        await db_session.commit()

        response = await client.post(
            "/api/v1/tools/mac_oui/execute",
            json={"ouis": ["001122"]},
        )

        assert response.status_code == 403


class TestModuleDeployedAt:
    """#364 — execute response exposes module_deployed_at (earliest sync date)."""

    async def test_module_deployed_at_from_earliest_sync(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        from datetime import UTC, datetime

        from app.models.oui_sync_log import OuiSyncLog

        await _seed_tool(db_session)
        await _seed_mac_oui_data(db_session)

        await db_session.execute(delete(OuiSyncLog.__table__))
        first = datetime(2026, 1, 15, 3, 0, tzinfo=UTC)
        later = datetime(2026, 5, 20, 3, 0, tzinfo=UTC)
        for ts in (later, first):  # insert out of order on purpose
            db_session.add(
                OuiSyncLog(
                    id=new_uuid7(),
                    started_at=ts,
                    finished_at=ts,
                    triggered_by="scheduler",
                    status="success",
                    added=0,
                    changed=0,
                    confirmed=0,
                )
            )
        await db_session.commit()

        response = await client.post(
            "/api/v1/tools/mac_oui/execute",
            json={"ouis": ["001122"]},
        )

        assert response.status_code == 200
        assert response.json()["result"]["module_deployed_at"] == "2026-01-15"

    async def test_module_deployed_at_absent_without_sync(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        from app.models.oui_sync_log import OuiSyncLog

        await _seed_tool(db_session)
        await _seed_mac_oui_data(db_session)
        await db_session.execute(delete(OuiSyncLog.__table__))
        await db_session.commit()

        response = await client.post(
            "/api/v1/tools/mac_oui/execute",
            json={"ouis": ["001122"]},
        )

        assert response.status_code == 200
        assert "module_deployed_at" not in response.json()["result"]

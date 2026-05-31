"""Covers AC-MAC-OUI-050, 051, 052, 053, 081, 082, 083, 084, 087, 088."""

import pathlib
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import Delete, delete, event, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import Session

from app.models.mac_oui import MacOui
from app.models.mac_oui_history import MacOuiHistory
from app.models.preferences import GlobalSetting
from app.services.oui_sync_service import (
    FAILURE_COUNTER_KEYS,
    OuiSyncService,
    classify_change,
)

FIXTURES = pathlib.Path(__file__).parent.parent.parent / "fixtures" / "ieee"


def _read_fixture(name: str) -> str:
    return (FIXTURES / name).read_text()


async def _make_test_factory(_engine):
    return async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)


async def _seed_settings(session_factory, **kwargs):
    """Seed/upsert GlobalSetting rows into the test DB."""
    defaults = {
        "oui_sync_failures_ma_l": "0",
        "oui_sync_failures_ma_m": "0",
        "oui_sync_failures_ma_s": "0",
        "oui_sync_running": "0",
    }
    defaults.update(kwargs)
    async with session_factory() as session:
        async with session.begin():
            for key, value in defaults.items():
                row = await session.execute(select(GlobalSetting).where(GlobalSetting.key == key))
                existing = row.scalar_one_or_none()
                if existing:
                    existing.value = value
                else:
                    session.add(GlobalSetting(key=key, value=value))


async def _cleanup_oui_tables(session_factory):
    """Remove all MacOui and MacOuiHistory rows between tests."""
    async with session_factory() as session:
        async with session.begin():
            await session.execute(delete(MacOuiHistory))
            await session.execute(delete(MacOui))


# ── classify_change unit tests ────────────────────────────────────────────────


def test_classify_name_change():
    """Covers AC-MAC-OUI-050 — change_type='name_change'."""
    assert classify_change("Cisco", "Cisco LLC", "addr", "addr") == "name_change"


def test_classify_name_and_address_change_as_name_change():
    """Covers AC-MAC-OUI-051 — Aruba→HPE with different address → name_change."""
    assert (
        classify_change(
            "Aruba Networks", "Hewlett Packard Enterprise",
            "San Jose, CA", "Houston, TX",
        )
        == "name_change"
    )


def test_classify_address_only_change():
    """Covers AC-MAC-OUI-052 — change_type='address_change'."""
    assert (
        classify_change("Cisco", "Cisco", "Old Address", "New Address")
        == "address_change"
    )


def test_classify_revoked_keyword():
    """Covers AC-MAC-OUI-053 — keyword 'revoked' → change_type='revoked'."""
    assert classify_change("Cisco", "Cisco [revoked]", "a", "a") == "revoked"
    assert classify_change("Cisco", "REVOKED ASSIGNMENT", "a", "a") == "revoked"


def test_classify_revoked_dashes():
    assert classify_change("Cisco", "----", "a", "a") == "revoked"


def test_classify_revoked_empty():
    assert classify_change("Cisco", "   ", "a", "a") == "revoked"


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_mock_response(status_code: int, text: str) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text
    return resp


def _make_mock_http(get_side_effect=None) -> MagicMock:
    http = MagicMock()
    http.get = AsyncMock(side_effect=get_side_effect)
    http.aclose = AsyncMock()
    return http


# ── OuiSyncService tests ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_sync_nominal_all_3_files_ok(_engine):
    """Covers AC-MAC-OUI-081 — 3 files OK, correct insertions."""
    factory = await _make_test_factory(_engine)
    await _cleanup_oui_tables(factory)
    await _seed_settings(factory)

    oui_content = _read_fixture("oui-sample.txt")
    mam_content = _read_fixture("mam-sample.txt")
    oui36_content = _read_fixture("oui36-sample.txt")

    async def mock_get(url, **kwargs):
        if "oui28" in url:
            return _make_mock_response(200, mam_content)
        elif "oui36" in url:
            return _make_mock_response(200, oui36_content)
        else:
            return _make_mock_response(200, oui_content)

    mock_http = _make_mock_http(get_side_effect=mock_get)
    service = OuiSyncService(db_session_factory=factory, http_client=mock_http)
    report = await service.sync_all()

    assert report.files_failed == []
    assert report.added == 17 + 5 + 5
    assert report.changed == 0
    assert report.confirmed == 0

    async with factory() as session:
        result = await session.execute(select(MacOui).where(MacOui.oui_type == "MA-L"))
        ma_l_rows = result.scalars().all()
        assert len(ma_l_rows) == 17


@pytest.mark.asyncio
async def test_sync_idempotent(_engine):
    """Sync twice without changes → added=0, changed=0, confirmed=N."""
    factory = await _make_test_factory(_engine)
    await _cleanup_oui_tables(factory)
    await _seed_settings(factory)

    content = _read_fixture("oui-sample.txt")

    async def mock_get(url, **kwargs):
        return _make_mock_response(200, content)

    s1 = OuiSyncService(db_session_factory=factory, http_client=_make_mock_http(get_side_effect=mock_get))
    report1 = await s1.sync_all()
    assert report1.added == 17
    assert report1.changed == 0

    s2 = OuiSyncService(db_session_factory=factory, http_client=_make_mock_http(get_side_effect=mock_get))
    report2 = await s2.sync_all()
    assert report2.added == 0
    assert report2.changed == 0
    assert report2.confirmed == 17


@pytest.mark.asyncio
async def test_name_change_detected(_engine):
    """Covers AC-MAC-OUI-050 — change detection creates history with name_change."""
    factory = await _make_test_factory(_engine)
    await _cleanup_oui_tables(factory)
    await _seed_settings(factory)

    content1 = "00-00-01   (hex)\t\tOld Corp Name"
    content2 = "00-00-01   (hex)\t\tNew Corp Name"

    async def mock_get1(url, **kwargs):
        return _make_mock_response(200, content1)

    s1 = OuiSyncService(db_session_factory=factory, http_client=_make_mock_http(get_side_effect=mock_get1))
    await s1.sync_all()

    async def mock_get2(url, **kwargs):
        return _make_mock_response(200, content2)

    s2 = OuiSyncService(db_session_factory=factory, http_client=_make_mock_http(get_side_effect=mock_get2))
    report = await s2.sync_all()

    assert report.changed == 1
    async with factory() as session:
        result = await session.execute(select(MacOuiHistory))
        history_rows = result.scalars().all()
        assert len(history_rows) == 1
        assert history_rows[0].change_type == "name_change"
        assert history_rows[0].previous_organization == "Old Corp Name"
        assert history_rows[0].new_organization == "New Corp Name"


@pytest.mark.asyncio
async def test_address_only_change(_engine):
    """Covers AC-MAC-OUI-052 — change_type='address_change'."""
    factory = await _make_test_factory(_engine)
    await _cleanup_oui_tables(factory)
    await _seed_settings(factory)

    content1 = "00-00-01   (hex)\t\tSame Corp\n\t\t\t\tOld Address"
    content2 = "00-00-01   (hex)\t\tSame Corp\n\t\t\t\tNew Address"

    async def mock_get1(url, **kwargs):
        return _make_mock_response(200, content1)

    s1 = OuiSyncService(db_session_factory=factory, http_client=_make_mock_http(get_side_effect=mock_get1))
    await s1.sync_all()

    async def mock_get2(url, **kwargs):
        return _make_mock_response(200, content2)

    s2 = OuiSyncService(db_session_factory=factory, http_client=_make_mock_http(get_side_effect=mock_get2))
    report = await s2.sync_all()

    assert report.changed == 1
    async with factory() as session:
        result = await session.execute(select(MacOuiHistory))
        history = result.scalars().all()
        assert len(history) == 1
        assert history[0].change_type == "address_change"


@pytest.mark.asyncio
async def test_revoked_detected(_engine):
    """Covers AC-MAC-OUI-053 — revoked keyword → change_type='revoked'."""
    factory = await _make_test_factory(_engine)
    await _cleanup_oui_tables(factory)
    await _seed_settings(factory)

    content1 = "00-00-01   (hex)\t\tActive Corp"
    content2 = "00-00-01   (hex)\t\t----"

    async def mock_get1(url, **kwargs):
        return _make_mock_response(200, content1)

    s1 = OuiSyncService(db_session_factory=factory, http_client=_make_mock_http(get_side_effect=mock_get1))
    await s1.sync_all()

    async def mock_get2(url, **kwargs):
        return _make_mock_response(200, content2)

    s2 = OuiSyncService(db_session_factory=factory, http_client=_make_mock_http(get_side_effect=mock_get2))
    report = await s2.sync_all()

    assert report.changed == 1
    async with factory() as session:
        result = await session.execute(select(MacOuiHistory))
        history = result.scalars().all()
        assert len(history) == 1
        assert history[0].change_type == "revoked"


@pytest.mark.asyncio
async def test_file_fails_others_continue(_engine):
    """Covers AC-MAC-OUI-082 — MA-L fails, MA-M and MA-S continue."""
    import httpx

    factory = await _make_test_factory(_engine)
    await _cleanup_oui_tables(factory)
    await _seed_settings(factory)

    mam_content = _read_fixture("mam-sample.txt")
    oui36_content = _read_fixture("oui36-sample.txt")

    async def mock_get(url, **kwargs):
        if "oui.txt" in url and "oui28" not in url and "oui36" not in url:
            raise httpx.TimeoutException("Timeout")
        elif "oui28" in url:
            return _make_mock_response(200, mam_content)
        elif "oui36" in url:
            return _make_mock_response(200, oui36_content)
        return _make_mock_response(404, "")

    mock_http = _make_mock_http(get_side_effect=mock_get)
    service = OuiSyncService(db_session_factory=factory, http_client=mock_http)
    report = await service.sync_all()

    assert "MA-L" in report.files_failed
    assert "MA-M" not in report.files_failed
    assert "MA-S" not in report.files_failed
    assert report.added == 5 + 5


@pytest.mark.asyncio
async def test_three_consecutive_failures_alert(_engine, caplog):
    """Covers AC-MAC-OUI-083 — log CRITICAL ALERT_OUI_SYNC_FAILED_3X."""
    import logging
    import httpx

    factory = await _make_test_factory(_engine)
    await _cleanup_oui_tables(factory)
    await _seed_settings(factory, oui_sync_failures_ma_l="2")

    async def mock_get(url, **kwargs):
        raise httpx.TimeoutException("Timeout")

    mock_http = _make_mock_http(get_side_effect=mock_get)
    caplog.set_level(logging.ERROR)
    service = OuiSyncService(db_session_factory=factory, http_client=mock_http)
    await service.sync_all()

    alert_logs = [r for r in caplog.records if "ALERT_OUI_SYNC_FAILED_3X" in r.message]
    assert len(alert_logs) >= 1


@pytest.mark.asyncio
async def test_absent_oui_preserved(_engine):
    """Covers AC-MAC-OUI-084 — OUI not in current file → row unchanged."""
    factory = await _make_test_factory(_engine)
    await _cleanup_oui_tables(factory)
    await _seed_settings(factory)

    content1 = "00-00-01   (hex)\t\tCorp A\n00-00-02   (hex)\t\tCorp B"
    content2 = "00-00-01   (hex)\t\tCorp A"

    async def mock_get1(url, **kwargs):
        return _make_mock_response(200, content1)

    s1 = OuiSyncService(db_session_factory=factory, http_client=_make_mock_http(get_side_effect=mock_get1))
    await s1.sync_all()

    async with factory() as session:
        result = await session.execute(
            select(MacOui).where(MacOui.oui == "000002", MacOui.oui_type == "MA-L")
        )
        row = result.scalar_one_or_none()
        assert row is not None
        old_last_seen = row.last_seen

    async def mock_get2(url, **kwargs):
        return _make_mock_response(200, content2)

    s2 = OuiSyncService(db_session_factory=factory, http_client=_make_mock_http(get_side_effect=mock_get2))
    report = await s2.sync_all()

    assert report.added == 0
    assert report.changed == 0
    async with factory() as session:
        result = await session.execute(
            select(MacOui).where(MacOui.oui == "000002", MacOui.oui_type == "MA-L")
        )
        row = result.scalar_one_or_none()
        assert row is not None
        assert row.last_seen == old_last_seen


@pytest.mark.asyncio
async def test_overlap_ma_l_ma_m_inserts_both(_engine):
    """Covers AC-MAC-OUI-088 — overlapping prefixes in MA-L and MA-M → 2 rows."""
    factory = await _make_test_factory(_engine)
    await _cleanup_oui_tables(factory)
    await _seed_settings(factory)

    content_ma_l = "8C-1F-64   (hex)\t\tIEEE Registration Authority\n\t\t\t\tSome address"
    content_ma_m = "8C-1F-64-0   (hex)\t\tAcme Corp"

    async def mock_get(url, **kwargs):
        if "oui28" in url:
            return _make_mock_response(200, content_ma_m)
        elif "oui36" in url:
            return _make_mock_response(200, "")
        else:
            return _make_mock_response(200, content_ma_l)

    mock_http = _make_mock_http(get_side_effect=mock_get)
    service = OuiSyncService(db_session_factory=factory, http_client=mock_http)
    await service.sync_all()

    async with factory() as session:
        result = await session.execute(
            select(MacOui).where(MacOui.oui.in_(["8C1F64", "8C1F640"]))
        )
        rows = result.scalars().all()
        assert len(rows) == 2
        types = {r.oui_type for r in rows}
        assert types == {"MA-L", "MA-M"}


@pytest.mark.asyncio
async def test_no_delete_ever(_engine):
    """Verify that no DELETE is emitted during any sync operation."""
    factory = await _make_test_factory(_engine)
    await _cleanup_oui_tables(factory)
    await _seed_settings(factory)

    content = "00-00-01   (hex)\t\tTest Corp"

    async def mock_get(url, **kwargs):
        return _make_mock_response(200, content)

    delete_calls = []

    @event.listens_for(Session, "do_orm_execute")
    def block_deletes(orm_execute_state):
        if isinstance(orm_execute_state.statement, Delete):
            delete_calls.append(orm_execute_state.statement)

    mock_http = _make_mock_http(get_side_effect=mock_get)
    service = OuiSyncService(db_session_factory=factory, http_client=mock_http)
    await service.sync_all()

    assert len(delete_calls) == 0, f"UNEXPECTED DELETE during sync: {delete_calls}"

"""Covers AC-MAC-OUI-050, 051, 052, 053, 081, 082, 083, 084, 087, 088."""

import logging
import pathlib
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from sqlalchemy import Delete, delete, event, select
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.orm import Session

from app.models.mac_oui import MacOui
from app.models.mac_oui_history import MacOuiHistory
from app.models.preferences import GlobalSetting
from app.services.oui_sync_service import OuiSyncService, classify_change

FIXTURES = pathlib.Path(__file__).parent.parent.parent / "fixtures" / "ieee"


def _read_fixture(name: str) -> str:
    return (FIXTURES / name).read_text()


async def _make_test_factory(_engine):
    from sqlalchemy.ext.asyncio import AsyncSession as _AsyncSession

    return async_sessionmaker(_engine, class_=_AsyncSession, expire_on_commit=False)


async def _seed_settings(session_factory, **kwargs):
    """Seed/upsert GlobalSetting rows into the test DB."""
    defaults = {
        "oui_sync_failures_ma_l": "0",
        "oui_sync_failures_ma_m": "0",
        "oui_sync_failures_ma_s": "0",
        "oui_sync_running": "0",
        "oui_sync_started_at": "",
    }
    defaults.update(kwargs)
    async with session_factory() as session, session.begin():
        for key, value in defaults.items():
            row = await session.execute(select(GlobalSetting).where(GlobalSetting.key == key))
            existing = row.scalar_one_or_none()
            if existing:
                existing.value = value
            else:
                session.add(GlobalSetting(key=key, value=value))


async def _cleanup_oui_tables(session_factory):
    """Remove all MacOui and MacOuiHistory rows between tests."""
    async with session_factory() as session, session.begin():
        await session.execute(delete(MacOuiHistory))
        await session.execute(delete(MacOui))


# ── classify_change unit tests ───────────────────────────────────────────────


def test_classify_name_change():
    """Covers AC-MAC-OUI-050 — change_type='name_change'."""
    assert classify_change("Cisco", "Cisco LLC") == "name_change"


def test_classify_name_and_address_change_as_name_change():
    """Covers AC-MAC-OUI-051 — Aruba→HPE with different address → name_change."""
    assert (
        classify_change("Aruba Networks", "Hewlett Packard Enterprise")
        == "name_change"
    )


def test_classify_address_only_change():
    """Covers AC-MAC-OUI-052 — change_type='address_change'."""
    assert (
        classify_change("Cisco", "Cisco")
        == "address_change"
    )


def test_classify_revoked_keyword():
    """Covers AC-MAC-OUI-053 — keyword 'revoked' → change_type='revoked'."""
    assert classify_change("Cisco", "Cisco [revoked]") == "revoked"
    assert classify_change("Cisco", "REVOKED ASSIGNMENT") == "revoked"


def test_classify_revoked_dashes():
    assert classify_change("Cisco", "----") == "revoked"


def test_classify_revoked_empty():
    assert classify_change("Cisco", "   ") == "revoked"


# ── Mock helpers for HTTP streaming ─────────────────────────────────────────


class _MockStreamResponse:
    """Simulates httpx streaming response for sync_one's http.stream()."""

    def __init__(
        self, status_code: int, content: bytes, headers: dict | None = None
    ):
        self.status_code = status_code
        self._content = content
        self.headers = MagicMock()
        _headers = headers or {}
        self.headers.get = MagicMock(
            side_effect=lambda k, default=None: _headers.get(k, default)
        )

    async def aiter_bytes(self, chunk_size: int = 64 * 1024):
        for i in range(0, len(self._content), chunk_size):
            yield self._content[i:i + chunk_size]

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


def _make_mock_http(stream_responses: dict | None = None):
    """Mock httpx.AsyncClient returning streaming responses from a dict keyed by URL."""
    http = MagicMock()

    if stream_responses:

        @asynccontextmanager
        async def mock_stream(method, url, **kwargs):
            resp = stream_responses.get(url)
            if resp is None:
                resp = _MockStreamResponse(404, b"")
            yield resp

        http.stream = mock_stream
    else:

        @asynccontextmanager
        async def mock_stream(method, url, **kwargs):
            yield _MockStreamResponse(200, b"")

        http.stream = mock_stream

    http.aclose = AsyncMock()
    return http


# ── OuiSyncService tests ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_sync_nominal_all_3_files_ok(_engine):
    """Covers AC-MAC-OUI-081 — 3 files OK, correct insertions."""
    factory = await _make_test_factory(_engine)
    await _cleanup_oui_tables(factory)
    await _seed_settings(factory)

    oui_content = _read_fixture("oui-sample.txt")
    mam_content = _read_fixture("mam-sample.txt")
    oui36_content = _read_fixture("oui36-sample.txt")

    responses = {
        "https://standards-oui.ieee.org/oui/oui.txt": _MockStreamResponse(200, oui_content.encode()),
        "https://standards-oui.ieee.org/oui28/mam.txt": _MockStreamResponse(200, mam_content.encode()),
        "https://standards-oui.ieee.org/oui36/oui36.txt": _MockStreamResponse(200, oui36_content.encode()),
    }
    mock_http = _make_mock_http(responses)

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
    responses = {url: _MockStreamResponse(200, content.encode()) for url in [
        "https://standards-oui.ieee.org/oui/oui.txt",
        "https://standards-oui.ieee.org/oui28/mam.txt",
        "https://standards-oui.ieee.org/oui36/oui36.txt",
    ]}

    s1 = OuiSyncService(db_session_factory=factory, http_client=_make_mock_http(responses))
    report1 = await s1.sync_all()
    assert report1.added == 17
    assert report1.changed == 0

    s2 = OuiSyncService(db_session_factory=factory, http_client=_make_mock_http(responses))
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
    url = "https://standards-oui.ieee.org/oui/oui.txt"

    mock1 = _make_mock_http({url: _MockStreamResponse(200, content1.encode())})
    s1 = OuiSyncService(db_session_factory=factory, http_client=mock1)
    await s1.sync_all()

    mock2 = _make_mock_http({url: _MockStreamResponse(200, content2.encode())})
    s2 = OuiSyncService(db_session_factory=factory, http_client=mock2)
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
    url = "https://standards-oui.ieee.org/oui/oui.txt"

    mock1 = _make_mock_http({url: _MockStreamResponse(200, content1.encode())})
    s1 = OuiSyncService(db_session_factory=factory, http_client=mock1)
    await s1.sync_all()

    mock2 = _make_mock_http({url: _MockStreamResponse(200, content2.encode())})
    s2 = OuiSyncService(db_session_factory=factory, http_client=mock2)
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
    url = "https://standards-oui.ieee.org/oui/oui.txt"

    mock1 = _make_mock_http({url: _MockStreamResponse(200, content1.encode())})
    s1 = OuiSyncService(db_session_factory=factory, http_client=mock1)
    await s1.sync_all()

    mock2 = _make_mock_http({url: _MockStreamResponse(200, content2.encode())})
    s2 = OuiSyncService(db_session_factory=factory, http_client=mock2)
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
    factory = await _make_test_factory(_engine)
    await _cleanup_oui_tables(factory)
    await _seed_settings(factory)

    mam_content = _read_fixture("mam-sample.txt")
    oui36_content = _read_fixture("oui36-sample.txt")

    ma_l_url = "https://standards-oui.ieee.org/oui/oui.txt"
    mam_url = "https://standards-oui.ieee.org/oui28/mam.txt"
    oui36_url = "https://standards-oui.ieee.org/oui36/oui36.txt"

    @asynccontextmanager
    async def mock_stream(method, url, **kwargs):
        if url == ma_l_url:
            raise httpx.TimeoutException("Timeout")
        elif url == mam_url:
            yield _MockStreamResponse(200, mam_content.encode())
        elif url == oui36_url:
            yield _MockStreamResponse(200, oui36_content.encode())
        else:
            yield _MockStreamResponse(404, b"")

    mock_http = MagicMock()
    mock_http.stream = mock_stream
    mock_http.aclose = AsyncMock()

    service = OuiSyncService(db_session_factory=factory, http_client=mock_http)
    report = await service.sync_all()

    assert "MA-L" in report.files_failed
    assert "MA-M" not in report.files_failed
    assert "MA-S" not in report.files_failed
    assert report.added == 5 + 5


@pytest.mark.asyncio
async def test_three_consecutive_failures_alert(_engine, caplog):
    """Covers AC-MAC-OUI-083 — log CRITICAL ALERT_OUI_SYNC_FAILED_3X."""
    factory = await _make_test_factory(_engine)
    await _cleanup_oui_tables(factory)
    await _seed_settings(factory, oui_sync_failures_ma_l="2")

    @asynccontextmanager
    async def mock_stream(method, url, **kwargs):
        raise httpx.TimeoutException("Timeout")
        yield  # unreachable, makes this an async generator for the contextmanager

    mock_http = MagicMock()
    mock_http.stream = mock_stream
    mock_http.aclose = AsyncMock()

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
    url = "https://standards-oui.ieee.org/oui/oui.txt"

    mock1 = _make_mock_http({url: _MockStreamResponse(200, content1.encode())})
    s1 = OuiSyncService(db_session_factory=factory, http_client=mock1)
    await s1.sync_all()

    async with factory() as session:
        result = await session.execute(
            select(MacOui).where(MacOui.oui == "000002", MacOui.oui_type == "MA-L")
        )
        row = result.scalar_one_or_none()
        assert row is not None
        old_last_seen = row.last_seen

    mock2 = _make_mock_http({url: _MockStreamResponse(200, content2.encode())})
    s2 = OuiSyncService(db_session_factory=factory, http_client=mock2)
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

    responses = {
        "https://standards-oui.ieee.org/oui/oui.txt": _MockStreamResponse(200, content_ma_l.encode()),
        "https://standards-oui.ieee.org/oui28/mam.txt": _MockStreamResponse(200, content_ma_m.encode()),
        "https://standards-oui.ieee.org/oui36/oui36.txt": _MockStreamResponse(200, b""),
    }
    mock_http = _make_mock_http(responses)
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
    url = "https://standards-oui.ieee.org/oui/oui.txt"

    delete_calls = []

    def block_deletes(orm_execute_state):
        if isinstance(orm_execute_state.statement, Delete):
            delete_calls.append(orm_execute_state.statement)

    event.listen(Session, "do_orm_execute", block_deletes)
    try:
        mock_http = _make_mock_http({url: _MockStreamResponse(200, content.encode())})
        service = OuiSyncService(db_session_factory=factory, http_client=mock_http)
        await service.sync_all()
        assert len(delete_calls) == 0, f"UNEXPECTED DELETE during sync: {delete_calls}"
    finally:
        event.remove(Session, "do_orm_execute", block_deletes)


# ── New tests for auditor fixes ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_stale_running_flag_ignored_after_ttl(_engine, monkeypatch):
    """H1: Stale running flag (started_at > TTL) → sync proceeds normally."""
    factory = await _make_test_factory(_engine)
    await _cleanup_oui_tables(factory)
    stale = (datetime.now(UTC) - timedelta(hours=2)).isoformat()
    await _seed_settings(factory, oui_sync_running="1", oui_sync_started_at=stale)

    content = "00-00-01   (hex)\t\tTest Corp"
    url = "https://standards-oui.ieee.org/oui/oui.txt"
    mock_http = _make_mock_http({url: _MockStreamResponse(200, content.encode())})

    service = OuiSyncService(db_session_factory=factory, http_client=mock_http)
    report = await service.sync_all()

    # Should proceed (not return early with "already running")
    assert report.added == 1


@pytest.mark.asyncio
async def test_download_exceeds_cap_failure(_engine, monkeypatch):
    """M4: Download exceeding OUI_MAX_DOWNLOAD_BYTES cap → file failed."""
    monkeypatch.setattr("app.services.oui_sync_service.OUI_MAX_DOWNLOAD_BYTES", 100)
    factory = await _make_test_factory(_engine)
    await _cleanup_oui_tables(factory)
    await _seed_settings(factory)

    # Mock response with Content-Length > cap
    url = "https://standards-oui.ieee.org/oui/oui.txt"
    mock_http = _make_mock_http(
        {url: _MockStreamResponse(200, b"x" * 200, headers={"content-length": "200"})}
    )

    service = OuiSyncService(db_session_factory=factory, http_client=mock_http)
    report = await service.sync_all()

    assert "MA-L" in report.files_failed
    assert report.added == 0


@pytest.mark.asyncio
async def test_redirect_treated_as_failure(_engine):
    """M5: HTTP 301 redirect → file failed (follow_redirects=False)."""
    factory = await _make_test_factory(_engine)
    await _cleanup_oui_tables(factory)
    await _seed_settings(factory)

    url = "https://standards-oui.ieee.org/oui/oui.txt"
    mock_http = _make_mock_http({url: _MockStreamResponse(301, b"")})

    service = OuiSyncService(db_session_factory=factory, http_client=mock_http)
    report = await service.sync_all()

    assert "MA-L" in report.files_failed


@pytest.mark.asyncio
async def test_owned_http_client_closed_after_sync(_engine, monkeypatch):
    """M7: when the service owns the http client (lazy creation), _cleanup closes it."""
    factory = await _make_test_factory(_engine)
    await _cleanup_oui_tables(factory)
    await _seed_settings(factory)

    created_clients: list[MagicMock] = []

    @asynccontextmanager
    async def failing_stream(method, url, **kw):
        # Trigger the except-branch in sync_one without doing real I/O
        raise httpx.TimeoutException("test")
        yield  # noqa: pragma: no cover — required marker for asynccontextmanager

    def tracking_client_factory(**kwargs):
        client = MagicMock()
        client.aclose = AsyncMock()
        client.stream = failing_stream
        created_clients.append(client)
        return client

    monkeypatch.setattr(
        "app.services.oui_sync_service.httpx.AsyncClient",
        tracking_client_factory,
    )

    # Service without pre-built client → _owns_http=True
    service = OuiSyncService(db_session_factory=factory)
    await service.sync_all()

    # One client created lazily, and it must have been closed
    assert len(created_clients) == 1
    created_clients[0].aclose.assert_awaited()


@pytest.mark.asyncio
async def test_pre_built_http_client_not_closed_by_service(_engine):
    """M7 inverse: when an external client is passed, the service must NOT close it
    (lifecycle is the caller's responsibility, e.g. scheduler job)."""
    factory = await _make_test_factory(_engine)
    await _cleanup_oui_tables(factory)
    await _seed_settings(factory)

    mock_http = _make_mock_http()
    service = OuiSyncService(db_session_factory=factory, http_client=mock_http)
    await service.sync_all()

    # Caller-owned client → service did not close it
    mock_http.aclose.assert_not_called()

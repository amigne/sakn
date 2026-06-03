"""Integration tests for oui_sync_log bounded retention (#374)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import new_uuid7
from app.models.oui_sync_log import OuiSyncLog
from app.services.oui_sync_log_cleanup_service import cleanup_old_oui_sync_logs

pytestmark = pytest.mark.asyncio


def _log(days_ago: float) -> OuiSyncLog:
    ts = datetime.now(UTC) - timedelta(days=days_ago)
    return OuiSyncLog(
        id=new_uuid7(),
        started_at=ts,
        finished_at=ts,
        triggered_by="scheduler",
        status="success",
        added=0,
        changed=0,
        confirmed=0,
    )


async def test_cleanup_deletes_old_keeps_recent(db_session: AsyncSession):
    """Rows older than retention are deleted; recent rows survive."""
    recent = _log(days_ago=10)
    old = _log(days_ago=400)
    db_session.add_all([recent, old])
    await db_session.flush()

    deleted = await cleanup_old_oui_sync_logs(db_session, retention_days=365)
    await db_session.flush()

    assert deleted == 1
    remaining_ids = set(
        (await db_session.execute(select(OuiSyncLog.id))).scalars().all()
    )
    assert recent.id in remaining_ids
    assert old.id not in remaining_ids


async def test_cleanup_always_preserves_latest_even_if_old(db_session: AsyncSession):
    """The single most recent row is kept even if it predates the cutoff."""
    # Wipe table so the latest row is deterministic within this test.
    from sqlalchemy import delete as sa_delete

    await db_session.execute(sa_delete(OuiSyncLog))
    older = _log(days_ago=800)
    newest = _log(days_ago=500)  # still older than 365d cutoff, but the latest one
    db_session.add_all([older, newest])
    await db_session.flush()

    deleted = await cleanup_old_oui_sync_logs(db_session, retention_days=365)
    await db_session.flush()

    assert deleted == 1
    count = (await db_session.execute(select(func.count(OuiSyncLog.id)))).scalar()
    assert count == 1
    surviving = (await db_session.execute(select(OuiSyncLog.id))).scalars().first()
    assert surviving == newest.id

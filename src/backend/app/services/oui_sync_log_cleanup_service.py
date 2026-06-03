"""Bounded retention for the oui_sync_log table (#374).

The OUI sync runs at least daily and appends one ``oui_sync_log`` row per run.
Without purging, the table grows unbounded. This service deletes rows older
than the configured retention while always preserving the most recent entry
so the admin status view never loses the "last run".
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.oui_sync_log import OuiSyncLog

RETENTION_SETTING_KEY = "module.mac_oui.OUI_SYNC_LOG_RETENTION_DAYS"
DEFAULT_RETENTION_DAYS = 365


async def cleanup_old_oui_sync_logs(db: AsyncSession, retention_days: int) -> int:
    """Delete oui_sync_log rows older than *retention_days*.

    The single most recent row is always kept, even if it predates the cutoff,
    so the status endpoint always has a "last run" to display. Returns the
    number of rows deleted. The caller is responsible for committing.
    """
    cutoff = datetime.now(UTC) - timedelta(days=retention_days)

    latest_id = select(OuiSyncLog.id).order_by(OuiSyncLog.started_at.desc()).limit(1).scalar_subquery()

    result = await db.execute(
        delete(OuiSyncLog).where(
            OuiSyncLog.started_at < cutoff,
            OuiSyncLog.id != latest_id,
        )
    )
    return result.rowcount or 0

"""Regression test for bug_001 — oui_sync_log.triggered_by allows 'cli'.

The sakn-cli sync-oui command records runs with triggered_by="cli". The
CHECK constraint must accept it (and still reject unknown values). The
constraint lives on the model so it is enforced in the test schema too.
"""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import new_uuid7, utcnow
from app.models.oui_sync_log import OuiSyncLog

pytestmark = pytest.mark.asyncio


def _log(triggered_by: str) -> OuiSyncLog:
    ts = utcnow()
    return OuiSyncLog(
        id=new_uuid7(),
        started_at=ts,
        finished_at=ts,
        triggered_by=triggered_by,
        status="success",
        added=0,
        changed=0,
        confirmed=0,
    )


@pytest.mark.parametrize("value", ["scheduler", "admin", "cli"])
async def test_triggered_by_accepts_known_values(db_session: AsyncSession, value: str):
    db_session.add(_log(value))
    await db_session.flush()  # no IntegrityError


async def test_triggered_by_rejects_unknown_value(db_session: AsyncSession):
    db_session.add(_log("bogus"))
    with pytest.raises(IntegrityError):
        await db_session.flush()

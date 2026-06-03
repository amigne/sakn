"""Regression test for #370 — audit_logs.admin_id is nullable.

ON DELETE SET NULL requires the column to be nullable; an audit entry with
an unknown actor must be writable with admin_id=NULL (not the old invalid
"unknown" sentinel that violated the users FK).
"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import new_uuid7
from app.models.log import AuditLog

pytestmark = pytest.mark.asyncio


async def test_audit_log_accepts_null_admin_id(db_session: AsyncSession):
    entry = AuditLog(
        id=new_uuid7(),
        admin_id=None,
        action="module.update",
        entity_type="tool_module",
        entity_id="some-id",
        old_value=None,
        new_value="{}",
    )
    db_session.add(entry)
    await db_session.flush()

    row = await db_session.execute(select(AuditLog).where(AuditLog.id == entry.id))
    stored = row.scalar_one()
    assert stored.admin_id is None

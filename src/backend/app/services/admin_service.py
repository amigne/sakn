"""Admin service — last admin protection, audit logging on admin actions."""

import json
import logging
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import AppError
from app.models import User, AuditLog
from app.models.base import new_uuid7

logger = logging.getLogger(__name__)


async def ensure_not_last_admin(db: AsyncSession, user_id: str) -> None:
    """Raise AppError if the given user is the last active administrator."""
    count = await db.execute(
        select(func.count(User.id)).where(
            User.role == "administrator",
            User.status.in_(["active", "pending"]),
            User.id != user_id,
        )
    )
    remaining = count.scalar() or 0
    if remaining == 0:
        raise AppError(
            422,
            "LAST_ADMIN",
            "errors.last_admin",
            "Cannot delete or demote the last administrator.",
        )


async def log_admin_action(
    db: AsyncSession,
    *,
    admin_id: str,
    action: str,
    entity_type: str,
    entity_id: str,
    old_value: dict[str, Any] | None = None,
    new_value: dict[str, Any] | None = None,
) -> AuditLog:
    entry = AuditLog(
        id=new_uuid7(),
        admin_id=admin_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        old_value=json.dumps(old_value) if old_value else None,
        new_value=json.dumps(new_value or {}),
    )
    db.add(entry)
    await db.flush()
    return entry

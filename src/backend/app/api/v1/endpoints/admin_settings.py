"""Admin global settings endpoints."""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.middleware.admin import require_admin
from app.models.preferences import GlobalSetting
from app.services.admin_service import log_admin_action

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/settings", tags=["admin-settings"])


@router.get("")
async def get_settings(
    request: Request,
    session: AsyncSession = Depends(get_session),
    _admin=Depends(require_admin),
) -> dict[str, Any]:
    rows = await session.execute(select(GlobalSetting))
    settings = {}
    for s in rows.scalars().all():
        settings[s.key] = s.value

    return {"settings": settings}


@router.put("")
async def update_settings(
    body: dict[str, Any],
    request: Request,
    session: AsyncSession = Depends(get_session),
    _admin=Depends(require_admin),
) -> dict[str, Any]:
    new_settings = body.get("settings", {})
    if not isinstance(new_settings, dict):
        raise HTTPException(status_code=400, detail="'settings' must be an object")

    admin_id = getattr(request.state, "user_id", None)
    updated = {}

    for key, value in new_settings.items():
        value_str = str(value)

        row = await session.execute(
            select(GlobalSetting).where(GlobalSetting.key == key)
        )
        existing = row.scalar_one_or_none()

        old_value = existing.value if existing else None

        if existing is not None:
            existing.value = value_str
        else:
            session.add(GlobalSetting(key=key, value=value_str))

        await log_admin_action(
            session,
            admin_id=admin_id or "unknown",
            action="settings.update",
            entity_type="global_setting",
            entity_id=key,
            old_value={"value": old_value} if old_value else None,
            new_value={"value": value_str},
        )
        updated[key] = value_str

    await session.commit()
    return {
        "settings": updated,
        "message_key": "admin.settings_updated",
        "message": "Settings updated.",
    }

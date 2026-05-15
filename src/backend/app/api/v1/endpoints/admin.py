"""Admin endpoints for module configuration.

Full admin guarding (middleware) arrives in Slice 7.
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select

from app.database import get_session
from app.models.preferences import GlobalSetting
from app.models import ToolModule

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])

MODULE_SETTING_PREFIX = "module."


async def _require_admin(request: Request) -> None:
    """Placeholder: proper admin middleware arrives in Slice 7."""
    role = getattr(request.state, "role", "visitor")
    if role != "administrator":
        raise HTTPException(status_code=403, detail="Admin access required")


@router.get("/modules/{module_name}/settings")
async def get_module_settings(
    module_name: str,
    request: Request,
    session=Depends(get_session),
) -> dict[str, Any]:
    await _require_admin(request)

    # Verify module exists
    row = await session.execute(
        select(ToolModule).where(ToolModule.name == module_name)
    )
    if row.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail=f"Module '{module_name}' not found")

    # Fetch all settings for this module
    prefix = f"{MODULE_SETTING_PREFIX}{module_name}."
    rows = await session.execute(
        select(GlobalSetting).where(GlobalSetting.key.like(f"{prefix}%"))
    )
    settings = {}
    for s in rows.scalars().all():
        key = s.key[len(prefix):]  # strip the module prefix
        settings[key] = s.value

    return {"module": module_name, "settings": settings}


@router.put("/modules/{module_name}/settings")
async def update_module_settings(
    module_name: str,
    body: dict[str, Any],
    request: Request,
    session=Depends(get_session),
) -> dict[str, Any]:
    await _require_admin(request)

    # Verify module exists
    row = await session.execute(
        select(ToolModule).where(ToolModule.name == module_name)
    )
    if row.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail=f"Module '{module_name}' not found")

    settings_to_update = body.get("settings", {})
    if not isinstance(settings_to_update, dict):
        raise HTTPException(status_code=400, detail="'settings' must be an object")

    prefix = f"{MODULE_SETTING_PREFIX}{module_name}."
    updated = {}

    for key, value in settings_to_update.items():
        full_key = f"{prefix}{key}"
        value_str = str(value).lower() if isinstance(value, bool) else str(value)

        row = await session.execute(
            select(GlobalSetting).where(GlobalSetting.key == full_key)
        )
        existing = row.scalar_one_or_none()

        if existing is not None:
            existing.value = value_str
        else:
            session.add(GlobalSetting(key=full_key, value=value_str))

        updated[key] = value

    await session.commit()
    return {"module": module_name, "settings": updated}

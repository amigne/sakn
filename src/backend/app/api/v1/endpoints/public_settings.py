"""Public settings endpoint — no authentication required.

Exposes non-sensitive global settings that are needed by public pages
(e.g., log retention days for the Privacy page).
"""

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models.preferences import GlobalSetting

router = APIRouter(prefix="/public-settings", tags=["public-settings"])

PUBLIC_SETTINGS = {"log_retention_days": "90"}


@router.get("")
async def get_public_settings(
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Return public-safe global settings. No auth required."""
    settings = dict(PUBLIC_SETTINGS)

    rows = await session.execute(
        select(GlobalSetting).where(GlobalSetting.key.in_(PUBLIC_SETTINGS.keys()))
    )
    for s in rows.scalars().all():
        settings[s.key] = s.value

    return {"settings": settings}

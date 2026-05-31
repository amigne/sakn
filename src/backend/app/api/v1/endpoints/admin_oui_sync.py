"""Admin endpoint for manual MAC OUI sync triggering."""

import asyncio
import logging
from datetime import UTC, datetime

import httpx
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import AppError
from app.config import settings
from app.database import async_session_factory, get_session
from app.middleware.admin import require_admin
from app.models.preferences import GlobalSetting
from app.services.oui_sync_service import OuiSyncService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/oui", tags=["admin-oui-sync"])

RUNNING_FLAG_KEY = "oui_sync_running"
_sync_lock = asyncio.Lock()


@router.post("/sync", status_code=202)
async def trigger_oui_sync(
    request: Request,
    session: AsyncSession = Depends(get_session),
    _admin=Depends(require_admin),
) -> dict:
    """Trigger a manual MAC OUI IEEE sync. Returns 202 with task_id, or 409 if already running."""
    from sqlalchemy import select

    # Check running flag
    row = await session.execute(
        select(GlobalSetting).where(GlobalSetting.key == RUNNING_FLAG_KEY)
    )
    setting = row.scalar_one_or_none()
    if setting and setting.value == "1":
        raise AppError(
            status_code=409,
            code="OUI_SYNC_ALREADY_RUNNING",
            message_key="errors.oui_sync_already_running",
            message="A MAC OUI sync is already in progress.",
        )

    import uuid

    task_id = str(uuid.uuid4())
    started_at = datetime.now(UTC)

    # Launch sync in background
    async def _run_sync():
        async with _sync_lock:
            http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(settings.OUI_DOWNLOAD_TIMEOUT_SECONDS),
                follow_redirects=True,
            )
            try:
                service = OuiSyncService(
                    db_session_factory=async_session_factory,
                    http_client=http_client,
                )
                await service.sync_all()
            except Exception:
                logger.exception("manual_oui_sync_failed", extra={"task_id": task_id})
            finally:
                await http_client.aclose()

    asyncio.create_task(_run_sync())

    return {
        "task_id": task_id,
        "started_at": started_at.isoformat(),
    }

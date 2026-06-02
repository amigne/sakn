"""Admin endpoint for manual MAC OUI sync triggering."""

import asyncio
import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import AppError
from app.database import async_session_factory, get_session
from app.middleware.admin import require_admin
from app.services.oui_sync_service import OuiSyncService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/oui", tags=["admin-oui-sync"])


def get_oui_sync_service() -> OuiSyncService:
    """Dependency: build an OuiSyncService that owns its HTTP client lifecycle.

    The service creates the httpx client lazily on first use and closes it in
    its `_cleanup` (called from `sync_all`'s finally). Pre-creating the client
    here would set `_owns_http=False` and leak it on every request.
    """
    return OuiSyncService(db_session_factory=async_session_factory)


@router.post("/sync", status_code=202)
async def trigger_oui_sync(
    request: Request,
    session: AsyncSession = Depends(get_session),
    _admin=Depends(require_admin),
    oui_service: OuiSyncService = Depends(get_oui_sync_service),
) -> dict:
    """Trigger a manual MAC OUI IEEE sync. Returns 202 with task_id, or 409 if already running."""
    # Atomic compare-and-set: acquire the lock before returning 202
    if not await oui_service.try_acquire_running_lock(session):
        raise AppError(
            status_code=409,
            code="OUI_SYNC_ALREADY_RUNNING",
            message_key="errors.oui_sync_already_running",
            message="A MAC OUI sync is already in progress.",
        )

    task_id = str(uuid.uuid4())
    started_at = datetime.now(UTC)

    # Launch sync in background (lock already held, skip re-check)
    async def _run_sync():
        try:
            await oui_service.sync_all(skip_lock_check=True)
        except Exception:
            logger.exception("manual_oui_sync_failed", extra={"task_id": task_id})

    asyncio.create_task(_run_sync())

    return {
        "task_id": task_id,
        "started_at": started_at.isoformat(),
    }

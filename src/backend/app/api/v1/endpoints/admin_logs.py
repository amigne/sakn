"""Admin log viewer endpoints."""

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.middleware.admin import require_admin
from app.services import log_service as log_svc

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/logs", tags=["admin-logs"])


@router.get("/tool-executions")
async def list_tool_executions(
    request: Request,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    tool: str | None = Query(None),
    user_id: str | None = Query(None),
    result: str | None = Query(None),
    from_date: str | None = Query(None),
    to_date: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
    _admin=Depends(require_admin),
) -> dict[str, Any]:
    from_dt = datetime.fromisoformat(from_date) if from_date else None
    to_dt = datetime.fromisoformat(to_date) if to_date else None

    entries, total = await log_svc.query_tool_execution_logs(
        session,
        offset=offset,
        limit=limit,
        tool=tool,
        user_id=user_id,
        result=result,
        from_date=from_dt,
        to_date=to_dt,
    )

    return {
        "tool_executions": entries,
        "pagination": {"offset": offset, "limit": limit, "total": total},
    }


@router.get("/security-events")
async def list_security_events(
    request: Request,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    event_type: str | None = Query(None),
    user_id: str | None = Query(None),
    from_date: str | None = Query(None),
    to_date: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
    _admin=Depends(require_admin),
) -> dict[str, Any]:
    from_dt = datetime.fromisoformat(from_date) if from_date else None
    to_dt = datetime.fromisoformat(to_date) if to_date else None

    entries, total = await log_svc.query_security_event_logs(
        session,
        offset=offset,
        limit=limit,
        event_type=event_type,
        user_id=user_id,
        from_date=from_dt,
        to_date=to_dt,
    )

    return {
        "security_events": entries,
        "pagination": {"offset": offset, "limit": limit, "total": total},
    }


@router.get("/audit")
async def list_audit_logs(
    request: Request,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    admin_id: str | None = Query(None),
    action: str | None = Query(None),
    entity_type: str | None = Query(None),
    from_date: str | None = Query(None),
    to_date: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
    _admin=Depends(require_admin),
) -> dict[str, Any]:
    from_dt = datetime.fromisoformat(from_date) if from_date else None
    to_dt = datetime.fromisoformat(to_date) if to_date else None

    entries, total = await log_svc.query_audit_logs(
        session,
        offset=offset,
        limit=limit,
        admin_id=admin_id,
        action=action,
        entity_type=entity_type,
        from_date=from_dt,
        to_date=to_dt,
    )

    return {
        "audit_logs": entries,
        "pagination": {"offset": offset, "limit": limit, "total": total},
    }

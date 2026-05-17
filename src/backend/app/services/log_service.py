"""Log service — create and query tool execution, security event, and audit logs."""

import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ToolExecutionLog, SecurityEventLog, AuditLog
from app.models.base import new_uuid7

logger = logging.getLogger(__name__)


# ── Creation ────────────────────────────────────────────────────────────────


async def create_tool_execution_log(
    db: AsyncSession,
    *,
    user_id: str | None,
    session_id: str | None,
    source_ip: str,
    tool_name: str,
    parameters: dict[str, Any],
    result: str,  # success / failure / partial
    duration_ms: int,
    error_message: str | None = None,
) -> ToolExecutionLog:
    entry = ToolExecutionLog(
        id=new_uuid7(),
        user_id=user_id,
        session_id=session_id,
        source_ip=source_ip,
        tool_name=tool_name,
        parameters=json.dumps(parameters),
        result=result,
        duration_ms=duration_ms,
        error_message=error_message,
    )
    db.add(entry)
    await db.flush()
    return entry


async def create_security_event_log(
    db: AsyncSession,
    *,
    event_type: str,
    source_ip: str,
    user_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> SecurityEventLog:
    entry = SecurityEventLog(
        id=new_uuid7(),
        event_type=event_type,
        source_ip=source_ip,
        user_id=user_id,
        details=json.dumps(details or {}),
    )
    db.add(entry)
    await db.flush()
    return entry


async def create_audit_log(
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
        new_value=json.dumps(new_value) if new_value else "{}",
    )
    db.add(entry)
    await db.flush()
    return entry


# ── Querying ────────────────────────────────────────────────────────────────


async def query_tool_execution_logs(
    db: AsyncSession,
    *,
    offset: int = 0,
    limit: int = 20,
    tool: str | None = None,
    user_id: str | None = None,
    result: str | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
) -> tuple[list[dict[str, Any]], int]:
    from app.models import User

    query = select(ToolExecutionLog, User.email).outerjoin(
        User, ToolExecutionLog.user_id == User.id
    )
    count_query = select(func.count(ToolExecutionLog.id))

    if tool:
        query = query.where(ToolExecutionLog.tool_name == tool)
        count_query = count_query.where(ToolExecutionLog.tool_name == tool)
    if user_id:
        query = query.where(ToolExecutionLog.user_id == user_id)
        count_query = count_query.where(ToolExecutionLog.user_id == user_id)
    if result:
        query = query.where(ToolExecutionLog.result == result)
        count_query = count_query.where(ToolExecutionLog.result == result)
    if from_date:
        query = query.where(ToolExecutionLog.created_at >= from_date)
        count_query = count_query.where(ToolExecutionLog.created_at >= from_date)
    if to_date:
        query = query.where(ToolExecutionLog.created_at <= to_date)
        count_query = count_query.where(ToolExecutionLog.created_at <= to_date)

    total_row = await db.execute(count_query)
    total = total_row.scalar() or 0

    rows = await db.execute(
        query.order_by(desc(ToolExecutionLog.created_at)).offset(offset).limit(limit)
    )
    results = rows.all()

    entries = []
    for e, user_email in results:
        d = _tool_execution_to_dict(e)
        d["user_email"] = user_email
        entries.append(d)

    return entries, total


async def query_security_event_logs(
    db: AsyncSession,
    *,
    offset: int = 0,
    limit: int = 20,
    event_type: str | None = None,
    user_id: str | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
) -> tuple[list[dict[str, Any]], int]:
    from app.models import User

    query = select(SecurityEventLog, User.email).outerjoin(
        User, SecurityEventLog.user_id == User.id
    )
    count_query = select(func.count(SecurityEventLog.id))

    if event_type:
        query = query.where(SecurityEventLog.event_type == event_type)
        count_query = count_query.where(SecurityEventLog.event_type == event_type)
    if user_id:
        query = query.where(SecurityEventLog.user_id == user_id)
        count_query = count_query.where(SecurityEventLog.user_id == user_id)
    if from_date:
        query = query.where(SecurityEventLog.created_at >= from_date)
        count_query = count_query.where(SecurityEventLog.created_at >= from_date)
    if to_date:
        query = query.where(SecurityEventLog.created_at <= to_date)
        count_query = count_query.where(SecurityEventLog.created_at <= to_date)

    total_row = await db.execute(count_query)
    total = total_row.scalar() or 0

    rows = await db.execute(
        query.order_by(desc(SecurityEventLog.created_at)).offset(offset).limit(limit)
    )
    results = rows.all()

    entries = []
    for e, user_email in results:
        d = _security_event_to_dict(e)
        d["user_email"] = user_email
        entries.append(d)

    return entries, total


async def query_audit_logs(
    db: AsyncSession,
    *,
    offset: int = 0,
    limit: int = 20,
    admin_id: str | None = None,
    action: str | None = None,
    entity_type: str | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
) -> tuple[list[dict[str, Any]], int]:
    from app.models import User

    query = select(AuditLog, User.email).outerjoin(
        User, AuditLog.admin_id == User.id
    )
    count_query = select(func.count(AuditLog.id))

    if admin_id:
        query = query.where(AuditLog.admin_id == admin_id)
        count_query = count_query.where(AuditLog.admin_id == admin_id)
    if action:
        query = query.where(AuditLog.action == action)
        count_query = count_query.where(AuditLog.action == action)
    if entity_type:
        query = query.where(AuditLog.entity_type == entity_type)
        count_query = count_query.where(AuditLog.entity_type == entity_type)
    if from_date:
        query = query.where(AuditLog.created_at >= from_date)
        count_query = count_query.where(AuditLog.created_at >= from_date)
    if to_date:
        query = query.where(AuditLog.created_at <= to_date)
        count_query = count_query.where(AuditLog.created_at <= to_date)

    total_row = await db.execute(count_query)
    total = total_row.scalar() or 0

    rows = await db.execute(
        query.order_by(desc(AuditLog.created_at)).offset(offset).limit(limit)
    )
    results = rows.all()

    entries = []
    for e, admin_email in results:
        d = _audit_log_to_dict(e)
        d["admin_email"] = admin_email
        entries.append(d)

    return entries, total


# ── Cleanup ─────────────────────────────────────────────────────────────────


async def cleanup_old_logs(db: AsyncSession, retention_days: int = 90) -> dict[str, int]:
    """Delete log entries older than retention_days. Returns counts per table."""
    from datetime import timedelta

    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=retention_days)

    deleted: dict[str, int] = {}

    for model, name in [
        (ToolExecutionLog, "tool_execution_logs"),
        (SecurityEventLog, "security_event_logs"),
        (AuditLog, "audit_logs"),
    ]:
        result = await db.execute(
            select(func.count(model.id)).where(model.created_at < cutoff)
        )
        count = result.scalar() or 0
        if count > 0:
            await db.execute(
                model.__table__.delete().where(model.created_at < cutoff)
            )
        deleted[name] = count

    await db.flush()
    return deleted


# ── Helpers ─────────────────────────────────────────────────────────────────


def _tool_execution_to_dict(e: ToolExecutionLog) -> dict[str, Any]:
    params = json.loads(e.parameters) if isinstance(e.parameters, str) else e.parameters
    # Extract a human-readable query string from parameters
    query = ""
    if isinstance(params, dict):
        query = params.get("target") or params.get("domain") or params.get("url") or ""
        if not query:
            query = ", ".join(f"{k}={v}" for k, v in params.items() if k not in ("record_types",))
    return {
        "id": e.id,
        "user_id": e.user_id,
        "session_id": e.session_id,
        "source_ip": e.source_ip,
        "tool_name": e.tool_name,
        "query": query,
        "parameters": params,
        "result": e.result,
        "duration_ms": e.duration_ms,
        "error_message": e.error_message,
        "created_at": e.created_at.isoformat() if e.created_at else None,
    }


def _security_event_to_dict(e: SecurityEventLog) -> dict[str, Any]:
    return {
        "id": e.id,
        "event_type": e.event_type,
        "source_ip": e.source_ip,
        "user_id": e.user_id,
        "details": json.loads(e.details) if isinstance(e.details, str) else e.details,
        "created_at": e.created_at.isoformat() if e.created_at else None,
    }


def _audit_log_to_dict(e: AuditLog) -> dict[str, Any]:
    return {
        "id": e.id,
        "admin_id": e.admin_id,
        "action": e.action,
        "entity_type": e.entity_type,
        "entity_id": e.entity_id,
        "old_value": json.loads(e.old_value) if isinstance(e.old_value, str) and e.old_value else e.old_value,
        "new_value": json.loads(e.new_value) if isinstance(e.new_value, str) else e.new_value,
        "created_at": e.created_at.isoformat() if e.created_at else None,
    }

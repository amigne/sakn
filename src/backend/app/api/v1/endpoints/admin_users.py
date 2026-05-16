"""Admin user management endpoints."""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.middleware.admin import require_admin
from app.models import User, Session
from app.services.admin_service import ensure_not_last_admin, log_admin_action

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/users", tags=["admin-users"])


@router.get("")
async def list_users(
    request: Request,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
    search: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
    _admin=Depends(require_admin),
) -> dict[str, Any]:
    query = select(User)
    count_q = select(func.count(User.id))

    if status:
        query = query.where(User.status == status)
        count_q = count_q.where(User.status == status)
    if search:
        query = query.where(User.email.ilike(f"%{search}%"))
        count_q = count_q.where(User.email.ilike(f"%{search}%"))

    total_row = await session.execute(count_q)
    total = total_row.scalar() or 0

    rows = await session.execute(
        query.order_by(User.created_at.desc()).offset(offset).limit(limit)
    )
    users = rows.scalars().all()

    return {
        "users": [
            {
                "id": u.id,
                "email": u.email,
                "first_name": u.first_name,
                "last_name": u.last_name,
                "role": u.role,
                "status": u.status,
                "email_verified": u.email_verified_at is not None,
                "failed_login_attempts": u.failed_login_attempts,
                "locked_until": u.locked_until.isoformat() if u.locked_until else None,
                "admin_notes": u.admin_notes,
                "created_at": u.created_at.isoformat() if u.created_at else None,
                "updated_at": u.updated_at.isoformat() if u.updated_at else None,
            }
            for u in users
        ],
        "pagination": {"offset": offset, "limit": limit, "total": total},
    }


@router.get("/{user_id}")
async def get_user(
    user_id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
    _admin=Depends(require_admin),
) -> dict[str, Any]:
    row = await session.execute(select(User).where(User.id == user_id))
    user = row.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    # Get active sessions
    sessions_row = await session.execute(
        select(Session).where(Session.user_id == user_id)
    )
    sessions_list = sessions_row.scalars().all()

    return {
        "user": {
            "id": user.id,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "role": user.role,
            "status": user.status,
            "email_verified": user.email_verified_at is not None,
            "failed_login_attempts": user.failed_login_attempts,
            "locked_until": user.locked_until.isoformat() if user.locked_until else None,
            "admin_notes": user.admin_notes,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "updated_at": user.updated_at.isoformat() if user.updated_at else None,
        },
        "sessions": [
            {
                "id": s.id,
                "ip_address": s.ip_address,
                "user_agent": s.user_agent,
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "last_activity_at": s.last_activity_at.isoformat() if s.last_activity_at else None,
            }
            for s in sessions_list
        ],
    }


async def _change_user_status(
    session: AsyncSession,
    user_id: str,
    new_status: str | None,
    action: str,
    request: Request,
) -> dict[str, Any]:
    row = await session.execute(select(User).where(User.id == user_id))
    user = row.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    admin_id = getattr(request.state, "user_id", None)
    old_status = user.status

    if new_status:
        user.status = new_status
    await session.flush()

    await log_admin_action(
        session,
        admin_id=admin_id or "unknown",
        action=action,
        entity_type="user",
        entity_id=user_id,
        old_value={"status": old_status},
        new_value={"status": new_status or old_status},
    )
    await session.commit()

    return {
        "user": {
            "id": user.id,
            "email": user.email,
            "role": user.role,
            "status": user.status,
        },
        "message_key": f"admin.user_{'blocked' if new_status == 'blocked' else 'unblocked' if new_status == 'active' else action}",
        "message": f"User {action}.",
    }


@router.put("/{user_id}/block")
async def block_user(
    user_id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
    _admin=Depends(require_admin),
) -> dict[str, Any]:
    return await _change_user_status(session, user_id, "blocked", "user.block", request)


@router.put("/{user_id}/unblock")
async def unblock_user(
    user_id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
    _admin=Depends(require_admin),
) -> dict[str, Any]:
    return await _change_user_status(session, user_id, "active", "user.unblock", request)


@router.put("/{user_id}/lock")
async def lock_user(
    user_id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
    _admin=Depends(require_admin),
) -> dict[str, Any]:
    return await _change_user_status(session, user_id, "locked", "user.lock", request)


@router.put("/{user_id}/unlock")
async def unlock_user(
    user_id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
    _admin=Depends(require_admin),
) -> dict[str, Any]:
    return await _change_user_status(session, user_id, "active", "user.unlock", request)


@router.put("/{user_id}/promote")
async def promote_user(
    user_id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
    _admin=Depends(require_admin),
) -> dict[str, Any]:
    row = await session.execute(select(User).where(User.id == user_id))
    user = row.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    old_role = user.role
    user.role = "administrator"
    admin_id = getattr(request.state, "user_id", None)
    await log_admin_action(
        session, admin_id=admin_id or "unknown",
        action="user.promote", entity_type="user", entity_id=user_id,
        old_value={"role": old_role}, new_value={"role": "administrator"},
    )
    await session.commit()
    return {"user": {"id": user.id, "email": user.email, "role": user.role}}


@router.put("/{user_id}/demote")
async def demote_user(
    user_id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
    _admin=Depends(require_admin),
) -> dict[str, Any]:
    row = await session.execute(select(User).where(User.id == user_id))
    user = row.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if user.role == "administrator":
        await ensure_not_last_admin(session, user_id)
    old_role = user.role
    user.role = "authenticated"
    admin_id = getattr(request.state, "user_id", None)
    await log_admin_action(
        session, admin_id=admin_id or "unknown",
        action="user.demote", entity_type="user", entity_id=user_id,
        old_value={"role": old_role}, new_value={"role": "authenticated"},
    )
    await session.commit()
    return {"user": {"id": user.id, "email": user.email, "role": user.role}}


@router.put("/{user_id}/verify-email")
async def admin_verify_email(
    user_id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
    _admin=Depends(require_admin),
) -> dict[str, Any]:
    from datetime import datetime, timezone

    row = await session.execute(select(User).where(User.id == user_id))
    user = row.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    user.email_verified_at = datetime.now(timezone.utc)
    if user.status == "pending":
        user.status = "active"
    admin_id = getattr(request.state, "user_id", None)
    await log_admin_action(
        session, admin_id=admin_id or "unknown",
        action="user.verify_email", entity_type="user", entity_id=user_id,
        new_value={"email_verified": True},
    )
    await session.commit()
    return {"user": {"id": user.id, "email": user.email, "email_verified": True}}


@router.get("/{user_id}/rate-limit-status")
async def get_user_rate_limit_status(
    user_id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
    _admin=Depends(require_admin),
) -> dict[str, Any]:
    """Return current rate limit counters for a user."""
    row = await session.execute(select(User).where(User.id == user_id))
    user = row.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    from app.services.rate_limit_service import get_effective_limits
    from app.redis.rate_limit_store import get_current_counts

    limits = await get_effective_limits(session, user.role, None)

    soft_limit = limits["soft_limit"]
    hard_limit = limits["hard_limit"]
    soft_window_s = 1
    hard_window_s = limits["window_seconds"]

    # Check user key + each active session key + each session IP
    soft_count = 0
    hard_count = 0
    s1, h1 = await get_current_counts("user", user_id, soft_window_s, hard_window_s)
    soft_count += s1
    hard_count += h1

    sessions_row_s = await session.execute(
        select(Session).where(Session.user_id == user_id)
    )
    seen_ips = set()
    for s in sessions_row_s.scalars().all():
        s2, h2 = await get_current_counts("session", s.id, soft_window_s, hard_window_s)
        soft_count += s2
        hard_count += h2
        if s.ip_address and s.ip_address not in seen_ips:
            seen_ips.add(s.ip_address)
            s3, h3 = await get_current_counts("ip", s.ip_address, soft_window_s, hard_window_s)
            soft_count += s3
            hard_count += h3

    return {
        "role": user.role,
        "soft_count": soft_count,
        "soft_limit": soft_limit,
        "soft_window_s": soft_window_s,
        "hard_count": hard_count,
        "hard_limit": hard_limit,
        "hard_window_s": hard_window_s,
    }


@router.put("/{user_id}/notes")
async def update_notes(
    user_id: str,
    body: dict[str, Any],
    request: Request,
    session: AsyncSession = Depends(get_session),
    _admin=Depends(require_admin),
) -> dict[str, Any]:
    row = await session.execute(select(User).where(User.id == user_id))
    user = row.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    notes = body.get("notes", "")
    old_notes = user.admin_notes
    user.admin_notes = notes

    admin_id = getattr(request.state, "user_id", None)
    await log_admin_action(
        session,
        admin_id=admin_id or "unknown",
        action="user.notes",
        entity_type="user",
        entity_id=user_id,
        old_value={"admin_notes": old_notes},
        new_value={"admin_notes": notes},
    )
    await session.commit()

    return {
        "user": {
            "id": user.id,
            "email": user.email,
            "admin_notes": user.admin_notes,
        },
        "message_key": "admin.notes_updated",
        "message": "Notes updated.",
    }


@router.delete("/{user_id}")
async def delete_user(
    user_id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
    _admin=Depends(require_admin),
) -> dict[str, Any]:
    row = await session.execute(select(User).where(User.id == user_id))
    user = row.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    # Last admin protection
    if user.role == "administrator":
        await ensure_not_last_admin(session, user_id)

    admin_id = getattr(request.state, "user_id", None)

    # Anonymize logs
    from app.models import ToolExecutionLog, SecurityEventLog

    await session.execute(
        ToolExecutionLog.__table__.update()
        .where(ToolExecutionLog.user_id == user_id)
        .values(user_id=None, session_id=None)
    )
    await session.execute(
        SecurityEventLog.__table__.update()
        .where(SecurityEventLog.user_id == user_id)
        .values(user_id=None)
    )

    # Delete user (cascades sessions, preferences, verifications, resets)
    await session.delete(user)

    await log_admin_action(
        session,
        admin_id=admin_id or "unknown",
        action="user.delete",
        entity_type="user",
        entity_id=user_id,
        new_value={"email": user.email, "role": user.role},
    )
    await session.commit()
    await session.flush()

    return {
        "message_key": "admin.user_deleted",
        "message": "User deleted.",
    }

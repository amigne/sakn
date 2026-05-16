"""Admin tool management endpoints."""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.middleware.admin import require_admin
from app.models import ToolModule, RoleToolPermission
from app.models.tool_module import RateLimitConfig
from app.services.admin_service import log_admin_action

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin-tools"])


@router.get("/tools")
async def list_tools(
    request: Request,
    session: AsyncSession = Depends(get_session),
    _admin=Depends(require_admin),
) -> dict[str, Any]:
    rows = await session.execute(
        select(ToolModule).order_by(ToolModule.name)
    )
    tools = rows.scalars().all()

    return {
        "tools": [
            {
                "id": t.id,
                "name": t.name,
                "display_name_key": t.display_name_key,
                "description_key": t.description_key,
                "enabled": t.enabled,
                "version": t.version,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in tools
        ]
    }


@router.put("/tools/{tool_name}")
async def update_tool(
    tool_name: str,
    body: dict[str, Any],
    request: Request,
    session: AsyncSession = Depends(get_session),
    _admin=Depends(require_admin),
) -> dict[str, Any]:
    row = await session.execute(
        select(ToolModule).where(ToolModule.name == tool_name)
    )
    tool = row.scalar_one_or_none()
    if tool is None:
        raise HTTPException(status_code=404, detail="Tool not found")

    old_enabled = tool.enabled
    if "enabled" in body:
        tool.enabled = bool(body["enabled"])

    admin_id = getattr(request.state, "user_id", None)
    await log_admin_action(
        session,
        admin_id=admin_id or "unknown",
        action="tool.update",
        entity_type="tool_module",
        entity_id=tool.id,
        old_value={"enabled": old_enabled},
        new_value={"enabled": tool.enabled},
    )
    await session.commit()

    return {
        "tool": {
            "id": tool.id,
            "name": tool.name,
            "enabled": tool.enabled,
        },
        "message_key": "admin.tool_updated",
        "message": "Tool updated.",
    }


# ── Role Permissions ────────────────────────────────────────────────────────


@router.get("/role-permissions")
async def list_role_permissions(
    request: Request,
    session: AsyncSession = Depends(get_session),
    _admin=Depends(require_admin),
) -> dict[str, Any]:
    rows = await session.execute(
        select(RoleToolPermission, ToolModule.name)
        .join(ToolModule, RoleToolPermission.tool_id == ToolModule.id)
        .order_by(RoleToolPermission.role, ToolModule.name)
    )
    permissions = []
    for perm, tool_name in rows.all():
        permissions.append({
            "id": perm.id,
            "role": perm.role,
            "tool_id": perm.tool_id,
            "tool_name": tool_name,
            "allowed": perm.allowed,
        })
    return {"permissions": permissions}


@router.put("/role-permissions")
async def update_role_permissions(
    body: dict[str, Any],
    request: Request,
    session: AsyncSession = Depends(get_session),
    _admin=Depends(require_admin),
) -> dict[str, Any]:
    permissions_data = body.get("permissions", [])
    if not isinstance(permissions_data, list):
        raise HTTPException(status_code=400, detail="'permissions' must be an array")

    admin_id = getattr(request.state, "user_id", None)
    updated = []

    for p in permissions_data:
        perm_id = p.get("id")
        allowed = p.get("allowed")
        if perm_id is None or allowed is None:
            continue

        row = await session.execute(
            select(RoleToolPermission).where(RoleToolPermission.id == perm_id)
        )
        perm = row.scalar_one_or_none()
        if perm is None:
            continue

        old_allowed = perm.allowed
        perm.allowed = bool(allowed)

        await log_admin_action(
            session,
            admin_id=admin_id or "unknown",
            action="permission.update",
            entity_type="role_tool_permission",
            entity_id=perm_id,
            old_value={"allowed": old_allowed, "role": perm.role, "tool_id": perm.tool_id},
            new_value={"allowed": perm.allowed, "role": perm.role, "tool_id": perm.tool_id},
        )
        updated.append({"id": perm_id, "role": perm.role, "tool_id": perm.tool_id, "allowed": perm.allowed})

    await session.commit()
    return {
        "permissions": updated,
        "message_key": "admin.permissions_updated",
        "message": "Permissions updated.",
    }

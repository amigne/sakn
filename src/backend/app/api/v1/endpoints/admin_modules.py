"""Admin module management endpoints.

Module enable/disable, DNS server presets CRUD + reorder.
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.middleware.admin import require_admin
from app.models import ToolModule
from app.models.tool_module import DnsServerPreset
from app.services.admin_service import log_admin_action

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/modules", tags=["admin-modules"])

MODULE_SETTING_PREFIX = "module."


# ── Module Enable/Disable ───────────────────────────────────────────────────


@router.get("")
async def list_modules(
    request: Request,
    session: AsyncSession = Depends(get_session),
    _admin=Depends(require_admin),
) -> dict[str, Any]:
    rows = await session.execute(
        select(ToolModule).order_by(ToolModule.name)
    )
    modules = rows.scalars().all()
    return {
        "modules": [
            {
                "id": m.id,
                "name": m.name,
                "display_name_key": m.display_name_key,
                "description_key": m.description_key,
                "enabled": m.enabled,
                "version": m.version,
            }
            for m in modules
        ]
    }


@router.put("/{module_name}")
async def update_module(
    module_name: str,
    body: dict[str, Any],
    request: Request,
    session: AsyncSession = Depends(get_session),
    _admin=Depends(require_admin),
) -> dict[str, Any]:
    row = await session.execute(
        select(ToolModule).where(ToolModule.name == module_name)
    )
    module = row.scalar_one_or_none()
    if module is None:
        raise HTTPException(status_code=404, detail=f"Module '{module_name}' not found")

    old_enabled = module.enabled
    if "enabled" in body:
        module.enabled = bool(body["enabled"])

    admin_id = getattr(request.state, "user_id", None)
    await log_admin_action(
        session,
        admin_id=admin_id or "unknown",
        action="module.update",
        entity_type="tool_module",
        entity_id=module.id,
        old_value={"enabled": old_enabled},
        new_value={"enabled": module.enabled},
    )
    await session.commit()

    return {
        "module": {"id": module.id, "name": module.name, "enabled": module.enabled},
        "message_key": "admin.module_updated",
        "message": f"Module '{module_name}' updated.",
    }


# ── Module Settings ──────────────────────────────────────────────────────────


@router.get("/{module_name}/settings")
async def get_module_settings(
    module_name: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
    _admin=Depends(require_admin),
) -> dict[str, Any]:
    row = await session.execute(
        select(ToolModule).where(ToolModule.name == module_name)
    )
    if row.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail=f"Module '{module_name}' not found")

    from app.models.preferences import GlobalSetting

    prefix = f"{MODULE_SETTING_PREFIX}{module_name}."
    rows = await session.execute(
        select(GlobalSetting).where(GlobalSetting.key.like(f"{prefix}%"))
    )
    settings = {}
    for s in rows.scalars().all():
        key = s.key[len(prefix):]
        settings[key] = s.value

    return {"module": module_name, "settings": settings}


@router.put("/{module_name}/settings")
async def update_module_settings(
    module_name: str,
    body: dict[str, Any],
    request: Request,
    session: AsyncSession = Depends(get_session),
    _admin=Depends(require_admin),
) -> dict[str, Any]:
    row = await session.execute(
        select(ToolModule).where(ToolModule.name == module_name)
    )
    if row.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail=f"Module '{module_name}' not found")

    settings_to_update = body.get("settings", {})
    if not isinstance(settings_to_update, dict):
        raise HTTPException(status_code=400, detail="'settings' must be an object")

    from app.models.preferences import GlobalSetting

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


# ── DNS Server Presets ──────────────────────────────────────────────────────


@router.get("/{tool_name}/dns-servers")
async def list_dns_servers(
    tool_name: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
    _admin=Depends(require_admin),
) -> dict[str, Any]:
    row = await session.execute(
        select(ToolModule).where(ToolModule.name == tool_name)
    )
    tool = row.scalar_one_or_none()
    if tool is None:
        raise HTTPException(status_code=404, detail=f"Module '{tool_name}' not found")

    rows = await session.execute(
        select(DnsServerPreset)
        .where(DnsServerPreset.tool_module_id == tool.id)
        .order_by(DnsServerPreset.sort_order)
    )
    presets = rows.scalars().all()
    return {
        "tool": tool_name,
        "presets": [
            {
                "id": p.id,
                "ip_address": p.ip_address,
                "description": p.description,
                "sort_order": p.sort_order,
            }
            for p in presets
        ],
    }


@router.post("/{tool_name}/dns-servers")
async def create_dns_server(
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
        raise HTTPException(status_code=404, detail=f"Module '{tool_name}' not found")

    ip_address = body.get("ip_address", "").strip()
    description = body.get("description", "").strip()

    if not ip_address:
        raise HTTPException(status_code=400, detail="ip_address is required")
    if not description:
        raise HTTPException(status_code=400, detail="description is required")

    count_row = await session.execute(
        select(DnsServerPreset).where(DnsServerPreset.tool_module_id == tool.id)
    )
    sort_order = len(count_row.scalars().all())

    preset = DnsServerPreset(
        tool_module_id=tool.id,
        ip_address=ip_address,
        description=description,
        sort_order=sort_order,
    )
    session.add(preset)
    await session.commit()
    await session.refresh(preset)

    return {
        "preset": {
            "id": preset.id,
            "ip_address": preset.ip_address,
            "description": preset.description,
            "sort_order": preset.sort_order,
        }
    }


@router.put("/{tool_name}/dns-servers/reorder")
async def reorder_dns_servers(
    tool_name: str,
    body: dict[str, Any],
    request: Request,
    session: AsyncSession = Depends(get_session),
    _admin=Depends(require_admin),
) -> dict[str, Any]:
    order = body.get("order", [])
    if not isinstance(order, list):
        raise HTTPException(status_code=400, detail="'order' must be a list of preset ids")

    for idx, preset_id in enumerate(order):
        row = await session.execute(
            select(DnsServerPreset).where(DnsServerPreset.id == preset_id)
        )
        preset = row.scalar_one_or_none()
        if preset is not None:
            preset.sort_order = idx

    await session.commit()
    return {"reordered": True}


@router.put("/{tool_name}/dns-servers/{preset_id}")
async def update_dns_server(
    tool_name: str,
    preset_id: str,
    body: dict[str, Any],
    request: Request,
    session: AsyncSession = Depends(get_session),
    _admin=Depends(require_admin),
) -> dict[str, Any]:
    row = await session.execute(
        select(DnsServerPreset).where(DnsServerPreset.id == preset_id)
    )
    preset = row.scalar_one_or_none()
    if preset is None:
        raise HTTPException(status_code=404, detail="Preset not found")

    ip_address = body.get("ip_address", "").strip()
    description = body.get("description", "").strip()

    if ip_address:
        preset.ip_address = ip_address
    if description:
        preset.description = description

    await session.commit()
    await session.refresh(preset)

    return {
        "preset": {
            "id": preset.id,
            "ip_address": preset.ip_address,
            "description": preset.description,
            "sort_order": preset.sort_order,
        }
    }


@router.delete("/{tool_name}/dns-servers/{preset_id}")
async def delete_dns_server(
    tool_name: str,
    preset_id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
    _admin=Depends(require_admin),
) -> dict[str, Any]:
    row = await session.execute(
        select(DnsServerPreset).where(DnsServerPreset.id == preset_id)
    )
    preset = row.scalar_one_or_none()
    if preset is None:
        raise HTTPException(status_code=404, detail="Preset not found")

    await session.delete(preset)
    await session.commit()

    return {"deleted": True}

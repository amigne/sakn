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


# ── DNS Server Presets ──────────────────────────────────────────────


@router.get("/modules/{tool_name}/dns-servers")
async def list_dns_servers(
    tool_name: str,
    request: Request,
    session=Depends(get_session),
) -> dict[str, Any]:
    await _require_admin(request)

    from app.models.tool_module import DnsServerPreset

    # Get tool module id
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


@router.post("/modules/{tool_name}/dns-servers")
async def create_dns_server(
    tool_name: str,
    body: dict[str, Any],
    request: Request,
    session=Depends(get_session),
) -> dict[str, Any]:
    await _require_admin(request)

    from app.models.tool_module import DnsServerPreset

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

    # Determine next sort_order
    count_row = await session.execute(
        select(DnsServerPreset)
        .where(DnsServerPreset.tool_module_id == tool.id)
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


@router.put("/modules/{tool_name}/dns-servers/reorder")
async def reorder_dns_servers(
    tool_name: str,
    body: dict[str, Any],
    request: Request,
    session=Depends(get_session),
) -> dict[str, Any]:
    await _require_admin(request)

    from app.models.tool_module import DnsServerPreset

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


@router.put("/modules/{tool_name}/dns-servers/{preset_id}")
async def update_dns_server(
    tool_name: str,
    preset_id: str,
    body: dict[str, Any],
    request: Request,
    session=Depends(get_session),
) -> dict[str, Any]:
    await _require_admin(request)

    from app.models.tool_module import DnsServerPreset

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


@router.delete("/modules/{tool_name}/dns-servers/{preset_id}")
async def delete_dns_server(
    tool_name: str,
    preset_id: str,
    request: Request,
    session=Depends(get_session),
) -> dict[str, Any]:
    await _require_admin(request)

    from app.models.tool_module import DnsServerPreset

    row = await session.execute(
        select(DnsServerPreset).where(DnsServerPreset.id == preset_id)
    )
    preset = row.scalar_one_or_none()
    if preset is None:
        raise HTTPException(status_code=404, detail="Preset not found")

    await session.delete(preset)
    await session.commit()

    return {"deleted": True}

"""Admin module management endpoints.

Module enable/disable, module status, settings, DNS server presets CRUD + reorder.
"""

import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_session
from app.middleware.admin import require_admin
from app.models import ToolModule
from app.models.oui_sync_log import OuiSyncLog
from app.models.tool_module import DnsServerPreset
from app.services.admin_service import log_admin_action

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/modules", tags=["admin-modules"])

MODULE_SETTING_PREFIX = "module."


def _safe_parse_files_failed(raw: str | None) -> list[str]:
    """Parse a JSON-encoded files_failed string, returning an empty list on errors."""
    if not raw:
        return []
    try:
        result = json.loads(raw)
        return result if isinstance(result, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


# ── Module Enable/Disable ───────────────────────────────────────────────────


@router.get("")
async def list_modules(
    request: Request,
    session: AsyncSession = Depends(get_session),
    _admin=Depends(require_admin),
) -> dict[str, Any]:
    from app.models.preferences import GlobalSetting

    rows = await session.execute(
        select(ToolModule).order_by(ToolModule.name)
    )
    modules = rows.scalars().all()

    # Build set of module names that have at least one GlobalSetting with the module prefix
    prefix = f"{MODULE_SETTING_PREFIX}"
    settings_rows = await session.execute(
        select(GlobalSetting.key).where(GlobalSetting.key.like(f"{prefix}%"))
    )
    settings_modules: set[str] = set()
    for (key,) in settings_rows.all():
        rest = key[len(prefix):]
        mod_name = rest.split(".")[0]
        settings_modules.add(mod_name)

    # Also include modules with DnsServerPreset entries (not stored in GlobalSetting)
    preset_rows = await session.execute(
        select(ToolModule.name)
        .join(DnsServerPreset, DnsServerPreset.tool_module_id == ToolModule.id)
        .distinct()
    )
    for (mod_name,) in preset_rows.all():
        settings_modules.add(mod_name)

    return {
        "modules": [
            {
                "id": m.id,
                "name": m.name,
                "display_name_key": m.display_name_key,
                "description_key": m.description_key,
                "enabled": m.enabled,
                "version": m.version,
                # N5 — use the DB column as the primary signal, but also fall
                # back to the computed value for modules created by seed logic
                # that sets has_settings after the tool_module row is inserted.
                "has_settings": m.has_settings or m.name in settings_modules,
                "has_status": m.has_status,
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

# M4 — Backend validation for known MAC OUI settings (defense in depth).
# Ranges match the frontend SETTING_DEFS in MacOuiSettingsModal.tsx.
_MAC_OUI_SETTING_VALIDATORS: dict[str, tuple[int, int]] = {
    "MAC_OUI_FRONTEND_INPUT_MAX_CHARS": (1000, 200000),
    "MAC_OUI_BACKEND_BATCH_MAX_SIZE": (100, 10000),
    "MAC_OUI_HISTORY_PAGE_SIZE": (5, 50),
    "OUI_SYNC_HOUR": (0, 23),
}


def _validate_mac_oui_setting(key: str, value: str) -> None:
    """Raise HTTPException(400) if *key* is a known MAC OUI setting but *value*
    is not a valid integer within its allowed range."""
    validator = _MAC_OUI_SETTING_VALIDATORS.get(key)
    if validator is None:
        return  # unknown key — allow (forward-compat)
    min_val, max_val = validator
    try:
        int_val = int(value)
    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Setting '{key}' must be an integer.",
        ) from exc
    if int_val < min_val or int_val > max_val:
        raise HTTPException(
            status_code=400,
            detail=f"Setting '{key}' must be between {min_val} and {max_val}.",
        )


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
    tool_mod = row.scalar_one_or_none()
    if tool_mod is None:
        raise HTTPException(status_code=404, detail=f"Module '{module_name}' not found")

    settings_to_update = body.get("settings", {})
    if not isinstance(settings_to_update, dict):
        raise HTTPException(status_code=400, detail="'settings' must be an object")

    from app.models.preferences import GlobalSetting

    prefix = f"{MODULE_SETTING_PREFIX}{module_name}."
    old_settings: dict[str, str] = {}
    updated: dict[str, str] = {}

    # Capture old values for audit (M3)
    if module_name == "mac_oui":
        old_rows = await session.execute(
            select(GlobalSetting).where(GlobalSetting.key.like(f"{prefix}%"))
        )
        for s in old_rows.scalars().all():
            old_settings[s.key[len(prefix):]] = s.value

    for key, value in settings_to_update.items():
        full_key = f"{prefix}{key}"
        value_str = str(value).lower() if isinstance(value, bool) else str(value)

        # M4 — validate value if this is a known MAC OUI setting
        if module_name == "mac_oui":
            _validate_mac_oui_setting(key, value_str)

        row = await session.execute(
            select(GlobalSetting).where(GlobalSetting.key == full_key)
        )
        existing = row.scalar_one_or_none()

        if existing is not None:
            existing.value = value_str
        else:
            session.add(GlobalSetting(key=full_key, value=value_str))

        updated[key] = value_str

    # M3 — audit log for settings changes
    admin_id = getattr(request.state, "user_id", None)
    await log_admin_action(
        session,
        admin_id=admin_id or "unknown",
        action="module.settings.update",
        entity_type="tool_module",
        entity_id=tool_mod.id,
        old_value=old_settings,
        new_value=updated,
    )

    await session.commit()

    # M2 — reschedule OUI sync job if OUI_SYNC_HOUR changed for mac_oui
    if module_name == "mac_oui" and "OUI_SYNC_HOUR" in updated:
        try:
            scheduler = request.app.state.scheduler
            new_hour = int(updated["OUI_SYNC_HOUR"])
            from apscheduler.triggers.cron import CronTrigger
            scheduler.reschedule_job(
                "oui_sync_daily",
                trigger=CronTrigger(hour=new_hour, minute=0, timezone="UTC"),
            )
            logger.info(
                "oui_sync_job_rescheduled",
                extra={"new_hour": new_hour},
            )
        except Exception:
            # Best-effort: rescheduling may fail in multi-worker setups
            # where the API worker is not the scheduler owner.
            logger.warning(
                "oui_sync_job_reschedule_failed",
                exc_info=True,
                extra={"setting_key": "OUI_SYNC_HOUR", "new_value": updated["OUI_SYNC_HOUR"]},
            )

    return {"module": module_name, "settings": updated}


# ── Module Status (generic, Sprint 5) ────────────────────────────────────────

OUI_SYNC_FAILURE_KEYS = {
    "MA-L": "oui_sync_failures_ma_l",
    "MA-M": "oui_sync_failures_ma_m",
    "MA-S": "oui_sync_failures_ma_s",
}


def _compute_next_scheduled_run(sync_hour: int) -> str:
    """Compute the next scheduled UTC run time at the given hour."""
    now = datetime.now(UTC)
    today_run = now.replace(hour=sync_hour, minute=0, second=0, microsecond=0)
    if now >= today_run:
        today_run += timedelta(days=1)
    return today_run.isoformat()


@router.get("/{tool_name}/status")
async def get_module_status(
    tool_name: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
    _admin=Depends(require_admin),
) -> Any:
    """Generic module status endpoint. Returns null if has_status=false."""
    from app.models.preferences import GlobalSetting

    row = await session.execute(
        select(ToolModule).where(ToolModule.name == tool_name)
    )
    tool_mod = row.scalar_one_or_none()
    if tool_mod is None:
        raise HTTPException(status_code=404, detail=f"Module '{tool_name}' not found")

    if not tool_mod.has_status:
        return None

    # --- Fetch last 30 sync log rows -------------------------------------------------
    log_rows = await session.execute(
        select(OuiSyncLog)
        .order_by(OuiSyncLog.started_at.desc())
        .limit(30)
    )
    logs = log_rows.scalars().all()

    # --- Fetch consecutive failure counters from GlobalSetting ------------------------
    failure_keys = list(OUI_SYNC_FAILURE_KEYS.values())
    failure_rows = await session.execute(
        select(GlobalSetting).where(GlobalSetting.key.in_(failure_keys))
    )
    failure_map: dict[str, int] = {}
    key_to_file = {v: k for k, v in OUI_SYNC_FAILURE_KEYS.items()}
    for s in failure_rows.scalars().all():
        file_name = key_to_file.get(s.key)
        if file_name:
            failure_map[file_name] = int(s.value) if s.value else 0

    consecutive_failures = {
        "MA-L": failure_map.get("MA-L", 0),
        "MA-M": failure_map.get("MA-M", 0),
        "MA-S": failure_map.get("MA-S", 0),
    }

    # --- Total records ----------------------------------------------------------------
    from sqlalchemy import func as sa_func

    from app.models.mac_oui import MacOui
    count_result = await session.execute(select(sa_func.count(MacOui.id)))
    total_records = count_result.scalar() or 0

    # --- Determine status -------------------------------------------------------------
    if not logs:
        derived_status = "idle"
    elif any(log.status == "running" for log in logs[:1]):
        derived_status = "running"
    elif any(v >= 3 for v in consecutive_failures.values()):
        derived_status = "alert"
    else:
        last_log = logs[0]
        if last_log.status == "failed":
            derived_status = "alert"
        elif last_log.files_failed:
            failed_files = _safe_parse_files_failed(last_log.files_failed)
            derived_status = "partial" if 1 <= len(failed_files) <= 2 else "success"
        else:
            derived_status = "success"

    # --- Last run details -------------------------------------------------------------
    last_run = None
    if logs:
        last = logs[0]
        last_run = {
            "started_at": last.started_at.isoformat(),
            "finished_at": last.finished_at.isoformat() if last.finished_at else None,
            "triggered_by": last.triggered_by,
            "added": last.added,
            "changed": last.changed,
            "confirmed": last.confirmed,
            "files_failed": _safe_parse_files_failed(last.files_failed),
        }

    # --- Next scheduled run -----------------------------------------------------------
    # Determine the effective sync hour: DB setting > env config
    sync_hour = settings.OUI_SYNC_HOUR
    try:
        setting_row = await session.execute(
            select(GlobalSetting).where(
                GlobalSetting.key == "module.mac_oui.OUI_SYNC_HOUR"
            )
        )
        db_hour = setting_row.scalar_one_or_none()
        if db_hour is not None:
            sync_hour = int(db_hour.value)
    except (ValueError, TypeError):
        pass

    next_scheduled_run = _compute_next_scheduled_run(sync_hour)

    # --- History (last 30) ------------------------------------------------------------
    history = []
    for log in logs:
        entry: dict[str, Any] = {
            "started_at": log.started_at.isoformat(),
            "finished_at": log.finished_at.isoformat() if log.finished_at else None,
            "triggered_by": log.triggered_by,
            "status": log.status,
            "added": log.added,
            "changed": log.changed,
            "confirmed": log.confirmed,
            "files_failed": _safe_parse_files_failed(log.files_failed),
            "error_message": log.error_message,
        }
        history.append(entry)

    return {
        "status": derived_status,
        "last_run": last_run,
        "next_scheduled_run": next_scheduled_run,
        "consecutive_failures": consecutive_failures,
        "total_records": total_records,
        "history": history,
    }


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

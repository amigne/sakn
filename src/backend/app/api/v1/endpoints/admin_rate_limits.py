"""Admin rate limit management endpoints.

Matrix validation: per-tool limits must be ≤ global limits for the same role.
0 = no limit. Changes take effect immediately.
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.middleware.admin import require_admin
from app.models import ToolModule
from app.models.tool_module import RateLimitConfig
from app.services.admin_service import log_admin_action

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin-rate-limits"])


@router.get("/rate-limits")
async def list_rate_limits(
    request: Request,
    session: AsyncSession = Depends(get_session),
    _admin=Depends(require_admin),
) -> dict[str, Any]:
    rows = await session.execute(
        select(RateLimitConfig).order_by(RateLimitConfig.role, RateLimitConfig.tool_id)
    )
    configs = rows.scalars().all()

    limits = []
    for c in configs:
        tool_name = None
        if c.tool_id:
            tool_row = await session.execute(
                select(ToolModule.name).where(ToolModule.id == c.tool_id)
            )
            tool_name = tool_row.scalar_one_or_none()

        limits.append({
            "id": c.id,
            "role": c.role,
            "tool_id": c.tool_id,
            "tool_name": tool_name,
            "soft_limit": c.soft_limit,
            "hard_limit": c.hard_limit,
            "window_seconds": c.window_seconds,
        })
    return {"rate_limits": limits}


@router.put("/rate-limits")
async def update_rate_limits(
    body: dict[str, Any],
    request: Request,
    session: AsyncSession = Depends(get_session),
    _admin=Depends(require_admin),
) -> dict[str, Any]:
    limits_data = body.get("rate_limits", [])
    if not isinstance(limits_data, list):
        raise HTTPException(status_code=400, detail="'rate_limits' must be an array")

    # Load existing configs for validation
    existing_rows = await session.execute(select(RateLimitConfig))
    existing_map: dict[tuple[str, str | None], RateLimitConfig] = {}
    for c in existing_rows.scalars().all():
        existing_map[(c.role, c.tool_id)] = c

    # Validate matrix: per-tool must be ≤ global for same role
    incoming: dict[tuple[str, str | None], dict] = {}
    for item in limits_data:
        role = item.get("role", "")
        tool_id = item.get("tool_id", None)
        if not role:
            continue
        incoming[(role, tool_id)] = item

    for (role, tool_id), item in incoming.items():
        # Per-tool: tool_id is not None
        if tool_id is not None and (role, None) in incoming:
            global_item = incoming[(role, None)]
            gs, gh = global_item.get("soft_limit", 0), global_item.get("hard_limit", 0)
            ps, ph = item.get("soft_limit", 0), item.get("hard_limit", 0)
            if gs > 0 and ps > gs:
                raise HTTPException(
                    status_code=422,
                    detail=f"Per-tool soft limit ({ps}) exceeds global ({gs}) for role {role}",
                )
            if gh > 0 and ph > gh:
                raise HTTPException(
                    status_code=422,
                    detail=f"Per-tool hard limit ({ph}) exceeds global ({gh}) for role {role}",
                )
        # Also check against existing global if not in this batch
        if tool_id is not None and (role, None) not in incoming:
            global_config = existing_map.get((role, None))
            if global_config:
                ps, ph = item.get("soft_limit", 0), item.get("hard_limit", 0)
                if global_config.soft_limit > 0 and ps > global_config.soft_limit:
                    raise HTTPException(
                        status_code=422,
                        detail=(
                            f"Per-tool soft limit ({ps}) exceeds "
                            f"global ({global_config.soft_limit}) for role {role}"
                        ),
                    )
                if global_config.hard_limit > 0 and ph > global_config.hard_limit:
                    raise HTTPException(
                        status_code=422,
                        detail=(
                            f"Per-tool hard limit ({ph}) exceeds "
                            f"global ({global_config.hard_limit}) for role {role}"
                        ),
                    )

    admin_id = getattr(request.state, "user_id", None)
    updated = []

    for item in limits_data:
        role = item.get("role", "")
        tool_id = item.get("tool_id", None)
        if not role:
            continue

        key = (role, tool_id)
        config = existing_map.get(key)
        old_values = {}

        if config:
            old_values = {
                "role": config.role,
                "tool_id": config.tool_id,
                "soft_limit": config.soft_limit,
                "hard_limit": config.hard_limit,
                "window_seconds": config.window_seconds,
            }
            config.soft_limit = item.get("soft_limit", config.soft_limit)
            config.hard_limit = item.get("hard_limit", config.hard_limit)
            config.window_seconds = item.get("window_seconds", config.window_seconds)
        else:
            config = RateLimitConfig(
                role=role,
                tool_id=tool_id,
                soft_limit=item.get("soft_limit", 0),
                hard_limit=item.get("hard_limit", 0),
                window_seconds=item.get("window_seconds", 60),
            )
            session.add(config)
            await session.flush()

        await log_admin_action(
            session,
            admin_id=admin_id or "unknown",
            action="rate_limit.update",
            entity_type="rate_limit_config",
            entity_id=config.id,
            old_value=old_values if old_values else None,
            new_value={
                "role": config.role,
                "tool_id": config.tool_id,
                "soft_limit": config.soft_limit,
                "hard_limit": config.hard_limit,
                "window_seconds": config.window_seconds,
            },
        )
        updated.append({
            "id": config.id,
            "role": config.role,
            "tool_id": config.tool_id,
            "soft_limit": config.soft_limit,
            "hard_limit": config.hard_limit,
            "window_seconds": config.window_seconds,
        })

    await session.commit()
    return {
        "rate_limits": updated,
        "message_key": "admin.rate_limits_updated",
        "message": "Rate limits updated.",
    }

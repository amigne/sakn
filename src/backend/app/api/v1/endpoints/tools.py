import json
import logging
import time
from typing import Any

from fastapi import APIRouter, Depends, Request, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.config import settings
from app.database import get_session, async_session_factory
from app.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tools", tags=["tools"])


def get_registry(request: Request) -> ToolRegistry:
    if not hasattr(request.app.state, "tool_registry"):
        from app.tools.ping import PingTool
        from app.tools.traceroute import TracerouteTool

        registry = ToolRegistry()
        registry.register(PingTool())
        registry.register(TracerouteTool())
        request.app.state.tool_registry = registry
    return request.app.state.tool_registry


@router.get("/available-for/{role}")
async def list_tools_for_role(
    role: str,
    session=Depends(get_session),
):
    """Public: list tools available to a given role (for the no-tools page)."""
    from app.models import ToolModule
    from app.models.tool_module import RoleToolPermission

    row = await session.execute(
        select(ToolModule).where(ToolModule.enabled == True)
    )
    enabled_tools = {t.name for t in row.scalars().all()}

    perm_row = await session.execute(
        select(RoleToolPermission, ToolModule.name)
        .join(ToolModule, RoleToolPermission.tool_id == ToolModule.id)
        .where(RoleToolPermission.role == role, RoleToolPermission.allowed == True)
    )
    allowed_tools = {tool_name for _, tool_name in perm_row.all()}

    available = sorted(enabled_tools & allowed_tools)
    return {"role": role, "tools": available}


@router.get("")
async def list_tools(
    request: Request,
    registry: ToolRegistry = Depends(get_registry),
    session=Depends(get_session),
):
    """List tools filtered by enabled status and role permissions."""
    from app.models import ToolModule
    from app.models.tool_module import RoleToolPermission

    role = getattr(request.state, "role", "visitor")

    # Load enabled tool names from DB
    row = await session.execute(
        select(ToolModule).where(ToolModule.enabled == True)
    )
    enabled_tools = {t.name for t in row.scalars().all()}

    # Load role permissions (which tools this role is allowed to use)
    perm_row = await session.execute(
        select(RoleToolPermission, ToolModule.name)
        .join(ToolModule, RoleToolPermission.tool_id == ToolModule.id)
        .where(RoleToolPermission.role == role, RoleToolPermission.allowed == True)
    )
    allowed_tools = {tool_name for _, tool_name in perm_row.all()}

    tools = []
    for tool in registry._tools.values():
        definition = tool.get_definition()
        if definition.name in enabled_tools and definition.name in allowed_tools:
            tools.append(tool.to_api_definition())

    return {"tools": tools}


@router.get("/{tool_name}/dns-servers")
async def list_tool_dns_servers(
    tool_name: str,
    session=Depends(get_session),
) -> dict[str, Any]:
    """Return DNS server presets for a tool (public endpoint)."""
    from app.models.tool_module import DnsServerPreset, RoleToolPermission
    from app.models import ToolModule

    row = await session.execute(
        select(ToolModule)
        .where(ToolModule.name == tool_name, ToolModule.enabled == True)
        .join(RoleToolPermission, RoleToolPermission.tool_id == ToolModule.id)
        .where(RoleToolPermission.role == "visitor", RoleToolPermission.allowed == True)
    )
    tool = row.scalar_one_or_none()
    if tool is None:
        return {"tool": tool_name, "servers": []}

    rows = await session.execute(
        select(DnsServerPreset)
        .where(DnsServerPreset.tool_module_id == tool.id)
        .order_by(DnsServerPreset.sort_order)
    )
    presets = rows.scalars().all()
    return {
        "tool": tool_name,
        "servers": [
            {"value": p.ip_address, "label": p.description}
            for p in presets
        ],
    }


def _get_ws_manager(app) -> "ConnectionManager":
    from app.websocket.manager import ConnectionManager

    if not hasattr(app.state, "ws_manager"):
        app.state.ws_manager = ConnectionManager()
    return app.state.ws_manager


def _read_session_from_ws(websocket: WebSocket) -> tuple[str, str | None]:
    """Read session token from WebSocket cookies (BaseHTTPMiddleware skips WS)."""
    from app.models.base import new_uuid7

    cookies = websocket.headers.get("cookie", "")
    # Parse session token from cookie header
    for part in cookies.split(";"):
        part = part.strip()
        if part.startswith("__Host-sakn_session=") or part.startswith("sakn_session="):
            return part.split("=", 1)[1], None
    return f"anon_{new_uuid7()}", None


def _is_allowed_origin(origin: str | None) -> bool:
    """Check Origin header against CORS_ORIGINS allowlist (CSWSH protection for WebSockets)."""
    if not origin:
        return True  # non-browser clients don't send Origin
    allowed = [o.strip() for o in settings.CORS_ORIGINS.split(",")]
    return origin in allowed


@router.websocket("/{tool_name}/stream")
async def tool_stream(websocket: WebSocket, tool_name: str):
    from app.websocket.handlers.ping_ws import handle_ping_stream
    from app.websocket.handlers.traceroute_ws import handle_traceroute_stream

    if tool_name not in ("ping", "traceroute"):
        await websocket.close(code=4004)
        return

    # CSWSH protection: validate Origin BEFORE any DB/Redis query
    origin = websocket.headers.get("origin")
    if not _is_allowed_origin(origin):
        logger.warning("WebSocket origin rejected: tool=%s origin=%s", tool_name, origin)
        await websocket.close(code=4003)
        return

    # Resolve session and check access BEFORE accepting
    session_token, _ = _read_session_from_ws(websocket)
    user_id = None
    role = "visitor"

    try:
        from app.database import async_session_factory, is_db_available
        from app.models.tool_module import RoleToolPermission
        from app.models import ToolModule, User
        from app.security.tokens import hash_token

        if is_db_available():
            async with async_session_factory() as db:
                # Check tool enabled
                row = await db.execute(
                    select(ToolModule).where(ToolModule.name == tool_name)
                )
                tool_mod = row.scalar_one_or_none()
                if tool_mod is None or not tool_mod.enabled:
                    await websocket.close(code=4003)
                    return

                # Resolve user from session
                if session_token and not session_token.startswith("anon_"):
                    token_hash = hash_token(session_token)
                    try:
                        from app.redis.session_store import get_session as redis_get
                        redis_data = await redis_get(token_hash)
                    except Exception:
                        redis_data = None

                    if redis_data:
                        user_id = redis_data.get("user_id")
                    else:
                        # DB fallback for session
                        from app.models import Session
                        srow = await db.execute(
                            select(Session).where(Session.token_hash == token_hash)
                        )
                        sess = srow.scalar_one_or_none()
                        if sess:
                            user_id = sess.user_id

                    if user_id:
                        urow = await db.execute(select(User.role).where(User.id == user_id))
                        r = urow.scalar_one_or_none()
                        if r:
                            role = r

                # Check role permission
                perm_row = await db.execute(
                    select(RoleToolPermission).where(
                        RoleToolPermission.role == role,
                        RoleToolPermission.tool_id == tool_mod.id,
                    )
                )
                perm = perm_row.scalar_one_or_none()
                if perm is None or not perm.allowed:
                    await websocket.close(code=4003)
                    return

                # Check rate limit (WebSocket bypasses BaseHTTPMiddleware)
                from app.services.rate_limit_service import check_tool_rate_limit
                source_ip = websocket.client.host if websocket.client else "unknown"
                rate_result = await check_tool_rate_limit(
                    db,
                    role=role,
                    user_id=user_id,
                    session_id=session_token,
                    source_ip=source_ip,
                    tool_id=tool_mod.id,
                )
                if not rate_result.allowed:
                    await websocket.close(code=4029)
                    return
        else:
            await websocket.close(code=4503)
            return
    except Exception:
        logger.exception("DB error during WebSocket authorization check for tool=%s", tool_name)
        await websocket.close(code=4503)
        return

    manager = _get_ws_manager(websocket.app)
    source_ip = websocket.client.host if websocket.client else "unknown"

    # manager.connect() does websocket.accept() internally
    await manager.connect(websocket, session_token, user_id)

    try:
        if tool_name == "ping":
            await handle_ping_stream(websocket, session_token, user_id, source_ip)
        elif tool_name == "traceroute":
            await handle_traceroute_stream(websocket, session_token, user_id, source_ip)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.exception("tool_stream error")
    finally:
        await manager.disconnect(session_token)


async def _check_tool_access(
    tool_name: str, request: Request, session
) -> None:
    """Raise HTTPException if tool is disabled or role not allowed."""
    from fastapi import HTTPException
    from app.models import ToolModule
    from app.models.tool_module import RoleToolPermission

    role = getattr(request.state, "role", "visitor")

    # Check enabled
    row = await session.execute(
        select(ToolModule).where(ToolModule.name == tool_name)
    )
    tool_mod = row.scalar_one_or_none()
    if tool_mod is None or not tool_mod.enabled:
        raise HTTPException(
            status_code=403,
            detail={
                "error": {
                    "code": "TOOL_DISABLED",
                    "message_key": "errors.tool_disabled",
                    "message": f"Tool '{tool_name}' is not available.",
                }
            },
        )

    # Check role permission — auto-create if missing (self-healing from seed failures)
    perm_row = await session.execute(
        select(RoleToolPermission).where(
            RoleToolPermission.role == role,
            RoleToolPermission.tool_id == tool_mod.id,
        )
    )
    perm = perm_row.scalar_one_or_none()
    if perm is None:
        from sqlalchemy.exc import IntegrityError

        perm = RoleToolPermission(role=role, tool_id=tool_mod.id, allowed=True)
        session.add(perm)
        try:
            await session.flush()
        except IntegrityError:
            await session.rollback()
            # Race: another request created the row between our SELECT and INSERT
            perm_row = await session.execute(
                select(RoleToolPermission).where(
                    RoleToolPermission.role == role,
                    RoleToolPermission.tool_id == tool_mod.id,
                )
            )
            perm = perm_row.scalar_one_or_none()
            if perm is None:
                raise  # should not happen — constraint exists, must be a different error
    if not perm.allowed:
        raise HTTPException(
            status_code=403,
            detail={
                "error": {
                    "code": "ROLE_NOT_ALLOWED",
                    "message_key": "errors.role_not_allowed",
                    "message": f"Your role does not have access to '{tool_name}'.",
                }
            },
        )


@router.post("/{tool_name}/execute")
async def execute_tool(
    tool_name: str,
    params: dict[str, Any],
    request: Request,
    registry: ToolRegistry = Depends(get_registry),
    session=Depends(get_session),
):
    """Execute an instant tool."""
    tool = registry.get(tool_name)
    if tool is None:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "NOT_FOUND",
                    "message_key": "errors.not_found",
                    "message": f"Tool '{tool_name}' not found",
                }
            },
        )

    await _check_tool_access(tool_name, request, session)

    session_id = getattr(request.state, "session_id", "unknown")
    user_id = getattr(request.state, "user_id", None)
    source_ip = request.client.host if request.client else "unknown"

    from app.tools.base import ExecutionContext

    context = ExecutionContext(
        user_id=user_id,
        session_id=session_id,
        source_ip=source_ip,
        role=getattr(request.state, "role", "visitor"),
        request_id=getattr(request.state, "request_id", ""),
    )

    start_time = time.monotonic()
    result = await tool.execute(params, context)
    elapsed_ms = int((time.monotonic() - start_time) * 1000)

    # Log tool execution (best-effort, non-blocking)
    try:
        from app.database import is_db_available as db_ok

        if db_ok():
            import app.services.log_service as log_svc

            async with async_session_factory() as log_db:
                await log_svc.create_tool_execution_log(
                    log_db,
                    user_id=user_id,
                    session_id=session_id,
                    source_ip=source_ip,
                    tool_name=tool_name,
                    parameters=params,
                    result="success" if result.success else ("failure" if result.error else "partial"),
                    duration_ms=elapsed_ms,
                    error_message=result.error,
                )
                await log_db.commit()
    except Exception:
        logger.exception("Failed to log tool execution")

    return {
        "result": {
            "success": result.success,
            "data": result.data,
            "error": result.error,
            "duration_ms": result.duration_ms or elapsed_ms,
        }
    }

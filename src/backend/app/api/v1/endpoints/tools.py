import logging
from typing import Any

from fastapi import APIRouter, Depends, Request, WebSocket, WebSocketDisconnect

from app.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tools", tags=["tools"])


def get_registry(request: Request) -> ToolRegistry:
    if not hasattr(request.app.state, "tool_registry"):
        from app.tools.ping import PingTool

        registry = ToolRegistry()
        registry.register(PingTool())
        request.app.state.tool_registry = registry
    return request.app.state.tool_registry


@router.get("")
async def list_tools(registry: ToolRegistry = Depends(get_registry)):
    tools = [tool.to_api_definition() for tool in registry._tools.values()]
    return {"tools": tools}


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
        if part.startswith("sakn_session="):
            return part.split("=", 1)[1], None
    return f"anon_{new_uuid7()}", None


@router.websocket("/{tool_name}/stream")
async def tool_stream(websocket: WebSocket, tool_name: str):
    from app.websocket.handlers.ping_ws import handle_ping_stream

    manager = _get_ws_manager(websocket.app)
    session_id, user_id = _read_session_from_ws(websocket)
    source_ip = websocket.client.host if websocket.client else "unknown"

    await manager.connect(websocket, session_id, user_id)

    try:
        if tool_name == "ping":
            await handle_ping_stream(websocket, session_id, user_id, source_ip)
        else:
            await websocket.send_json({
                "type": "error",
                "message_key": "errors.not_found",
                "message": f"Tool '{tool_name}' not available",
            })
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.exception("tool_stream error")
    finally:
        await manager.disconnect(session_id)


@router.post("/{tool_name}/execute")
async def execute_tool(
    tool_name: str,
    params: dict[str, Any],
    request: Request,
    registry: ToolRegistry = Depends(get_registry),
):
    """Execute an instant tool (skeleton for future tools)."""
    tool = registry.get(tool_name)
    if tool is None:
        return {
            "error": {
                "code": "NOT_FOUND",
                "message_key": "errors.not_found",
                "message": f"Tool '{tool_name}' not found",
            }
        }

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

    result = await tool.execute(params, context)
    return {
        "result": {
            "success": result.success,
            "data": result.data,
            "error": result.error,
            "duration_ms": result.duration_ms,
        }
    }

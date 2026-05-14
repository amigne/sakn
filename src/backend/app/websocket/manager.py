import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


@dataclass
class WSConnection:
    websocket: WebSocket
    session_id: str
    user_id: str | None
    connected_at: float = field(default_factory=lambda: asyncio.get_event_loop().time())
    last_heartbeat: float = field(default_factory=lambda: asyncio.get_event_loop().time())


class ConnectionManager:
    def __init__(self):
        self._connections: dict[str, WSConnection] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, session_id: str, user_id: str | None) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections[session_id] = WSConnection(
                websocket=websocket,
                session_id=session_id,
                user_id=user_id,
            )

    async def disconnect(self, session_id: str) -> None:
        async with self._lock:
            conn = self._connections.pop(session_id, None)
        if conn:
            try:
                await conn.websocket.close()
            except Exception:
                pass

    async def send_json(self, session_id: str, message: dict[str, Any]) -> bool:
        conn = self._connections.get(session_id)
        if conn is None:
            return False
        try:
            await conn.websocket.send_json(message)
            return True
        except Exception:
            await self.disconnect(session_id)
            return False

    async def broadcast(self, message: dict[str, Any]) -> None:
        for session_id in list(self._connections.keys()):
            await self.send_json(session_id, message)

    async def heartbeat(self, idle_timeout: float = 120.0) -> None:
        now = asyncio.get_event_loop().time()
        stale = []
        async with self._lock:
            for session_id, conn in self._connections.items():
                if now - conn.last_heartbeat > idle_timeout:
                    stale.append(session_id)
                else:
                    conn.last_heartbeat = now
        for session_id in stale:
            await self.disconnect(session_id)

    def is_connected(self, session_id: str) -> bool:
        return session_id in self._connections

    @property
    def active_count(self) -> int:
        return len(self._connections)

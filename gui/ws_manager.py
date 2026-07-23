"""WebSocket connection manager and notify_clients helper.

Isolated into its own module to break circular imports between server.py
(app creation, WebSocket routes) and the route/batch modules that need
to broadcast notifications.
"""

import asyncio

from fastapi import WebSocket

_main_loop = None


def set_main_loop(loop):
    global _main_loop
    _main_loop = loop


class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                self.disconnect(connection)


manager = ConnectionManager()


def notify_clients(event_type: str, status: str, message: str, level: str = "info", metadata: dict = None):
    if _main_loop is None or _main_loop.is_closed():
        return
    payload = {
        "event_type": event_type,
        "status": status,
        "message": message,
        "level": level,
        "metadata": metadata or {},
    }
    asyncio.run_coroutine_threadsafe(manager.broadcast(payload), _main_loop)

"""WebSocket connection manager and ``notify_clients`` helper.

Isolated into its own module to break circular imports between ``server.py``
(app creation, WebSocket routes) and the route/batch modules that need
to broadcast notifications.
"""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import WebSocket

_main_loop: asyncio.AbstractEventLoop | None = None
"""Reference to the running asyncio event loop, set by :func:`set_main_loop`."""


def set_main_loop(loop: asyncio.AbstractEventLoop | None) -> None:
    """Store a reference to the running event loop for cross-thread scheduling.

    Args:
        loop: The main event loop (or ``None`` to clear).
    """
    global _main_loop
    _main_loop = loop


class ConnectionManager:
    """Manages active WebSocket connections and provides broadcast capabilities."""

    def __init__(self) -> None:
        """Initialise with an empty connection list."""
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        """Accept a new WebSocket connection and add it to the active list.

        Args:
            websocket: The incoming WebSocket to accept and track.
        """
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket from the active connection list.

        Safe to call even if the websocket is not currently tracked.

        Args:
            websocket: The WebSocket to remove.
        """
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict[str, Any]) -> None:
        """Send a JSON message to every connected WebSocket.

        Connections that raise an exception during send are automatically
        disconnected.

        Args:
            message: Dictionary payload to serialise as JSON.
        """
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                self.disconnect(connection)


manager: ConnectionManager = ConnectionManager()
"""Module-level singleton connection manager instance."""


def notify_clients(
    event_type: str,
    status: str,
    message: str,
    level: str = "info",
    metadata: dict[str, Any] | None = None,
) -> None:
    """Schedule a broadcast notification to all connected WebSocket clients.

    Uses :func:`asyncio.run_coroutine_threadsafe` to safely schedule the
    broadcast from any thread.  Silently returns if no event loop has been
    registered yet.

    Args:
        event_type: High-level event category (e.g. ``"batch"``, ``"compile"``).
        status: Status label (e.g. ``"started"``, ``"success"``, ``"error"``).
        message: Human-readable notification text.
        level: Log/display level (``"info"``, ``"warning"``, ``"error"``, ``"success"``).
        metadata: Optional extra key-value pairs to include in the payload.
    """
    if _main_loop is None or _main_loop.is_closed():
        return

    payload: dict[str, Any] = {
        "event_type": event_type,
        "status": status,
        "message": message,
        "level": level,
        "metadata": metadata or {},
    }
    asyncio.run_coroutine_threadsafe(manager.broadcast(payload), _main_loop)


def stream_llm_token(job_id: int, token_text: str, word_count: int) -> None:
    """Push a single LLM output token to all connected WebSocket clients.

    Args:
        job_id: The 1-indexed batch job number.
        token_text: The delta content from the LLM chunk.
        word_count: Current total word count of the accumulated script.
    """
    import logging
    _log = logging.getLogger("shorts_creator")
    if _main_loop is None:
        _log.error("[stream_llm_token] _main_loop is None — event loop not registered yet")
        return
    if _main_loop.is_closed():
        _log.error("[stream_llm_token] _main_loop is closed")
        return
    payload: dict[str, Any] = {
        "event_type": "llm_token",
        "job_id": job_id,
        "token": token_text,
        "word_count": word_count,
    }
    # Rate-limited logging: log every 10th call to avoid flood
    try:
        _stream_llm_count = getattr(stream_llm_token, "_call_count", 0) + 1
        stream_llm_token._call_count = _stream_llm_count
        if _stream_llm_count <= 3 or _stream_llm_count % 20 == 0:
            _log.info(
                "[stream_llm_token #%d] job %d: %d words, token=%r, conns=%d",
                _stream_llm_count, job_id, word_count, token_text[:30],
                len(manager.active_connections),
            )
    except Exception as log_e:
        _log.error("[stream_llm_token] logging error: %s", log_e)
    asyncio.run_coroutine_threadsafe(manager.broadcast(payload), _main_loop)


def stream_llm_event(job_id: int, event: str, word_count: int | None = None) -> None:
    """Push an LLM lifecycle event (started/completed) to all connected WebSocket clients.

    Args:
        job_id: The 1-indexed batch job number.
        event: One of ``"llm_started"`` or ``"llm_completed"``.
        word_count: Final word count (only for ``"llm_completed"``).
    """
    import logging
    _log = logging.getLogger("shorts_creator")
    if _main_loop is None:
        _log.warning("[stream_llm_event] _main_loop is None — event loop not registered yet")
        return
    if _main_loop.is_closed():
        _log.warning("[stream_llm_event] _main_loop is closed")
        return
    payload: dict[str, Any] = {
        "event_type": event,
        "job_id": job_id,
        "word_count": word_count,
    }
    _log.info("[stream_llm_event] job %d: event=%s, word_count=%s", job_id, event, word_count)
    asyncio.run_coroutine_threadsafe(manager.broadcast(payload), _main_loop)

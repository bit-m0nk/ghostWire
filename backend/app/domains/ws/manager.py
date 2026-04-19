"""GhostWire — WebSocket connection manager.

Tracks every connected WebSocket client and provides a broadcast method.
Used by the live-push router to fan out session snapshots and events.

Thread safety: All public methods are called from FastAPI's async event loop.
The ``broadcast`` and ``send_event`` methods use asyncio.gather with
return_exceptions=True so a slow / broken client never stalls the others.
"""
import asyncio
import logging
from typing import Callable

from fastapi import WebSocket

log = logging.getLogger("ghostwire.ws")


class ConnectionManager:
    def __init__(self) -> None:
        # Map: websocket → set of subscribed channels ("sessions", "events", "all")
        self._clients: dict[WebSocket, set[str]] = {}
        self._lock = asyncio.Lock()

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def connect(self, ws: WebSocket, channels: set[str] | None = None) -> None:
        await ws.accept()
        async with self._lock:
            self._clients[ws] = channels or {"all"}
        log.debug(f"WS connect: total={len(self._clients)}")

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            self._clients.pop(ws, None)
        log.debug(f"WS disconnect: total={len(self._clients)}")

    # ── Sending ───────────────────────────────────────────────────────────────

    async def broadcast(self, payload: dict, channel: str = "all") -> None:
        """Send ``payload`` to every client subscribed to ``channel`` (or "all")."""
        import json

        data = json.dumps(payload)
        async with self._lock:
            targets = [
                ws for ws, chans in self._clients.items()
                if channel in chans or "all" in chans
            ]

        if not targets:
            return

        results = await asyncio.gather(
            *[ws.send_text(data) for ws in targets],
            return_exceptions=True,
        )
        for ws, result in zip(targets, results):
            if isinstance(result, Exception):
                log.debug(f"WS send failed (client likely disconnected): {result}")
                async with self._lock:
                    self._clients.pop(ws, None)

    async def send_personal(self, ws: WebSocket, payload: dict) -> None:
        import json
        try:
            await ws.send_text(json.dumps(payload))
        except Exception as exc:
            log.debug(f"WS personal send failed: {exc}")

    # ── Stats ─────────────────────────────────────────────────────────────────

    @property
    def count(self) -> int:
        return len(self._clients)


# Singleton — import this everywhere
manager = ConnectionManager()

"""
WebSocket connection manager for real-time state broadcasting.

Maintains a set of active connections and broadcasts SystemState
to all clients every ws_broadcast_interval_seconds.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from fastapi import WebSocket

from .config import settings
from .models import SystemState, WSMessage, WSMessageType
from .state_aggregator import aggregator

logger = logging.getLogger("cc.websocket")


class ConnectionManager:
    """Manages WebSocket connections and state broadcasting."""

    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()
        self._broadcast_task: asyncio.Task | None = None
        self._running = False

    @property
    def connection_count(self) -> int:
        return len(self._connections)

    async def connect(self, websocket: WebSocket) -> None:
        """Accept a new WebSocket connection."""
        await websocket.accept()
        self._connections.add(websocket)
        logger.info("WS client connected (total=%d)", len(self._connections))

        # Send current state immediately on connect
        msg = WSMessage(
            type=WSMessageType.CONNECTED,
            payload={"message": "Connected to NemoClaw Command Center"},
        )
        await self._safe_send(websocket, msg)

        # Send current state
        await self._send_state(websocket, aggregator.state)

    async def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection."""
        self._connections.discard(websocket)
        logger.info("WS client disconnected (total=%d)", len(self._connections))

    async def start_broadcasting(self) -> None:
        """Start the periodic broadcast loop."""
        self._running = True
        self._broadcast_task = asyncio.create_task(self._broadcast_loop())
        logger.info(
            "WS broadcasting started (interval=%ds)",
            settings.ws_broadcast_interval_seconds,
        )

    async def stop_broadcasting(self) -> None:
        """Stop the broadcast loop and close all connections."""
        self._running = False
        if self._broadcast_task:
            self._broadcast_task.cancel()
            try:
                await self._broadcast_task
            except asyncio.CancelledError:
                pass

        # Close all connections
        for ws in list(self._connections):
            try:
                await ws.close()
            except Exception:
                pass
        self._connections.clear()
        logger.info("WS broadcasting stopped")

    async def _broadcast_loop(self) -> None:
        """Broadcast state to all connected clients periodically."""
        while self._running:
            await asyncio.sleep(settings.ws_broadcast_interval_seconds)
            if self._connections:
                state = aggregator.state
                await self.broadcast_state(state)

    async def broadcast_state(self, state: SystemState) -> None:
        """Send state to all connected clients."""
        dead: list[WebSocket] = []
        for ws in self._connections:
            try:
                await self._send_state(ws, state)
            except Exception:
                dead.append(ws)

        for ws in dead:
            self._connections.discard(ws)
            logger.debug("Removed dead WS connection")

    async def broadcast_alert(self, domain: str, message: str) -> None:
        """Send a health alert to all connected clients."""
        msg = WSMessage(
            type=WSMessageType.HEALTH_ALERT,
            payload={"domain": domain, "message": message},
        )
        dead: list[WebSocket] = []
        for ws in self._connections:
            try:
                await self._safe_send(ws, msg)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._connections.discard(ws)

    async def _send_state(self, ws: WebSocket, state: SystemState) -> None:
        """Send a state update message to one client."""
        msg = WSMessage(
            type=WSMessageType.STATE_UPDATE,
            payload=state.model_dump(mode="json"),
        )
        await self._safe_send(ws, msg)

    async def _safe_send(self, ws: WebSocket, msg: WSMessage) -> None:
        """Send a message, raising on failure so caller can clean up."""
        await ws.send_json(msg.model_dump(mode="json"))


# Module-level singleton
ws_manager = ConnectionManager()

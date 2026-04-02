"""
WebSocket connection manager for real-time state broadcasting.

CC-1: Core state broadcasting (singleton, periodic loop)
CC-2: Brain insight broadcast
CC-3: Channel-based endpoints (/ws/state, /ws/chat, /ws/alerts)

Maintains backward compatibility with the legacy /ws endpoint
while adding channel support for CC-3.
"""

from __future__ import annotations

import asyncio
import json as _json
import logging
from typing import Any

from fastapi import WebSocket

from app.config import settings
from app.domain.models import SystemState, WSMessage, WSMessageType
from app.services.state_aggregator import aggregator

logger = logging.getLogger("cc.websocket")

VALID_CHANNELS = {"state", "chat", "alerts"}


class ConnectionManager:
    """Manages WebSocket connections and state broadcasting.

    Supports both:
      - Legacy mode: connect(websocket) → added to 'state' channel (CC-1/CC-2 compat)
      - Channel mode: connect_channel("chat", websocket) → added to specific channel (CC-3)
    """

    def __init__(self) -> None:
        # CC-1: Legacy connection set (backward compat)
        self._connections: set[WebSocket] = set()
        # CC-3: Channel-based connection sets
        self._channels: dict[str, set[WebSocket]] = {
            ch: set() for ch in VALID_CHANNELS
        }
        self._broadcast_task: asyncio.Task | None = None
        self._running = False

    @property
    def connection_count(self) -> int:
        return len(self._connections)

    def connection_counts(self) -> dict[str, int]:
        """Return connection count per channel (CC-3)."""
        return {ch: len(conns) for ch, conns in self._channels.items()}

    # ------------------------------------------------------------------
    # Legacy connection lifecycle (CC-1/CC-2 — /ws endpoint)
    # ------------------------------------------------------------------

    async def connect(self, websocket: WebSocket) -> None:
        """Accept a new WebSocket connection (legacy /ws mode)."""
        await websocket.accept()
        self._connections.add(websocket)
        # Also add to state channel so channel broadcasts reach legacy clients
        self._channels["state"].add(websocket)
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
        """Remove a WebSocket connection (legacy mode)."""
        self._connections.discard(websocket)
        # Also remove from all channels
        for ch_set in self._channels.values():
            ch_set.discard(websocket)
        logger.info("WS client disconnected (total=%d)", len(self._connections))

    # ------------------------------------------------------------------
    # Channel connection lifecycle (CC-3 — /ws/state, /ws/chat, /ws/alerts)
    # ------------------------------------------------------------------

    async def connect_channel(self, channel: str, websocket: WebSocket) -> None:
        """Accept and register a WebSocket on a specific channel (CC-3)."""
        if channel not in VALID_CHANNELS:
            logger.warning("Rejected WS connect to unknown channel: %s", channel)
            await websocket.close(code=4000, reason=f"Unknown channel: {channel}")
            return
        await websocket.accept()
        self._channels[channel].add(websocket)
        logger.info(
            "WS channel connected: %s (total=%d)",
            channel,
            len(self._channels[channel]),
        )

    async def disconnect_channel(self, channel: str, websocket: WebSocket) -> None:
        """Remove a WebSocket from its channel (CC-3)."""
        self._channels.get(channel, set()).discard(websocket)
        logger.info(
            "WS channel disconnected: %s (remaining=%d)",
            channel,
            len(self._channels.get(channel, set())),
        )

    # ------------------------------------------------------------------
    # Broadcasting lifecycle (CC-1)
    # ------------------------------------------------------------------

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

        # Close all legacy connections
        for ws in list(self._connections):
            try:
                await ws.close()
            except Exception:
                pass
        self._connections.clear()

        # Close all channel connections
        for ch_set in self._channels.values():
            for ws in list(ch_set):
                try:
                    await ws.close()
                except Exception:
                    pass
            ch_set.clear()

        logger.info("WS broadcasting stopped")

    async def _broadcast_loop(self) -> None:
        """Broadcast state to all connected clients periodically."""
        while self._running:
            await asyncio.sleep(settings.ws_broadcast_interval_seconds)
            if self._connections or self._channels["state"]:
                state = aggregator.state
                await self.broadcast_state(state)

    # ------------------------------------------------------------------
    # State broadcasting (CC-1 — sends to legacy + state channel)
    # ------------------------------------------------------------------

    async def broadcast_state(self, state: SystemState) -> None:
        """Send state to all legacy clients + state channel subscribers."""
        # Legacy clients (CC-1)
        dead: list[WebSocket] = []
        for ws in self._connections:
            try:
                await self._send_state(ws, state)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._connections.discard(ws)
            # Also remove from channels
            for ch_set in self._channels.values():
                ch_set.discard(ws)
            logger.debug("Removed dead legacy WS connection")

        # Channel clients that aren't also legacy (CC-3)
        state_only = self._channels["state"] - self._connections
        dead_ch: set[WebSocket] = set()
        if state_only:
            state_data = state.model_dump(mode="json")
            for ws in state_only:
                try:
                    await ws.send_json({"type": "state_update", "data": state_data})
                except Exception:
                    dead_ch.add(ws)
            if dead_ch:
                self._channels["state"] -= dead_ch

    # ------------------------------------------------------------------
    # Alert broadcasting (CC-1)
    # ------------------------------------------------------------------

    async def broadcast_alert(self, domain: str, message: str) -> None:
        """Send a health alert to legacy clients + alerts channel."""
        # Legacy
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

        # CC-3: alerts channel
        alert_data = {"type": "alert", "data": {"domain": domain, "message": message}}
        dead_ch: set[WebSocket] = set()
        for ws in self._channels["alerts"]:
            try:
                await ws.send_json(alert_data)
            except Exception:
                dead_ch.add(ws)
        if dead_ch:
            self._channels["alerts"] -= dead_ch

    # ------------------------------------------------------------------
    # Brain broadcasting (CC-2)
    # ------------------------------------------------------------------

    async def broadcast_brain_message(self, message: dict) -> None:
        """Broadcast a brain insight/response to all connected WS clients."""
        data = _json.dumps(message)
        dead: set[WebSocket] = set()
        # Send to legacy clients
        for ws in self._connections:
            try:
                await ws.send_text(data)
            except Exception:
                dead.add(ws)
        self._connections -= dead

        # Also send to state channel clients (CC-3)
        state_only = self._channels["state"] - self._connections
        dead_ch: set[WebSocket] = set()
        for ws in state_only:
            try:
                await ws.send_text(data)
            except Exception:
                dead_ch.add(ws)
        if dead_ch:
            self._channels["state"] -= dead_ch

    # ------------------------------------------------------------------
    # Chat broadcasting (CC-3)
    # ------------------------------------------------------------------

    async def broadcast_chat_message(self, message: dict[str, Any]) -> None:
        """Broadcast a new chat message to /ws/chat subscribers."""
        data = {"type": "chat_message", "data": message}
        dead: set[WebSocket] = set()
        for ws in self._channels["chat"]:
            try:
                await ws.send_json(data)
            except Exception:
                dead.add(ws)
        if dead:
            self._channels["chat"] -= dead

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _send_state(self, ws: WebSocket, state: SystemState) -> None:
        """Send a state update message to one client."""
        msg = WSMessage(
            type=WSMessageType.STATE_UPDATE,
            payload=state.model_dump(mode="json"),
        )
        await self._safe_send(ws, msg)

    async def _safe_send(self, ws: WebSocket, msg: WSMessage) -> None:
        """Send a message, suppressing disconnect errors."""
        try:
            await ws.send_json(msg.model_dump(mode="json"))
        except Exception:
            # Client disconnected — will be cleaned up by the connection loop
            pass


# Module-level singleton
ws_manager = ConnectionManager()

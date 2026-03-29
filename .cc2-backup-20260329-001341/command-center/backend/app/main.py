"""
NemoClaw Command Center — FastAPI Backend (CC-1)

Entry point for the Command Center API server.
Starts the state aggregator and WebSocket broadcaster on startup,
stops them cleanly on shutdown.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .auth import get_active_token, verify_ws_token
from .config import ensure_directories, settings
from .routers import health, state
from .state_aggregator import aggregator
from .websocket_manager import ws_manager

# ── Logging ────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(name)-18s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("cc.main")


# ── Lifespan ───────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    ensure_directories()

    # Print auth token for local dev
    token = get_active_token()
    logger.info("=" * 60)
    logger.info("NemoClaw Command Center v1.0.0")
    logger.info("API:       http://%s:%d", settings.host, settings.port)
    logger.info("WebSocket: ws://%s:%d/ws", settings.host, settings.port)
    logger.info("Repo:      %s", settings.repo_root)
    logger.info("Token:     %s", token)
    logger.info("=" * 60)

    # Start background services
    await aggregator.start()
    await ws_manager.start_broadcasting()

    # Run initial scan immediately
    await aggregator.force_scan()
    logger.info(
        "Initial scan complete — %d skills, %d agents, %d MA systems",
        aggregator.state.skills.total_built,
        aggregator.state.agents.total,
        aggregator.state.ma_systems.total,
    )

    yield

    # Shutdown
    await ws_manager.stop_broadcasting()
    await aggregator.stop()
    logger.info("Command Center stopped")


# ── App ────────────────────────────────────────────────────────────────

app = FastAPI(
    title="NemoClaw Command Center",
    version="1.0.0",
    description="Real-time system state aggregation and management for NemoClaw",
    lifespan=lifespan,
)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(state.router)
app.include_router(health.router)


# ── WebSocket Endpoint ─────────────────────────────────────────────────


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time state updates.
    Authenticates via ?token= query parameter.
    """
    if not await verify_ws_token(websocket):
        await websocket.close(code=4001, reason="Unauthorized")
        return

    await ws_manager.connect(websocket)
    try:
        while True:
            # Keep connection alive, handle client messages
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_json({"type": "pong"})
            elif data == "refresh":
                new_state = await aggregator.force_scan()
                await ws_manager.broadcast_state(new_state)
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket)
    except Exception:
        await ws_manager.disconnect(websocket)

"""
NemoClaw Command Center — FastAPI Backend (CC-1 / CC-2 / CC-3)

Entry point for the Command Center API server.
Starts the state aggregator and WebSocket broadcaster on startup,
stops them cleanly on shutdown.
"""

from __future__ import annotations

import os
from pathlib import Path

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.auth import get_active_token, verify_ws_token
from app.config import ensure_directories, settings
from app.api.routers import health, state

# CC-2: AI Brain
import asyncio as _brain_asyncio
from app.services.brain_service import BrainService
from app.api.routers.brain import router as brain_router, set_dependencies as brain_set_deps

# CC-3: Communications
from app.services.message_store import MessageStore
from app.services.agent_chat_service import AgentChatService
from app.domain.comms_models import LaneType
from app.api.routers import comms
from app.api.routers import agents as agents_router
# ── CC-5 imports ──
from app.services.skill_service import SkillService
# ── CC-7 imports ──
from app.services.project_service import ProjectService
from app.api.routers import projects as projects_router
# ── CC-6 imports ──
from app.services.ops_service import OpsService
from app.api.routers import ops as ops_router
from app.api.routers import skills as skills_router

from app.services.state_aggregator import aggregator
from app.adapters.websocket_manager import ws_manager

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

    # CC-2: Initialize Brain service
    _brain_routing_alias = os.environ.get("CC_BRAIN_ROUTING_ALIAS", "balanced")
    _brain_project_root = os.environ.get("CC_PROJECT_ROOT", str(Path(__file__).parent.parent.parent.parent))
    _brain_service = BrainService(
        project_root=_brain_project_root,
        routing_alias=_brain_routing_alias,
    )

    # Wire brain dependencies
    brain_set_deps(_brain_service, aggregator)
    if _brain_service.is_available:
        logger.info(f"Brain online: {_brain_service.provider_info}")

    # CC-3: Initialize MessageStore + AgentChatService
    _data_dir = Path(__file__).parent.parent / "data"
    _data_dir.mkdir(parents=True, exist_ok=True)

    message_store = MessageStore(persist_path=str(_data_dir / "messages.json"))
    agent_chat_service = AgentChatService()

    # Pre-create DM lanes for all agents
    for agent_info in agent_chat_service.list_agents():
        message_store.create_lane(
            lane_id=agent_info["lane_id"],
            name=agent_info["name"],
            lane_type=LaneType.DM,
            participants=[agent_info["id"]],
            avatar=agent_info["avatar"],
        )

    # Pre-create All Hands + System lanes
    all_agent_ids = [a["id"] for a in agent_chat_service.list_agents()]
    message_store.create_lane(
        lane_id="all-hands",
        name="All Hands",
        lane_type=LaneType.BROADCAST,
        participants=all_agent_ids,
        avatar="\U0001f4e2",
    )
    message_store.create_lane(
        lane_id="system",
        name="System",
        lane_type=LaneType.SYSTEM,
        participants=[],
        avatar="\U0001f514",
    )

    logger.info(
        "CC-3: MessageStore initialized (%d lanes), AgentChatService %s (%d agents)",
        len(message_store.get_lanes()),
        "online" if agent_chat_service.is_available else "offline",
        len(agent_chat_service.agents),
    )

    # CC-2: Auto-insight background task
    _insight_interval = int(os.environ.get("CC_BRAIN_INSIGHT_INTERVAL_SECONDS", "300"))

    async def _auto_insight_loop():
        """Generate strategic insight every N seconds."""
        import logging
        _logger = logging.getLogger("cc.brain.auto")
        _logger.info(f"Auto-insight loop started (interval: {_insight_interval}s)")
        await _brain_asyncio.sleep(30)  # Wait 30s after startup before first insight
        while True:
            try:
                if _brain_service.is_available:
                    _state = aggregator.state
                    _sd = _state.model_dump() if hasattr(_state, "model_dump") else _state.dict()
                    _insight = await _brain_service.generate_insight(_sd)
                    if _insight.get("available"):
                        # Broadcast via WS if manager is available
                        _wm = getattr(app.state, "ws_manager", None)
                        if _wm and hasattr(_wm, "broadcast_brain_message"):
                            await _wm.broadcast_brain_message({
                                "type": "brain_insight",
                                "data": _insight,
                            })
                        _logger.info("Auto-insight generated and broadcast")
            except Exception as e:
                _logger.error(f"Auto-insight error: {e}")
            await _brain_asyncio.sleep(_insight_interval)

    _brain_asyncio.ensure_future(_auto_insight_loop())

    # Expose services on app.state
    app.state.ws_manager = ws_manager
    app.state.message_store = message_store
    app.state.agent_chat_service = agent_chat_service


    # ── CC-5: Skill service ──
    _repo_root = Path(__file__).resolve().parents[3]
    app.state.skill_service = SkillService(_repo_root)
    logger.info(f"CC-5: SkillService loaded ({len(app.state.skill_service.skills)} skills)")

    # ── CC-6: Ops service ──
    from app.services.ops_service import OpsService
    app.state.ops_service = OpsService(Path(__file__).resolve().parents[3])
    logger.info("CC-6: OpsService initialized")

    # ── CC-7: Project service ──
    from app.services.project_service import ProjectService
    app.state.project_service = ProjectService(Path(__file__).resolve().parents[3])
    logger.info("CC-7: ProjectService initialized")
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
app.include_router(brain_router)  # CC-2: Brain
app.include_router(comms.router)  # CC-3: Communications
app.include_router(agents_router.router)  # CC-4: Agents
app.include_router(skills_router.router)
app.include_router(projects_router.router)  # CC-7
app.include_router(ops_router.router)  # CC-6


# ── WebSocket Endpoints ────────────────────────────────────────────────


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    Legacy WebSocket endpoint for real-time state updates (CC-1/CC-2).
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


def _check_ws_token(token: str) -> bool:
    """Validate a WS query-param token against the active token."""
    expected = get_active_token()
    return token == expected


@app.websocket("/ws/state")
async def ws_state_channel(websocket: WebSocket, token: str = ""):
    """CC-3: State updates channel (10s scan + brain insights)."""
    if not _check_ws_token(token):
        await websocket.close(code=4001, reason="Unauthorized")
        return
    await ws_manager.connect_channel("state", websocket)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_json({"type": "pong"})
    except Exception:
        await ws_manager.disconnect_channel("state", websocket)


@app.websocket("/ws/chat")
async def ws_chat_channel(websocket: WebSocket, token: str = ""):
    """CC-3: Chat messages channel."""
    if not _check_ws_token(token):
        await websocket.close(code=4001, reason="Unauthorized")
        return
    await ws_manager.connect_channel("chat", websocket)
    try:
        while True:
            await websocket.receive_text()
    except Exception:
        await ws_manager.disconnect_channel("chat", websocket)


@app.websocket("/ws/alerts")
async def ws_alerts_channel(websocket: WebSocket, token: str = ""):
    """CC-3: Alerts channel."""
    if not _check_ws_token(token):
        await websocket.close(code=4001, reason="Unauthorized")
        return
    await ws_manager.connect_channel("alerts", websocket)
    try:
        while True:
            await websocket.receive_text()
    except Exception:
        await ws_manager.disconnect_channel("alerts", websocket)

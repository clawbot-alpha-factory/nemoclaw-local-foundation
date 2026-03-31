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
# ── CC-8 imports ──
from app.services.client_service import ClientService
from app.api.routers import clients as clients_router
# ── CC-7 imports ──
from app.services.project_service import ProjectService
from app.api.routers import projects as projects_router
# ── CC-6 imports ──
from app.services.ops_service import OpsService
from app.api.routers import ops as ops_router
from app.api.routers import skills as skills_router

# ── Engine (E-2) imports ──
from app.services.execution_service import ExecutionService
from app.services.skill_chain_runner import SkillChainRunner
from app.api.routers import execution as execution_router

# ── Engine (E-3) imports ──
from app.services.orchestrator_service import OrchestratorService
from app.services.project_lifecycle_service import ProjectLifecycleService
from app.services.team_formation_service import TeamFormationService
from app.services.multi_project_service import MultiProjectService
from app.api.routers import orchestrator as orchestrator_router

# ── Engine (E-4a) imports ──
from app.services.agent_loop_service import AgentLoopService
from app.services.agent_memory_service import AgentMemoryService
from app.services.scheduler_service import SchedulerService
from app.services.checkpoint_service import CheckpointService
from app.api.routers import engine as engine_router

# ── Engine (E-4b) imports ──
from app.services.agent_protocol_service import AgentProtocolService
from app.services.workspace_service import WorkspaceService
from app.services.debate_service import DebateService
from app.services.context_service import ContextService
from app.services.knowledge_base_service import KnowledgeBaseService
from app.services.feedback_loop_service import FeedbackLoopService
from app.api.routers import protocol as protocol_router

# ── Engine (E-4c) imports ──
from app.services.guardrail_service import GuardrailService
from app.services.alert_service import AlertService
from app.services.webhook_service import WebhookService
from app.services.config_service import ConfigService
from app.services.secret_manager import SecretManager
from app.services.sla_service import SLAService
from app.services.audit_service import AuditService
from app.services.approval_chain_service import ApprovalChainService
from app.api.routers import enterprise as enterprise_router

# ── Engine (E-7b) imports ──
from app.services.build_plan_tracker import BuildPlanTracker
from app.services.code_generation_service import CodeGenerationService
from app.services.code_review_service import CodeReviewService
from app.services.deploy_service import DeployService
from app.services.phase_completion_service import PhaseCompletionService
from app.api.routers import self_build as self_build_router

# ── Engine (E-8) imports ──
from app.services.bridge_manager import BridgeManager
from app.api.routers import bridges as bridges_router

# ── Engine (E-5) imports ──
from app.services.skill_factory_service import SkillFactoryService
from app.api.routers import skill_factory as skill_factory_router

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

    # ── CC-8: Client service ──
    from app.services.client_service import ClientService
    app.state.client_service = ClientService(Path(__file__).resolve().parents[3])
    logger.info("CC-8: ClientService initialized")

    # ── CC-9: Approval service ──
    try:
        from app.services.approval_service import ApprovalService
        app.state.approval_service = ApprovalService(Path(__file__).resolve().parents[3])
        logger.info("CC-9: ApprovalService initialized")
    except ImportError:
        pass

    # ── E-3: Orchestrator + Project Lifecycle ──
    _repo_root_e3 = Path(__file__).resolve().parents[3]
    app.state.orchestrator_service = OrchestratorService(_repo_root_e3)
    app.state.lifecycle_service = ProjectLifecycleService(app.state.project_service)
    app.state.team_service = TeamFormationService()
    app.state.multi_project_service = MultiProjectService(app.state.project_service)
    logger.info("E-3: Orchestrator + Lifecycle + Team + MultiProject initialized")

    # ── E-2: Execution Engine ──
    _repo_root_engine = Path(__file__).resolve().parents[3]
    app.state.execution_service = ExecutionService(_repo_root_engine)
    app.state.chain_runner = SkillChainRunner(app.state.execution_service)
    await app.state.execution_service.start()
    logger.info("E-2: ExecutionService + SkillChainRunner started")

    # ── E-4a: Agent Runtime ──
    app.state.agent_memory_service = AgentMemoryService()
    app.state.scheduler_service = SchedulerService()
    app.state.checkpoint_service = CheckpointService()
    app.state.agent_loop_service = AgentLoopService(
        execution_service=app.state.execution_service,
        memory_service=app.state.agent_memory_service,
        scheduler_service=app.state.scheduler_service,
        checkpoint_service=app.state.checkpoint_service,
    )
    logger.info("E-4a: AgentLoopService + Memory + Scheduler + Checkpoint initialized")

    # ── E-4b: Agent Collaboration ──
    app.state.protocol_service = AgentProtocolService()
    app.state.workspace_service = WorkspaceService()
    app.state.debate_service = DebateService()
    app.state.context_service = ContextService(
        execution_service=app.state.execution_service,
        workspace_service=app.state.workspace_service,
    )
    app.state.knowledge_base_service = KnowledgeBaseService()
    app.state.feedback_loop_service = FeedbackLoopService(
        protocol_service=app.state.protocol_service,
    )
    logger.info("E-4b: Protocol + Workspace + Debate + Context + KB + Feedback initialized")

    # ── E-4c: Enterprise Operations ──
    app.state.config_service = ConfigService()
    app.state.guardrail_service = GuardrailService(config_service=app.state.config_service)
    app.state.alert_service = AlertService()
    app.state.webhook_service = WebhookService(execution_service=app.state.execution_service)
    app.state.secret_manager = SecretManager()
    app.state.sla_service = SLAService(alert_service=app.state.alert_service)
    app.state.audit_service = AuditService()
    app.state.approval_chain_service = ApprovalChainService(audit_service=app.state.audit_service)
    logger.info("E-4c: Guardrails + Alerts + Webhooks + Config + Secrets + SLA + Audit + Approvals initialized")

    # ── E-5: Skill Factory ──
    app.state.skill_factory_service = SkillFactoryService(
        repo_root=Path(__file__).resolve().parents[3],
        execution_service=app.state.execution_service,
        skill_service=app.state.skill_service,
        audit_service=app.state.audit_service,
    )
    logger.info("E-5: SkillFactoryService initialized")

    # ── E-7b: Self-Build Engine (THE TIPPING POINT) ──
    app.state.build_plan_tracker = BuildPlanTracker()
    app.state.code_generation_service = CodeGenerationService(Path(__file__).resolve().parents[3])
    app.state.code_review_service = CodeReviewService(Path(__file__).resolve().parents[3])
    app.state.deploy_service = DeployService(
        repo_root=Path(__file__).resolve().parents[3],
        alert_service=app.state.alert_service,
        audit_service=app.state.audit_service,
    )
    app.state.phase_completion_service = PhaseCompletionService(
        repo_root=Path(__file__).resolve().parents[3],
        build_tracker=app.state.build_plan_tracker,
    )
    logger.info("E-7b: Self-Build Engine initialized (THE TIPPING POINT)")

    # ── E-8: Bridge Activation ──
    app.state.bridge_manager = BridgeManager(
        guardrail_service=app.state.guardrail_service,
        audit_service=app.state.audit_service,
    )
    logger.info("E-8: BridgeManager initialized")

    yield

    # E-4a shutdown
    if hasattr(app.state, 'agent_loop_service'):
        await app.state.agent_loop_service.stop_all()
        logger.info("E-4a: All agent loops stopped")

    # E-2 shutdown
    await app.state.execution_service.stop()

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
# CC-9
from app.api.routers import approvals as approvals_router
from app.api.routers import settings as settings_router
app.include_router(approvals_router.router)  # CC-9
app.include_router(settings_router.router)  # CC-10
app.include_router(clients_router.router)  # CC-8
app.include_router(projects_router.router)  # CC-7
app.include_router(ops_router.router)  # CC-6

# Engine (E-2)
app.include_router(execution_router.router)  # E-2: Execution
app.include_router(orchestrator_router.router)  # E-3: Orchestrator
app.include_router(engine_router.router)  # E-4a: Engine
app.include_router(protocol_router.router)  # E-4b: Protocol
app.include_router(enterprise_router.router)  # E-4c: Enterprise
app.include_router(skill_factory_router.router)  # E-5: Skill Factory
app.include_router(self_build_router.router)  # E-7b: Self-Build
app.include_router(bridges_router.router)  # E-8: Bridges


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

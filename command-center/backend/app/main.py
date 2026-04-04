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
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest
from starlette.responses import Response as StarletteResponse

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
from app.services.planning_service import PlanningService
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

# ── CC-TD: Task Dispatch ──
from app.services.task_dispatch_service import TaskDispatchService

# ── Engine (E-4a) imports ──
from app.services.agent_loop_service import AgentLoopService
from app.services.agent_memory_service import AgentMemoryService
from app.services.scheduler_service import SchedulerService
from app.services.checkpoint_service import CheckpointService
from app.services.agent_notification_service import AgentNotificationService
from app.services.message_pool_service import MessagePoolService
from app.services.task_workflow_service import TaskWorkflowService
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

# ── Engine (E-9 fix) imports ──
from app.services.tool_access_service import ToolAccessService
from app.services.skill_agent_mapping import SkillAgentMappingService
from app.services.skill_chain_wiring import SkillChainWiringService
from app.services.global_state_service import GlobalStateService
from app.services.priority_engine import PriorityEngine
from app.services.failure_recovery_service import FailureRecoveryService

# ── Engine (E-10) imports ──
from app.services.pipeline_service import PipelineService
from app.services.catalog_service import CatalogService
from app.services.ab_test_service import ABTestService
from app.services.attribution_service import AttributionService
from app.services.event_bus_service import EventBusService
from app.api.routers import revenue as revenue_router

# ── Engine (E-11) imports ──
from app.services.onboarding_service import OnboardingService
from app.services.deliverable_service import DeliverableService
from app.services.work_log_service import WorkLogService
from app.services.churn_service import ChurnService
from app.api.routers import lifecycle as lifecycle_router

# ── Engine (E-12) imports ──
from app.services.metrics_service import MetricsService
from app.services.data_lifecycle_service import DataLifecycleService
from app.services.self_improvement_service import SelfImprovementService
from app.services.autonomous_loop_service import AutonomousLoopService
from app.services.autonomous_scheduler_service import AutonomousSchedulerService
from app.services.insight_action_bridge import InsightActionBridge
from app.services.prompt_optimization_service import PromptOptimizationService
from app.services.task_queue_service import TaskQueueService
from app.services.rate_limiter_service import RateLimiterService
from app.api.routers import infrastructure as infra_router
from app.api.routers import autonomous as autonomous_router
from app.api.routers import skill_wiring as skill_wiring_router

# ── P-2: Activity Event Log ──
from app.api.routers import activity as activity_router

# ── Engine (E-5) imports ──
from app.services.skill_factory_service import SkillFactoryService
from app.api.routers import skill_factory as skill_factory_router
from app.services.skill_request_service import SkillRequestService
from app.api.routers import skill_requests as skill_requests_router

# ── P-8: Skills Marketplace ──
from app.api.routers import marketplace as marketplace_router

# ── A2A Protocol ──
from app.api.routers.a2a import discovery_router as a2a_discovery_router, task_router as a2a_task_router

# ── E-13: Mega Projects ──
from app.services.mega_project_service import MegaProjectService
from app.api.routers import mega_projects as mega_projects_router

# ── Missions (Asana-backed) ──
from app.services.bridges.asana_bridge import AsanaBridge
from app.services.mission_manager_service import MissionManagerService
from app.api.routers import missions as missions_router

from app.services.state_aggregator import aggregator
from app.adapters.websocket_manager import ws_manager

# ── Structured Logging ────────────────────────────────────────────────
# Replaces bare basicConfig with JSON-structured logging + correlation IDs.
# LOG_FORMAT=human in dev, LOG_FORMAT=json in Docker (set in Dockerfile).
import sys as _sys
_repo_root_for_lib = str(Path(__file__).parent.parent.parent.parent)
if _repo_root_for_lib not in _sys.path:
    _sys.path.insert(0, _repo_root_for_lib)
from lib.structured_logging import get_logger as _get_logger, make_logging_middleware as _make_logging_middleware  # noqa: E402
from lib.vector_memory import VectorMemory  # noqa: E402

logger = _get_logger("cc.main")

# ── Sentry Error Tracking ────────────────────────────────────────────
_sentry_dsn = os.environ.get("SENTRY_DSN", "")
if _sentry_dsn:
    try:
        import sentry_sdk
        sentry_sdk.init(
            dsn=_sentry_dsn,
            traces_sample_rate=0.1,
            environment=os.environ.get("SENTRY_ENV", "development"),
        )
        logger.info("Sentry error tracking enabled")
    except ImportError:
        logger.warning("SENTRY_DSN set but sentry-sdk not installed")


# ── Lifespan ───────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    ensure_directories()

    # Print auth token for local dev
    token = get_active_token()
    logger.info("=" * 60)
    logger.info("NemoClaw Command Center v1.0.0")
    logger.info(f"API:       http://{settings.host}:{settings.port}")
    logger.info(f"WebSocket: ws://{settings.host}:{settings.port}/ws")
    logger.info(f"Repo:      {settings.repo_root}")
    logger.info(f"Token:     {token}")
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
    app.state.brain_service = _brain_service
    if _brain_service.is_available:
        logger.info(f"Brain online: {_brain_service.provider_info}")

    # CC-3: Initialize MessageStore + AgentChatService
    _data_dir = Path(__file__).parent.parent / "data"
    _data_dir.mkdir(parents=True, exist_ok=True)

    message_store = MessageStore(persist_path=str(_data_dir / "messages.json"))

    # ── SQLite persistence (Litestream-backed, ~1s RPO) ──
    from app.services.backup.sqlite_store import SQLiteStore
    _sqlite_store = SQLiteStore()  # ~/.nemoclaw/nemoclaw.db
    app.state.sqlite_store = _sqlite_store

    # Run migration on first boot (idempotent)
    if _sqlite_store.get_message_count() == 0 and (_data_dir / "messages.json").exists():
        from app.services.backup.migrate_json_to_sqlite import run_migration
        _mig = run_migration()
        logger.info("SQLite: First-boot migration complete: %s", _mig)
    else:
        logger.info("SQLite: DB ready (%d messages, %d lanes)",
                     _sqlite_store.get_message_count(), _sqlite_store.get_lane_count())

    # Hook: dual-write to SQLite on every message
    _original_add = message_store.add_message
    def _dual_write_add(*args, **kwargs):
        result = _original_add(*args, **kwargs)
        if result:
            try:
                _sqlite_store.add_message(result.model_dump(mode="json") if hasattr(result, "model_dump") else result)
            except Exception as e:
                logger.warning("SQLite dual-write failed: %s", e)
        return result
    message_store.add_message = _dual_write_add

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
    message_store.create_lane(
        lane_id="watercooler",
        name="Watercooler",
        lane_type=LaneType.GROUP,
        participants=all_agent_ids,
        avatar="\u2615",
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

    # ── Backup: Litestream handles real-time replication (~1s RPO) ──
    # Old 6-hour cron replaced. SQLite WAL → Litestream → S3/local replica.
    # Run: litestream replicate -config ~/.nemoclaw/litestream.yml
    logger.info("Backup: SQLite + Litestream architecture (RPO ~1s). Run litestream separately.")

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

    # ── S1: Planning service ──
    from app.services.planning_service import PlanningService
    app.state.planning_service = PlanningService(
        repo_root=Path(__file__).resolve().parents[3],
        project_service=app.state.project_service,
        approval_service=getattr(app.state, "approval_service", None),
    )
    # Wire planning_service back into project_service for milestone hooks
    app.state.project_service.planning_service = app.state.planning_service
    logger.info("S1: PlanningService initialized")

    # ── P-1: Project Scoped Memory ──
    from app.services.project_memory_service import ProjectMemoryService
    app.state.project_memory_service = ProjectMemoryService()
    logger.info("P-1: ProjectMemoryService initialized")

    # ── P-2: Activity Event Log ──
    from app.services.activity_log_service import ActivityLogService
    app.state.activity_log_service = ActivityLogService()
    logger.info("P-2: ActivityLogService initialized")

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

    # ── E-2b: Execution Observability ──
    from lib.circuit_breaker import SkillCircuitBreaker
    from lib.skill_metrics import SkillMetrics
    app.state.circuit_breaker = SkillCircuitBreaker(failure_threshold=5, recovery_timeout=60)
    app.state.skill_metrics = SkillMetrics()
    app.state.execution_service.circuit_breaker = app.state.circuit_breaker
    app.state.execution_service.skill_metrics = app.state.skill_metrics
    logger.info("E-2b: CircuitBreaker + SkillMetrics wired to execution")

    # ── E-2c: CLI Execution Backends ──
    from lib.executor_backends import ClaudeCodeBackend, CodexBackend
    app.state.execution_service.register_backend("claude_code", ClaudeCodeBackend())
    app.state.execution_service.register_backend("codex", CodexBackend())
    logger.info(
        "E-2c: ClaudeCodeBackend + CodexBackend registered (%d backends total)",
        len(app.state.execution_service.backend_registry),
    )

    # ── E-14: Research Service ──
    from app.services.research_service import ResearchService
    app.state.research_service = ResearchService(app.state.chain_runner)
    logger.info("E-14: ResearchService initialized")

    # ── E-4a: Agent Runtime ──
    from app.services.agent_factory_service import AgentFactoryService
    app.state.agent_factory = AgentFactoryService()
    app.state.agent_factory.create_all_workspaces()
    logger.info("E-4a: AgentFactoryService initialized — %d workspaces provisioned", len(app.state.agent_factory._agents))

    app.state.vector_memory = VectorMemory()
    app.state.agent_memory_service = AgentMemoryService()
    app.state.scheduler_service = SchedulerService()
    app.state.checkpoint_service = CheckpointService()
    app.state.message_pool = MessagePoolService()
    app.state.notification_service = AgentNotificationService(
        message_store=message_store,
        activity_log_service=getattr(app.state, "activity_log_service", None),
        message_pool=app.state.message_pool,
    )
    app.state.agent_loop_service = AgentLoopService(
        execution_service=app.state.execution_service,
        memory_service=app.state.agent_memory_service,
        scheduler_service=app.state.scheduler_service,
        checkpoint_service=app.state.checkpoint_service,
        notification_service=app.state.notification_service,
        activity_log_service=getattr(app.state, "activity_log_service", None),
        task_workflow_service=getattr(app.state, "orchestrator_service", None),
        vector_memory=app.state.vector_memory,
        agent_factory=app.state.agent_factory,
    )
    # Auto-start all agent loops — agents begin 5s tick cycles immediately
    await app.state.agent_loop_service.start_all()
    logger.info("E-4a: AgentLoopService + Memory + Scheduler + Checkpoint + Notifications initialized — ALL LOOPS RUNNING")

    # Wire notification_service into project_service and planning_service for lifecycle hooks
    app.state.project_service.notification_service = app.state.notification_service
    if hasattr(app.state, "planning_service"):
        app.state.planning_service.notification_service = app.state.notification_service
        app.state.planning_service.execution_service = app.state.execution_service

    # Wire message pool into agent loops for peer awareness
    app.state.agent_loop_service.message_pool = app.state.message_pool

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
    app.state.webhook_service = WebhookService(
        execution_service=app.state.execution_service,
        activity_log_service=getattr(app.state, "activity_log_service", None),
    )
    app.state.secret_manager = SecretManager()
    app.state.sla_service = SLAService(alert_service=app.state.alert_service)
    app.state.audit_service = AuditService()
    app.state.approval_chain_service = ApprovalChainService(
        audit_service=app.state.audit_service,
        activity_log_service=getattr(app.state, "activity_log_service", None),
    )
    logger.info("E-4c: Guardrails + Alerts + Webhooks + Config + Secrets + SLA + Audit + Approvals initialized")

    # ── E-4d: CEO Review Gate ──
    from app.services.ceo_reviewer_service import CEOReviewerService
    app.state.ceo_reviewer_service = CEOReviewerService(
        brain_service=app.state.brain_service,
        approval_chain_service=app.state.approval_chain_service,
    )
    app.state.agent_loop_service.ceo_reviewer = app.state.ceo_reviewer_service
    app.state.ceo_reviewer_service.ws_manager = ws_manager
    logger.info("E-4d: CEOReviewerService initialized — executive oversight wired into agent loops")

    # ── E-5: Skill Factory ──
    app.state.skill_factory_service = SkillFactoryService(
        repo_root=Path(__file__).resolve().parents[3],
        execution_service=app.state.execution_service,
        skill_service=app.state.skill_service,
        audit_service=app.state.audit_service,
    )
    logger.info("E-5: SkillFactoryService initialized")

    # ── Skill Request Workflow ──
    app.state.skill_request_service = SkillRequestService()
    logger.info("Skill Request Workflow initialized")

    # ── P-8: Skills Marketplace ──
    from app.services.skill_marketplace_service import SkillMarketplaceService
    app.state.skill_marketplace_service = SkillMarketplaceService(
        repo_root=Path(__file__).resolve().parents[3],
        skill_service=app.state.skill_service,
    )
    logger.info("P-8: SkillMarketplaceService initialized")

    # ── E-13: Mega Project Service ──
    app.state.mega_project_service = MegaProjectService(
        repo_root=Path(__file__).resolve().parents[3],
        project_service=app.state.project_service,
        team_service=app.state.team_service,
        execution_service=app.state.execution_service,
        message_store=message_store,
    )
    logger.info("E-13: MegaProjectService initialized")

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

    # ── Missions: Asana Bridge + MissionManager ──
    _asana_token = os.environ.get("ASANA_ACCESS_TOKEN", "")
    if not _asana_token:
        _env_file = Path(__file__).resolve().parents[3] / "config" / ".env"
        if _env_file.exists():
            for _line in _env_file.read_text().splitlines():
                if _line.strip().startswith("ASANA_ACCESS_TOKEN="):
                    _asana_token = _line.split("=", 1)[1].strip().strip("\"'")
                    break
    if _asana_token:
        app.state.asana_bridge = AsanaBridge(_asana_token)
        app.state.mission_manager_service = MissionManagerService(
            asana_bridge=app.state.asana_bridge,
            execution_service=app.state.execution_service,
            repo_root=Path(__file__).resolve().parents[3],
        )
        # Wire vector memory for knowledge accumulation on mission completion
        if hasattr(app.state, "vector_memory"):
            app.state.mission_manager_service.vector_memory = app.state.vector_memory
        # Wire event bus for cross-service notifications
        if hasattr(app.state, "event_bus"):
            app.state.mission_manager_service.event_bus = app.state.event_bus
        logger.info("Missions: AsanaBridge + MissionManagerService initialized (vector_memory=%s)",
                     "wired" if hasattr(app.state, "vector_memory") else "none")
    else:
        logger.warning("Missions: ASANA_ACCESS_TOKEN not found — MissionManager unavailable")

    # P-9: LanguageService available in app.services.language_service but
    # not initialized here — no router uses it yet (MENA localization planned).

    # ── E-9 Fix: Skill Wiring ──
    # ── E-9 Gap Fix: Global State + Priority + Recovery ──
    app.state.global_state = GlobalStateService()
    app.state.priority_engine = PriorityEngine(global_state=app.state.global_state)
    app.state.failure_recovery = FailureRecoveryService(global_state=app.state.global_state)
    logger.info("E-9: GlobalState + PriorityEngine + FailureRecovery initialized")

    app.state.skill_agent_mapping = SkillAgentMappingService()
    app.state.skill_chain_wiring = SkillChainWiringService(
        skill_agent_mapping=app.state.skill_agent_mapping,
        bridge_manager=app.state.bridge_manager,
    )
    # Wire skill_agent_mapping into agent loops for broadcast/peer messaging
    app.state.agent_loop_service.skill_agent_mapping = app.state.skill_agent_mapping

    # Wire skill_agent_mapping into execution_service for delegation
    app.state.execution_service.skill_agent_mapping = app.state.skill_agent_mapping

    # ── Tool Access Service — direct tool access from agent loops ──
    app.state.tool_access_service = ToolAccessService(Path(__file__).resolve().parents[3])
    app.state.agent_loop_service.tool_access_service = app.state.tool_access_service
    # Wire tool access to agent chat so agents can actually execute actions
    agent_chat_service.tool_access_service = app.state.tool_access_service
    agent_chat_service.execution_service = app.state.execution_service
    agent_chat_service.knowledge_base = app.state.knowledge_base_service
    agent_chat_service.vector_memory = app.state.vector_memory
    logger.info("E-9: Skill Agent Mapping + Chain Wiring + ToolAccessService initialized (wired to chat + KB + VectorMemory)")

    # ── E-10: Revenue Engine ──
    app.state.event_bus = EventBusService()
    app.state.pipeline_service = PipelineService(
        global_state=app.state.global_state,
        event_bus=app.state.event_bus,
    )
    app.state.catalog_service = CatalogService()
    app.state.ab_test_service = ABTestService(global_state=app.state.global_state)
    app.state.attribution_service = AttributionService(global_state=app.state.global_state)
    logger.info("E-10: Revenue Engine initialized (pipeline + catalog + A/B + attribution + events)")

    # ── E-11: Client Lifecycle ──
    app.state.onboarding_service = OnboardingService(
        global_state=app.state.global_state,
        event_bus=app.state.event_bus,
    )
    app.state.deliverable_service = DeliverableService(
        global_state=app.state.global_state,
        event_bus=app.state.event_bus,
    )
    app.state.work_log_service = WorkLogService()
    app.state.churn_service = ChurnService(
        global_state=app.state.global_state,
        event_bus=app.state.event_bus,
    )
    logger.info("E-11: Client Lifecycle initialized (onboarding + deliverables + churn)")

    # ── Wire event_bus + work_log into AgentLoopService (post-wire: E-10/E-11 created after E-4a) ──
    app.state.agent_loop_service.event_bus = app.state.event_bus
    app.state.agent_loop_service.work_log_service = app.state.work_log_service
    app.state.agent_loop_service.message_pool = app.state.message_pool
    app.state.agent_loop_service.subscribe_events()
    logger.info("Event bus + message_pool wired to AgentLoopService (9 event subscriptions)")

    # ── E-4a+: TaskWorkflowService (structured task execution) ──
    app.state.task_workflow_service = TaskWorkflowService(
        execution_service=app.state.execution_service,
        event_bus=app.state.event_bus,
        brain_service=app.state.brain_service,
    )
    app.state.agent_loop_service.task_workflow_service = app.state.task_workflow_service
    app.state.task_workflow_service.ceo_reviewer = app.state.ceo_reviewer_service
    logger.info("E-4a+: TaskWorkflowService initialized and wired to AgentLoopService + CEO phase gates")

    # ── A2A Protocol Service ──
    from app.services.a2a_service import A2AService
    app.state.a2a_service = A2AService(
        agent_loop_service=app.state.agent_loop_service,
        task_workflow_service=getattr(app.state, "task_workflow_service", None),
    )
    logger.info("A2A: Service initialized with %d agent cards", len(app.state.a2a_service.get_all_cards()))

    # ── CC-TD: Task Dispatch Service ──
    app.state.task_dispatch_service = TaskDispatchService(
        agent_loop_service=app.state.agent_loop_service,
        notification_service=app.state.notification_service,
        activity_log_service=getattr(app.state, "activity_log_service", None),
        event_bus=app.state.event_bus,
        audit_service=app.state.audit_service,
    )
    logger.info("CC-TD: TaskDispatchService initialized")

    # ── E-12: Full Autonomous Operation ──
    app.state.metrics_service = MetricsService(
        pipeline=app.state.pipeline_service,
        attribution=app.state.attribution_service,
        global_state=app.state.global_state,
        ab_test=app.state.ab_test_service,
        churn=app.state.churn_service,
        bridge_manager=app.state.bridge_manager,
        guardrail=app.state.guardrail_service,
        skill_agent_mapping=app.state.skill_agent_mapping,
    )
    app.state.data_lifecycle = DataLifecycleService()
    app.state.self_improvement = SelfImprovementService(
        global_state=app.state.global_state,
        metrics=app.state.metrics_service,
        pipeline=app.state.pipeline_service,
        skill_agent_mapping=app.state.skill_agent_mapping,
        priority_engine=app.state.priority_engine,
    )
    logger.info("E-12: Full Autonomous Operation initialized (metrics + data lifecycle + self-improvement)")

    # ── OpenClaw Adoptions: Queue + Rate Limiter ──
    app.state.task_queue = TaskQueueService(max_workers=3)
    await app.state.task_queue.start()
    app.state.rate_limiter = RateLimiterService()
    logger.info("Infra: TaskQueue (3 workers) + RateLimiter (6 limiters) initialized")

    # ── E-12 FINAL: True Autonomous Operation ──
    app.state.insight_bridge = InsightActionBridge(
        priority_engine=app.state.priority_engine,
        metrics=app.state.metrics_service,
        global_state=app.state.global_state,
    )
    app.state.autonomous_loop = AutonomousLoopService(
        priority_engine=app.state.priority_engine,
        chain_wiring=app.state.skill_chain_wiring,
        skill_agent_mapping=app.state.skill_agent_mapping,
        global_state=app.state.global_state,
        failure_recovery=app.state.failure_recovery,
        guardrail=app.state.guardrail_service,
        task_queue=app.state.task_queue,
    )
    app.state.autonomous_scheduler = AutonomousSchedulerService(
        failure_recovery=app.state.failure_recovery,
    )

    # Register scheduled jobs
    app.state.autonomous_scheduler.register(
        "metrics_snapshot", 86400, app.state.metrics_service.take_snapshot,
        "Daily metrics snapshot")
    app.state.autonomous_scheduler.register(
        "weekly_audit", 604800, app.state.self_improvement.run_weekly_audit,
        "Weekly self-audit")
    app.state.autonomous_scheduler.register(
        "data_maintenance", 21600, app.state.data_lifecycle.run_maintenance,
        "Data lifecycle maintenance (6h)")
    app.state.autonomous_scheduler.register(
        "metric_thresholds", 3600, app.state.insight_bridge.check_metrics,
        "Hourly metric threshold check")

    # ── Content & Social Automation Jobs ──
    async def _content_calendar_job():
        """Generate weekly content calendar via cnt-06."""
        await app.state.execution_service.queue_execution(
            skill_id="cnt-06-content-calendar-builder",
            agent_id="social_media_lead",
            inputs={"business_context": "NemoClaw AI company", "channels": "tiktok,instagram,linkedin,twitter"},
        )

    async def _social_scrape_job():
        """Run social intelligence scraping via int-05."""
        await app.state.execution_service.queue_execution(
            skill_id="int-05-cross-platform-scraper",
            agent_id="strategy_lead",
            inputs={"targets": "AI automation,AI agents,SaaS", "platforms": "tiktok,instagram,linkedin"},
        )

    async def _agent_self_promo_job():
        """Generate self-promotion content for all agents via cnt-11."""
        await app.state.execution_service.queue_execution(
            skill_id="cnt-11-agent-self-promo-generator",
            agent_id="social_media_lead",
            inputs={"agent_count": "11", "platforms": "tiktok,instagram"},
        )

    app.state.autonomous_scheduler.register(
        "content_calendar", 604800, _content_calendar_job,
        "Weekly content calendar generation (Zara)")
    app.state.autonomous_scheduler.register(
        "social_intelligence", 43200, _social_scrape_job,
        "Social intelligence scraping (12h)")
    app.state.autonomous_scheduler.register(
        "agent_self_promo", 86400, _agent_self_promo_job,
        "Daily agent self-promotion content")

    # Start scheduler
    await app.state.autonomous_scheduler.start_all()
    app.state.prompt_optimization = PromptOptimizationService(
        global_state=app.state.global_state,
    )
    logger.info("E-12+: Prompt Optimization Service initialized")

    # Start the autonomous execution loop — pulls from PriorityEngine continuously
    await app.state.autonomous_loop.start()
    logger.info("E-12 FINAL: Autonomous Loop RUNNING + Scheduler + InsightBridge — SYSTEM IS FULLY AUTONOMOUS")

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


# ── P-7: Security Headers Middleware ──
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to every HTTP response."""

    HEADERS = {
        "Strict-Transport-Security": "max-age=63072000; includeSubDomains",
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Content-Security-Policy": (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "connect-src 'self' ws: wss:"
        ),
        "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    }

    async def dispatch(self, request: StarletteRequest, call_next):
        response: StarletteResponse = await call_next(request)
        for header, value in self.HEADERS.items():
            response.headers[header] = value
        return response


app.add_middleware(SecurityHeadersMiddleware)

# Structured logging middleware — assigns X-Correlation-ID, logs every request
app.add_middleware(_make_logging_middleware())

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
from app.api.routers import ceo_review as ceo_review_router
app.include_router(ceo_review_router.router)  # E-4d: CEO Review Gate
app.include_router(skill_factory_router.router)  # E-5: Skill Factory
app.include_router(skill_requests_router.router)  # Skill Request Workflow
app.include_router(marketplace_router.router)  # P-8: Skills Marketplace
app.include_router(self_build_router.router)  # E-7b: Self-Build
app.include_router(bridges_router.router)  # E-8: Bridges
app.include_router(skill_wiring_router.router)  # E-9: Skill Wiring
app.include_router(revenue_router.router)  # E-10: Revenue
app.include_router(lifecycle_router.router)  # E-11: Lifecycle
app.include_router(autonomous_router.router)  # E-12: Autonomous
app.include_router(infra_router.router)  # Infra: Queue + Rate Limits
app.include_router(activity_router.router)  # P-2: Activity Event Log
app.include_router(mega_projects_router.router)  # E-13: Mega Projects
from app.api.routers import research as research_router
app.include_router(research_router.router)  # E-14: Research
app.include_router(a2a_discovery_router)  # A2A: Discovery (public)
app.include_router(a2a_task_router)  # A2A: Tasks (auth)
app.include_router(missions_router.router)  # Missions (Asana-backed)


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

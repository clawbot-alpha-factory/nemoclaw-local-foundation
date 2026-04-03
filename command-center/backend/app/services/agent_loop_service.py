"""
NemoClaw Execution Engine — AgentLoopService (E-4a)

Continuous execution loops for ALL 11 agents.
Cycle: observe → decide → act → learn → recover → idle

All agents run autonomous loops with role-appropriate tick intervals:
- L1/L2/L3 (strategic): 10s ticks, lower proactive split
- L4 (execution): 5s ticks, higher proactive split

NEW FILE: command-center/backend/app/services/agent_loop_service.py
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("cc.agent_loop")


# ── Loop States ────────────────────────────────────────────────────────

class LoopState:
    STOPPED = "stopped"
    STARTING = "starting"
    OBSERVING = "observing"
    DECIDING = "deciding"
    ACTING = "acting"
    LEARNING = "learning"
    RECOVERING = "recovering"
    IDLE = "idle"
    HUNTING = "hunting"
    STOPPING = "stopping"


# ── Agents eligible for loops ──────────────────────────────────────────

# Full autonomy mode (2026-04-02): ALL 11 agents with fast ticks, proactive behavior
LOOP_AGENTS = {
    # L1 — Executive
    "executive_operator": {
        "tick_seconds": 10,
        "priority_split": 0.3,  # 30% assigned, 70% strategic oversight
        "idle_behavior": "Review system health, audit agent performance, resolve cross-agent conflicts",
    },
    # L2 — Strategy & Operations
    "strategy_lead": {
        "tick_seconds": 10,
        "priority_split": 0.4,
        "idle_behavior": "Scan market signals, update competitive intelligence, refine growth strategy",
    },
    "operations_lead": {
        "tick_seconds": 10,
        "priority_split": 0.4,
        "idle_behavior": "Monitor system health, optimize workflows, plan capacity and skill gaps",
    },
    # L3 — Domain Leads
    "product_architect": {
        "tick_seconds": 10,
        "priority_split": 0.5,
        "idle_behavior": "Review architecture decisions, prototype new features, audit technical debt",
    },
    "growth_revenue_lead": {
        "tick_seconds": 5,
        "priority_split": 0.5,
        "idle_behavior": "Analyze revenue pipeline, identify pricing opportunities, run experiments",
    },
    "narrative_content_lead": {
        "tick_seconds": 5,
        "priority_split": 0.5,
        "idle_behavior": "Plan content calendar, draft brand narratives, review content quality",
    },
    "engineering_lead": {
        "tick_seconds": 10,
        "priority_split": 0.5,
        "idle_behavior": "Review code quality, plan implementations, audit CI/CD pipeline health",
    },
    # L4 — Execution Specialists
    "sales_outreach_lead": {
        "tick_seconds": 5,
        "priority_split": 0.5,
        "idle_behavior": "Scan pipeline for stale leads and follow-up opportunities",
    },
    "marketing_campaigns_lead": {
        "tick_seconds": 5,
        "priority_split": 0.5,
        "idle_behavior": "Analyze campaign performance and propose optimizations",
    },
    "client_success_lead": {
        "tick_seconds": 5,
        "priority_split": 0.5,
        "idle_behavior": "Check client health scores and flag churn risks",
    },
    "social_media_lead": {
        "tick_seconds": 5,
        "priority_split": 0.6,  # 60% proactive — content creation driven
        "idle_behavior": "Create viral content, monitor social engagement, respond to comments and trends",
    },
}


class AgentLoop:
    """A single agent's execution loop."""

    def __init__(self, agent_id: str, config: dict[str, Any]):
        self.agent_id = agent_id
        self.config = config
        self.state = LoopState.STOPPED
        self.tick_seconds = config.get("tick_seconds", 5)  # Fast ticks (2026-04-02)
        self.priority_split = config.get("priority_split", 0.5)  # Proactive agents
        self.idle_behavior = config.get("idle_behavior", "Wait for tasks")

        # Stats
        self.ticks = 0
        self.tasks_executed = 0
        self.tasks_failed = 0
        self.idle_hunts = 0
        self.total_cost = 0.0
        self.started_at: datetime | None = None
        self.last_tick: datetime | None = None
        self.current_task: str | None = None
        self.last_error: str | None = None

        # Control
        self._task: asyncio.Task | None = None
        self._running = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "state": self.state,
            "tick_seconds": self.tick_seconds,
            "ticks": self.ticks,
            "tasks_executed": self.tasks_executed,
            "tasks_failed": self.tasks_failed,
            "idle_hunts": self.idle_hunts,
            "total_cost": self.total_cost,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "last_tick": self.last_tick.isoformat() if self.last_tick else None,
            "current_task": self.current_task,
            "last_error": self.last_error,
            "uptime_seconds": int((datetime.now(timezone.utc) - self.started_at).total_seconds()) if self.started_at else 0,
        }

    def to_checkpoint(self) -> dict[str, Any]:
        """State for checkpoint persistence."""
        return {
            "agent_id": self.agent_id,
            "loop_state": self.state,
            "ticks": self.ticks,
            "tasks_executed": self.tasks_executed,
            "tasks_failed": self.tasks_failed,
            "idle_hunts": self.idle_hunts,
            "total_cost": self.total_cost,
        }


class AgentLoopService:
    """
    Manages all agent execution loops.

    Lifecycle:
      - start_agent(id) → creates async loop
      - stop_agent(id) → graceful shutdown + checkpoint
      - start_all() / stop_all() → bulk operations
      - shutdown() → emergency halt (revenue shutdown)
    """

    def __init__(
        self,
        execution_service=None,
        memory_service=None,
        scheduler_service=None,
        checkpoint_service=None,
        notification_service=None,
        event_bus=None,
        work_log_service=None,
        skill_agent_mapping=None,
        tool_access_service=None,
        task_workflow_service=None,
        activity_log_service=None,
        vector_memory=None,
    ):
        self.execution_service = execution_service
        self.memory_service = memory_service
        self.scheduler_service = scheduler_service
        self.checkpoint_service = checkpoint_service
        self.notification_service = notification_service
        self.event_bus = event_bus
        self.work_log_service = work_log_service
        self.skill_agent_mapping = skill_agent_mapping
        self.tool_access_service = tool_access_service
        self.task_workflow_service = task_workflow_service
        self.activity_log_service = activity_log_service
        self.vector_memory = vector_memory
        self.loops: dict[str, AgentLoop] = {}
        self._shutdown = False
        self._skill_failure_counts: dict[str, int] = {}

        logger.info(
            "AgentLoopService initialized (%d eligible agents)",
            len(LOOP_AGENTS),
        )

    async def start_agent(self, agent_id: str) -> dict[str, Any]:
        """Start an agent's execution loop."""
        if agent_id not in LOOP_AGENTS:
            return {"success": False, "reason": f"Agent {agent_id} not eligible for loops"}

        if agent_id in self.loops and self.loops[agent_id]._running:
            return {"success": False, "reason": f"Agent {agent_id} already running"}

        config = LOOP_AGENTS[agent_id]
        loop = AgentLoop(agent_id, config)

        # Restore from checkpoint if available
        if self.checkpoint_service:
            checkpoint = self.checkpoint_service.load(agent_id)
            if checkpoint:
                loop.ticks = checkpoint.get("ticks", 0)
                loop.tasks_executed = checkpoint.get("tasks_executed", 0)
                loop.tasks_failed = checkpoint.get("tasks_failed", 0)
                loop.idle_hunts = checkpoint.get("idle_hunts", 0)
                loop.total_cost = checkpoint.get("total_cost", 0.0)
                logger.info("Restored checkpoint for %s (ticks=%d)", agent_id, loop.ticks)

        loop._running = True
        loop.state = LoopState.STARTING
        loop.started_at = datetime.now(timezone.utc)
        loop._task = asyncio.create_task(self._run_loop(loop))
        self.loops[agent_id] = loop

        logger.info("Started agent loop: %s (tick=%ds)", agent_id, loop.tick_seconds)
        return {"success": True, "agent_id": agent_id, "state": loop.state}

    async def stop_agent(self, agent_id: str) -> dict[str, Any]:
        """Stop an agent's execution loop gracefully."""
        loop = self.loops.get(agent_id)
        if not loop or not loop._running:
            return {"success": False, "reason": f"Agent {agent_id} not running"}

        loop._running = False
        loop.state = LoopState.STOPPING

        if loop._task:
            loop._task.cancel()
            try:
                await loop._task
            except asyncio.CancelledError:
                pass

        loop.state = LoopState.STOPPED

        # Save checkpoint
        if self.checkpoint_service:
            self.checkpoint_service.save(agent_id, loop.to_checkpoint())

        logger.info("Stopped agent loop: %s (ticks=%d)", agent_id, loop.ticks)
        return {"success": True, "agent_id": agent_id, "final_state": loop.to_dict()}

    async def start_all(self) -> list[dict[str, Any]]:
        """Start all eligible agent loops."""
        results = []
        for agent_id in LOOP_AGENTS:
            result = await self.start_agent(agent_id)
            results.append(result)
        return results

    async def stop_all(self) -> list[dict[str, Any]]:
        """Stop all running agent loops."""
        results = []
        for agent_id in list(self.loops.keys()):
            result = await self.stop_agent(agent_id)
            results.append(result)
        return results

    async def shutdown(self) -> dict[str, Any]:
        """Emergency shutdown — stop everything immediately."""
        self._shutdown = True
        logger.warning("EMERGENCY SHUTDOWN initiated")

        results = await self.stop_all()

        # Stop execution service if available
        if self.execution_service:
            await self.execution_service.stop()

        return {
            "shutdown": True,
            "agents_stopped": len(results),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def get_loop_status(self, agent_id: str) -> dict[str, Any] | None:
        """Get status of an agent's loop."""
        loop = self.loops.get(agent_id)
        if not loop:
            return None
        return loop.to_dict()

    def get_all_status(self) -> dict[str, Any]:
        """Get status of all loops."""
        running = [a for a, l in self.loops.items() if l._running]
        return {
            "total_eligible": len(LOOP_AGENTS),
            "running": len(running),
            "running_agents": running,
            "loops": {
                agent_id: loop.to_dict()
                for agent_id, loop in self.loops.items()
            },
        }

    def get_engine_status(self) -> dict[str, Any]:
        """Full engine status combining execution + loops."""
        loop_status = self.get_all_status()
        exec_status = {}
        if self.execution_service:
            exec_status = self.execution_service.get_state().model_dump()

        return {
            "engine": "running" if not self._shutdown else "shutdown",
            "agent_loops": loop_status,
            "execution": exec_status,
            "shutdown": self._shutdown,
        }

    # ── Task Dispatch ─────────────────────────────────────────────────

    async def dispatch_task(
        self,
        agent_id: str,
        goal: str,
        source: str = "api",
    ) -> dict[str, Any]:
        """
        Dispatch a task to a specific agent.

        1. Create workflow via OrchestratorService (task_workflow_service)
        2. Assign to agent via ExecutionService
        3. Log to ActivityLog
        4. Notify agent via notification_service
        5. Return workflow_id for tracking

        Args:
            agent_id: Target agent (must be in LOOP_AGENTS)
            goal: Natural-language goal to decompose and execute
            source: Origin — "comms", "projects", or "api"
        """
        if agent_id not in LOOP_AGENTS:
            return {"success": False, "error": f"Unknown agent: {agent_id}"}

        # 1. Create workflow (decompose goal → plan → tasks)
        workflow = None
        if self.task_workflow_service:
            try:
                workflow = await self.task_workflow_service.create_plan(goal)
            except Exception as e:
                logger.error("dispatch_task: planning failed for %s: %s", agent_id, e)
                return {"success": False, "error": f"Planning failed: {e}"}

            if workflow.status == "failed":
                return {
                    "success": False,
                    "error": workflow.error or "Planning failed",
                    "workflow_id": workflow.workflow_id,
                }
        else:
            logger.warning("dispatch_task: no task_workflow_service — skipping planning")

        workflow_id = workflow.workflow_id if workflow else None

        # 2. Assign tasks to agent via ExecutionService
        if self.execution_service and workflow and workflow.tasks:
            from app.domain.engine_models import ExecutionRequest, LLMTier

            for task in workflow.tasks:
                request = ExecutionRequest(
                    skill_id=task.get("skill", task.get("skill_id", "")),
                    inputs=task.get("inputs", {}),
                    agent_id=agent_id,
                    tier=LLMTier.STANDARD,
                )
                self.execution_service.submit(request)

            logger.info(
                "dispatch_task: queued %d tasks for %s (workflow %s)",
                len(workflow.tasks), agent_id, workflow_id[:8],
            )

        # 3. Log to activity log
        if self.activity_log_service:
            await self.activity_log_service.append(
                category="execution",
                action="task_dispatched",
                actor_type="system",
                actor_id=source,
                entity_type="task",
                entity_id=workflow_id or "",
                summary=f"Dispatched to {agent_id}: {goal[:120]}",
                details={
                    "agent_id": agent_id,
                    "goal": goal,
                    "source": source,
                    "workflow_id": workflow_id,
                    "task_count": len(workflow.tasks) if workflow else 0,
                },
            )

        # 4. Notify agent
        if self.notification_service:
            self.notification_service.notify_agent(
                from_agent="system",
                to_agent=agent_id,
                intent="task_assigned",
                message=f"New task from {source}: {goal[:200]}",
            )

        return {
            "success": True,
            "workflow_id": workflow_id,
            "agent_id": agent_id,
            "source": source,
            "task_count": len(workflow.tasks) if workflow else 0,
        }

    # ── Event Bus Integration ─────────────────────────────────────────

    def subscribe_events(self) -> None:
        """Subscribe to system events via event bus."""
        if not self.event_bus:
            return
        self.event_bus.subscribe("skill_completed", self._on_skill_completed)
        self.event_bus.subscribe("skill_failed", self._on_skill_failed)
        self.event_bus.subscribe("demand_detected", self._on_demand_detected)
        self.event_bus.subscribe("budget_warning", self._on_budget_warning)
        self.event_bus.subscribe("content_viral", self._on_content_viral)
        self.event_bus.subscribe("task_started", self._on_task_started)
        self.event_bus.subscribe("task_completed", self._on_task_completed)
        self.event_bus.subscribe("task_failed", self._on_task_failed)
        self.event_bus.subscribe("deal_created", self._on_deal_created)
        logger.info("AgentLoopService subscribed to 9 event types")

    def _on_skill_completed(self, event) -> None:
        """Log completed skill to work log and reset failure counter."""
        data = event.data
        skill_id = data.get("skill_id", "")
        if skill_id and skill_id in self._skill_failure_counts:
            del self._skill_failure_counts[skill_id]
        if not self.work_log_service:
            return
        self.work_log_service.log_work(
            agent_id=data.get("agent_id", "system"),
            project_id=data.get("project_id", "default"),
            action="skill_completed",
            details=f"Skill {skill_id or '?'} completed successfully",
            artifacts=data.get("artifacts"),
        )

    def _on_skill_failed(self, event) -> None:
        """Log failed skill, track consecutive failures, escalate at 3."""
        data = event.data
        skill_id = data.get("skill_id", "?")

        # Track consecutive failures
        self._skill_failure_counts[skill_id] = self._skill_failure_counts.get(skill_id, 0) + 1
        count = self._skill_failure_counts[skill_id]

        if self.work_log_service:
            self.work_log_service.log_work(
                agent_id=data.get("agent_id", "system"),
                project_id=data.get("project_id", "default"),
                action="skill_failed",
                details=f"Skill {skill_id} failed ({count}x): {data.get('error', 'unknown')}",
            )

        # Escalate after 3 consecutive failures
        if count >= 3 and self.notification_service:
            team_agents = ["engineering_lead", "operations_lead"]
            lane_id = self.notification_service.create_task_channel(
                task_name=f"Debug: {skill_id} ({count} failures)",
                agent_ids=team_agents,
                lead_agent="engineering_lead",
            )
            self.notification_service.notify_user(
                agent_id="engineering_lead",
                category="blocker",
                message=f"Skill {skill_id} failed {count}x consecutively. "
                        f"Debug team channel created: {lane_id}. "
                        f"Last error: {data.get('error', 'unknown')[:200]}",
                priority="high",
            )
            # Reset counter after escalation
            self._skill_failure_counts[skill_id] = 0
            logger.warning("Skill %s escalated after %d failures → %s", skill_id, count, lane_id)

    def _on_demand_detected(self, event) -> None:
        """Queue research task for strategy_lead when demand is detected."""
        data = event.data
        logger.info("Demand detected — queuing research for strategy_lead: %s", data.get("signal", ""))
        if self.execution_service:
            from app.domain.engine_models import ExecutionRequest, LLMTier
            request = ExecutionRequest(
                skill_id=data.get("skill_id", "k55-seo-keyword-researcher"),
                inputs={"query": data.get("signal", ""), "source": event.source},
                agent_id="strategy_lead",
                tier=LLMTier.STANDARD,
            )
            self.execution_service.submit(request)

    def _on_budget_warning(self, event) -> None:
        """Send budget alert to system lane (once, not per-agent)."""
        data = event.data
        msg = f"Budget warning: {data.get('provider', '?')} at {data.get('usage_pct', '?')}% — {data.get('message', '')}"
        logger.warning(msg)
        if self.notification_service:
            self.notification_service.notify_user(
                agent_id="executive_operator",
                category="blocker",
                message=msg,
                priority="high",
            )

    def _on_content_viral(self, event) -> None:
        """Amplify viral content: queue repurposer + create team channel."""
        data = event.data
        title = data.get("title", data.get("url", "?"))
        msg = f"Content going viral: {title}"
        logger.info(msg)

        # Queue content repurposer to amplify
        if self.execution_service:
            from app.domain.engine_models import ExecutionRequest, LLMTier
            request = ExecutionRequest(
                skill_id="cnt-04-content-repurposer",
                inputs={
                    "source_content": title,
                    "url": data.get("url", ""),
                    "repurpose_goal": "Amplify viral content across channels",
                },
                agent_id="social_media_lead",
                tier=LLMTier.STANDARD,
                priority=2,
            )
            self.execution_service.submit(request)
            logger.info("Queued cnt-04-content-repurposer for viral content: %s", title)

        # Create team channel for coordination
        if self.notification_service:
            team_agents = ["social_media_lead", "marketing_campaigns_lead"]
            lane_id = self.notification_service.create_task_channel(
                task_name=f"Amplify: {title[:60]}",
                agent_ids=team_agents,
                lead_agent="social_media_lead",
            )
            for agent_id in team_agents:
                self.notification_service.notify_user(
                    agent_id=agent_id,
                    category="discovery",
                    message=f"{msg} — Team channel: {lane_id}",
                )

    def _on_deal_created(self, event) -> None:
        """Generate proposal for new deal + create sales team channel."""
        data = event.data
        deal_name = data.get("deal_name", data.get("company", "New deal"))
        logger.info("Deal created: %s — queuing proposal generator", deal_name)

        # Queue proposal generator
        if self.execution_service:
            from app.domain.engine_models import ExecutionRequest, LLMTier
            request = ExecutionRequest(
                skill_id="biz-01-proposal-generator",
                inputs={
                    "deal_name": deal_name,
                    "company": data.get("company", ""),
                    "value": str(data.get("value", "")),
                    "context": data.get("context", ""),
                },
                agent_id="sales_outreach_lead",
                tier=LLMTier.STANDARD,
                priority=2,
            )
            self.execution_service.submit(request)

        # Create team channel for deal coordination
        if self.notification_service:
            team_agents = ["sales_outreach_lead", "growth_revenue_lead"]
            self.notification_service.create_task_channel(
                task_name=f"Deal: {deal_name[:60]}",
                agent_ids=team_agents,
                lead_agent="sales_outreach_lead",
            )

    def _on_task_started(self, event) -> None:
        """Log workflow start to work log."""
        if not self.work_log_service:
            return
        data = event.data
        self.work_log_service.log_work(
            agent_id=data.get("agent_id", "system"),
            project_id=data.get("project_id", "default"),
            action="task_started",
            details=f"Workflow {data.get('workflow_id', '?')} started: {data.get('goal', '')[:100]}",
        )

    def _on_task_completed(self, event) -> None:
        """Log workflow completion and emit agent_idle for the freed agent."""
        data = event.data
        if self.work_log_service:
            self.work_log_service.log_work(
                agent_id=data.get("agent_id", "system"),
                project_id=data.get("project_id", "default"),
                action="task_completed",
                details=f"Workflow {data.get('workflow_id', '?')} completed",
            )
        # Emit agent_idle so other services know this agent is free
        if self.event_bus:
            self.event_bus.emit("agent_idle", {
                "agent_id": data.get("agent_id", ""),
                "freed_by": data.get("workflow_id", ""),
            }, source="agent_loop")

    def _on_task_failed(self, event) -> None:
        """Log workflow failure and broadcast blocker."""
        data = event.data
        if self.work_log_service:
            self.work_log_service.log_work(
                agent_id=data.get("agent_id", "system"),
                project_id=data.get("project_id", "default"),
                action="task_failed",
                details=f"Workflow {data.get('workflow_id', '?')} failed: {data.get('error', 'unknown')}",
            )
        if self.notification_service:
            agent_id = data.get("agent_id", "system")
            from app.services.agent_notification_service import VALID_AGENTS
            if agent_id in VALID_AGENTS:
                self.notification_service.notify_user(
                    agent_id=agent_id,
                    category="task_failed",
                    message=f"Workflow failed: {data.get('goal', '?')[:80]} — {data.get('error', '')}",
                    priority="high",
                )

    # ── Main Loop ──────────────────────────────────────────────────────

    async def _run_loop(self, loop: AgentLoop):
        """Main agent loop: observe → decide → act → learn → idle."""
        logger.info("Agent loop started: %s", loop.agent_id)

        try:
            while loop._running and not self._shutdown:
                loop.ticks += 1
                loop.last_tick = datetime.now(timezone.utc)

                try:
                    # ── OBSERVE ──
                    loop.state = LoopState.OBSERVING
                    context = await self._observe(loop)

                    # ── DECIDE ──
                    loop.state = LoopState.DECIDING
                    action = await self._decide(loop, context)

                    # ── ACT ──
                    if action:
                        loop.state = LoopState.ACTING
                        loop.current_task = action.get("description", "")
                        result = await self._act(loop, action)

                        # ── LEARN ──
                        loop.state = LoopState.LEARNING
                        await self._learn(loop, action, result)

                        if result.get("success"):
                            loop.tasks_executed += 1
                            loop.total_cost += result.get("cost", 0.0)
                        else:
                            loop.tasks_failed += 1
                            loop.last_error = result.get("error", "")
                            error = result.get("error", "Unknown error")
                            # Only send blocker for real failures (not generic)
                            if self.notification_service and error != "Unknown error":
                                self.notification_service.send_blocker_alert(
                                    agent_id=loop.agent_id,
                                    blocker=f"Task failed: {error}",
                                )

                        loop.current_task = None
                    else:
                        # ── IDLE / HUNT ──
                        loop.state = LoopState.HUNTING
                        loop.idle_hunts += 1
                        await self._idle_hunt(loop)

                    # ── DAILY DIGEST (every 500 ticks ~40-80 min) ──
                    if self.notification_service and loop.ticks % 500 == 0:
                        self.notification_service.send_daily_digest(loop.agent_id)

                    # ── CHECKPOINT ──
                    if self.checkpoint_service and loop.ticks % 10 == 0:
                        self.checkpoint_service.save(loop.agent_id, loop.to_checkpoint())

                except Exception as e:
                    loop.state = LoopState.RECOVERING
                    loop.last_error = str(e)
                    logger.error("Agent %s error on tick %d: %s", loop.agent_id, loop.ticks, e)

                # Sleep until next tick
                loop.state = LoopState.IDLE
                await asyncio.sleep(loop.tick_seconds)

        except asyncio.CancelledError:
            pass
        finally:
            loop.state = LoopState.STOPPED
            logger.info(
                "Agent loop ended: %s (ticks=%d, executed=%d, failed=%d)",
                loop.agent_id, loop.ticks, loop.tasks_executed, loop.tasks_failed,
            )

    async def _observe(self, loop: AgentLoop) -> dict[str, Any]:
        """Observe: gather context for decision-making."""
        context: dict[str, Any] = {
            "agent_id": loop.agent_id,
            "tick": loop.ticks,
            "scheduled_tasks": [],
            "pending_tasks": [],
        }

        # Check scheduled tasks
        if self.scheduler_service:
            due = self.scheduler_service.get_due_tasks(loop.agent_id)
            context["scheduled_tasks"] = [t.to_dict() for t in due]

        # Check execution queue for tasks assigned to this agent
        if self.execution_service:
            queue = self.execution_service.get_queue()
            context["pending_tasks"] = [
                e.model_dump() for e in queue
                if e.agent_id == loop.agent_id
            ]

        # Recall past experience from vector memory
        if self.vector_memory:
            try:
                memories = self.vector_memory.search(
                    "agent_memory",
                    f"recent tasks for {loop.agent_id}",
                    n_results=3,
                )
                context["past_experience"] = memories
            except Exception:
                context["past_experience"] = []

        return context

    async def _decide(self, loop: AgentLoop, context: dict[str, Any]) -> dict[str, Any] | None:
        """Decide: pick next action based on context."""
        # Priority 1: Scheduled tasks that are due
        scheduled = context.get("scheduled_tasks", [])
        for task in scheduled:
            if task.get("skill_id"):
                return {
                    "type": "scheduled",
                    "description": task["description"],
                    "skill_id": task["skill_id"],
                    "inputs": task.get("inputs", {}),
                    "task_id": task["task_id"],
                }

        # Priority 2: Pending execution tasks
        pending = context.get("pending_tasks", [])
        if pending:
            task = pending[0]
            return {
                "type": "queued",
                "description": f"Execute {task.get('skill_id', 'unknown')}",
                "execution_id": task.get("execution_id"),
            }

        # No action → idle
        return None

    async def _act(self, loop: AgentLoop, action: dict[str, Any]) -> dict[str, Any]:
        """Act: execute the chosen action. Uses browser via tool_access_service when needed."""
        action_type = action.get("type", "")

        # Browser actions — delegate to tool_access_service
        if action_type == "browser" and self.tool_access_service:
            browser_result, error = await self.tool_access_service.run_browser_task(
                agent_id=loop.agent_id,
                url=action.get("url", ""),
                actions=action.get("browser_actions", []),
            )
            if error:
                result = {"success": False, "error": f"Browser task failed: {error}"}
            else:
                result = {"success": True, "browser_result": browser_result, "cost": 0.0}
            self._emit_skill_event(loop, action, result)
            return result

        if action_type == "scheduled" and self.execution_service:
            # Route through TaskWorkflowService when available
            if self.task_workflow_service:
                goal = action.get("description", action.get("skill_id", "scheduled task"))
                wf_id = self.task_workflow_service.create_workflow(
                    goal=goal,
                    agent_id=loop.agent_id,
                    project_id=action.get("project_id"),
                )
                wf_result = await self.task_workflow_service.run_workflow(wf_id)
                result = {
                    "success": wf_result.get("success", False),
                    "workflow_id": wf_id,
                    "cost": 0.0,
                }
                if not wf_result.get("success"):
                    result["error"] = wf_result.get("error", "Workflow failed")
            else:
                from app.domain.engine_models import ExecutionRequest, LLMTier
                request = ExecutionRequest(
                    skill_id=action["skill_id"],
                    inputs=action.get("inputs", {}),
                    agent_id=loop.agent_id,
                    tier=LLMTier.STANDARD,
                )
                execution = self.execution_service.submit(request)
                result = {
                    "success": True,
                    "execution_id": execution.execution_id,
                    "cost": 0.0,
                }

            # Mark scheduled task as run
            if self.scheduler_service:
                task_id = action.get("task_id", "")
                task = self.scheduler_service.schedules.get(task_id)
                if task:
                    task.mark_run()

            self._emit_skill_event(loop, action, result)
            return result

        elif action_type == "queued":
            # Task already in execution queue — just acknowledge
            return {"success": True, "note": "Task already in execution queue"}

        result = {"success": False, "error": f"Unknown action type: {action_type}"}
        self._emit_skill_event(loop, action, result)
        return result

    def _emit_skill_event(self, loop: AgentLoop, action: dict[str, Any], result: dict[str, Any]) -> None:
        """Emit skill_completed or skill_failed event via event bus."""
        if not self.event_bus:
            return
        event_type = "skill_completed" if result.get("success") else "skill_failed"
        data: dict[str, Any] = {
            "agent_id": loop.agent_id,
            "skill_id": action.get("skill_id", ""),
            "action_type": action.get("type", ""),
        }
        if result.get("success"):
            data["execution_id"] = result.get("execution_id", "")
        else:
            data["error"] = result.get("error", "")
        self.event_bus.emit(event_type, data, source=f"agent_loop:{loop.agent_id}")

    def _is_high_tier_skill(self, skill_id: str) -> bool:
        """Check if a skill is tier 3/4 (shared across multiple agents)."""
        if not self.skill_agent_mapping or not skill_id:
            return False
        agents = self.skill_agent_mapping.get_skill_agents(skill_id)
        return len(agents) >= 2

    async def _learn(self, loop: AgentLoop, action: dict[str, Any], result: dict[str, Any]):
        """Learn: record outcome. Only broadcast meaningful results (not every tick)."""
        if not self.memory_service:
            return

        skill_id = action.get("skill_id", "")
        description = action.get("description", "")

        if result.get("success"):
            key = f"success_{action.get('type', 'unknown')}_{loop.ticks}"
            self.memory_service.learn(
                loop.agent_id,
                key=key,
                value=f"Completed: {description}",
                source="loop",
                importance=0.5,
            )
            # Only broadcast completions with a real description (not generic)
            if self.notification_service and description and len(description) > 10:
                self.notification_service.notify_user(
                    agent_id=loop.agent_id,
                    category="task_complete",
                    message=f"Completed [{skill_id or 'task'}]: {description}",
                )
            # Store success in vector memory for future recall
            if self.vector_memory:
                try:
                    summary = f"Completed {skill_id}: {description}"
                    self.vector_memory.add_memory(
                        "agent_memory", summary,
                        {"agent_id": loop.agent_id, "skill_id": skill_id, "type": "success"},
                        agent_id=loop.agent_id,
                    )
                    output_text = result.get("output", "")
                    if output_text and skill_id:
                        score = result.get("quality_score", 0)
                        self.vector_memory.add_skill_output(
                            skill_id, loop.agent_id, str(output_text)[:5000],
                            {"quality_score": score},
                        )
                except Exception:
                    pass
        else:
            error_msg = result.get("error", "unknown")
            key = f"failure_{action.get('type', 'unknown')}_{loop.ticks}"
            self.memory_service.learn(
                loop.agent_id,
                key=key,
                value=f"Failed: {error_msg}",
                source="loop",
                importance=1.0,
            )
            # Failures go to system lane (not all-hands broadcast)
            if self.notification_service and error_msg != "unknown":
                self.notification_service.notify_user(
                    agent_id=loop.agent_id,
                    category="task_failed",
                    message=f"Failed [{skill_id or 'task'}]: {error_msg}",
                    priority="high",
                )
            # Store failure/low-quality feedback in vector memory for learning
            if self.vector_memory:
                try:
                    quality_score = result.get("quality_score", 0)
                    critic_feedback = result.get("critic_feedback", error_msg)
                    if quality_score and quality_score < 8:
                        feedback = f"Task {skill_id} scored {quality_score}/10 because: {critic_feedback}"
                    else:
                        feedback = f"FAILURE: {skill_id} — {error_msg}"
                    self.vector_memory.add_memory(
                        "agent_memory", feedback,
                        {"agent_id": loop.agent_id, "skill_id": skill_id, "type": "failure"},
                        agent_id=loop.agent_id,
                    )
                except Exception:
                    pass

    async def _idle_hunt(self, loop: AgentLoop):
        """Idle: silently wait for work. No broadcasting, no peer spam."""
        logger.debug(
            "Agent %s idle hunt #%d: %s",
            loop.agent_id, loop.idle_hunts, loop.idle_behavior,
        )

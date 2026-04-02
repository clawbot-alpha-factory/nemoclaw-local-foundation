"""
NemoClaw Execution Engine — AgentLoopService (E-4a)

Continuous execution loops for agents.
Cycle: observe → decide → act → learn → recover → idle

3 initial agents: sales, marketing, client_success.
Each runs as an async task with configurable tick interval.

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

# Full autonomy mode (2026-04-02): fast ticks, balanced priority, proactive agents
LOOP_AGENTS = {
    "sales_outreach_lead": {
        "tick_seconds": 5,
        "priority_split": 0.5,  # 50% assigned, 50% self-generated (proactive)
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
    ):
        self.execution_service = execution_service
        self.memory_service = memory_service
        self.scheduler_service = scheduler_service
        self.checkpoint_service = checkpoint_service
        self.loops: dict[str, AgentLoop] = {}
        self._shutdown = False

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

                        loop.current_task = None
                    else:
                        # ── IDLE / HUNT ──
                        loop.state = LoopState.HUNTING
                        loop.idle_hunts += 1
                        await self._idle_hunt(loop)

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
        """Act: execute the chosen action."""
        action_type = action.get("type", "")

        if action_type == "scheduled" and self.execution_service:
            from app.domain.engine_models import ExecutionRequest, LLMTier
            request = ExecutionRequest(
                skill_id=action["skill_id"],
                inputs=action.get("inputs", {}),
                agent_id=loop.agent_id,
                tier=LLMTier.STANDARD,
            )
            execution = self.execution_service.submit(request)

            # Mark scheduled task as run
            if self.scheduler_service:
                task_id = action.get("task_id", "")
                task = self.scheduler_service.schedules.get(task_id)
                if task:
                    task.mark_run()

            return {
                "success": True,
                "execution_id": execution.execution_id,
                "cost": 0.0,  # actual cost tracked by ExecutionService
            }

        elif action_type == "queued":
            # Task already in execution queue — just acknowledge
            return {"success": True, "note": "Task already in execution queue"}

        return {"success": False, "error": f"Unknown action type: {action_type}"}

    async def _learn(self, loop: AgentLoop, action: dict[str, Any], result: dict[str, Any]):
        """Learn: record outcome for future decisions."""
        if not self.memory_service:
            return

        if result.get("success"):
            key = f"success_{action.get('type', 'unknown')}_{loop.ticks}"
            self.memory_service.learn(
                loop.agent_id,
                key=key,
                value=f"Completed: {action.get('description', '')}",
                source="loop",
                importance=0.5,
            )
        else:
            key = f"failure_{action.get('type', 'unknown')}_{loop.ticks}"
            self.memory_service.learn(
                loop.agent_id,
                key=key,
                value=f"Failed: {result.get('error', 'unknown')}",
                source="loop",
                importance=1.0,
            )

    async def _idle_hunt(self, loop: AgentLoop):
        """Idle: hunt for opportunities when no tasks are pending."""
        # Log idle behavior — actual hunting with LLM calls deferred to E-4b
        logger.debug(
            "Agent %s idle hunt #%d: %s",
            loop.agent_id, loop.idle_hunts, loop.idle_behavior,
        )

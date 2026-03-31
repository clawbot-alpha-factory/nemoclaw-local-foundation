"""
NemoClaw Execution Engine — Autonomous Loop Service (E-12)

Continuous execution loop: observe → decide → act → learn → repeat.
Dedup + cooldowns + global rate limit + performance-weighted selection.

NEW FILE: command-center/backend/app/services/autonomous_loop_service.py
"""
from __future__ import annotations
import asyncio, json, logging, time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("cc.autoloop")

EXECUTION_MODES = {
    "conservative": {"max_per_hour": 10, "tick_seconds": 120, "max_per_tick": 2},
    "balanced":     {"max_per_hour": 30, "tick_seconds": 60,  "max_per_tick": 5},
    "aggressive":   {"max_per_hour": 60, "tick_seconds": 30,  "max_per_tick": 10},
}


class ExecutionRecord:
    """Single decision→action→result chain record."""
    def __init__(self, trigger: str, skill_id: str, agent: str):
        self.trigger = trigger
        self.skill_id = skill_id
        self.agent = agent
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.result: str = "pending"
        self.detail: str = ""
        self.cost: float = 0
        self.completed_at: str | None = None

    def complete(self, result: str, detail: str = "", cost: float = 0) -> None:
        self.result = result
        self.detail = detail
        self.cost = cost
        self.completed_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "trigger": self.trigger, "skill_id": self.skill_id, "agent": self.agent,
            "result": self.result, "detail": self.detail[:200], "cost": self.cost,
            "started_at": self.started_at, "completed_at": self.completed_at,
        }


class AutonomousLoopService:
    """
    The heartbeat of autonomous operation.

    Every tick:
    1. Pull top tasks from PriorityEngine
    2. Dedup check (no duplicate within 1h, max 3 per skill per 24h)
    3. Guardrail check (spend ceiling)
    4. Global rate limit check
    5. Execute via SkillChainWiringService
    6. On failure → FailureRecoveryService
    7. On success → GlobalState.record_performance()
    8. Log decision→action→result chain
    """

    def __init__(self, priority_engine=None, chain_wiring=None, skill_agent_mapping=None,
                 global_state=None, failure_recovery=None, guardrail=None, task_queue=None):
        self.priority_engine = priority_engine
        self.chain_wiring = chain_wiring
        self.skill_agent_mapping = skill_agent_mapping
        self.global_state = global_state
        self.failure_recovery = failure_recovery
        self.guardrail = guardrail
        self.task_queue = task_queue

        self._running = False
        self._task: asyncio.Task | None = None
        self._mode = "conservative"
        self._tick_count = 0
        self._executions_this_hour: int = 0
        self._hour_reset: float = time.time()
        self._execution_log: list[ExecutionRecord] = []
        self._recent_skills: dict[str, list[float]] = defaultdict(list)  # skill_id → [timestamps]
        self._started_at: str | None = None

        self._persist_path = Path.home() / ".nemoclaw" / "autonomous-loop.json"
        self._persist_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info("AutonomousLoopService initialized (mode=%s)", self._mode)

    def set_mode(self, mode: str) -> dict[str, Any]:
        if mode not in EXECUTION_MODES:
            return {"error": f"Invalid mode. Available: {list(EXECUTION_MODES.keys())}"}
        self._mode = mode
        logger.info("Autonomous loop mode changed to: %s", mode)
        return {"mode": mode, "config": EXECUTION_MODES[mode]}

    async def start(self) -> dict[str, Any]:
        if self._running:
            return {"status": "already_running"}
        self._running = True
        self._started_at = datetime.now(timezone.utc).isoformat()
        self._task = asyncio.create_task(self._loop())
        logger.info("Autonomous loop STARTED (mode=%s)", self._mode)
        return {"status": "started", "mode": self._mode}

    async def stop(self) -> dict[str, Any]:
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
        logger.info("Autonomous loop STOPPED")
        return {"status": "stopped", "ticks": self._tick_count}

    async def _loop(self) -> None:
        """Main execution loop."""
        while self._running:
            try:
                await self._tick()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Autonomous loop error: %s", e)
                if self.failure_recovery:
                    await self.failure_recovery.handle_failure(
                        "autonomous_loop", str(e), "operations_lead"
                    )
            config = EXECUTION_MODES.get(self._mode, EXECUTION_MODES["conservative"])
            await asyncio.sleep(config["tick_seconds"])

    async def _tick(self) -> None:
        """Single loop tick."""
        self._tick_count += 1
        now = time.time()
        config = EXECUTION_MODES[self._mode]

        # Reset hourly counter
        if now - self._hour_reset > 3600:
            self._executions_this_hour = 0
            self._hour_reset = now

        # Global rate limit
        if self._executions_this_hour >= config["max_per_hour"]:
            logger.debug("Loop tick %d: rate limited (%d/%d/hr)",
                        self._tick_count, self._executions_this_hour, config["max_per_hour"])
            return

        if not self.priority_engine:
            return

        # Pull tasks
        tasks = self.priority_engine.get_top(config["max_per_tick"])
        if not tasks:
            return

        executed = 0
        for task in tasks:
            # Dedup: skip if same skill executed within 1 hour
            skill_id = task.get("metadata", {}).get("skill_id", task.get("task_type", ""))
            if self._is_duplicate(skill_id):
                logger.debug("Skip duplicate: %s (cooldown)", skill_id)
                continue

            # Guardrail check
            if self.guardrail:
                spend = getattr(self.guardrail, '_daily_spent', 0)
                ceiling = getattr(self.guardrail, '_ceiling', 20)
                if spend >= ceiling * 0.9:
                    logger.warning("Near spend ceiling (%.1f/%.1f) — pausing", spend, ceiling)
                    break

            # Execute
            record = ExecutionRecord(
                trigger=task.get("task_type", "priority"),
                skill_id=skill_id,
                agent=task.get("agent", ""),
            )

            try:
                if self.chain_wiring and skill_id:
                    result = await self.chain_wiring.execute_skill(
                        skill_id, {"input_data": task.get("description", "")}
                    )
                    if result.get("success"):
                        record.complete("success", result.get("stdout", "")[:200])
                        if self.global_state:
                            self.global_state.record_performance(
                                skill_id, True, 0, "", task.get("agent", "")
                            )
                    else:
                        record.complete("failed", result.get("error", ""))
                        if self.failure_recovery:
                            await self.failure_recovery.handle_failure(
                                skill_id, result.get("error", ""), task.get("agent", ""),
                                execute_fn=self.chain_wiring.execute_skill if self.chain_wiring else None,
                                inputs={"input_data": task.get("description", "")},
                            )
                else:
                    record.complete("skipped", "No chain_wiring or skill_id")

            except Exception as e:
                record.complete("error", str(e))
                logger.error("Execution error: %s", e)

            self._execution_log.append(record)
            self._record_skill_execution(skill_id)
            self._executions_this_hour += 1
            executed += 1

            # Remove from queue
            self.priority_engine.remove_task(task.get("item_id", ""))

        if executed > 0:
            logger.info("Loop tick %d: executed %d tasks (mode=%s, %d/hr)",
                       self._tick_count, executed, self._mode, self._executions_this_hour)
            self._persist()

    def _is_duplicate(self, skill_id: str) -> bool:
        """Check if skill was executed within cooldown period."""
        if not skill_id:
            return False
        now = time.time()
        # Clean old entries
        self._recent_skills[skill_id] = [t for t in self._recent_skills[skill_id] if now - t < 86400]
        recent = self._recent_skills[skill_id]
        # Within 1 hour = duplicate
        if any(now - t < 3600 for t in recent):
            return True
        # More than 3 in 24h = cooldown
        if len(recent) >= 3:
            return True
        return False

    def _record_skill_execution(self, skill_id: str) -> None:
        if skill_id:
            self._recent_skills[skill_id].append(time.time())

    def _persist(self) -> None:
        try:
            data = {
                "tick_count": self._tick_count,
                "mode": self._mode,
                "executions_this_hour": self._executions_this_hour,
                "recent_log": [r.to_dict() for r in self._execution_log[-50:]],
            }
            self._persist_path.write_text(json.dumps(data, indent=2, default=str))
        except Exception:
            pass

    def get_status(self) -> dict[str, Any]:
        config = EXECUTION_MODES[self._mode]
        return {
            "running": self._running,
            "mode": self._mode,
            "config": config,
            "tick_count": self._tick_count,
            "executions_this_hour": self._executions_this_hour,
            "max_per_hour": config["max_per_hour"],
            "started_at": self._started_at,
            "recent_executions": [r.to_dict() for r in self._execution_log[-10:]],
        }

    def get_decision_log(self, limit: int = 50) -> list[dict[str, Any]]:
        return [r.to_dict() for r in self._execution_log[-limit:]]

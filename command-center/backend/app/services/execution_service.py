"""
NemoClaw Execution Engine — ExecutionService (E-2)

Manages skill execution queue, subprocess invocation, dead letter queue,
and LLM tier routing. Skills run as subprocesses via skill-runner.py.

DECISION: Subprocess, not import — skill-runner.py uses LangGraph with
SqliteSaver which has dependency conflicts if imported directly.

NEW FILE: command-center/backend/app/services/execution_service.py
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any

from app.domain.engine_models import (
    ChainExecution,
    ChainRequest,
    ChainStatus,
    DeadLetterEntry,
    EngineState,
    ExecutionMode,
    ExecutionRequest,
    ExecutionStatus,
    LLMTier,
    TaskExecution,
    TraceContext,
)

logger = logging.getLogger("cc.execution")


# ── LLM Tier Routing (resolved from config/routing/routing-config.yaml) ───

def _resolve_tier_routing():
    """Build tier routing map from routing config instead of hardcoding (L-003)."""
    try:
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
        from lib.routing import resolve_alias
        tier_to_task = {
            LLMTier.LIGHTWEIGHT: "general_short",
            LLMTier.STANDARD: "moderate",
            LLMTier.COMPLEX: "complex_reasoning",
            LLMTier.CRITICAL: "premium",
        }
        routing = {}
        for tier, task_class in tier_to_task.items():
            provider, model, _ = resolve_alias(task_class)
            routing[tier] = {"CC_LLM_PROVIDER": provider, "CC_LLM_MODEL": model}

        return routing
    except Exception:
        return {}

TIER_ROUTING = _resolve_tier_routing()


class ExecutionService:
    """
    Manages the lifecycle of skill executions.

    - Queue: FIFO with priority ordering
    - Runner: subprocess via skill-runner.py
    - Dead letter: isolates after max_retries failures
    - Cost tracking: per-execution and daily totals
    """

    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.skill_runner = repo_root / "skills" / "skill-runner.py"
        self.python = repo_root / ".venv313" / "bin" / "python3"
        self.data_dir = repo_root / "command-center" / "backend" / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # State
        self.queue: deque[TaskExecution] = deque()
        self.active: dict[str, TaskExecution] = {}
        self.history: list[TaskExecution] = []
        self.dead_letter: list[DeadLetterEntry] = []
        self.mode: ExecutionMode = ExecutionMode.AGGRESSIVE  # Full autonomy (2026-04-02)
        self._start_time = time.time()

        # Concurrency maxed for all modes
        self._concurrency = {
            ExecutionMode.CONSERVATIVE: 4,
            ExecutionMode.BALANCED: 6,
            ExecutionMode.AGGRESSIVE: 8,
        }

        # Daily cost tracking — no ceiling (full autonomy 2026-04-02)
        self._daily_cost = 0.0
        self._daily_completed = 0
        self._daily_failed = 0
        self._cost_ceiling = 999999.0

        # Background processor
        self._processor_task: asyncio.Task | None = None
        self._running = False

        logger.info("ExecutionService initialized (repo: %s)", repo_root)

    # ── Lifecycle ──────────────────────────────────────────────────────

    async def start(self):
        """Start the background queue processor."""
        if self._running:
            return
        self._running = True
        self._processor_task = asyncio.create_task(self._process_loop())
        logger.info("ExecutionService started (mode: %s)", self.mode.value)

    async def stop(self):
        """Stop the background queue processor."""
        self._running = False
        if self._processor_task:
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass
        logger.info("ExecutionService stopped")

    # ── Submit ─────────────────────────────────────────────────────────

    def submit(self, request: ExecutionRequest) -> TaskExecution:
        """Submit a skill execution request to the queue."""
        trace = request.trace or TraceContext(agent_id=request.agent_id, phase="E-2")

        execution = TaskExecution(
            skill_id=request.skill_id,
            inputs=request.inputs,
            agent_id=request.agent_id,
            status=ExecutionStatus.QUEUED,
            tier=request.tier,
            priority=request.priority,
            trace=trace,
        )

        self.queue.append(execution)
        # Sort by priority (lower = higher priority)
        sorted_q = sorted(self.queue, key=lambda x: x.priority)
        self.queue = deque(sorted_q)

        logger.info(
            "Queued execution %s: skill=%s agent=%s tier=%s",
            execution.execution_id[:8],
            execution.skill_id,
            execution.agent_id,
            execution.tier.value,
        )
        return execution

    # ── Query ──────────────────────────────────────────────────────────

    def get_execution(self, execution_id: str) -> TaskExecution | None:
        """Look up an execution by ID across queue, active, and history."""
        for ex in self.queue:
            if ex.execution_id == execution_id:
                return ex
        if execution_id in self.active:
            return self.active[execution_id]
        for ex in self.history:
            if ex.execution_id == execution_id:
                return ex
        return None

    def get_queue(self) -> list[TaskExecution]:
        return list(self.queue)

    def get_active(self) -> list[TaskExecution]:
        return list(self.active.values())

    def get_history(self, limit: int = 50) -> list[TaskExecution]:
        return self.history[-limit:]

    def get_dead_letter(self) -> list[DeadLetterEntry]:
        return list(self.dead_letter)

    def get_state(self) -> EngineState:
        return EngineState(
            mode=self.mode,
            active_executions=len(self.active),
            queued_executions=len(self.queue),
            completed_today=self._daily_completed,
            failed_today=self._daily_failed,
            dead_letter_count=len(self.dead_letter),
            total_cost_today=self._daily_cost,
            uptime_seconds=int(time.time() - self._start_time),
        )

    # ── Cancel ─────────────────────────────────────────────────────────

    def cancel(self, execution_id: str) -> bool:
        """Cancel a queued execution. Cannot cancel running executions."""
        for i, ex in enumerate(self.queue):
            if ex.execution_id == execution_id:
                ex.status = ExecutionStatus.CANCELLED
                ex.completed_at = datetime.utcnow()
                self.history.append(ex)
                del self.queue[i]
                logger.info("Cancelled execution %s", execution_id[:8])
                return True
        return False

    # ── Background Processor ───────────────────────────────────────────

    async def _process_loop(self):
        """Main loop: pull from queue, execute, handle results."""
        logger.info("Queue processor started")
        while self._running:
            try:
                max_concurrent = self._concurrency.get(self.mode, 1)

                while (
                    self.queue
                    and len(self.active) < max_concurrent
                    and self._daily_cost < self._cost_ceiling
                ):
                    execution = self.queue.popleft()
                    self.active[execution.execution_id] = execution
                    asyncio.create_task(self._run_execution(execution))

                await asyncio.sleep(0.5)  # Fast polling
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Queue processor error: %s", e)
                await asyncio.sleep(1)  # Fast error recovery

    async def _run_execution(self, execution: TaskExecution):
        """Execute a single skill via subprocess."""
        execution.status = ExecutionStatus.RUNNING
        execution.started_at = datetime.utcnow()

        logger.info(
            "Running execution %s: skill=%s",
            execution.execution_id[:8],
            execution.skill_id,
        )

        try:
            result = await self._invoke_skill(execution)

            if result["success"]:
                execution.status = ExecutionStatus.COMPLETED
                execution.output_path = result.get("output_path")
                execution.envelope_path = result.get("envelope_path")
                execution.thread_id = result.get("thread_id")
                execution.cost = result.get("cost", 0.0)
                self._daily_completed += 1
                self._daily_cost += execution.cost
                logger.info(
                    "Completed %s: output=%s cost=$%.3f",
                    execution.execution_id[:8],
                    execution.output_path,
                    execution.cost,
                )
            else:
                execution.retry_count += 1
                if execution.retry_count >= execution.max_retries:
                    # Move to dead letter queue
                    execution.status = ExecutionStatus.DEAD_LETTER
                    execution.error = result.get("error", "Unknown error")
                    self._move_to_dead_letter(execution, result.get("error", ""))
                    self._daily_failed += 1
                else:
                    # Re-queue for retry
                    execution.status = ExecutionStatus.QUEUED
                    execution.error = result.get("error")
                    self.queue.appendleft(execution)
                    logger.warning(
                        "Retry %d/%d for %s: %s",
                        execution.retry_count,
                        execution.max_retries,
                        execution.execution_id[:8],
                        result.get("error", "")[:100],
                    )
                    # Remove from active before re-queue processing
                    self.active.pop(execution.execution_id, None)
                    return

        except Exception as e:
            execution.retry_count += 1
            execution.error = str(e)
            if execution.retry_count >= execution.max_retries:
                execution.status = ExecutionStatus.DEAD_LETTER
                self._move_to_dead_letter(execution, str(e))
                self._daily_failed += 1
            else:
                execution.status = ExecutionStatus.QUEUED
                self.queue.appendleft(execution)
                self.active.pop(execution.execution_id, None)
                return

        execution.completed_at = datetime.utcnow()
        self.active.pop(execution.execution_id, None)
        self.history.append(execution)

    async def _invoke_skill(self, execution: TaskExecution) -> dict[str, Any]:
        """
        Call skill-runner.py as subprocess.

        Returns dict with: success, output_path, envelope_path, thread_id, cost, error
        """
        # Build command
        cmd = [
            str(self.python),
            str(self.skill_runner),
            "--skill", execution.skill_id,
        ]

        # Add inputs
        for key, value in execution.inputs.items():
            cmd.extend(["--input", key, value])

        # Add --input-from if we have an envelope from a previous chain step
        if execution.envelope_path:
            cmd.extend(["--input-from", execution.envelope_path])

        # Build environment with LLM tier routing
        env = {**os.environ}
        tier_env = TIER_ROUTING.get(execution.tier, {})
        env.update(tier_env)
        env["PYTHONPATH"] = str(self.repo_root)

        logger.debug("Invoking: %s", " ".join(cmd[:6]) + "...")

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.repo_root),
                env=env,
            )

            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=900,  # 15 minute timeout (full autonomy 2026-04-02)
            )

            stdout_str = stdout.decode("utf-8", errors="replace")
            stderr_str = stderr.decode("utf-8", errors="replace")

            if proc.returncode == 0:
                return self._parse_skill_output(stdout_str, execution.skill_id)
            else:
                return {
                    "success": False,
                    "error": stderr_str[:500] or stdout_str[:500] or f"Exit code {proc.returncode}",
                }

        except asyncio.TimeoutError:
            return {"success": False, "error": "Skill execution timed out (900s)"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _parse_skill_output(self, stdout: str, skill_id: str) -> dict[str, Any]:
        """Parse skill-runner stdout for output paths and thread ID."""
        result: dict[str, Any] = {"success": True, "cost": 0.0}

        for line in stdout.split("\n"):
            line = line.strip()
            if line.startswith("[artifact] Written to:"):
                result["output_path"] = line.split("Written to:")[-1].strip()
            elif line.startswith("[envelope] Written to:"):
                result["envelope_path"] = line.split("Written to:")[-1].strip()
            elif line.startswith("Thread ID:"):
                result["thread_id"] = line.split("Thread ID:")[-1].strip()
            elif "[budget]" in line and "cost=$" in line:
                # Parse cost from budget lines: [budget] alias=... cost=$0.06 remaining=$19.9
                try:
                    cost_part = line.split("cost=$")[1].split()[0]
                    result["cost"] = result.get("cost", 0.0) + float(cost_part)
                except (IndexError, ValueError):
                    pass

        return result

    def _move_to_dead_letter(self, execution: TaskExecution, reason: str):
        """Move failed execution to dead letter queue for review."""
        entry = DeadLetterEntry(
            execution=execution,
            failure_reason=reason[:500],
            attempts=execution.retry_count,
        )
        self.dead_letter.append(entry)
        logger.warning(
            "Dead letter: %s (skill=%s, attempts=%d, reason=%s)",
            execution.execution_id[:8],
            execution.skill_id,
            execution.retry_count,
            reason[:100],
        )

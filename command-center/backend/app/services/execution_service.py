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

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from lib.executor_backends import ExecutionBackend, SubprocessBackend, get_backend

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
    - Delegation: queries skill_agent_mapping for best agent before execution
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

        # Delegation: injected post-init via main.py
        self.skill_agent_mapping = None  # SkillAgentMappingService (set after E-9 init)

        # Observability: injected post-init via main.py
        self.circuit_breaker = None   # SkillCircuitBreaker (set after E-2b init)
        self.skill_metrics = None     # SkillMetrics (set after E-2b init)

        # Execution-scoped breakers
        from lib.circuit_breaker import StepLimitBreaker, CostCeilingBreaker, RepetitionDetector, BackendCostBreaker
        self.step_breaker = StepLimitBreaker()
        self.cost_breaker = CostCeilingBreaker()
        self.repetition_detector = RepetitionDetector()

        # Per-backend cost breakers (flat-rate + API)
        self.backend_cost_breakers: dict[str, BackendCostBreaker] = {}
        self._init_backend_breakers(BackendCostBreaker)

        # Pluggable execution backends
        self.backend_registry: dict[str, ExecutionBackend] = {}
        self.register_backend("subprocess", SubprocessBackend(
            python_path=self.python,
            skill_runner_path=self.skill_runner,
            repo_root=self.repo_root,
        ))

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

    # ── Backend Cost Breakers ────────────────────────────────────────

    def _init_backend_breakers(self, BackendCostBreaker) -> None:
        """Initialize per-backend cost breakers from config/execution/backends.yaml."""
        try:
            from lib.config_loader import load_backends_config
            config = load_backends_config()
            if not config or "backends" not in config:
                return
            for name, cfg in config["backends"].items():
                btype = cfg.get("type", "per_token")
                if btype == "flat_rate":
                    breaker = BackendCostBreaker(
                        backend_name=name,
                        monthly_limit=cfg.get("monthly_minutes", 43200),
                        warn_pct=cfg.get("warn_pct", 0.8),
                        tracking="session_minutes",
                    )
                else:
                    breaker = BackendCostBreaker(
                        backend_name=name,
                        monthly_limit=300.0,  # sum of API provider budgets
                        warn_pct=cfg.get("warn_pct", 0.9),
                        tracking="budget_config",
                    )
                self.backend_cost_breakers[name] = breaker
            logger.info("Backend cost breakers initialized: %s", list(self.backend_cost_breakers.keys()))
        except Exception as e:
            logger.warning("Failed to init backend cost breakers: %s", e)

    # ── Backend Registry ─────────────────────────────────────────────

    def register_backend(self, name: str, backend: ExecutionBackend):
        """Register an execution backend by name."""
        self.backend_registry[name] = backend
        logger.info("Registered execution backend: %s (%s)", name, backend.name)

    def get_backend(self, name: str) -> ExecutionBackend | None:
        """Get a registered backend, or None."""
        return self.backend_registry.get(name)

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
            backend=request.backend,
            backend_model=request.backend_model,
            max_turns=request.max_turns,
        )

        self.queue.append(execution)
        # Sort by priority (lower = higher priority)
        sorted_q = sorted(self.queue, key=lambda x: x.priority)
        self.queue = deque(sorted_q)

        logger.info(
            "Queued execution %s: skill=%s agent=%s tier=%s backend=%s",
            execution.execution_id[:8],
            execution.skill_id,
            execution.agent_id,
            execution.tier.value,
            execution.backend,
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

    def _try_delegate(self, execution: TaskExecution) -> bool:
        """
        Check if a better agent exists for this skill and delegate if so.

        Returns True if execution was re-queued under a different agent.
        """
        if not self.skill_agent_mapping:
            return False

        best = self.skill_agent_mapping.get_best_agent_for_skill(execution.skill_id)
        if not best or best == execution.agent_id:
            return False

        # Best agent differs — delegate (re-queue under the better agent)
        logger.info(
            "Delegating %s from %s → %s (best agent for %s)",
            execution.execution_id[:8],
            execution.agent_id,
            best,
            execution.skill_id,
        )
        execution.agent_id = best
        return False  # Continue execution with updated agent_id

    async def _run_execution(self, execution: TaskExecution):
        """Execute a single skill via subprocess, with optional delegation."""
        execution.status = ExecutionStatus.RUNNING
        execution.started_at = datetime.utcnow()

        # Circuit breaker gate — skip if skill is tripped
        if self.circuit_breaker and not self.circuit_breaker.can_execute_skill(execution.skill_id):
            execution.status = ExecutionStatus.FAILED
            execution.error = f"Circuit breaker OPEN for {execution.skill_id}"
            execution.completed_at = datetime.utcnow()
            self.active.pop(execution.execution_id, None)
            self.history.append(execution)
            self._daily_failed += 1
            logger.warning("Circuit breaker blocked %s (skill=%s)", execution.execution_id[:8], execution.skill_id)
            return

        # Step limit breaker — check before execution
        tier_num = {LLMTier.LIGHTWEIGHT: 1, LLMTier.STANDARD: 2, LLMTier.COMPLEX: 3, LLMTier.CRITICAL: 4}.get(execution.tier)
        step_ok, step_reason = self.step_breaker.check(execution.execution_id, tier_num)
        if not step_ok:
            execution.status = ExecutionStatus.FAILED
            execution.error = step_reason
            execution.completed_at = datetime.utcnow()
            self.active.pop(execution.execution_id, None)
            self.history.append(execution)
            self._daily_failed += 1
            self.step_breaker.reset(execution.execution_id)
            logger.warning("Step breaker tripped %s: %s", execution.execution_id[:8], step_reason)
            return

        # Repetition detector — track (skill_id, inputs) per execution
        rep_ok, rep_reason = self.repetition_detector.record(
            execution.execution_id, execution.skill_id, execution.inputs,
        )
        if not rep_ok:
            execution.status = ExecutionStatus.FAILED
            execution.error = rep_reason
            execution.completed_at = datetime.utcnow()
            self.active.pop(execution.execution_id, None)
            self.history.append(execution)
            self._daily_failed += 1
            self.repetition_detector.reset(execution.execution_id)
            logger.warning("Repetition detector tripped %s: %s", execution.execution_id[:8], rep_reason)
            return

        # Check for better agent before executing
        self._try_delegate(execution)

        logger.info(
            "Running execution %s: skill=%s agent=%s",
            execution.execution_id[:8],
            execution.skill_id,
            execution.agent_id,
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

                # Cost ceiling breaker — track and warn
                self.cost_breaker.add_cost(execution.execution_id, execution.cost)
                cost_ok, cost_reason = self.cost_breaker.check(execution.execution_id)
                if not cost_ok:
                    logger.warning("Cost ceiling exceeded post-execution %s: %s", execution.execution_id[:8], cost_reason)

                logger.info(
                    "Completed %s: output=%s cost=$%.3f",
                    execution.execution_id[:8],
                    execution.output_path,
                    execution.cost,
                )
                # Record success in observability
                if self.circuit_breaker:
                    self.circuit_breaker.record_skill_result(execution.skill_id, True)
                if self.skill_metrics:
                    _dur = int((datetime.utcnow() - execution.started_at).total_seconds() * 1000) if execution.started_at else 0
                    self.skill_metrics.track_execution(
                        skill_id=execution.skill_id, agent_id=execution.agent_id,
                        success=True, duration_ms=_dur, cost_usd=execution.cost or 0.0,
                    )
            else:
                execution.retry_count += 1
                if execution.retry_count >= execution.max_retries:
                    # Move to dead letter queue
                    execution.status = ExecutionStatus.DEAD_LETTER
                    execution.error = result.get("error", "Unknown error")
                    self._move_to_dead_letter(execution, result.get("error", ""))
                    self._daily_failed += 1
                    # Record terminal failure in observability
                    if self.circuit_breaker:
                        self.circuit_breaker.record_skill_result(execution.skill_id, False)
                    if self.skill_metrics:
                        _dur = int((datetime.utcnow() - execution.started_at).total_seconds() * 1000) if execution.started_at else 0
                        self.skill_metrics.track_execution(
                            skill_id=execution.skill_id, agent_id=execution.agent_id,
                            success=False, duration_ms=_dur,
                        )
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
                # Record terminal failure in observability
                if self.circuit_breaker:
                    self.circuit_breaker.record_skill_result(execution.skill_id, False)
                if self.skill_metrics:
                    _dur = int((datetime.utcnow() - execution.started_at).total_seconds() * 1000) if execution.started_at else 0
                    self.skill_metrics.track_execution(
                        skill_id=execution.skill_id, agent_id=execution.agent_id,
                        success=False, duration_ms=_dur,
                    )
            else:
                execution.status = ExecutionStatus.QUEUED
                self.queue.appendleft(execution)
                self.active.pop(execution.execution_id, None)
                return

        execution.completed_at = datetime.utcnow()
        self.active.pop(execution.execution_id, None)
        self.history.append(execution)

        # Clean up execution-scoped breakers
        self.step_breaker.reset(execution.execution_id)
        self.cost_breaker.reset(execution.execution_id)
        self.repetition_detector.reset(execution.execution_id)

    async def _invoke_skill(self, execution: TaskExecution) -> dict[str, Any]:
        """
        Call skill via registered execution backend.

        Routes to a named backend if execution.backend is set,
        otherwise uses the default subprocess backend.
        Falls back to subprocess if a CLI backend fails.

        Returns dict with: success, output_path, envelope_path, thread_id, cost, error
        """
        # Check for an alternative backend
        backend_name = getattr(execution, "backend", None) or "subprocess"
        backend = self.backend_registry.get(backend_name)

        if backend and backend_name != "subprocess":
            # Route to CLI backend (claude_code, codex, etc.)
            prompt = execution.skill_id
            input_parts = [f"{k}={v}" for k, v in execution.inputs.items()]
            if input_parts:
                prompt += " " + " ".join(input_parts)

            # Resolve agent workspace for CLI execution
            agent_workspace = Path.home() / ".nemoclaw" / "workspaces" / execution.agent_id
            if not agent_workspace.exists():
                agent_workspace = self.repo_root

            logger.info("🔧 Routing to %s backend (model=%s): %s for agent %s → %s",
                        backend_name, execution.backend_model, execution.skill_id,
                        execution.agent_id, agent_workspace)
            result = await backend.execute(
                prompt=prompt,
                workdir=str(agent_workspace),
                model=execution.backend_model or "sonnet",
                max_turns=execution.max_turns,
                timeout=int(os.environ.get("SKILL_EXECUTION_TIMEOUT", 900)),
            )

            if result.get("success"):
                return self._parse_skill_output(result["output"], execution.skill_id)

            # Fallback to subprocess on CLI backend failure
            logger.warning("Backend %s failed for %s, falling back to subprocess: %s",
                           backend_name, execution.skill_id, result.get("error", ""))

        # Default: subprocess backend (skill-runner.py)
        return await self._invoke_skill_subprocess(execution)

    async def _invoke_skill_subprocess(self, execution: TaskExecution) -> dict[str, Any]:
        """Original subprocess invocation via skill-runner.py."""
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

        logger.debug("Invoking subprocess: %s", " ".join(cmd[:6]) + "...")

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
                timeout=int(os.environ.get("SKILL_EXECUTION_TIMEOUT", 900)),
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

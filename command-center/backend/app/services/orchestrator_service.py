"""
NemoClaw Execution Engine — OrchestratorService (E-3)

Wraps scripts/task_decomposer.py as a service.
Goal → Plan → Cost Estimate → Approval → Execution.

Audit trail (#9): trace_id propagates through every task.
Cross-stage dependencies (#36): tasks respect dependency order.

DECISION: Calls task_decomposer.py via subprocess (same pattern as skill-runner).
The script has its own LLM calls for decomposition — keeps it isolated.

NEW FILE: command-center/backend/app/services/orchestrator_service.py
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from app.domain.engine_models import (
    ExecutionRequest,
    ExecutionStatus,
    LLMTier,
    TraceContext,
)

logger = logging.getLogger("cc.orchestrator")


class WorkflowStatus:
    PLANNING = "planning"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Workflow:
    """A workflow = goal → plan → tasks → execution."""

    def __init__(self, goal: str, trace: TraceContext | None = None):
        self.workflow_id = str(uuid.uuid4())
        self.goal = goal
        self.trace = trace or TraceContext(phase="E-3")
        self.status = WorkflowStatus.PLANNING
        self.plan: dict[str, Any] = {}
        self.tasks: list[dict[str, Any]] = []
        self.cost_estimate: float = 0.0
        self.actual_cost: float = 0.0
        self.created_at = datetime.utcnow()
        self.started_at: datetime | None = None
        self.completed_at: datetime | None = None
        self.error: str | None = None
        self.task_results: list[dict[str, Any]] = []

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "goal": self.goal,
            "trace": self.trace.model_dump(),
            "status": self.status,
            "plan": self.plan,
            "tasks": self.tasks,
            "cost_estimate": self.cost_estimate,
            "actual_cost": self.actual_cost,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error": self.error,
            "task_results": self.task_results,
        }


class OrchestratorService:
    """
    Decomposes goals into executable plans and runs them.

    Flow:
      1. POST /orchestrator/plan → decompose goal → return plan with cost
      2. POST /orchestrator/execute → approve + execute plan
      3. Tasks run via ExecutionService in dependency order
    """

    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.python = str(repo_root / ".venv313" / "bin" / "python3")
        self.decomposer = str(repo_root / "scripts" / "task_decomposer.py")
        self.workflows: dict[str, Workflow] = {}

        logger.info("OrchestratorService initialized")

    async def create_plan(self, goal: str) -> Workflow:
        """Decompose a goal into an executable plan."""
        trace = TraceContext(phase="E-3")
        workflow = Workflow(goal=goal, trace=trace)
        self.workflows[workflow.workflow_id] = workflow

        logger.info("Planning workflow %s: %s", workflow.workflow_id[:8], goal)

        try:
            plan = await self._decompose(goal)
            workflow.plan = plan
            workflow.tasks = plan.get("tasks", [])
            workflow.cost_estimate = plan.get("total_cost_estimate", 0.0)
            # Auto-approve + auto-execute (full autonomy 2026-04-02)
            workflow.status = WorkflowStatus.APPROVED
            logger.info(
                "Auto-approved %s: %d tasks, est. $%.2f — executing immediately",
                workflow.workflow_id[:8],
                len(workflow.tasks),
                workflow.cost_estimate,
            )
        except Exception as e:
            workflow.status = WorkflowStatus.FAILED
            workflow.error = str(e)
            logger.error("Planning failed for %s: %s", workflow.workflow_id[:8], e)

        return workflow

    async def execute_workflow(
        self, workflow_id: str, execution_service=None
    ) -> Workflow | None:
        """Approve and execute a planned workflow."""
        workflow = self.workflows.get(workflow_id)
        if not workflow:
            return None

        if workflow.status != WorkflowStatus.AWAITING_APPROVAL:
            logger.warning(
                "Cannot execute %s: status=%s",
                workflow_id[:8], workflow.status,
            )
            return workflow

        workflow.status = WorkflowStatus.APPROVED
        workflow.started_at = datetime.utcnow()

        if execution_service:
            asyncio.create_task(
                self._run_tasks(workflow, execution_service)
            )
        else:
            workflow.status = WorkflowStatus.FAILED
            workflow.error = "No ExecutionService available"

        return workflow

    async def _run_tasks(self, workflow: Workflow, execution_service):
        """Execute tasks in dependency order via ExecutionService."""
        workflow.status = WorkflowStatus.EXECUTING
        completed_tasks: set[str] = set()

        # Build dependency map
        dep_map: dict[str, list[str]] = {}
        task_map: dict[str, dict] = {}
        for task in workflow.tasks:
            tid = task.get("id", "")
            dep_map[tid] = task.get("depends_on", []) or []
            task_map[tid] = task

        try:
            # Topological execution
            while len(completed_tasks) < len(workflow.tasks):
                # Find tasks whose dependencies are all complete
                ready = [
                    tid for tid, deps in dep_map.items()
                    if tid not in completed_tasks
                    and all(d in completed_tasks for d in deps)
                ]

                if not ready:
                    workflow.status = WorkflowStatus.FAILED
                    workflow.error = "Circular dependency or unresolvable tasks"
                    break

                for tid in ready:
                    task = task_map[tid]
                    skill_id = task.get("skill", "")

                    if not skill_id:
                        # Task has no skill — mark as completed (planning/approval tasks)
                        completed_tasks.add(tid)
                        workflow.task_results.append({
                            "task_id": tid,
                            "status": "skipped",
                            "reason": "No skill assigned",
                        })
                        continue

                    # Submit to execution service
                    request = ExecutionRequest(
                        skill_id=skill_id,
                        inputs=task.get("inputs", {}),
                        agent_id=task.get("assigned_to", ""),
                        tier=LLMTier.STANDARD,
                        trace=workflow.trace,
                    )

                    execution = execution_service.submit(request)

                    # Wait for completion
                    result = await self._wait_for_execution(
                        execution_service, execution.execution_id
                    )

                    if result and result.status == ExecutionStatus.COMPLETED:
                        completed_tasks.add(tid)
                        workflow.actual_cost += result.cost
                        workflow.task_results.append({
                            "task_id": tid,
                            "execution_id": result.execution_id,
                            "status": "completed",
                            "output_path": result.output_path,
                            "cost": result.cost,
                        })
                    else:
                        error = result.error if result else "Execution failed"
                        workflow.task_results.append({
                            "task_id": tid,
                            "status": "failed",
                            "error": error,
                        })
                        # Continue with other tasks (don't fail entire workflow)
                        completed_tasks.add(tid)

            if workflow.status == WorkflowStatus.EXECUTING:
                workflow.status = WorkflowStatus.COMPLETED
                workflow.completed_at = datetime.utcnow()
                logger.info(
                    "Workflow %s completed: %d tasks, cost=$%.3f",
                    workflow.workflow_id[:8],
                    len(workflow.tasks),
                    workflow.actual_cost,
                )

        except Exception as e:
            workflow.status = WorkflowStatus.FAILED
            workflow.error = str(e)
            logger.error("Workflow %s failed: %s", workflow.workflow_id[:8], e)

    async def _wait_for_execution(
        self, execution_service, execution_id: str, timeout: int = 600
    ):
        """Poll ExecutionService for completion."""
        start = asyncio.get_event_loop().time()
        while (asyncio.get_event_loop().time() - start) < timeout:
            ex = execution_service.get_execution(execution_id)
            if ex and ex.status in (
                ExecutionStatus.COMPLETED,
                ExecutionStatus.FAILED,
                ExecutionStatus.CANCELLED,
                ExecutionStatus.DEAD_LETTER,
            ):
                return ex
            await asyncio.sleep(1)  # Fast polling
        return None

    async def _decompose(self, goal: str) -> dict[str, Any]:
        """Call task_decomposer.py --decompose --dry-run to get a plan."""
        cmd = [
            self.python,
            self.decomposer,
            "--decompose", goal,
            "--dry-run",
        ]

        env = {**os.environ, "PYTHONPATH": str(self.repo_root)}

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.repo_root),
                env=env,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=600  # 10 min for complex goals
            )

            stdout_str = stdout.decode("utf-8", errors="replace")
            stderr_str = stderr.decode("utf-8", errors="replace")

            if proc.returncode == 0:
                return self._parse_plan(stdout_str, goal)
            else:
                # If decomposer fails, create a simple plan from the goal
                logger.warning(
                    "Decomposer failed (exit %d), creating simple plan: %s",
                    proc.returncode, stderr_str[:200],
                )
                return self._simple_plan(goal)

        except asyncio.TimeoutError:
            logger.warning("Decomposer timed out, creating simple plan")
            return self._simple_plan(goal)
        except Exception as e:
            logger.warning("Decomposer error (%s), creating simple plan", e)
            return self._simple_plan(goal)

    def _parse_plan(self, stdout: str, goal: str) -> dict[str, Any]:
        """Parse task_decomposer.py output into a plan."""
        # Try to find JSON in output
        for line in stdout.split("\n"):
            line = line.strip()
            if line.startswith("{"):
                try:
                    return json.loads(line)
                except json.JSONDecodeError:
                    pass

        # Try the whole output as JSON
        try:
            return json.loads(stdout)
        except json.JSONDecodeError:
            pass

        # Fallback: create simple plan
        return self._simple_plan(goal)

    def _simple_plan(self, goal: str) -> dict[str, Any]:
        """Create a basic plan when decomposer fails."""
        # Detect goal type and assign appropriate skills
        goal_lower = goal.lower()

        tasks = []

        if any(w in goal_lower for w in ["research", "market", "analyze"]):
            tasks.append({
                "id": "task_001",
                "title": "Market Research",
                "description": f"Research: {goal}",
                "assigned_to": "strategy_lead",
                "capability": "research",
                "skill": "e12-market-research-analyst",
                "inputs": {
                    "research_topic": goal,
                    "industry_context": "Technology and SaaS industry analysis",
                },
                "depends_on": [],
                "estimated_cost_usd": 0.15,
            })

        if any(w in goal_lower for w in ["competitor", "competitive", "intel"]):
            tasks.append({
                "id": "task_002",
                "title": "Competitive Intelligence",
                "description": f"Competitive analysis for: {goal}",
                "assigned_to": "strategy_lead",
                "capability": "analysis",
                "skill": "e08-comp-intel-synth",
                "inputs": {
                    "analysis_topic": goal,
                    "industry": "Technology",
                },
                "depends_on": ["task_001"] if tasks else [],
                "estimated_cost_usd": 0.15,
            })

        if any(w in goal_lower for w in ["write", "content", "copy", "draft"]):
            tasks.append({
                "id": f"task_{len(tasks) + 1:03d}",
                "title": "Content Creation",
                "description": f"Create content: {goal}",
                "assigned_to": "narrative_content_lead",
                "capability": "content",
                "skill": "d11-copywriting-specialist",
                "inputs": {
                    "copy_brief": goal,
                    "target_audience": "B2B decision makers",
                    "copy_format": "article",
                },
                "depends_on": [tasks[-1]["id"]] if tasks else [],
                "estimated_cost_usd": 0.15,
            })

        # If no tasks matched, create a generic research task
        if not tasks:
            tasks.append({
                "id": "task_001",
                "title": "Research & Analysis",
                "description": goal,
                "assigned_to": "strategy_lead",
                "capability": "research",
                "skill": "e12-market-research-analyst",
                "inputs": {
                    "research_topic": goal,
                    "industry_context": "General business analysis and strategic planning",
                },
                "depends_on": [],
                "estimated_cost_usd": 0.15,
            })

        total_cost = sum(t.get("estimated_cost_usd", 0.15) for t in tasks)

        return {
            "goal": goal,
            "tasks": tasks,
            "total_cost_estimate": total_cost,
            "task_count": len(tasks),
            "estimated_duration_minutes": len(tasks) * 3,
        }

    def get_workflow(self, workflow_id: str) -> Workflow | None:
        return self.workflows.get(workflow_id)

    def list_workflows(self) -> list[dict[str, Any]]:
        return [w.to_dict() for w in self.workflows.values()]

    def cancel_workflow(self, workflow_id: str) -> bool:
        workflow = self.workflows.get(workflow_id)
        if not workflow:
            return False
        if workflow.status in (WorkflowStatus.COMPLETED, WorkflowStatus.CANCELLED):
            return False
        workflow.status = WorkflowStatus.CANCELLED
        workflow.completed_at = datetime.utcnow()
        return True

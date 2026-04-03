"""
NemoClaw Execution Engine — TaskWorkflowService (E-4a+)

Structured task execution: brainstorm → plan → execute → validate → document.
Each workflow writes artifacts to ~/.nemoclaw/workflows/{workflow_id}/.

Phases:
  1. BRAINSTORM — Generate 3 approaches via LLM
  2. PLAN — Decompose chosen approach into executable steps
  3. EXECUTE — Run skills per step
  4. VALIDATE — Quality check on outputs
  5. DOCUMENT — Write execution log and summary

NEW FILE: command-center/backend/app/services/task_workflow_service.py
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger("cc.task_workflow")

WORKFLOWS_DIR = Path.home() / ".nemoclaw" / "workflows"


class WorkflowPhase(str, Enum):
    BRAINSTORM = "brainstorm"
    PLAN = "plan"
    EXECUTE = "execute"
    VALIDATE = "validate"
    DOCUMENT = "document"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskWorkflow:
    """A single structured workflow instance."""

    def __init__(self, goal: str, agent_id: str, project_id: str | None = None):
        self.workflow_id = f"wf-{int(time.time())}-{uuid.uuid4().hex[:6]}"
        self.goal = goal
        self.agent_id = agent_id
        self.project_id = project_id or "default"
        self.phase = WorkflowPhase.BRAINSTORM
        self.created_at = datetime.now(timezone.utc)
        self.updated_at = self.created_at
        self.completed_at: datetime | None = None

        # Phase outputs
        self.approaches: list[dict[str, Any]] = []
        self.plan_steps: list[dict[str, Any]] = []
        self.execution_results: list[dict[str, Any]] = []
        self.validation: dict[str, Any] = {}
        self.error: str | None = None

        # Collaboration
        self.team_lane_id: str | None = None

        # File paths
        self.work_dir = WORKFLOWS_DIR / self.workflow_id
        self.work_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def from_summary(summary_path: Path) -> TaskWorkflow | None:
        """Reconstruct a TaskWorkflow from a summary.json on disk."""
        try:
            data = json.loads(summary_path.read_text())
        except (json.JSONDecodeError, OSError):
            return None

        wf = object.__new__(TaskWorkflow)
        wf.workflow_id = data.get("workflow_id", summary_path.parent.name)
        wf.goal = data.get("goal", "")
        wf.agent_id = data.get("agent_id", "unknown")
        wf.project_id = data.get("project_id", "default")
        wf.phase = WorkflowPhase.COMPLETED if data.get("completed_at") else WorkflowPhase.FAILED
        wf.created_at = datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(timezone.utc)
        wf.updated_at = wf.created_at
        wf.completed_at = datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None

        wf.approaches = [{} for _ in range(data.get("approaches", 0))] if isinstance(data.get("approaches"), int) else data.get("approaches", [])
        wf.plan_steps = [{} for _ in range(data.get("plan_steps", 0))] if isinstance(data.get("plan_steps"), int) else data.get("plan_steps", [])
        wf.execution_results = data.get("execution_results", [])
        wf.validation = data.get("validation", {})
        wf.error = data.get("error")

        wf.team_lane_id = data.get("team_lane_id")
        wf.work_dir = summary_path.parent
        return wf

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "goal": self.goal,
            "agent_id": self.agent_id,
            "project_id": self.project_id,
            "phase": self.phase.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "approaches_count": len(self.approaches),
            "plan_steps_count": len(self.plan_steps),
            "executions_count": len(self.execution_results),
            "validation": self.validation,
            "error": self.error,
            "team_lane_id": getattr(self, "team_lane_id", None),
            "files": self._file_paths(),
        }

    def _file_paths(self) -> dict[str, str]:
        paths: dict[str, str] = {}
        for name in ["brainstorm.md", "plan.md", "execution-log.jsonl", "validation-report.md"]:
            p = self.work_dir / name
            if p.exists():
                paths[name] = str(p)
        return paths


class TaskWorkflowService:
    """
    Structured task execution through 5 phases.

    Dependencies (injected post-creation):
      - execution_service: skill execution
      - event_bus: emit task lifecycle events
      - brain_service: LLM calls for brainstorm/plan/validate
    """

    def __init__(
        self,
        execution_service=None,
        event_bus=None,
        brain_service=None,
    ):
        self.execution_service = execution_service
        self.event_bus = event_bus
        self.brain_service = brain_service
        self.ceo_reviewer = None  # Wired post-init from main.py
        self._workflows: dict[str, TaskWorkflow] = {}
        WORKFLOWS_DIR.mkdir(parents=True, exist_ok=True)
        self._scan_disk()
        logger.info("TaskWorkflowService initialized (dir=%s, loaded=%d)", WORKFLOWS_DIR, len(self._workflows))

    # ── Public API ────────────────────────────────────────────────────

    async def create_plan(self, goal: str, agent_id: str = "operations_lead"):
        """Create and execute a workflow plan. Compatible with dispatch_task API.

        Returns an object with .workflow_id, .status, .tasks, .error
        matching what agent_loop_service.dispatch_task() expects.
        """
        wf_id = self.create_workflow(goal, agent_id)
        result = await self.run_workflow(wf_id)
        wf = self._workflows.get(wf_id)

        # Build adapter matching expected interface (.status, .tasks, .error)
        class _PlanResult:
            def __init__(self, wf, result):
                self.workflow_id = wf.workflow_id if wf else wf_id
                self.error = wf.error if wf else result.get("error")
                # Map phase to status
                if wf and wf.error:
                    self.status = "failed"
                elif result.get("success") is False:
                    self.status = "failed"
                    self.error = self.error or result.get("error", "Unknown failure")
                else:
                    self.status = "completed"
                # Map plan_steps to tasks
                self.tasks = []
                if wf:
                    for step in wf.plan_steps:
                        self.tasks.append({
                            "skill": step.get("skill_id", step.get("skill", "")),
                            "skill_id": step.get("skill_id", step.get("skill", "")),
                            "inputs": step.get("inputs", {}),
                            "name": step.get("name", step.get("title", "")),
                        })

        return _PlanResult(wf, result)

    def create_workflow(
        self, goal: str, agent_id: str, project_id: str | None = None
    ) -> str:
        """Create a new workflow and return its ID."""
        wf = TaskWorkflow(goal, agent_id, project_id)
        self._workflows[wf.workflow_id] = wf
        self._emit("task_started", wf)
        logger.info("Workflow created: %s for %s — %s", wf.workflow_id, agent_id, goal[:80])
        return wf.workflow_id

    async def run_workflow(self, workflow_id: str) -> dict[str, Any]:
        """Execute all phases sequentially. Returns structured result."""
        wf = self._workflows.get(workflow_id)
        if not wf:
            return {"success": False, "error": f"Workflow {workflow_id} not found"}

        try:
            await self._phase_brainstorm(wf)
            if not self._check_phase_gate(wf, "brainstorm", "plan"):
                return {"success": False, "error": "Phase gate blocked: brainstorm → plan", "workflow": wf.to_dict()}
            await self._phase_plan(wf)
            if not self._check_phase_gate(wf, "plan", "execute"):
                return {"success": False, "error": "Phase gate blocked: plan → execute", "workflow": wf.to_dict()}
            await self._phase_execute(wf)
            if not self._check_phase_gate(wf, "execute", "validate"):
                return {"success": False, "error": "Phase gate blocked: execute → validate", "workflow": wf.to_dict()}
            await self._phase_validate(wf)
            await self._phase_document(wf)

            wf.phase = WorkflowPhase.COMPLETED
            wf.completed_at = datetime.now(timezone.utc)
            wf.updated_at = wf.completed_at
            self._emit("task_completed", wf)

            return {"success": True, "workflow": wf.to_dict()}

        except Exception as e:
            wf.phase = WorkflowPhase.FAILED
            wf.error = str(e)
            wf.updated_at = datetime.now(timezone.utc)
            self._emit("task_failed", wf, error=str(e))
            logger.error("Workflow %s failed: %s", workflow_id, e)
            return {"success": False, "error": str(e), "workflow": wf.to_dict()}

    def _check_phase_gate(self, wf, from_phase: str, to_phase: str) -> bool:
        """Check CEO phase gate if available. Returns True if passed or no reviewer."""
        if not self.ceo_reviewer:
            return True
        result = self.ceo_reviewer.validate_phase_gate(
            mission_id=wf.workflow_id,
            from_phase=from_phase,
            to_phase=to_phase,
        )
        if not result.passed:
            wf.phase = WorkflowPhase.FAILED
            wf.error = f"Phase gate blocked: {', '.join(result.blockers)}"
            wf.updated_at = datetime.now(timezone.utc)
            self._emit("task_failed", wf, error=wf.error)
            logger.warning("Workflow %s blocked at phase gate %s → %s: %s", wf.workflow_id, from_phase, to_phase, result.blockers)
        return result.passed

    def get_workflow(self, workflow_id: str) -> dict[str, Any] | None:
        wf = self._workflows.get(workflow_id)
        return wf.to_dict() if wf else None

    def list_workflows(self, agent_id: str | None = None) -> list[dict[str, Any]]:
        wfs = self._workflows.values()
        if agent_id:
            wfs = [w for w in wfs if w.agent_id == agent_id]
        return sorted(
            [w.to_dict() for w in wfs],
            key=lambda d: d.get("created_at", ""),
            reverse=True,
        )

    def list_artifacts(self, workflow_id: str) -> list[dict[str, Any]]:
        """List artifact files for a workflow."""
        wf_dir = WORKFLOWS_DIR / workflow_id
        if not wf_dir.is_dir():
            return []
        files: list[dict[str, Any]] = []
        for p in sorted(wf_dir.iterdir()):
            if p.is_file():
                stat = p.stat()
                files.append({
                    "name": p.name,
                    "size_bytes": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                })
        return files

    def get_artifact(self, workflow_id: str, filename: str) -> str | None:
        """Read artifact file content. Returns None if not found. Guards path traversal."""
        if "/" in filename or "\\" in filename or ".." in filename:
            return None
        path = WORKFLOWS_DIR / workflow_id / filename
        if not path.is_file():
            return None
        try:
            return path.read_text()
        except OSError:
            return None

    # ── Disk Scan ─────────────────────────────────────────────────────

    def _scan_disk(self) -> None:
        """Load existing workflows from disk — uses summary.json if available, falls back to dir metadata."""
        if not WORKFLOWS_DIR.is_dir():
            return
        for d in WORKFLOWS_DIR.iterdir():
            if not d.is_dir() or d.name in self._workflows:
                continue
            summary = d / "summary.json"
            if summary.is_file():
                wf = TaskWorkflow.from_summary(summary)
                if wf:
                    self._workflows[wf.workflow_id] = wf
            else:
                # No summary.json — reconstruct minimal workflow from files present
                files = [f.name for f in d.iterdir() if f.is_file()]
                if files:
                    wf = object.__new__(TaskWorkflow)
                    wf.workflow_id = d.name
                    wf.goal = "(restored from disk)"
                    wf.agent_id = "unknown"
                    wf.project_id = "default"
                    wf.phase = WorkflowPhase.BRAINSTORM
                    wf.created_at = datetime.fromtimestamp(d.stat().st_ctime, tz=timezone.utc)
                    wf.updated_at = wf.created_at
                    wf.completed_at = None
                    wf.approaches = []
                    wf.plan_steps = []
                    wf.execution_results = []
                    wf.validation = {}
                    wf.error = None
                    wf.team_lane_id = None
                    wf.work_dir = d
                    self._workflows[wf.workflow_id] = wf
        logger.info("Disk scan: loaded %d workflows from %s", len(self._workflows), WORKFLOWS_DIR)

    # ── Phase 1: Brainstorm ───────────────────────────────────────────

    async def _phase_brainstorm(self, wf: TaskWorkflow) -> None:
        wf.phase = WorkflowPhase.BRAINSTORM
        wf.updated_at = datetime.now(timezone.utc)

        prompt = (
            f"Generate exactly 3 distinct approaches to accomplish this goal:\n\n"
            f"Goal: {wf.goal}\n"
            f"Agent: {wf.agent_id}\n"
            f"Project: {wf.project_id}\n\n"
            f"For each approach provide:\n"
            f"1. Name (short title)\n"
            f"2. Strategy (2-3 sentences)\n"
            f"3. Skills needed (NemoClaw skill IDs if known)\n"
            f"4. Risk level (low/medium/high)\n"
            f"5. Estimated steps\n"
        )

        if self.brain_service:
            result = await self.brain_service.analyze(prompt, context="workflow_brainstorm")
            # analyze() returns raw string — parse into structured approaches
            text = result if isinstance(result, str) else result.get("analysis", str(result))
            wf.approaches = self._parse_approaches(text, wf.goal)
        else:
            # Fallback: single direct approach
            wf.approaches = [
                {
                    "name": "Direct Execution",
                    "strategy": f"Execute goal directly: {wf.goal}",
                    "skills": [],
                    "risk": "low",
                    "steps": 1,
                },
            ]

        # Write brainstorm.md
        md = f"# Brainstorm — {wf.goal}\n\n"
        md += f"**Workflow:** {wf.workflow_id}\n"
        md += f"**Agent:** {wf.agent_id}\n"
        md += f"**Generated:** {wf.updated_at.isoformat()}\n\n"
        for i, a in enumerate(wf.approaches, 1):
            md += f"## Approach {i}: {a['name']}\n"
            md += f"- **Strategy:** {a['strategy']}\n"
            md += f"- **Skills:** {', '.join(a.get('skills', [])) or 'TBD'}\n"
            md += f"- **Risk:** {a.get('risk', 'unknown')}\n"
            md += f"- **Steps:** {a.get('steps', '?')}\n\n"

        (wf.work_dir / "brainstorm.md").write_text(md)
        logger.info("Brainstorm complete: %s — %d approaches", wf.workflow_id, len(wf.approaches))

    def _parse_approaches(self, text: str, goal: str) -> list[dict[str, Any]]:
        """Parse LLM brainstorm text into structured approaches."""
        approaches: list[dict[str, Any]] = []
        # Simple heuristic: split on numbered patterns
        sections = []
        current: list[str] = []
        for line in text.split("\n"):
            stripped = line.strip()
            if stripped and (stripped[0].isdigit() or stripped.startswith("## ") or stripped.startswith("Approach")):
                if current:
                    sections.append("\n".join(current))
                current = [line]
            else:
                current.append(line)
        if current:
            sections.append("\n".join(current))

        for i, section in enumerate(sections[:3]):
            approaches.append({
                "name": f"Approach {i + 1}",
                "strategy": section.strip()[:300],
                "skills": [],
                "risk": "medium",
                "steps": 3,
            })

        # Ensure at least one approach
        if not approaches:
            approaches.append({
                "name": "Direct Execution",
                "strategy": f"Execute directly: {goal}",
                "skills": [],
                "risk": "low",
                "steps": 1,
            })
        return approaches

    # ── Phase 2: Plan ─────────────────────────────────────────────────

    async def _phase_plan(self, wf: TaskWorkflow) -> None:
        wf.phase = WorkflowPhase.PLAN
        wf.updated_at = datetime.now(timezone.utc)

        # Use first approach (best/default)
        chosen = wf.approaches[0] if wf.approaches else {"strategy": wf.goal}

        prompt = (
            f"Decompose this approach into concrete executable steps.\n\n"
            f"Goal: {wf.goal}\n"
            f"Approach: {chosen.get('strategy', wf.goal)}\n\n"
            f"For each step provide:\n"
            f"1. Step name\n"
            f"2. Description\n"
            f"3. Skill ID to run (or 'manual')\n"
            f"4. Inputs needed\n"
            f"5. Expected output\n"
        )

        if self.brain_service:
            result = await self.brain_service.analyze(prompt, context="workflow_plan")
            text = result if isinstance(result, str) else result.get("analysis", str(result))
            wf.plan_steps = self._parse_plan(text)
        else:
            wf.plan_steps = [
                {
                    "step": 1,
                    "name": "Execute goal",
                    "description": wf.goal,
                    "skill_id": None,
                    "inputs": {},
                    "expected_output": "Goal accomplished",
                },
            ]

        # Write plan.md
        md = f"# Execution Plan — {wf.goal}\n\n"
        md += f"**Chosen approach:** {chosen.get('name', 'Direct')}\n\n"
        md += "| # | Step | Skill | Description |\n"
        md += "|---|------|-------|-------------|\n"
        for s in wf.plan_steps:
            md += f"| {s['step']} | {s['name']} | {s.get('skill_id') or 'manual'} | {s['description'][:60]} |\n"

        (wf.work_dir / "plan.md").write_text(md)
        logger.info("Plan complete: %s — %d steps", wf.workflow_id, len(wf.plan_steps))

    def _parse_plan(self, text: str) -> list[dict[str, Any]]:
        """Parse LLM plan into structured steps."""
        steps: list[dict[str, Any]] = []
        for i, line in enumerate(text.split("\n"), 1):
            stripped = line.strip()
            if stripped and (stripped[0].isdigit() or stripped.startswith("- ")):
                steps.append({
                    "step": len(steps) + 1,
                    "name": stripped.lstrip("0123456789.-) ").strip()[:80],
                    "description": stripped,
                    "skill_id": None,
                    "inputs": {},
                    "expected_output": "Step output",
                })
            if len(steps) >= 10:
                break
        if not steps:
            steps.append({
                "step": 1,
                "name": "Execute",
                "description": text[:200],
                "skill_id": None,
                "inputs": {},
                "expected_output": "Output",
            })
        return steps

    # ── Phase 3: Execute ──────────────────────────────────────────────

    async def _phase_execute(self, wf: TaskWorkflow) -> None:
        wf.phase = WorkflowPhase.EXECUTE
        wf.updated_at = datetime.now(timezone.utc)
        log_path = wf.work_dir / "execution-log.jsonl"

        # For complex workflows (5+ steps), use SupervisorGraph for LLM-driven routing
        skill_steps = [s for s in wf.plan_steps if s.get("skill_id")]
        if len(wf.plan_steps) >= 5 and skill_steps:
            await self._execute_via_supervisor(wf, log_path)
            return

        for step in wf.plan_steps:
            entry: dict[str, Any] = {
                "step": step["step"],
                "name": step["name"],
                "skill_id": step.get("skill_id"),
                "started_at": datetime.now(timezone.utc).isoformat(),
                "success": False,
            }

            skill_id = step.get("skill_id")
            if skill_id and self.execution_service:
                try:
                    from app.domain.engine_models import ExecutionRequest, LLMTier
                    request = ExecutionRequest(
                        skill_id=skill_id,
                        inputs=step.get("inputs", {}),
                        agent_id=wf.agent_id,
                        tier=LLMTier.STANDARD,
                    )
                    execution = self.execution_service.submit(request)
                    entry["execution_id"] = execution.execution_id
                    entry["success"] = True
                except Exception as e:
                    entry["error"] = str(e)
            else:
                # Manual step — mark as passed-through
                entry["success"] = True
                entry["note"] = "No skill_id — manual/passthrough step"

            entry["completed_at"] = datetime.now(timezone.utc).isoformat()
            wf.execution_results.append(entry)

            # Append to JSONL
            with open(log_path, "a") as f:
                f.write(json.dumps(entry, default=str) + "\n")

        logger.info(
            "Execute complete: %s — %d/%d succeeded",
            wf.workflow_id,
            sum(1 for r in wf.execution_results if r.get("success")),
            len(wf.execution_results),
        )

    async def _execute_via_supervisor(self, wf: TaskWorkflow, log_path: Path) -> None:
        """Use SupervisorGraph for complex workflows with 5+ plan steps.

        The supervisor LLM decides routing instead of sequential execution.
        """
        import sys
        from pathlib import Path as _Path
        repo = _Path(__file__).resolve().parents[4]
        sys.path.insert(0, str(repo))

        try:
            from scripts.orchestrator import SupervisorGraph

            logger.info(
                "Executing via SupervisorGraph: %s (%d steps)",
                wf.workflow_id, len(wf.plan_steps),
            )

            sg = SupervisorGraph(task_class="moderate")
            result = sg.run(wf.goal, workspace_id=wf.workflow_id)

            # Map supervisor results back to workflow execution_results
            for role, output in result.get("agent_outputs", {}).items():
                entry: dict[str, Any] = {
                    "step": len(wf.execution_results) + 1,
                    "name": f"supervisor:{role}",
                    "skill_id": output.get("skill_id"),
                    "started_at": datetime.now(timezone.utc).isoformat(),
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                    "success": output.get("success", False),
                    "mode": "supervisor_graph",
                }
                if output.get("error"):
                    entry["error"] = output["error"]
                if output.get("quality"):
                    entry["quality_score"] = output["quality"]

                wf.execution_results.append(entry)
                with open(log_path, "a") as f:
                    f.write(json.dumps(entry, default=str) + "\n")

            # Log routing decisions for audit
            for decision in result.get("routing_decisions", []):
                with open(log_path, "a") as f:
                    f.write(json.dumps({
                        "type": "routing_decision",
                        "timestamp": decision.get("timestamp"),
                        "agents": decision.get("agents"),
                        "reasoning": decision.get("reasoning", "")[:200],
                    }, default=str) + "\n")

            logger.info(
                "SupervisorGraph complete: %s — %d/%d agents succeeded",
                wf.workflow_id,
                result.get("agents_succeeded", 0),
                result.get("agents_total", 0),
            )

        except ImportError as e:
            logger.warning("SupervisorGraph unavailable, falling back to sequential: %s", e)
            # Fallback: run sequentially (re-enter _phase_execute without supervisor)
            for step in wf.plan_steps:
                entry = {
                    "step": step["step"],
                    "name": step["name"],
                    "skill_id": step.get("skill_id"),
                    "started_at": datetime.now(timezone.utc).isoformat(),
                    "success": True,
                    "note": "Sequential fallback — SupervisorGraph unavailable",
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                }
                wf.execution_results.append(entry)
                with open(log_path, "a") as f:
                    f.write(json.dumps(entry, default=str) + "\n")

    # ── Phase 4: Validate ─────────────────────────────────────────────

    async def _phase_validate(self, wf: TaskWorkflow) -> None:
        wf.phase = WorkflowPhase.VALIDATE
        wf.updated_at = datetime.now(timezone.utc)

        total = len(wf.execution_results)
        succeeded = sum(1 for r in wf.execution_results if r.get("success"))
        failed = total - succeeded

        wf.validation = {
            "total_steps": total,
            "succeeded": succeeded,
            "failed": failed,
            "success_rate": round(succeeded / total, 2) if total else 0,
            "passed": failed == 0,
        }

        # LLM quality check if brain available
        if self.brain_service and succeeded > 0:
            prompt = (
                f"Evaluate the quality of this workflow execution.\n\n"
                f"Goal: {wf.goal}\n"
                f"Steps executed: {total}, Succeeded: {succeeded}, Failed: {failed}\n"
                f"Rate the overall quality 1-10 and suggest improvements.\n"
            )
            result = await self.brain_service.analyze(prompt, context="workflow_validate")
            text = result if isinstance(result, str) else result.get("analysis", str(result))
            wf.validation["quality_assessment"] = text[:500]

        # Write validation-report.md
        md = f"# Validation Report — {wf.goal}\n\n"
        md += f"**Workflow:** {wf.workflow_id}\n"
        md += f"**Agent:** {wf.agent_id}\n\n"
        md += f"## Results\n"
        md += f"- Total steps: {total}\n"
        md += f"- Succeeded: {succeeded}\n"
        md += f"- Failed: {failed}\n"
        md += f"- Success rate: {wf.validation['success_rate']:.0%}\n"
        md += f"- **Verdict:** {'PASS' if wf.validation['passed'] else 'FAIL'}\n\n"
        if wf.validation.get("quality_assessment"):
            md += f"## Quality Assessment\n{wf.validation['quality_assessment']}\n"

        (wf.work_dir / "validation-report.md").write_text(md)
        logger.info("Validate complete: %s — %s", wf.workflow_id, "PASS" if wf.validation["passed"] else "FAIL")

    # ── Phase 5: Document ─────────────────────────────────────────────

    async def _phase_document(self, wf: TaskWorkflow) -> None:
        wf.phase = WorkflowPhase.DOCUMENT
        wf.updated_at = datetime.now(timezone.utc)

        # Write final summary to work_dir
        summary = {
            "workflow_id": wf.workflow_id,
            "goal": wf.goal,
            "agent_id": wf.agent_id,
            "project_id": wf.project_id,
            "created_at": wf.created_at.isoformat(),
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "approaches": len(wf.approaches),
            "plan_steps": len(wf.plan_steps),
            "execution_results": wf.execution_results,
            "validation": wf.validation,
            "files": list(wf._file_paths().keys()),
        }
        (wf.work_dir / "summary.json").write_text(
            json.dumps(summary, indent=2, default=str)
        )
        logger.info("Document complete: %s — summary written", wf.workflow_id)

    # ── Event Emission ────────────────────────────────────────────────

    def _emit(self, event_type: str, wf: TaskWorkflow, error: str | None = None) -> None:
        if not self.event_bus:
            return
        data: dict[str, Any] = {
            "workflow_id": wf.workflow_id,
            "goal": wf.goal,
            "agent_id": wf.agent_id,
            "project_id": wf.project_id,
            "phase": wf.phase.value,
        }
        if error:
            data["error"] = error
        self.event_bus.emit(event_type, data, source=f"task_workflow:{wf.agent_id}")

"""
NemoClaw Command Center — PlanningService (S1)

Automatic forward-planning after milestone completions.
Agents propose next phases, create follow-up tasks, and generate roadmaps.
Integrates with ApprovalService for phase-gate approvals.

JSON persistence to data/plans.json.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

log = logging.getLogger("cc.planning")

# Phase templates keyed by common milestone patterns
PHASE_TEMPLATES: dict[str, list[dict[str, Any]]] = {
    "research_complete": [
        {"title": "Analysis & Synthesis", "offset_days": 7, "priority": "high"},
        {"title": "Recommendation Report", "offset_days": 14, "priority": "medium"},
    ],
    "design_complete": [
        {"title": "Implementation Sprint", "offset_days": 14, "priority": "high"},
        {"title": "QA & Testing", "offset_days": 21, "priority": "high"},
        {"title": "Deployment", "offset_days": 28, "priority": "critical"},
    ],
    "launch_complete": [
        {"title": "Post-Launch Monitoring", "offset_days": 7, "priority": "high"},
        {"title": "Performance Review", "offset_days": 14, "priority": "medium"},
        {"title": "Iteration Planning", "offset_days": 21, "priority": "medium"},
    ],
    "default": [
        {"title": "Review & Retrospective", "offset_days": 3, "priority": "medium"},
        {"title": "Next Phase Planning", "offset_days": 7, "priority": "medium"},
    ],
}


class PlanningService:
    """Forward-planning service triggered by milestone completions."""

    def __init__(
        self,
        repo_root: Path,
        project_service: Any = None,
        approval_service: Any = None,
        notification_service: Any = None,
    ) -> None:
        self.repo_root = Path(repo_root)
        self.project_service = project_service
        self.approval_service = approval_service
        self.notification_service = notification_service
        self.data_dir: Path = self.repo_root / "command-center" / "backend" / "data"
        self.data_file: Path = self.data_dir / "plans.json"
        self.plans: dict[str, dict[str, Any]] = {}
        self._load()
        log.info("PlanningService initialized with %d plans from %s", len(self.plans), self.data_file)

    # ── Persistence ───────────────────────────────────────────────────

    def _load(self) -> None:
        if self.data_file.exists():
            try:
                data = json.loads(self.data_file.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    self.plans = data
                elif isinstance(data, list):
                    self.plans = {p["id"]: p for p in data if "id" in p}
                else:
                    self.plans = {}
            except (json.JSONDecodeError, KeyError) as exc:
                log.warning("Failed to load plans from %s: %s", self.data_file, exc)
                self.plans = {}
        else:
            self.plans = {}

    def _save(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        try:
            self.data_file.write_text(
                json.dumps(self.plans, indent=2, default=str),
                encoding="utf-8",
            )
        except OSError as exc:
            log.error("Failed to save plans to %s: %s", self.data_file, exc)

    @staticmethod
    def _generate_id() -> str:
        return uuid4().hex[:8]

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    # ── Core API ──────────────────────────────────────────────────────

    def propose_next_phase(
        self,
        project_id: str,
        agent_id: str,
    ) -> dict[str, Any]:
        """Create an approval request for the next phase of a project.

        Inspects current milestones to determine what phase comes next,
        then submits an approval request through ApprovalService.

        Returns:
            Dict with proposal details and approval_id (if approval service available).
        """
        project = self._get_project(project_id)
        if not project:
            return {"success": False, "reason": f"Project {project_id} not found"}

        milestones = project.get("milestones", [])
        completed = [m for m in milestones if m.get("status") == "completed"]
        pending = [m for m in milestones if m.get("status") in ("pending", "in_progress")]

        # Determine next phase from pending milestones
        next_milestone = pending[0] if pending else None
        phase_title = next_milestone["title"] if next_milestone else "New Phase"

        proposal_id = self._generate_id()
        now = self._now()

        proposal: dict[str, Any] = {
            "id": proposal_id,
            "project_id": project_id,
            "agent_id": agent_id,
            "phase_title": phase_title,
            "status": "pending_approval",
            "completed_milestones": len(completed),
            "remaining_milestones": len(pending),
            "created_at": now,
            "approval_id": None,
        }

        # Submit to approval service if available
        if self.approval_service and hasattr(self.approval_service, "create"):
            approval = self.approval_service.create(
                title=f"Phase proposal: {phase_title}",
                description=(
                    f"Agent {agent_id} proposes advancing project "
                    f"'{project.get('name', project_id)}' to phase: {phase_title}. "
                    f"{len(completed)} milestones completed, {len(pending)} remaining."
                ),
                category="task",
                priority="medium",
                requester=agent_id,
                metadata={"project_id": project_id, "proposal_id": proposal_id},
            )
            proposal["approval_id"] = approval.get("id")
            proposal["status"] = "awaiting_approval"
            log.info("Phase proposal submitted for approval: %s", approval.get("id"))

        self.plans[proposal_id] = proposal
        self._save()
        log.info(
            "Proposed next phase '%s' for project %s by agent %s",
            phase_title, project_id, agent_id,
        )
        return {"success": True, "proposal": proposal}

    def create_followup_tasks(
        self,
        project_id: str,
        completed_milestone: dict[str, Any],
    ) -> dict[str, Any]:
        """Queue follow-up tasks/milestones after a milestone completes.

        Matches the completed milestone title against phase templates
        to determine appropriate next steps.

        Returns:
            Dict with created milestones list.
        """
        project = self._get_project(project_id)
        if not project:
            return {"success": False, "reason": f"Project {project_id} not found"}

        title_lower = completed_milestone.get("title", "").lower()

        # Match template by keyword
        template_key = "default"
        for key in PHASE_TEMPLATES:
            if key == "default":
                continue
            # Check if the milestone title contains the phase keyword
            keyword = key.replace("_complete", "").replace("_", " ")
            if keyword in title_lower:
                template_key = key
                break

        template = PHASE_TEMPLATES[template_key]
        now = self._now()
        created_milestones: list[dict[str, Any]] = []

        for step in template:
            due = datetime.now(timezone.utc) + timedelta(days=step["offset_days"])
            # Only add if a similar milestone doesn't already exist
            existing_titles = {m.get("title", "").lower() for m in project.get("milestones", [])}
            if step["title"].lower() in existing_titles:
                continue

            if self.project_service and hasattr(self.project_service, "add_milestone"):
                milestone = self.project_service.add_milestone(
                    project_id=project_id,
                    title=step["title"],
                    description=f"Auto-generated follow-up after: {completed_milestone.get('title', 'milestone')}",
                    status="pending",
                    due_date=due.isoformat(),
                )
                if milestone:
                    created_milestones.append(milestone)

        # Record the plan
        plan_id = self._generate_id()
        self.plans[plan_id] = {
            "id": plan_id,
            "type": "followup",
            "project_id": project_id,
            "trigger_milestone": completed_milestone.get("id"),
            "trigger_title": completed_milestone.get("title"),
            "template_used": template_key,
            "milestones_created": [m.get("id") for m in created_milestones],
            "created_at": now,
        }
        self._save()

        log.info(
            "Created %d follow-up milestones for project %s (template: %s)",
            len(created_milestones), project_id, template_key,
        )
        return {"success": True, "created": created_milestones, "template": template_key}

    def generate_roadmap(
        self,
        project_id: str,
    ) -> dict[str, Any]:
        """Generate a multi-phase timeline with dependencies for a project.

        Returns:
            Roadmap dict with phases, dependencies, and timeline.
        """
        project = self._get_project(project_id)
        if not project:
            return {"success": False, "reason": f"Project {project_id} not found"}

        milestones = project.get("milestones", [])
        now = self._now()

        # Build phases from milestones
        phases: list[dict[str, Any]] = []
        for i, m in enumerate(milestones):
            phase: dict[str, Any] = {
                "order": i + 1,
                "milestone_id": m.get("id"),
                "title": m.get("title", "Untitled"),
                "status": m.get("status", "pending"),
                "due_date": m.get("due_date"),
                "depends_on": milestones[i - 1].get("id") if i > 0 else None,
            }
            phases.append(phase)

        # Compute overall progress
        total = len(phases)
        completed = sum(1 for p in phases if p["status"] == "completed")
        in_progress = sum(1 for p in phases if p["status"] == "in_progress")

        # Find critical path (longest chain of pending items)
        pending_phases = [p for p in phases if p["status"] in ("pending", "in_progress")]
        earliest_due = None
        latest_due = None
        for p in pending_phases:
            if p.get("due_date"):
                if earliest_due is None or p["due_date"] < earliest_due:
                    earliest_due = p["due_date"]
                if latest_due is None or p["due_date"] > latest_due:
                    latest_due = p["due_date"]

        roadmap: dict[str, Any] = {
            "project_id": project_id,
            "project_name": project.get("name", ""),
            "total_phases": total,
            "completed": completed,
            "in_progress": in_progress,
            "pending": total - completed - in_progress,
            "progress_pct": round((completed / total * 100) if total > 0 else 0.0, 1),
            "phases": phases,
            "timeline": {
                "earliest_pending_due": earliest_due,
                "latest_due": latest_due,
            },
            "generated_at": now,
        }

        log.info(
            "Generated roadmap for project %s: %d phases, %.1f%% complete",
            project_id, total, roadmap["progress_pct"],
        )
        return {"success": True, "roadmap": roadmap}

    # ── Query API ─────────────────────────────────────────────────────

    def get_plan(self, plan_id: str) -> Optional[dict[str, Any]]:
        return self.plans.get(plan_id)

    def list_plans(
        self,
        project_id: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        results = list(self.plans.values())
        if project_id:
            results = [p for p in results if p.get("project_id") == project_id]
        results.sort(key=lambda p: p.get("created_at", ""), reverse=True)
        return results

    def reload(self) -> None:
        self._load()

    # ── Helpers ────────────────────────────────────────────────────────

    def _get_project(self, project_id: str) -> Optional[dict[str, Any]]:
        if self.project_service and hasattr(self.project_service, "get_project"):
            return self.project_service.get_project(project_id)
        return None

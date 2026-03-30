"""
NemoClaw Execution Engine — ProjectLifecycleService (E-3)

10-stage project lifecycle with stage gate enforcement.
Stages: Ideation → Research → Planning → Design → Build → Launch → Sell → Deliver → Retain → Scale

Stage gate enforcement (#35): can't advance until exit criteria met.
Extends existing ProjectService — doesn't replace it.

NEW FILE: command-center/backend/app/services/project_lifecycle_service.py
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger("cc.lifecycle")


# ── Stage Definitions ──────────────────────────────────────────────────

LIFECYCLE_STAGES = [
    {
        "name": "ideation",
        "display": "Ideation",
        "agents": ["executive_operator", "strategy_lead", "engineering_lead"],
        "gate": {
            "description": "Problem validated, opportunity scored",
            "required_fields": ["problem_statement", "opportunity_score"],
        },
    },
    {
        "name": "research",
        "display": "Research",
        "agents": ["strategy_lead", "sales_outreach_lead"],
        "gate": {
            "description": "Market analysis complete, ICP defined",
            "required_fields": ["market_analysis", "icp_definition"],
        },
    },
    {
        "name": "planning",
        "display": "Planning",
        "agents": ["operations_lead", "product_lead"],
        "gate": {
            "description": "Plan approved, budget allocated, timeline set",
            "required_fields": ["plan_approved", "budget_allocated"],
        },
    },
    {
        "name": "design",
        "display": "Design",
        "agents": ["engineering_lead", "product_lead"],
        "gate": {
            "description": "Architecture approved, skill requirements listed",
            "required_fields": ["architecture_approved", "skill_requirements"],
        },
    },
    {
        "name": "build",
        "display": "Build",
        "agents": ["engineering_lead", "narrative_content_lead"],
        "gate": {
            "description": "Skills built, content created, tests pass",
            "required_fields": ["build_complete", "tests_pass"],
        },
    },
    {
        "name": "launch",
        "display": "Launch",
        "agents": ["marketing_campaigns_lead", "sales_outreach_lead"],
        "gate": {
            "description": "GTM plan executed, campaigns live",
            "required_fields": ["gtm_executed", "campaigns_live"],
        },
    },
    {
        "name": "sell",
        "display": "Sell",
        "agents": ["sales_outreach_lead", "marketing_campaigns_lead"],
        "gate": {
            "description": "Pipeline active, proposals sent",
            "required_fields": ["pipeline_active", "proposals_sent"],
        },
    },
    {
        "name": "deliver",
        "display": "Deliver",
        "agents": ["client_success_lead", "operations_lead"],
        "gate": {
            "description": "Deliverables produced and sent",
            "required_fields": ["deliverables_complete"],
        },
    },
    {
        "name": "retain",
        "display": "Retain",
        "agents": ["client_success_lead", "sales_outreach_lead"],
        "gate": {
            "description": "Health monitoring active, upsell identified",
            "required_fields": ["health_monitoring_active"],
        },
    },
    {
        "name": "scale",
        "display": "Scale",
        "agents": ["executive_operator", "growth_revenue_lead", "strategy_lead"],
        "gate": {
            "description": "Performance reviewed, expansion plan set",
            "required_fields": ["performance_reviewed", "expansion_plan"],
        },
    },
]

STAGE_NAMES = [s["name"] for s in LIFECYCLE_STAGES]
STAGE_INDEX = {s["name"]: i for i, s in enumerate(LIFECYCLE_STAGES)}


class ProjectLifecycleService:
    """
    Manages 10-stage project lifecycle with gate enforcement.

    Each project has a lifecycle_state dict:
      - current_stage: str
      - stage_data: dict[stage_name, dict] — gate field values per stage
      - history: list of stage transitions
    """

    def __init__(self, project_service):
        self.project_service = project_service
        logger.info("ProjectLifecycleService initialized (%d stages)", len(LIFECYCLE_STAGES))

    def initialize_lifecycle(self, project_id: str) -> dict[str, Any] | None:
        """Initialize lifecycle for a project (starts at Ideation)."""
        project = self.project_service.get_project(project_id)
        if not project:
            return None

        lifecycle = {
            "current_stage": "ideation",
            "stage_data": {s["name"]: {} for s in LIFECYCLE_STAGES},
            "history": [
                {
                    "stage": "ideation",
                    "action": "initialized",
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ],
        }

        # Store lifecycle on project
        project["lifecycle"] = lifecycle
        project["assigned_agents"] = LIFECYCLE_STAGES[0]["agents"]
        self.project_service._save()

        logger.info("Lifecycle initialized for project %s at Ideation", project_id)
        return lifecycle

    def get_lifecycle(self, project_id: str) -> dict[str, Any] | None:
        """Get lifecycle state for a project."""
        project = self.project_service.get_project(project_id)
        if not project:
            return None

        lifecycle = project.get("lifecycle")
        if not lifecycle:
            return None

        current = lifecycle["current_stage"]
        current_idx = STAGE_INDEX.get(current, 0)
        stage_def = LIFECYCLE_STAGES[current_idx]

        return {
            "project_id": project_id,
            "current_stage": current,
            "current_stage_display": stage_def["display"],
            "current_agents": stage_def["agents"],
            "gate": stage_def["gate"],
            "stage_data": lifecycle.get("stage_data", {}).get(current, {}),
            "progress": f"{current_idx + 1}/{len(LIFECYCLE_STAGES)}",
            "stages": [
                {
                    "name": s["name"],
                    "display": s["display"],
                    "status": (
                        "completed" if STAGE_INDEX[s["name"]] < current_idx
                        else "current" if s["name"] == current
                        else "upcoming"
                    ),
                }
                for s in LIFECYCLE_STAGES
            ],
            "history": lifecycle.get("history", []),
        }

    def update_stage_data(
        self, project_id: str, field: str, value: Any
    ) -> dict[str, Any] | None:
        """Update a gate field for the current stage."""
        project = self.project_service.get_project(project_id)
        if not project or "lifecycle" not in project:
            return None

        current = project["lifecycle"]["current_stage"]
        project["lifecycle"]["stage_data"].setdefault(current, {})[field] = value
        self.project_service._save()
        return project["lifecycle"]["stage_data"][current]

    def advance_stage(self, project_id: str, force: bool = False) -> dict[str, Any]:
        """
        Advance project to next lifecycle stage.

        Returns dict with success/failure and reason.
        Gate enforcement: all required_fields must be truthy unless force=True.
        """
        project = self.project_service.get_project(project_id)
        if not project or "lifecycle" not in project:
            return {"success": False, "reason": "Project or lifecycle not found"}

        lifecycle = project["lifecycle"]
        current = lifecycle["current_stage"]
        current_idx = STAGE_INDEX.get(current, 0)

        # Check if already at final stage
        if current_idx >= len(LIFECYCLE_STAGES) - 1:
            return {"success": False, "reason": "Already at final stage (Scale)"}

        # Gate check
        if not force:
            stage_def = LIFECYCLE_STAGES[current_idx]
            gate = stage_def["gate"]
            stage_data = lifecycle["stage_data"].get(current, {})
            missing = [
                f for f in gate["required_fields"]
                if not stage_data.get(f)
            ]
            if missing:
                return {
                    "success": False,
                    "reason": f"Gate not met: missing {', '.join(missing)}",
                    "gate": gate["description"],
                    "missing_fields": missing,
                }

        # Advance
        next_stage = LIFECYCLE_STAGES[current_idx + 1]
        lifecycle["current_stage"] = next_stage["name"]
        lifecycle["history"].append({
            "stage": next_stage["name"],
            "action": "advanced",
            "from_stage": current,
            "timestamp": datetime.utcnow().isoformat(),
            "forced": force,
        })

        # Update agents
        project["assigned_agents"] = next_stage["agents"]
        self.project_service._save()

        logger.info(
            "Project %s advanced: %s → %s",
            project_id, current, next_stage["name"],
        )

        return {
            "success": True,
            "previous_stage": current,
            "current_stage": next_stage["name"],
            "agents": next_stage["agents"],
        }

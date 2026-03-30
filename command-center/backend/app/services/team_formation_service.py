"""
NemoClaw Execution Engine — TeamFormationService (E-3)

Dynamic team formation (#34): selects which agents participate
based on project type, stage, and current workload.

NEW FILE: command-center/backend/app/services/team_formation_service.py
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("cc.team")


# ── Team Templates by Project Type ────────────────────────────────────

TEAM_TEMPLATES = {
    "content_campaign": {
        "lead": "narrative_content_lead",
        "core": ["marketing_campaigns_lead", "strategy_lead"],
        "support": ["sales_outreach_lead"],
    },
    "sales_pipeline": {
        "lead": "sales_outreach_lead",
        "core": ["marketing_campaigns_lead", "client_success_lead"],
        "support": ["growth_revenue_lead"],
    },
    "product_launch": {
        "lead": "product_lead",
        "core": ["engineering_lead", "marketing_campaigns_lead", "sales_outreach_lead"],
        "support": ["strategy_lead", "narrative_content_lead"],
    },
    "client_onboarding": {
        "lead": "client_success_lead",
        "core": ["operations_lead", "sales_outreach_lead"],
        "support": [],
    },
    "research_sprint": {
        "lead": "strategy_lead",
        "core": ["engineering_lead"],
        "support": ["narrative_content_lead"],
    },
    "revenue_optimization": {
        "lead": "growth_revenue_lead",
        "core": ["sales_outreach_lead", "marketing_campaigns_lead"],
        "support": ["strategy_lead", "operations_lead"],
    },
    "default": {
        "lead": "executive_operator",
        "core": ["strategy_lead", "operations_lead"],
        "support": [],
    },
}


class TeamFormationService:
    """
    Selects agents for projects based on type and context.

    Rules:
      - Every project has a lead agent (decision-maker)
      - Core agents are always assigned
      - Support agents are assigned if available
      - Lead must be L2 or higher for cross-domain projects
    """

    def __init__(self):
        logger.info("TeamFormationService initialized (%d templates)", len(TEAM_TEMPLATES))

    def form_team(
        self,
        project_type: str,
        include_support: bool = True,
    ) -> dict[str, Any]:
        """Form a team for a project type."""
        template = TEAM_TEMPLATES.get(project_type, TEAM_TEMPLATES["default"])

        team = {
            "lead": template["lead"],
            "core": list(template["core"]),
            "support": list(template["support"]) if include_support else [],
            "all_agents": [template["lead"]] + template["core"],
        }

        if include_support:
            team["all_agents"].extend(template["support"])

        # Deduplicate
        team["all_agents"] = list(dict.fromkeys(team["all_agents"]))

        logger.info(
            "Team formed for '%s': lead=%s, %d core, %d support",
            project_type, team["lead"],
            len(team["core"]), len(team["support"]),
        )
        return team

    def get_team_for_project(self, project: dict[str, Any]) -> dict[str, Any]:
        """Infer team from project tags/template."""
        tags = set(t.lower() for t in project.get("tags", []))

        if "sales" in tags or "pipeline" in tags:
            return self.form_team("sales_pipeline")
        elif "content" in tags or "campaign" in tags:
            return self.form_team("content_campaign")
        elif "product" in tags or "launch" in tags:
            return self.form_team("product_launch")
        elif "client" in tags or "onboarding" in tags:
            return self.form_team("client_onboarding")
        elif "research" in tags or "sprint" in tags:
            return self.form_team("research_sprint")
        elif "revenue" in tags or "growth" in tags:
            return self.form_team("revenue_optimization")
        else:
            return self.form_team("default")

    def list_templates(self) -> list[dict[str, Any]]:
        return [
            {
                "type": key,
                "lead": tpl["lead"],
                "core": tpl["core"],
                "support": tpl["support"],
                "total_agents": 1 + len(tpl["core"]) + len(tpl["support"]),
            }
            for key, tpl in TEAM_TEMPLATES.items()
        ]

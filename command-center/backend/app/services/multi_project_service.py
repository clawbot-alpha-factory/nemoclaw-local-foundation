"""
NemoClaw Execution Engine — MultiProjectService (E-3)

Multi-project management (#40): 5-10 concurrent projects.
Resource contention resolution, time allocation (70/20/10),
priority ranking.

NEW FILE: command-center/backend/app/services/multi_project_service.py
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("cc.multiproject")


class MultiProjectService:
    """
    Manages concurrent projects with resource allocation.

    Rules:
      - Max 10 concurrent active projects
      - Agents split time: 70% primary, 20% secondary, 10% support
      - Priority ranking determines resource allocation on contention
      - Agent with highest contention gets flagged
    """

    MAX_ACTIVE_PROJECTS = 10

    # Time allocation percentages by role
    TIME_ALLOCATION = {
        "lead": 0.40,     # 40% of agent's time
        "core": 0.30,     # 30% per project
        "support": 0.10,  # 10% per project
    }

    def __init__(self, project_service):
        self.project_service = project_service
        logger.info("MultiProjectService initialized")

    def get_active_projects(self) -> list[dict[str, Any]]:
        """Get all active projects sorted by priority."""
        projects = self.project_service.list_projects(status="active")
        # Sort by updated_at (most recent = highest priority)
        projects.sort(key=lambda p: p.get("updated_at", ""), reverse=True)
        return projects[:self.MAX_ACTIVE_PROJECTS]

    def get_agent_allocation(self, agent_id: str) -> dict[str, Any]:
        """Get time allocation for an agent across all active projects."""
        active = self.get_active_projects()
        allocations = []
        total_pct = 0.0

        for project in active:
            agents = project.get("assigned_agents", [])
            if agent_id in agents:
                # Determine role (simplified: first agent = lead)
                if agents and agents[0] == agent_id:
                    role = "lead"
                elif agent_id in agents[:3]:
                    role = "core"
                else:
                    role = "support"

                pct = self.TIME_ALLOCATION.get(role, 0.10)
                total_pct += pct

                allocations.append({
                    "project_id": project["id"],
                    "project_name": project.get("name", ""),
                    "role": role,
                    "time_allocation_pct": pct,
                })

        return {
            "agent_id": agent_id,
            "total_allocation_pct": round(total_pct, 2),
            "overallocated": total_pct > 1.0,
            "projects": allocations,
        }

    def get_resource_contention(self) -> dict[str, Any]:
        """Find agents that are overallocated."""
        active = self.get_active_projects()

        # Collect all assigned agents
        all_agents: set[str] = set()
        for p in active:
            all_agents.update(p.get("assigned_agents", []))

        contention = []
        for agent_id in sorted(all_agents):
            alloc = self.get_agent_allocation(agent_id)
            if alloc["overallocated"]:
                contention.append(alloc)

        return {
            "active_projects": len(active),
            "total_agents": len(all_agents),
            "overallocated_agents": len(contention),
            "contention": contention,
        }

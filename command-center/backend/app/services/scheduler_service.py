"""
NemoClaw Execution Engine — SchedulerService (E-4a)

Cron-like recurring tasks per agent (#1).
Each agent has a schedule of tasks that fire at defined intervals.

NEW FILE: command-center/backend/app/services/scheduler_service.py
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any, Callable

logger = logging.getLogger("cc.scheduler")


class ScheduledTask:
    """A recurring task definition."""

    def __init__(
        self,
        task_id: str,
        agent_id: str,
        description: str,
        interval_seconds: int,
        skill_id: str = "",
        inputs: dict[str, str] | None = None,
    ):
        self.task_id = task_id
        self.agent_id = agent_id
        self.description = description
        self.interval_seconds = interval_seconds
        self.skill_id = skill_id
        self.inputs = inputs or {}
        self.last_run: float = 0.0
        self.run_count: int = 0
        self.enabled: bool = True

    def is_due(self) -> bool:
        if not self.enabled:
            return False
        return (time.time() - self.last_run) >= self.interval_seconds

    def mark_run(self):
        self.last_run = time.time()
        self.run_count += 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "agent_id": self.agent_id,
            "description": self.description,
            "interval_seconds": self.interval_seconds,
            "skill_id": self.skill_id,
            "inputs": self.inputs,
            "last_run": datetime.fromtimestamp(self.last_run, tz=timezone.utc).isoformat() if self.last_run else None,
            "run_count": self.run_count,
            "enabled": self.enabled,
            "next_due_seconds": max(0, self.interval_seconds - (time.time() - self.last_run)) if self.last_run else 0,
        }


# ── Default Schedules ──────────────────────────────────────────────────

DEFAULT_SCHEDULES: list[dict[str, Any]] = [
    {
        "task_id": "sales-icp-scan",
        "agent_id": "sales_outreach_lead",
        "description": "Scan for new ICP matches",
        "interval_seconds": 86400,  # daily
        "skill_id": "e12-market-research-analyst",
        "inputs": {
            "research_topic": "New ICP matches for B2B SaaS outbound prospecting",
            "industry_context": "Technology and SaaS sales automation",
        },
    },
    {
        "task_id": "sales-followup",
        "agent_id": "sales_outreach_lead",
        "description": "Follow up pending outreach",
        "interval_seconds": 86400,  # daily
    },
    {
        "task_id": "marketing-ad-check",
        "agent_id": "marketing_campaigns_lead",
        "description": "Check ad performance",
        "interval_seconds": 14400,  # every 4 hours
    },
    {
        "task_id": "marketing-weekly-report",
        "agent_id": "marketing_campaigns_lead",
        "description": "Weekly campaign report",
        "interval_seconds": 604800,  # weekly
    },
    {
        "task_id": "cs-health-check",
        "agent_id": "client_success_lead",
        "description": "Client health score check",
        "interval_seconds": 86400,  # daily
    },
]


class SchedulerService:
    """
    Manages recurring task schedules for agents.

    Checks due tasks each tick and returns them to the agent loop.
    """

    def __init__(self):
        self.schedules: dict[str, ScheduledTask] = {}
        self._load_defaults()
        logger.info(
            "SchedulerService initialized (%d scheduled tasks)",
            len(self.schedules),
        )

    def _load_defaults(self):
        for s in DEFAULT_SCHEDULES:
            task = ScheduledTask(**s)
            self.schedules[task.task_id] = task

    def get_due_tasks(self, agent_id: str) -> list[ScheduledTask]:
        """Get tasks that are due for an agent."""
        return [
            t for t in self.schedules.values()
            if t.agent_id == agent_id and t.is_due()
        ]

    def get_agent_schedule(self, agent_id: str) -> list[dict[str, Any]]:
        """Get full schedule for an agent."""
        return [
            t.to_dict()
            for t in self.schedules.values()
            if t.agent_id == agent_id
        ]

    def add_task(
        self,
        task_id: str,
        agent_id: str,
        description: str,
        interval_seconds: int,
        skill_id: str = "",
        inputs: dict[str, str] | None = None,
    ) -> ScheduledTask:
        task = ScheduledTask(
            task_id=task_id,
            agent_id=agent_id,
            description=description,
            interval_seconds=interval_seconds,
            skill_id=skill_id,
            inputs=inputs,
        )
        self.schedules[task_id] = task
        return task

    def remove_task(self, task_id: str) -> bool:
        if task_id in self.schedules:
            del self.schedules[task_id]
            return True
        return False

    def toggle_task(self, task_id: str, enabled: bool) -> bool:
        task = self.schedules.get(task_id)
        if task:
            task.enabled = enabled
            return True
        return False

    def get_all_schedules(self) -> list[dict[str, Any]]:
        return [t.to_dict() for t in self.schedules.values()]

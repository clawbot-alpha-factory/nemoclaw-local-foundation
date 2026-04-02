"""
Task Dispatch Service (CC-TD)

Unified task dispatch from any UI surface — comms, projects, direct API.
Creates workflow → assigns to agent → logs activity → notifies agent.

NEW FILE: command-center/backend/app/services/task_dispatch_service.py
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger("cc.task_dispatch")


class TaskDispatchService:
    """Dispatch tasks to agents from any UI surface.

    Orchestrates: workflow creation → agent assignment → activity log → notification.
    """

    def __init__(
        self,
        agent_loop_service=None,
        notification_service=None,
        activity_log_service=None,
        event_bus=None,
        audit_service=None,
    ):
        self.agent_loop_service = agent_loop_service
        self.notification_service = notification_service
        self.activity_log_service = activity_log_service
        self.event_bus = event_bus
        self.audit_service = audit_service

        # In-memory dispatch log for status tracking
        self._dispatches: dict[str, dict] = {}

        logger.info("TaskDispatchService initialized")

    async def dispatch_task(
        self,
        agent_id: str,
        goal: str,
        source: str = "api",
        project_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Dispatch a task to a specific agent.

        Args:
            agent_id: Target agent ID (e.g. "strategy_lead")
            goal: Natural-language goal description
            source: Origin surface — "comms", "projects", "api"
            project_id: Optional project context

        Returns:
            {workflow_id, agent_id, status, created_at, ...}
        """
        dispatch_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc)

        # 1. Delegate to AgentLoopService.dispatch_task for workflow + execution
        workflow_id = None
        task_count = 0
        status = "dispatched"

        if self.agent_loop_service:
            result = await self.agent_loop_service.dispatch_task(
                agent_id=agent_id,
                goal=goal,
                source=source,
            )
            if not result.get("success"):
                error = result.get("error", "Dispatch failed")
                logger.error("dispatch_task failed: %s → %s", agent_id, error)

                record = {
                    "dispatch_id": dispatch_id,
                    "workflow_id": None,
                    "agent_id": agent_id,
                    "goal": goal,
                    "source": source,
                    "project_id": project_id,
                    "status": "failed",
                    "error": error,
                    "created_at": created_at.isoformat(),
                }
                self._dispatches[dispatch_id] = record
                return record

            workflow_id = result.get("workflow_id")
            task_count = result.get("task_count", 0)
        else:
            logger.warning("No agent_loop_service — dispatch recorded but not executed")
            status = "pending"

        # 2. Log to audit trail
        if self.audit_service:
            self.audit_service.log(
                action="task_dispatched",
                agent_id=agent_id,
                details={
                    "dispatch_id": dispatch_id,
                    "workflow_id": workflow_id,
                    "goal": goal[:500],
                    "source": source,
                    "project_id": project_id,
                    "task_count": task_count,
                },
            )

        # 3. Log to activity feed
        if self.activity_log_service:
            await self.activity_log_service.append(
                category="execution",
                action="task_dispatched",
                actor_type="user",
                actor_id=source,
                entity_type="task",
                entity_id=workflow_id or dispatch_id,
                summary=f"Task dispatched to {agent_id}: {goal[:120]}",
                details={
                    "dispatch_id": dispatch_id,
                    "agent_id": agent_id,
                    "project_id": project_id,
                    "source": source,
                },
            )

        # 4. Emit event for reactive subscribers
        if self.event_bus:
            self.event_bus.emit("task_dispatched", {
                "dispatch_id": dispatch_id,
                "workflow_id": workflow_id,
                "agent_id": agent_id,
                "goal": goal,
                "source": source,
                "project_id": project_id,
            })

        # 5. Build response record
        record = {
            "dispatch_id": dispatch_id,
            "workflow_id": workflow_id,
            "agent_id": agent_id,
            "goal": goal,
            "source": source,
            "project_id": project_id,
            "status": status,
            "task_count": task_count,
            "created_at": created_at.isoformat(),
        }
        self._dispatches[dispatch_id] = record

        logger.info(
            "Task dispatched: %s → agent=%s workflow=%s tasks=%d source=%s",
            dispatch_id[:8], agent_id,
            (workflow_id or "none")[:8], task_count, source,
        )

        return record

    def get_dispatch(self, dispatch_id: str) -> dict[str, Any] | None:
        """Look up a dispatch record by ID."""
        return self._dispatches.get(dispatch_id)

    def get_dispatches(
        self,
        agent_id: str | None = None,
        source: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """List recent dispatches, optionally filtered."""
        records = list(self._dispatches.values())

        if agent_id:
            records = [r for r in records if r["agent_id"] == agent_id]
        if source:
            records = [r for r in records if r["source"] == source]

        # Most recent first
        records.sort(key=lambda r: r["created_at"], reverse=True)
        return records[:limit]

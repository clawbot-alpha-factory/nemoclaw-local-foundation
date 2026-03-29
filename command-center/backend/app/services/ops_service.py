"""
NemoClaw Command Center — Ops Service (CC-6)
Provides task lifecycle management, budget/cost tracking, and system operations overview.
JSON persistence for tasks, activity feed, and dashboard aggregation.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

log = logging.getLogger("cc.cc.6")

VALID_STATUSES = {"pending", "in_progress", "blocked", "completed", "cancelled"}
TERMINAL_STATUSES = {"completed", "cancelled"}


class OpsService:
    """Central service for task management, budget tracking, and operations dashboard."""

    def __init__(self, repo_root: Path) -> None:
        """Initialize OpsService with repo root path and load persisted data.

        Args:
            repo_root: Path to the repository root directory.
        """
        self.repo_root = Path(repo_root)
        self.data_dir = self.repo_root / "command-center" / "backend" / "data"
        self.tasks_file = self.data_dir / "tasks.json"
        self.tasks: dict[str, dict[str, Any]] = {}
        self.activity_feed: list[dict[str, Any]] = []
        self._max_activity = 50
        self._load_tasks()
        log.info(
            "OpsService initialized — %d tasks loaded, data_dir=%s",
            len(self.tasks),
            self.data_dir,
        )

    # ── Persistence ────────────────────────────────────────────────────────

    def _load_tasks(self) -> None:
        """Load tasks and activity feed from JSON file on disk."""
        if self.tasks_file.exists():
            try:
                raw = json.loads(self.tasks_file.read_text(encoding="utf-8"))
                self.tasks = raw.get("tasks", {})
                self.activity_feed = raw.get("activity_feed", [])
                log.info("Loaded %d tasks from %s", len(self.tasks), self.tasks_file)
            except (json.JSONDecodeError, KeyError) as exc:
                log.warning("Failed to load tasks file %s: %s", self.tasks_file, exc)
                self.tasks = {}
                self.activity_feed = []
        else:
            log.info("No tasks file found at %s — starting fresh", self.tasks_file)
            self.tasks = {}
            self.activity_feed = []

    def _save_tasks(self) -> None:
        """Persist tasks and activity feed to JSON file on disk."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "tasks": self.tasks,
            "activity_feed": self.activity_feed,
            "saved_at": datetime.now(timezone.utc).isoformat(),
        }
        self.tasks_file.write_text(
            json.dumps(payload, indent=2, default=str), encoding="utf-8"
        )
        log.debug("Saved %d tasks to %s", len(self.tasks), self.tasks_file)

    def _record_activity(self, action: str, task_id: str, details: Optional[dict[str, Any]] = None) -> None:
        """Record an action in the activity feed.

        Args:
            action: Description of the action performed.
            task_id: ID of the task involved.
            details: Optional extra context for the activity entry.
        """
        entry = {
            "id": uuid4().hex[:8],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "task_id": task_id,
            "details": details or {},
        }
        self.activity_feed.insert(0, entry)
        self.activity_feed = self.activity_feed[: self._max_activity]

    # ── Task Lifecycle ─────────────────────────────────────────────────────

    def create_task(
        self,
        title: str,
        description: str = "",
        agent_id: Optional[str] = None,
        skill_id: Optional[str] = None,
        priority: str = "medium",
        tags: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """Create a new task and persist it.

        Args:
            title: Short title for the task.
            description: Longer description of what needs to be done.
            agent_id: Optional agent to assign the task to.
            skill_id: Optional skill linked to the task.
            priority: Priority level (critical, high, medium, low).
            tags: Optional list of tags for categorization.

        Returns:
            The newly created task dict.
        """
        task_id = uuid4().hex[:8]
        now = datetime.now(timezone.utc).isoformat()
        task: dict[str, Any] = {
            "id": task_id,
            "title": title,
            "description": description,
            "status": "pending",
            "priority": priority,
            "agent_id": agent_id,
            "skill_id": skill_id,
            "tags": tags or [],
            "created_at": now,
            "updated_at": now,
            "assigned_at": now if agent_id else None,
            "completed_at": None,
            "history": [
                {
                    "timestamp": now,
                    "action": "created",
                    "from_status": None,
                    "to_status": "pending",
                }
            ],
        }
        self.tasks[task_id] = task
        self._record_activity("task_created", task_id, {"title": title, "agent_id": agent_id})
        self._save_tasks()
        log.info("Created task %s: %s", task_id, title)
        return task

    def update_task(
        self,
        task_id: str,
        status: Optional[str] = None,
        agent_id: Optional[str] = None,
        title: Optional[str] = None,
        description: Optional[str] = None,
        priority: Optional[str] = None,
        tags: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """Update an existing task's fields and persist changes.

        Args:
            task_id: The ID of the task to update.
            status: New status (must be a valid status).
            agent_id: New agent assignment.
            title: Updated title.
            description: Updated description.
            priority: Updated priority.
            tags: Updated tags.

        Returns:
            The updated task dict.

        Raises:
            KeyError: If the task_id does not exist.
            ValueError: If the provided status is invalid.
        """
        if task_id not in self.tasks:
            raise KeyError(f"Task {task_id} not found")

        task = self.tasks[task_id]
        now = datetime.now(timezone.utc).isoformat()
        changes: dict[str, Any] = {}

        if status is not None:
            if status not in VALID_STATUSES:
                raise ValueError(
                    f"Invalid status '{status}'. Must be one of: {', '.join(sorted(VALID_STATUSES))}"
                )
            old_status = task["status"]
            if old_status != status:
                task["history"].append(
                    {
                        "timestamp": now,
                        "action": "status_change",
                        "from_status": old_status,
                        "to_status": status,
                    }
                )
                task["status"] = status
                changes["status"] = {"from": old_status, "to": status}
                if status in TERMINAL_STATUSES:
                    task["completed_at"] = now

        if agent_id is not None:
            old_agent = task["agent_id"]
            task["agent_id"] = agent_id
            task["assigned_at"] = now
            task["history"].append(
                {
                    "timestamp": now,
                    "action": "assigned",
                    "from_agent": old_agent,
                    "to_agent": agent_id,
                }
            )
            changes["agent_id"] = {"from": old_agent, "to": agent_id}

        if title is not None:
            task["title"] = title
            changes["title"] = title

        if description is not None:
            task["description"] = description
            changes["description"] = True

        if priority is not None:
            task["priority"] = priority
            changes["priority"] = priority

        if tags is not None:
            task["tags"] = tags
            changes["tags"] = tags

        task["updated_at"] = now
        action_name = "task_updated"
        if "status" in changes and changes["status"]["to"] in TERMINAL_STATUSES:
            action_name = "task_completed" if changes["status"]["to"] == "completed" else "task_cancelled"

        self._record_activity(action_name, task_id, changes)
        self._save_tasks()
        log.info("Updated task %s: %s", task_id, changes)
        return task

    def assign_task(self, task_id: str, agent_id: str) -> dict[str, Any]:
        """Assign a task to an agent and set status to in_progress if pending.

        Args:
            task_id: The ID of the task.
            agent_id: The agent ID to assign.

        Returns:
            The updated task dict.
        """
        task = self.tasks.get(task_id)
        if not task:
            raise KeyError(f"Task {task_id} not found")

        new_status = "in_progress" if task["status"] == "pending" else None
        return self.update_task(task_id, status=new_status, agent_id=agent_id)

    def complete_task(self, task_id: str) -> dict[str, Any]:
        """Mark a task as completed.

        Args:
            task_id: The ID of the task.

        Returns:
            The updated task dict.
        """
        return self.update_task(task_id, status="completed")

    def get_tasks(
        self,
        status: Optional[str] = None,
        agent_id: Optional[str] = None,
        priority: Optional[str] = None,
        skill_id: Optional[str] = None,
        search: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Get tasks with optional filtering.

        Args:
            status: Filter by task status.
            agent_id: Filter by assigned agent.
            priority: Filter by priority level.
            skill_id: Filter by linked skill.
            search: Free-text search in title and description.

        Returns:
            List of matching task dicts, sorted by updated_at descending.
        """
        results: list[dict[str, Any]] = []
        for task in self.tasks.values():
            if status and task["status"] != status:
                continue
            if agent_id and task["agent_id"] != agent_id:
                continue
            if priority and task["priority"] != priority:
                continue
            if skill_id and task["skill_id"] != skill_id:
                continue
            if search:
                needle = search.lower()
                haystack = f"{task['title']} {task['description']}".lower()
                if needle not in haystack:
                    continue
            results.append(task)

        results.sort(key=lambda t: t.get("updated_at", ""), reverse=True)
        return results

    # ── Budget / Cost Tracking ─────────────────────────────────────────────

    def _load_state_aggregator(self) -> dict[str, Any]:
        """Load budget data from the state_aggregator JSON file.

        Returns:
            Parsed state aggregator data or empty dict if not available.
        """
        candidates = [
            self.repo_root / "data" / "state_aggregator.json",
            self.repo_root / "command-center" / "backend" / "data" / "state_aggregator.json",
            self.repo_root / "state_aggregator.json",
        ]
        for path in candidates:
            if path.exists():
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                    log.debug("Loaded state_aggregator from %s", path)
                    return data
                except (json.JSONDecodeError, OSError) as exc:
                    log.warning("Failed to read state_aggregator at %s: %s", path, exc)
        log.debug("No state_aggregator file found")
        return {}

    def get_budget_overview(self) -> dict[str, Any]:
        """Compute budget overview with spend-per-provider trends and projections.

        Returns:
            Dict with budget totals, per-provider breakdown, burn rate, and projections.
        """
        state = self._load_state_aggregator()
        budget_data = state.get("budget", state.get("costs", {}))

        # Extract provider costs
        providers: dict[str, float] = {}
        total_spent = 0.0
        total_budget = 0.0

        if isinstance(budget_data, dict):
            total_spent = float(budget_data.get("total_spent", budget_data.get("spent", 0)))
            total_budget = float(budget_data.get("total_budget", budget_data.get("budget", 0)))
            provider_data = budget_data.get("providers", budget_data.get("by_provider", {}))
            if isinstance(provider_data, dict):
                for provider, info in provider_data.items():
                    if isinstance(info, (int, float)):
                        providers[provider] = float(info)
                    elif isinstance(info, dict):
                        providers[provider] = float(info.get("spent", info.get("cost", 0)))
                    total_for_providers = sum(providers.values())
                    if total_spent == 0 and total_for_providers > 0:
                        total_spent = total_for_providers

        # Compute burn rate and projections
        history = budget_data.get("history", []) if isinstance(budget_data, dict) else []
        daily_burn = 0.0
        if history and len(history) >= 2:
            try:
                recent = history[-7:] if len(history) >= 7 else history
                costs = [float(h.get("cost", h.get("spent", 0))) for h in recent]
                daily_burn = sum(costs) / len(costs) if costs else 0.0
            except (TypeError, ValueError):
                daily_burn = 0.0
        elif total_spent > 0:
            # Estimate from state metadata
            created_at = state.get("created_at", state.get("started_at"))
            if created_at:
                try:
                    start = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                    days_elapsed = max(
                        (datetime.now(timezone.utc) - start).total_seconds() / 86400, 1
                    )
                    daily_burn = total_spent / days_elapsed
                except (ValueError, TypeError):
                    daily_burn = 0.0

        remaining = max(total_budget - total_spent, 0) if total_budget > 0 else 0
        days_remaining = remaining / daily_burn if daily_burn > 0 else None
        monthly_projection = daily_burn * 30

        return {
            "total_budget": total_budget,
            "total_spent": total_spent,
            "remaining": remaining,
            "utilization_pct": round((total_spent / total_budget * 100), 2) if total_budget > 0 else 0,
            "daily_burn_rate": round(daily_burn, 4),
            "monthly_projection": round(monthly_projection, 2),
            "days_remaining": round(days_remaining, 1) if days_remaining is not None else None,
            "by_provider": {
                provider: {
                    "spent": round(cost, 4),
                    "pct_of_total": round(cost / total_spent * 100, 2) if total_spent > 0 else 0,
                }
                for provider, cost in sorted(providers.items(), key=lambda x: x[1], reverse=True)
            },
            "trend": self._compute_spend_trends(history),
            "computed_at": datetime.now(timezone.utc).isoformat(),
        }

    def _compute_spend_trends(self, history: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Compute daily spend trends from history data.

        Args:
            history: List of historical cost entries.

        Returns:
            List of trend data points.
        """
        if not history:
            return []

        trends: list[dict[str, Any]] = []
        for entry in history[-30:]:
            try:
                trends.append(
                    {
                        "date": entry.get("date", entry.get("timestamp", "unknown")),
                        "cost": float(entry.get("cost", entry.get("spent", 0))),
                        "provider": entry.get("provider", "unknown"),
                    }
                )
            except (TypeError, ValueError):
                continue
        return trends

    # ── System Operations Overview ─────────────────────────────────────────

    def _get_task_counts_by_status(self) -> dict[str, int]:
        """Count tasks grouped by status.

        Returns:
            Dict mapping status to task count.
        """
        counts: dict[str, int] = {s: 0 for s in VALID_STATUSES}
        for task in self.tasks.values():
            status = task.get("status", "pending")
            counts[status] = counts.get(status, 0) + 1
        return counts

    def _get_agent_utilization(self) -> list[dict[str, Any]]:
        """Compute agent utilization based on task assignments and completions.

        Returns:
            List of agent utilization records sorted by total tasks descending.
        """
        agent_stats: dict[str, dict[str, int]] = {}
        for task in self.tasks.values():
            aid = task.get("agent_id")
            if not aid:
                continue
            if aid not in agent_stats:
                agent_stats[aid] = {
                    "assigned": 0,
                    "completed": 0,
                    "in_progress": 0,
                    "blocked": 0,
                    "pending": 0,
                    "cancelled": 0,
                }
            agent_stats[aid]["assigned"] += 1
            status = task.get("status", "pending")
            if status in agent_stats[aid]:
                agent_stats[aid][status] += 1

        utilization: list[dict[str, Any]] = []
        for aid, stats in agent_stats.items():
            total = stats["assigned"]
            completed = stats["completed"]
            rate = round(completed / total * 100, 1) if total > 0 else 0.0
            utilization.append(
                {
                    "agent_id": aid,
                    "total_assigned": total,
                    "completed": completed,
                    "in_progress": stats["in_progress"],
                    "blocked": stats["blocked"],
                    "pending": stats["pending"],
                    "cancelled": stats["cancelled"],
                    "completion_rate": rate,
                }
            )

        utilization.sort(key=lambda x: x["total_assigned"], reverse=True)
        return utilization

    def get_activity_feed(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get the most recent activity entries.

        Args:
            limit: Maximum number of entries to return (default 50).

        Returns:
            List of activity feed entries, most recent first.
        """
        return self.activity_feed[:limit]

    # ── Dashboard ──────────────────────────────────────────────────────────

    def get_dashboard(self) -> dict[str, Any]:
        """Get a complete operations dashboard with tasks, budget, and system overview.

        Returns:
            Dict containing task summary, agent utilization, budget overview,
            and recent activity.
        """
        status_counts = self._get_task_counts_by_status()
        total_tasks = sum(status_counts.values())
        active_tasks = status_counts.get("in_progress", 0) + status_counts.get("pending", 0)

        return {
            "summary": {
                "total_tasks": total_tasks,
                "active_tasks": active_tasks,
                "by_status": status_counts,
                "completion_rate": round(
                    status_counts.get("completed", 0) / total_tasks * 100, 1
                )
                if total_tasks > 0
                else 0.0,
            },
            "agent_utilization": self._get_agent_utilization(),
            "budget": self.get_budget_overview(),
            "recent_activity": self.get_activity_feed(limit=10),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
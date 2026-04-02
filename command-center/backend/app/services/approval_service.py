"""
NemoClaw Command Center — Approval Service (CC-9)
Manages approval request CRUD, routing, queuing, and audit trail.
JSON persistence with in-memory state.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import uuid4

log = logging.getLogger("cc.cc.9")

PRIORITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}

CATEGORY_ROUTING = {
    "budget": "executive_operator",
    "task": "operations_lead",
    "deployment": "engineering_lead",
    "access": "executive_operator",
}

AUTHORITY_LEVELS = {
    "executive_operator": 1,
    "operations_lead": 2,
    "engineering_lead": 2,
    "senior_agent": 3,
    "agent": 4,
}

CONFLICT_HIERARCHY = ["retain", "close", "acquire"]


class ApprovalService:
    """Central service for approval requests, routing, queuing, and audit."""

    def __init__(self, repo_root: Path) -> None:
        """Initialize the ApprovalService with repo root path.

        Args:
            repo_root: Path to the repository root directory.
        """
        self.repo_root = Path(repo_root)
        self.data_dir: Path = self.repo_root / "command-center" / "backend" / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.approvals_file: Path = self.data_dir / "approvals.json"
        self.audit_file: Path = self.data_dir / "approval_audit.json"
        self.approvals: dict[str, dict] = {}
        self.audit_trail: list[dict] = []
        self._load()
        log.info(
            "ApprovalService initialized — %d approvals loaded, %d audit entries",
            len(self.approvals),
            len(self.audit_trail),
        )

    # ── Persistence ────────────────────────────────────────────────────────

    def _load(self) -> None:
        """Load approvals and audit trail from JSON files."""
        if self.approvals_file.exists():
            try:
                raw = json.loads(self.approvals_file.read_text(encoding="utf-8"))
                if isinstance(raw, list):
                    self.approvals = {a["id"]: a for a in raw}
                elif isinstance(raw, dict):
                    self.approvals = raw
                else:
                    self.approvals = {}
                log.info("Loaded %d approvals from %s", len(self.approvals), self.approvals_file)
            except (json.JSONDecodeError, KeyError) as exc:
                log.warning("Failed to load approvals file: %s", exc)
                self.approvals = {}
        else:
            self.approvals = {}

        if self.audit_file.exists():
            try:
                self.audit_trail = json.loads(self.audit_file.read_text(encoding="utf-8"))
                if not isinstance(self.audit_trail, list):
                    self.audit_trail = []
                log.info("Loaded %d audit entries from %s", len(self.audit_trail), self.audit_file)
            except json.JSONDecodeError as exc:
                log.warning("Failed to load audit file: %s", exc)
                self.audit_trail = []
        else:
            self.audit_trail = []

    def _save(self) -> None:
        """Persist approvals and audit trail to JSON files."""
        try:
            self.approvals_file.write_text(
                json.dumps(list(self.approvals.values()), indent=2, default=str),
                encoding="utf-8",
            )
            self.audit_file.write_text(
                json.dumps(self.audit_trail, indent=2, default=str),
                encoding="utf-8",
            )
        except OSError as exc:
            log.error("Failed to save approval data: %s", exc)

    # ── Normalization ─────────────────────────────────────────────────────

    def _normalize(self, approval: dict) -> dict:
        """Normalize internal approval dict to match frontend Approval interface.

        Maps internal field names to frontend-expected names and ensures all
        required fields are present.
        """
        return {
            "id": approval.get("id", ""),
            "title": approval.get("title", ""),
            "description": approval.get("description", ""),
            "status": approval.get("status", "pending"),
            "priority": approval.get("priority", "medium"),
            "category": approval.get("category", "general"),
            "requester": approval.get("requester") or approval.get("requested_by", ""),
            "assignee": approval.get("assignee") or approval.get("assigned_to"),
            "notes": approval.get("notes") or None,
            "reason": approval.get("reason") or None,
            "escalated_to": approval.get("escalated_to") or None,
            "created_at": approval.get("created_at", ""),
            "updated_at": approval.get("updated_at") or approval.get("created_at", ""),
            "resolved_at": approval.get("resolved_at") or None,
            "metadata": approval.get("metadata") or {},
        }

    # ── Audit ──────────────────────────────────────────────────────────────

    def _log_audit(
        self,
        approval_id: str,
        action: str,
        actor: str,
        details: Optional[str] = None,
    ) -> dict:
        """Record an audit trail entry for an approval action.

        Args:
            approval_id: The ID of the approval request.
            action: The action performed (created, approved, rejected, escalated, updated).
            actor: The agent or user performing the action.
            details: Optional additional details.

        Returns:
            The audit entry dict.
        """
        entry = {
            "id": uuid4().hex[:8],
            "approval_id": approval_id,
            "action": action,
            "actor": actor,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "details": {"message": details} if isinstance(details, str) else (details or {}),
        }
        self.audit_trail.append(entry)
        log.info(
            "Audit: %s on approval %s by %s — %s",
            action,
            approval_id,
            actor,
            details or "",
        )
        return entry

    # ── Routing ────────────────────────────────────────────────────────────

    def _route_approver(self, category: str) -> str:
        """Determine the default approver based on category.

        Args:
            category: The approval category (budget/task/deployment/access).

        Returns:
            The agent_id of the assigned approver.
        """
        approver = CATEGORY_ROUTING.get(category, "operations_lead")
        log.debug("Routing category '%s' to approver '%s'", category, approver)
        return approver

    def _get_escalation_target(self, current_approver: str) -> Optional[str]:
        """Get the next escalation target based on authority level.

        Escalation chain follows authority levels: 4 → 3 → 2 → 1.

        Args:
            current_approver: The current approver's agent_id.

        Returns:
            The agent_id of the escalation target, or None if at top level.
        """
        current_level = AUTHORITY_LEVELS.get(current_approver, 4)
        target_level = current_level - 1
        if target_level < 1:
            log.warning("Cannot escalate beyond authority level 1 for %s", current_approver)
            return None

        for agent_id, level in AUTHORITY_LEVELS.items():
            if level == target_level:
                log.info(
                    "Escalation: %s (level %d) → %s (level %d)",
                    current_approver,
                    current_level,
                    agent_id,
                    target_level,
                )
                return agent_id
        return None

    # ── Conflict Resolution ────────────────────────────────────────────────

    def resolve_conflict(self, action_a: str, action_b: str) -> str:
        """Resolve a conflict between two actions using the hierarchy.

        Conflict resolution hierarchy: retain > close > acquire.

        Args:
            action_a: First action.
            action_b: Second action.

        Returns:
            The winning action.
        """
        idx_a = CONFLICT_HIERARCHY.index(action_a) if action_a in CONFLICT_HIERARCHY else len(CONFLICT_HIERARCHY)
        idx_b = CONFLICT_HIERARCHY.index(action_b) if action_b in CONFLICT_HIERARCHY else len(CONFLICT_HIERARCHY)
        winner = action_a if idx_a <= idx_b else action_b
        log.info("Conflict resolution: '%s' vs '%s' → '%s'", action_a, action_b, winner)
        return winner

    # ── CRUD ───────────────────────────────────────────────────────────────

    def create(
        self,
        title: str,
        description: str,
        requested_by: str = "",
        priority: str = "medium",
        category: str = "general",
        notes: Optional[str] = None,
        assignee: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> dict:
        """Create a new approval request.

        Args:
            title: Title of the approval request.
            description: Detailed description.
            requested_by: The agent_id of the requester.
            priority: Priority level (low/medium/high/critical).
            category: Category for routing.
            notes: Optional notes.
            assignee: Optional explicit assignee (overrides routing).
            metadata: Optional metadata dict.

        Returns:
            The created approval request dict (normalized).
        """
        if priority not in PRIORITY_ORDER:
            raise ValueError(f"Invalid priority: {priority}. Must be one of {list(PRIORITY_ORDER.keys())}")

        approval_id = uuid4().hex[:8]
        now = datetime.now(timezone.utc).isoformat()
        assigned_to = assignee or CATEGORY_ROUTING.get(category, "operations_lead")

        approval = {
            "id": approval_id,
            "title": title,
            "description": description,
            "requester": requested_by,
            "assignee": assigned_to,
            "status": "pending",
            "priority": priority,
            "category": category,
            "created_at": now,
            "updated_at": now,
            "resolved_at": None,
            "notes": notes or "",
            "reason": None,
            "escalated_to": None,
            "metadata": metadata or {},
        }

        self.approvals[approval_id] = approval
        self._log_audit(approval_id, "created", requested_by, f"Assigned to {assigned_to}")
        self._save()

        log.info(
            "Created approval %s: '%s' [%s/%s] assigned to %s",
            approval_id,
            title,
            category,
            priority,
            assigned_to,
        )
        return self._normalize(approval)

    def list_all(
        self,
        status: Optional[str] = None,
        category: Optional[str] = None,
        priority: Optional[str] = None,
        requested_by: Optional[str] = None,
        assigned_to: Optional[str] = None,
    ) -> list[dict]:
        """List all approval requests with optional filters.

        Args:
            status: Filter by status.
            category: Filter by category.
            priority: Filter by priority.
            requested_by: Filter by requester agent_id.
            assigned_to: Filter by assigned approver agent_id.

        Returns:
            List of matching approval request dicts.
        """
        results = list(self.approvals.values())

        if status:
            results = [a for a in results if a["status"] == status]
        if category:
            results = [a for a in results if a["category"] == category]
        if priority:
            results = [a for a in results if a["priority"] == priority]
        if requested_by:
            results = [a for a in results if a["requested_by"] == requested_by]
        if assigned_to:
            results = [a for a in results if (a.get("assigned_to") or a.get("assignee")) == assigned_to]

        log.debug("Listed %d approvals (filters: status=%s, category=%s, priority=%s)", len(results), status, category, priority)
        return [self._normalize(a) for a in results]

    def get(self, approval_id: str) -> Optional[dict]:
        """Get a single approval request by ID.

        Args:
            approval_id: The approval request ID.

        Returns:
            The approval request dict, or None if not found.
        """
        approval = self.approvals.get(approval_id)
        if not approval:
            log.warning("Approval %s not found", approval_id)
            return None
        return self._normalize(approval)

    def approve(
        self,
        approval_id: str,
        approved_by: str,
        notes: Optional[str] = None,
    ) -> Optional[dict]:
        """Approve a pending approval request.

        Args:
            approval_id: The approval request ID.
            approved_by: The agent_id of the approver.
            notes: Optional approval notes.

        Returns:
            The updated approval request dict, or None if not found.

        Raises:
            ValueError: If the approval is not in pending status.
        """
        approval = self.approvals.get(approval_id)
        if not approval:
            log.warning("Cannot approve: approval %s not found", approval_id)
            return None

        if approval["status"] != "pending":
            raise ValueError(
                f"Cannot approve: approval {approval_id} is '{approval['status']}', not 'pending'"
            )

        now = datetime.now(timezone.utc).isoformat()
        approval["status"] = "approved"
        approval["updated_at"] = now
        approval["resolved_at"] = now
        if notes:
            approval["notes"] = f"{approval.get('notes', '')}\n[Approved] {notes}".strip()

        self._log_audit(approval_id, "approved", approved_by, notes)
        self._save()

        log.info("Approval %s approved by %s", approval_id, approved_by)
        return self._normalize(approval)

    def reject(
        self,
        approval_id: str,
        rejected_by: str,
        notes: Optional[str] = None,
    ) -> Optional[dict]:
        """Reject a pending approval request.

        Args:
            approval_id: The approval request ID.
            rejected_by: The agent_id of the rejector.
            notes: Optional rejection reason.

        Returns:
            The updated approval request dict, or None if not found.

        Raises:
            ValueError: If the approval is not in pending status.
        """
        approval = self.approvals.get(approval_id)
        if not approval:
            log.warning("Cannot reject: approval %s not found", approval_id)
            return None

        if approval["status"] != "pending":
            raise ValueError(
                f"Cannot reject: approval {approval_id} is '{approval['status']}', not 'pending'"
            )

        now = datetime.now(timezone.utc).isoformat()
        approval["status"] = "rejected"
        approval["updated_at"] = now
        approval["resolved_at"] = now
        approval["reason"] = notes
        if notes:
            approval["notes"] = f"{approval.get('notes', '')}\n[Rejected] {notes}".strip()

        self._log_audit(approval_id, "rejected", rejected_by, notes)
        self._save()

        log.info("Approval %s rejected by %s", approval_id, rejected_by)
        return self._normalize(approval)

    def escalate(
        self,
        approval_id: str,
        escalated_by: str,
        notes: Optional[str] = None,
    ) -> Optional[dict]:
        """Escalate a pending approval request to a higher authority.

        Args:
            approval_id: The approval request ID.
            escalated_by: The agent_id initiating escalation.
            notes: Optional escalation reason.

        Returns:
            The updated approval request dict, or None if not found or cannot escalate.

        Raises:
            ValueError: If the approval is not in pending status or cannot be escalated.
        """
        approval = self.approvals.get(approval_id)
        if not approval:
            log.warning("Cannot escalate: approval %s not found", approval_id)
            return None

        if approval["status"] != "pending":
            raise ValueError(
                f"Cannot escalate: approval {approval_id} is '{approval['status']}', not 'pending'"
            )

        current_assignee = approval.get("assigned_to", "agent")
        escalation_target = self._get_escalation_target(current_assignee)

        if not escalation_target:
            raise ValueError(
                f"Cannot escalate: approval {approval_id} is already at the highest authority level"
            )

        now = datetime.now(timezone.utc).isoformat()
        approval["status"] = "escalated"
        approval["assignee"] = escalation_target
        approval["assigned_to"] = escalation_target
        approval["escalated_to"] = escalation_target
        approval["updated_at"] = now
        if notes:
            approval["notes"] = f"{approval.get('notes', '')}\n[Escalated] {notes}".strip()

        self._log_audit(
            approval_id,
            "escalated",
            escalated_by,
            f"Escalated from {current_assignee} to {escalation_target}. {notes or ''}".strip(),
        )
        self._save()

        log.info(
            "Approval %s escalated from %s to %s by %s",
            approval_id,
            current_assignee,
            escalation_target,
            escalated_by,
        )
        return self._normalize(approval)

    def update(
        self,
        approval_id: str,
        updated_by: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        priority: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Optional[dict]:
        """Update fields on a pending approval request.

        Args:
            approval_id: The approval request ID.
            updated_by: The agent_id performing the update.
            title: New title, if changing.
            description: New description, if changing.
            priority: New priority, if changing.
            notes: Additional notes to append.

        Returns:
            The updated approval request dict, or None if not found.

        Raises:
            ValueError: If the approval is not in pending status or invalid priority.
        """
        approval = self.approvals.get(approval_id)
        if not approval:
            log.warning("Cannot update: approval %s not found", approval_id)
            return None

        if approval["status"] not in ("pending",):
            raise ValueError(
                f"Cannot update: approval {approval_id} is '{approval['status']}', not 'pending'"
            )

        changes = []
        if title is not None:
            approval["title"] = title
            changes.append(f"title='{title}'")
        if description is not None:
            approval["description"] = description
            changes.append("description updated")
        if priority is not None:
            if priority not in PRIORITY_ORDER:
                raise ValueError(f"Invalid priority: {priority}")
            approval["priority"] = priority
            changes.append(f"priority='{priority}'")
        if notes is not None:
            approval["notes"] = f"{approval['notes']}\n[Updated] {notes}".strip()
            changes.append("notes appended")

        approval["updated_at"] = datetime.now(timezone.utc).isoformat()
        change_summary = ", ".join(changes) if changes else "no changes"
        self._log_audit(approval_id, "updated", updated_by, change_summary)
        self._save()

        log.info("Approval %s updated by %s: %s", approval_id, updated_by, change_summary)
        return self._normalize(approval)

    def delete(self, approval_id: str, deleted_by: str) -> bool:
        """Delete an approval request.

        Args:
            approval_id: The approval request ID.
            deleted_by: The agent_id performing the deletion.

        Returns:
            True if deleted, False if not found.
        """
        if approval_id not in self.approvals:
            log.warning("Cannot delete: approval %s not found", approval_id)
            return False

        del self.approvals[approval_id]
        self._log_audit(approval_id, "deleted", deleted_by)
        self._save()

        log.info("Approval %s deleted by %s", approval_id, deleted_by)
        return True

    # ── Queue ──────────────────────────────────────────────────────────────

    def get_queue(
        self,
        assigned_to: Optional[str] = None,
        category: Optional[str] = None,
    ) -> list[dict]:
        """Get the pending approval queue sorted by priority and age.

        Sorted by: priority (critical first), then creation time (oldest first).

        Args:
            assigned_to: Optional filter by assigned approver.
            category: Optional filter by category.

        Returns:
            Sorted list of pending approval request dicts.
        """
        pending = [a for a in self.approvals.values() if a["status"] == "pending"]

        if assigned_to:
            pending = [a for a in pending if a.get("assigned_to") == assigned_to]
        if category:
            pending = [a for a in pending if a["category"] == category]

        pending.sort(
            key=lambda a: (
                PRIORITY_ORDER.get(a["priority"], 99),
                a["created_at"],
            )
        )

        log.debug("Queue: %d pending items (assigned_to=%s, category=%s)", len(pending), assigned_to, category)
        return [self._normalize(a) for a in pending]

    # ── Stats ──────────────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        """Get summary statistics for all approval requests.

        Returns:
            Dict with counts by status, category, priority, and queue depth.
        """
        all_approvals = list(self.approvals.values())

        status_counts: dict[str, int] = {}
        category_counts: dict[str, int] = {}
        priority_counts: dict[str, int] = {}

        for a in all_approvals:
            status_counts[a["status"]] = status_counts.get(a["status"], 0) + 1
            category_counts[a["category"]] = category_counts.get(a["category"], 0) + 1
            priority_counts[a["priority"]] = priority_counts.get(a["priority"], 0) + 1

        queue = self.get_queue()

        return {
            "total": len(all_approvals),
            "by_status": status_counts,
            "by_category": category_counts,
            "by_priority": priority_counts,
            "queue_depth": len(queue),
            "critical_pending": sum(1 for a in queue if a["priority"] == "critical"),
            "high_pending": sum(1 for a in queue if a["priority"] == "high"),
        }

    # ── Audit Trail Access ─────────────────────────────────────────────────

    def get_audit_trail(
        self,
        approval_id: Optional[str] = None,
        actor: Optional[str] = None,
        action: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict]:
        """Retrieve audit trail entries with optional filters.

        Args:
            approval_id: Filter by approval request ID.
            actor: Filter by actor agent_id.
            action: Filter by action type.
            limit: Maximum number of entries to return.

        Returns:
            List of audit trail entry dicts, most recent first.
        """
        results = list(self.audit_trail)

        if approval_id:
            results = [e for e in results if e["approval_id"] == approval_id]
        if actor:
            results = [e for e in results if e["actor"] == actor]
        if action:
            results = [e for e in results if e["action"] == action]

        results.sort(key=lambda e: e["timestamp"], reverse=True)
        return results[:limit]

    # ── Blockers ──────────────────────────────────────────────────────────

    BLOCKER_CATEGORIES = frozenset([
        "account_creation", "login", "api_key", "external_service",
        "budget", "deployment", "infrastructure",
    ])

    def get_blockers(self) -> list[dict]:
        """Get pending approvals in blocker categories, sorted by priority."""
        pending = [a for a in self.approvals.values() if a["status"] in ("pending", "escalated")]
        blockers = [a for a in pending if a.get("category") in self.BLOCKER_CATEGORIES]
        blockers.sort(key=lambda a: (PRIORITY_ORDER.get(a["priority"], 99), a["created_at"]))
        return [self._normalize(a) for a in blockers]

    # ── History ──────────────────────────────────────────────────────────

    def get_history(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        """Get resolved approvals (approved/rejected), most recent first."""
        resolved = [a for a in self.approvals.values() if a["status"] in ("approved", "rejected")]
        resolved.sort(key=lambda a: a.get("resolved_at") or a.get("updated_at", ""), reverse=True)
        return [self._normalize(a) for a in resolved[offset:offset + limit]]

    # ── Bulk Operations ──────────────────────────────────────────────────

    def bulk_approve(
        self,
        ids: list[str],
        approved_by: str = "system",
        notes: str = "Bulk approved",
    ) -> dict:
        """Approve multiple pending approvals at once.

        Returns:
            Dict with succeeded, failed, and total counts.
        """
        succeeded = []
        failed = []
        for aid in ids:
            try:
                result = self.approve(approval_id=aid, approved_by=approved_by, notes=notes)
                if result:
                    succeeded.append(result)
                else:
                    failed.append({"id": aid, "error": "Not found"})
            except (ValueError, Exception) as e:
                failed.append({"id": aid, "error": str(e)})
        return {"succeeded": succeeded, "failed": failed, "total": len(ids)}

    def bulk_reject(
        self,
        ids: list[str],
        rejected_by: str = "system",
        reason: str = "Bulk rejected",
    ) -> dict:
        """Reject multiple pending approvals at once.

        Returns:
            Dict with succeeded, failed, and total counts.
        """
        succeeded = []
        failed = []
        for aid in ids:
            try:
                result = self.reject(approval_id=aid, rejected_by=rejected_by, notes=reason)
                if result:
                    succeeded.append(result)
                else:
                    failed.append({"id": aid, "error": "Not found"})
            except (ValueError, Exception) as e:
                failed.append({"id": aid, "error": str(e)})
        return {"succeeded": succeeded, "failed": failed, "total": len(ids)}

    # ── Reload ─────────────────────────────────────────────────────────────

    def reload(self) -> None:
        """Reload all data from disk."""
        self._load()
        log.info("ApprovalService reloaded — %d approvals", len(self.approvals))
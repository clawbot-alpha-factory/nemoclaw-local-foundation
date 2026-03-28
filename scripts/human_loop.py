#!/usr/bin/env python3
"""
NemoClaw Human-in-the-Loop v1.0 (MA-16)

Unified human approval workflow for all MA systems:
- 4 actions: approve, reject, modify, defer
- 6 approval categories from across MA systems
- Configurable expiry per approval type
- Priority-based ordering (critical first)
- Context-rich approval requests with full provenance
- Approval history and audit trail
- MA-4 decision log integration

Usage:
  python3 scripts/human_loop.py --test
  python3 scripts/human_loop.py --pending
  python3 scripts/human_loop.py --approve APPROVAL_ID
  python3 scripts/human_loop.py --reject APPROVAL_ID --reason "explanation"
  python3 scripts/human_loop.py --history
  python3 scripts/human_loop.py --stats
  python3 scripts/human_loop.py --expire
"""

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import defaultdict

REPO = Path.home() / "nemoclaw-local-foundation"
HITL_DIR = Path.home() / ".nemoclaw" / "human-loop"
PENDING_PATH = HITL_DIR / "pending.json"
HISTORY_PATH = HITL_DIR / "approval-history.jsonl"
STATS_PATH = HITL_DIR / "approval-stats.json"

# ═══════════════════════════════════════════════════════════════════════════════
# APPROVAL CATEGORIES & EXPIRY CONFIG
# ═══════════════════════════════════════════════════════════════════════════════

APPROVAL_CATEGORIES = {
    "cost_override": {
        "description": "Plan or task exceeds cost threshold",
        "source": "MA-5/MA-6",
        "default_priority": "high",
        "expiry_hours": 24,
        "expiry_action": "reject",  # reject | defer | escalate
    },
    "circuit_breaker": {
        "description": "Cost circuit breaker tripped, override requested",
        "source": "MA-6",
        "default_priority": "critical",
        "expiry_hours": 4,
        "expiry_action": "reject",
    },
    "behavior_escalation": {
        "description": "Agent behavior violation escalated",
        "source": "MA-8",
        "default_priority": "high",
        "expiry_hours": 48,
        "expiry_action": "defer",
    },
    "lesson_approval": {
        "description": "High-risk process/system lesson needs approval",
        "source": "MA-13",
        "default_priority": "medium",
        "expiry_hours": 72,
        "expiry_action": "defer",
    },
    "quality_escalation": {
        "description": "Output failed quality gate after max revisions",
        "source": "MA-15",
        "default_priority": "high",
        "expiry_hours": 24,
        "expiry_action": "reject",
    },
    "decision_review": {
        "description": "Agent requests human input on a decision",
        "source": "MA-4",
        "default_priority": "medium",
        "expiry_hours": 48,
        "expiry_action": "defer",
    },
}

PRIORITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}

VALID_ACTIONS = {"approve", "reject", "modify", "defer"}


# ═══════════════════════════════════════════════════════════════════════════════
# APPROVAL REQUEST
# ═══════════════════════════════════════════════════════════════════════════════

def new_approval(category, title, description, requesting_agent,
                  priority=None, context=None, options=None,
                  related_ids=None, expiry_hours=None):
    """Create a new approval request.

    Args:
        category: one of APPROVAL_CATEGORIES keys
        title: short summary
        description: detailed context for reviewer
        requesting_agent: which agent triggered this
        priority: override priority (critical/high/medium/low)
        context: dict with source-specific data
        options: list of choices for human to pick from
        related_ids: list of related decision/lesson/plan IDs
        expiry_hours: override expiry (None = use category default)
    """
    cat_def = APPROVAL_CATEGORIES.get(category, {})
    prio = priority or cat_def.get("default_priority", "medium")
    exp_h = expiry_hours if expiry_hours is not None else cat_def.get("expiry_hours", 48)

    now = datetime.now(timezone.utc)
    expires_at = (now + timedelta(hours=exp_h)).isoformat() if exp_h > 0 else None

    return {
        "id": f"approval_{uuid.uuid4().hex[:8]}",
        "created_at": now.isoformat(),
        "category": category,
        "title": title,
        "description": description,
        "requesting_agent": requesting_agent,
        "priority": prio,
        "context": context or {},
        "options": options or [],
        "related_ids": related_ids or [],
        "status": "pending",  # pending | approved | rejected | modified | deferred | expired
        "expires_at": expires_at,
        "expiry_action": cat_def.get("expiry_action", "defer"),
        "action_taken": None,
        "action_by": None,
        "action_at": None,
        "action_reason": None,
        "modification": None,  # for modify action
        "deferred_until": None,  # for defer action
    }


# ═══════════════════════════════════════════════════════════════════════════════
# APPROVAL QUEUE
# ═══════════════════════════════════════════════════════════════════════════════

class ApprovalQueue:
    """Persistent approval queue with priority ordering."""

    def __init__(self):
        self.approvals = {}  # id → approval
        self._load()

    def _load(self):
        HITL_DIR.mkdir(parents=True, exist_ok=True)
        if PENDING_PATH.exists():
            try:
                with open(PENDING_PATH) as f:
                    self.approvals = json.load(f)
            except (json.JSONDecodeError, IOError):
                self.approvals = {}

    def _save(self):
        HITL_DIR.mkdir(parents=True, exist_ok=True)
        with open(PENDING_PATH, "w") as f:
            json.dump(self.approvals, f, indent=2)

    def submit(self, approval):
        """Submit a new approval request.

        Returns: (approval_id, position_in_queue)
        """
        self.approvals[approval["id"]] = approval
        self._save()
        position = self._get_position(approval["id"])
        return approval["id"], position

    def get_pending(self, category=None, priority=None):
        """Get pending approvals, sorted by priority then age.

        Returns: list of approvals (critical first, oldest first within priority)
        """
        pending = [a for a in self.approvals.values() if a["status"] == "pending"]

        if category:
            pending = [a for a in pending if a["category"] == category]
        if priority:
            pending = [a for a in pending if a["priority"] == priority]

        pending.sort(key=lambda a: (
            PRIORITY_ORDER.get(a["priority"], 99),
            a["created_at"],
        ))
        return pending

    def get(self, approval_id):
        return self.approvals.get(approval_id)

    def _get_position(self, approval_id):
        """Get position in priority queue."""
        pending = self.get_pending()
        for i, a in enumerate(pending):
            if a["id"] == approval_id:
                return i + 1
        return 0


# ═══════════════════════════════════════════════════════════════════════════════
# HUMAN ACTION HANDLER
# ═══════════════════════════════════════════════════════════════════════════════

class HumanActionHandler:
    """Handles human actions on approval requests."""

    def __init__(self, queue):
        self.queue = queue
        self.history_log = ApprovalHistory()
        self.stats = ApprovalStats()

    def approve(self, approval_id, reason="", acted_by="human_operator"):
        """Approve a pending request.

        Returns: (success, message)
        """
        return self._act(approval_id, "approved", reason, acted_by)

    def reject(self, approval_id, reason="", acted_by="human_operator"):
        """Reject a pending request.

        Returns: (success, message)
        """
        return self._act(approval_id, "rejected", reason, acted_by)

    def modify(self, approval_id, modification, reason="", acted_by="human_operator"):
        """Approve with modifications.

        Args:
            modification: dict describing changes (e.g., {"new_budget": 20, "new_scope": "reduced"})

        Returns: (success, message)
        """
        approval = self.queue.get(approval_id)
        if not approval:
            return False, f"Approval {approval_id} not found"
        if approval["status"] != "pending":
            return False, f"Approval already {approval['status']}"

        approval["modification"] = modification
        return self._act(approval_id, "modified", reason, acted_by)

    def defer(self, approval_id, defer_hours=24, reason="", acted_by="human_operator"):
        """Defer a decision for later review.

        Returns: (success, message)
        """
        approval = self.queue.get(approval_id)
        if not approval:
            return False, f"Approval {approval_id} not found"
        if approval["status"] != "pending":
            return False, f"Approval already {approval['status']}"

        new_expiry = (datetime.now(timezone.utc) + timedelta(hours=defer_hours)).isoformat()
        approval["deferred_until"] = new_expiry
        approval["expires_at"] = new_expiry

        return self._act(approval_id, "deferred", reason, acted_by)

    def _act(self, approval_id, action, reason, acted_by):
        """Execute an action on an approval."""
        approval = self.queue.get(approval_id)
        if not approval:
            return False, f"Approval {approval_id} not found"
        if approval["status"] != "pending" and action != "deferred":
            return False, f"Approval already {approval['status']}"

        now = datetime.now(timezone.utc).isoformat()
        approval["status"] = action
        approval["action_taken"] = action
        approval["action_by"] = acted_by
        approval["action_at"] = now
        approval["action_reason"] = reason

        self.queue._save()

        # Log to history
        self.history_log.record(approval)

        # Update stats
        self.stats.record(approval)

        # Log to MA-4
        self._log_to_decisions(approval)

        return True, f"Approval {approval_id}: {action}"

    def expire_stale(self):
        """Expire pending approvals past their expiry time.

        Returns: list of expired approval IDs
        """
        now = datetime.now(timezone.utc)
        expired = []

        for aid, approval in self.queue.approvals.items():
            if approval["status"] != "pending":
                continue

            expires_at = approval.get("expires_at")
            if not expires_at:
                continue

            try:
                exp_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                continue

            if now >= exp_dt:
                expiry_action = approval.get("expiry_action", "reject")

                if expiry_action == "reject":
                    approval["status"] = "expired"
                    approval["action_taken"] = "expired_reject"
                elif expiry_action == "defer":
                    # Extend by original expiry period
                    cat_def = APPROVAL_CATEGORIES.get(approval["category"], {})
                    new_hours = cat_def.get("expiry_hours", 48)
                    approval["expires_at"] = (now + timedelta(hours=new_hours)).isoformat()
                    approval["action_taken"] = "expired_deferred"
                    continue  # don't mark as expired
                elif expiry_action == "escalate":
                    approval["status"] = "expired"
                    approval["action_taken"] = "expired_escalated"
                else:
                    approval["status"] = "expired"
                    approval["action_taken"] = "expired"

                approval["action_at"] = now.isoformat()
                approval["action_by"] = "system"
                approval["action_reason"] = f"Auto-expired: {expiry_action}"

                expired.append(aid)
                self.history_log.record(approval)
                self.stats.record(approval)

        if expired:
            self.queue._save()

        return expired

    def _log_to_decisions(self, approval):
        """Log approval action to MA-4."""
        try:
            sys.path.insert(0, str(REPO / "scripts"))
            from decision_log import DecisionLog
            dl = DecisionLog()
            title = f"Human approval: {approval['action_taken']} — {approval['title'][:50]}"
            desc = (
                f"Category: {approval['category']}\n"
                f"Agent: {approval['requesting_agent']}\n"
                f"Action: {approval['action_taken']}\n"
                f"By: {approval['action_by']}\n"
                f"Reason: {approval.get('action_reason', 'N/A')}\n"
            )
            if approval.get("modification"):
                desc += f"Modification: {json.dumps(approval['modification'])[:100]}\n"
            dec_id, _ = dl.propose("executive_operator", title, desc,
                                    reversibility="reversible", confidence=0.95)
            dl.decide(dec_id, f"Human: {approval['action_taken']}",
                     approval.get("action_reason", "")[:100], decided_by="human_operator")
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════════════════════
# APPROVAL HISTORY
# ═══════════════════════════════════════════════════════════════════════════════

class ApprovalHistory:
    """Persistent approval history for audit trail."""

    def record(self, approval):
        HITL_DIR.mkdir(parents=True, exist_ok=True)
        entry = {
            "timestamp": approval.get("action_at", datetime.now(timezone.utc).isoformat()),
            "approval_id": approval["id"],
            "category": approval["category"],
            "title": approval["title"][:80],
            "requesting_agent": approval["requesting_agent"],
            "priority": approval["priority"],
            "action": approval.get("action_taken", "unknown"),
            "action_by": approval.get("action_by", "unknown"),
            "reason": approval.get("action_reason", ""),
            "modification": approval.get("modification"),
            "wait_time_s": self._calc_wait_time(approval),
        }
        with open(HISTORY_PATH, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def _calc_wait_time(self, approval):
        """Calculate how long the approval waited."""
        try:
            created = datetime.fromisoformat(approval["created_at"].replace("Z", "+00:00"))
            acted = datetime.fromisoformat(
                (approval.get("action_at") or approval["created_at"]).replace("Z", "+00:00"))
            return round((acted - created).total_seconds(), 1)
        except (ValueError, AttributeError):
            return 0

    def get_recent(self, n=20):
        """Get recent approval history."""
        if not HISTORY_PATH.exists():
            return []
        entries = []
        with open(HISTORY_PATH) as f:
            for line in f:
                try:
                    entries.append(json.loads(line.strip()))
                except json.JSONDecodeError:
                    continue
        return entries[-n:]


# ═══════════════════════════════════════════════════════════════════════════════
# APPROVAL STATISTICS
# ═══════════════════════════════════════════════════════════════════════════════

class ApprovalStats:
    """Tracks approval statistics."""

    def __init__(self):
        self.data = {
            "total": 0,
            "approved": 0,
            "rejected": 0,
            "modified": 0,
            "deferred": 0,
            "expired": 0,
            "by_category": {},
            "by_agent": {},
            "avg_wait_time_s": 0,
            "wait_times": [],
        }
        self._load()

    def _load(self):
        HITL_DIR.mkdir(parents=True, exist_ok=True)
        if STATS_PATH.exists():
            try:
                with open(STATS_PATH) as f:
                    self.data = json.load(f)
            except (json.JSONDecodeError, IOError):
                pass

    def _save(self):
        HITL_DIR.mkdir(parents=True, exist_ok=True)
        with open(STATS_PATH, "w") as f:
            json.dump(self.data, f, indent=2)

    def record(self, approval):
        self.data["total"] += 1
        action = approval.get("action_taken", "unknown")

        if action in ("approved",):
            self.data["approved"] += 1
        elif action in ("rejected", "expired_reject"):
            self.data["rejected"] += 1
        elif action in ("modified",):
            self.data["modified"] += 1
        elif action in ("deferred", "expired_deferred"):
            self.data["deferred"] += 1
        elif "expired" in action:
            self.data["expired"] += 1

        # By category
        cat = approval["category"]
        if cat not in self.data["by_category"]:
            self.data["by_category"][cat] = {"total": 0, "approved": 0, "rejected": 0}
        self.data["by_category"][cat]["total"] += 1
        if action in ("approved", "modified"):
            self.data["by_category"][cat]["approved"] += 1
        elif "reject" in action or "expired" in action:
            self.data["by_category"][cat]["rejected"] += 1

        # By agent
        agent = approval["requesting_agent"]
        if agent not in self.data["by_agent"]:
            self.data["by_agent"][agent] = {"total": 0, "approved": 0, "rejected": 0}
        self.data["by_agent"][agent]["total"] += 1
        if action in ("approved", "modified"):
            self.data["by_agent"][agent]["approved"] += 1
        elif "reject" in action:
            self.data["by_agent"][agent]["rejected"] += 1

        # Wait time
        try:
            created = datetime.fromisoformat(approval["created_at"].replace("Z", "+00:00"))
            acted_str = approval.get("action_at") or approval["created_at"]
            acted = datetime.fromisoformat(acted_str.replace("Z", "+00:00"))
            wait = (acted - created).total_seconds()
            self.data["wait_times"].append(wait)
            self.data["wait_times"] = self.data["wait_times"][-200:]
            self.data["avg_wait_time_s"] = round(
                sum(self.data["wait_times"]) / len(self.data["wait_times"]), 1)
        except (ValueError, AttributeError):
            pass

        self._save()


# ═══════════════════════════════════════════════════════════════════════════════
# HUMAN LOOP MANAGER (main interface)
# ═══════════════════════════════════════════════════════════════════════════════

class HumanLoopManager:
    """Top-level interface for human-in-the-loop approvals."""

    def __init__(self):
        self.queue = ApprovalQueue()
        self.handler = HumanActionHandler(self.queue)

    def request_approval(self, category, title, description, requesting_agent,
                          priority=None, context=None, options=None,
                          related_ids=None, expiry_hours=None):
        """Submit a new approval request.

        Returns: (approval_id, position_in_queue)
        """
        approval = new_approval(
            category, title, description, requesting_agent,
            priority, context, options, related_ids, expiry_hours)
        return self.queue.submit(approval)

    def approve(self, approval_id, reason=""):
        return self.handler.approve(approval_id, reason)

    def reject(self, approval_id, reason=""):
        return self.handler.reject(approval_id, reason)

    def modify(self, approval_id, modification, reason=""):
        return self.handler.modify(approval_id, modification, reason)

    def defer(self, approval_id, defer_hours=24, reason=""):
        return self.handler.defer(approval_id, defer_hours, reason)

    def expire_stale(self):
        return self.handler.expire_stale()

    def get_pending(self, category=None, priority=None):
        return self.queue.get_pending(category, priority)

    def get_stats(self):
        return self.handler.stats.data

    def get_history(self, n=20):
        return self.handler.history_log.get_recent(n)

    def get_summary(self):
        """Quick summary of current state."""
        pending = self.queue.get_pending()
        critical = [a for a in pending if a["priority"] == "critical"]
        high = [a for a in pending if a["priority"] == "high"]
        return {
            "total_pending": len(pending),
            "critical": len(critical),
            "high": len(high),
            "medium": len(pending) - len(critical) - len(high),
            "categories": defaultdict(int, {a["category"]: 0 for a in pending}),
        }


# ═══════════════════════════════════════════════════════════════════════════════
# TESTS
# ═══════════════════════════════════════════════════════════════════════════════

def run_tests():
    print("=" * 60)
    print("  MA-16 Human-in-the-Loop Tests")
    print("=" * 60)

    tp = 0
    tt = 0

    def test(name, condition, detail=""):
        nonlocal tp, tt
        tt += 1
        if condition:
            tp += 1
            print(f"  ✅ {name}")
        else:
            print(f"  ❌ {name}: {detail}")

    # Clean state
    mgr = HumanLoopManager()
    mgr.queue.approvals = {}

    # Test 1: Categories defined
    test("6 approval categories", len(APPROVAL_CATEGORIES) == 6)

    # Test 2: All categories have required fields
    req = ["description", "source", "default_priority", "expiry_hours", "expiry_action"]
    all_ok = all(all(f in c for f in req) for c in APPROVAL_CATEGORIES.values())
    test("All categories have required config", all_ok)

    # Test 3: Submit approval
    aid1, pos1 = mgr.request_approval(
        "cost_override", "Plan exceeds $15 budget",
        "Plan plan_001 estimated cost $18.50 exceeds $15 threshold",
        "strategy_lead", priority="high",
        context={"plan_id": "plan_001", "estimated_cost": 18.50})
    test("Approval submitted", aid1 is not None and pos1 >= 1)

    # Test 4: Approval in pending queue
    pending = mgr.get_pending()
    test("Appears in pending", len(pending) >= 1 and pending[0]["id"] == aid1)

    # Test 5: Priority ordering
    aid2, _ = mgr.request_approval(
        "circuit_breaker", "Circuit breaker tripped",
        "Anthropic budget at 150%", "executive_operator", priority="critical")
    pending = mgr.get_pending()
    test("Critical comes first", pending[0]["priority"] == "critical")

    # Test 6: Approve
    ok, msg = mgr.approve(aid2, "Override approved — one-time exception")
    test("Approve works", ok)
    test("Status = approved", mgr.queue.get(aid2)["status"] == "approved")

    # Test 8: Reject
    aid3, _ = mgr.request_approval(
        "lesson_approval", "New workflow rule proposed",
        "MA-13 suggests adding mandatory review for all outputs",
        "executive_operator", priority="medium")
    ok, msg = mgr.reject(aid3, "Not appropriate at this stage")
    test("Reject works", ok)
    test("Status = rejected", mgr.queue.get(aid3)["status"] == "rejected")

    # Test 10: Modify
    aid4, _ = mgr.request_approval(
        "cost_override", "Budget increase requested",
        "Need $25 for comprehensive research", "strategy_lead",
        context={"requested_amount": 25.0})
    ok, msg = mgr.modify(aid4, {"new_budget": 20.0, "scope": "reduced"}, "Approved with reduced scope")
    test("Modify works", ok)
    test("Modification stored", mgr.queue.get(aid4)["modification"] == {"new_budget": 20.0, "scope": "reduced"})

    # Test 12: Defer
    aid5, _ = mgr.request_approval(
        "behavior_escalation", "Agent role drift detected",
        "engineering_lead acting in market_strategy domain", "engineering_lead")
    ok, msg = mgr.defer(aid5, defer_hours=12, reason="Need more context")
    test("Defer works", ok)
    test("Deferred until set", mgr.queue.get(aid5)["deferred_until"] is not None)

    # Test 14: Cannot act on already-actioned approval
    ok, msg = mgr.approve(aid3)  # already rejected
    test("Cannot re-act on closed approval", not ok)

    # Test 15: Expiry — create an already-expired approval
    expired_approval = new_approval(
        "quality_escalation", "Test expiry",
        "Output failed 3x", "narrative_content_lead")
    expired_approval["expires_at"] = (
        datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    mgr.queue.approvals[expired_approval["id"]] = expired_approval
    mgr.queue._save()

    expired_ids = mgr.expire_stale()
    test("Expiry processes stale approvals", expired_approval["id"] in expired_ids)
    test("Expired status set",
         mgr.queue.get(expired_approval["id"])["status"] == "expired")

    # Test 17: Defer-on-expiry (lesson_approval has expiry_action=defer)
    defer_exp = new_approval(
        "lesson_approval", "Test defer expiry",
        "Should auto-defer", "strategy_lead")
    defer_exp["expires_at"] = (
        datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    mgr.queue.approvals[defer_exp["id"]] = defer_exp
    mgr.queue._save()
    mgr.expire_stale()
    test("Defer-on-expiry extends deadline",
         mgr.queue.get(defer_exp["id"])["status"] == "pending")

    # Test 18: Filter by category
    pending_cost = mgr.get_pending(category="cost_override")
    test("Filter by category works",
         all(a["category"] == "cost_override" for a in pending_cost))

    # Test 19: Filter by priority
    mgr.request_approval("decision_review", "Low priority test",
                           "Test", "operations_lead", priority="low")
    pending_low = mgr.get_pending(priority="low")
    test("Filter by priority works",
         all(a["priority"] == "low" for a in pending_low))

    # Test 20: History tracking
    history = mgr.get_history()
    test("History recorded", len(history) > 0)

    # Test 21: History has wait time
    has_wait = any(h.get("wait_time_s") is not None for h in history)
    test("History includes wait time", has_wait)

    # Test 22: Stats tracking
    stats = mgr.get_stats()
    test("Stats: total tracked", stats["total"] > 0)
    test("Stats: by category", len(stats["by_category"]) > 0)
    test("Stats: by agent", len(stats["by_agent"]) > 0)

    # Test 25: Summary
    summary = mgr.get_summary()
    test("Summary produced",
         "total_pending" in summary and "critical" in summary)

    # Test 26: Approval has expiry
    approval = mgr.queue.get(aid1)
    test("Approval has expiry time", approval.get("expires_at") is not None)

    # Test 27: Context preserved
    test("Context preserved in approval",
         approval.get("context", {}).get("plan_id") == "plan_001")

    # Test 28: No expiry when expiry_hours=0
    aid_no_exp, _ = mgr.request_approval(
        "decision_review", "No expiry test", "Test",
        "strategy_lead", expiry_hours=0)
    test("Zero expiry = no expires_at",
         mgr.queue.get(aid_no_exp).get("expires_at") is None)

    print(f"\n  Results: {tp}/{tt} passed")
    return tp == tt


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="NemoClaw Human-in-the-Loop")
    parser.add_argument("--test", action="store_true", help="Run all tests")
    parser.add_argument("--pending", action="store_true", help="Show pending approvals")
    parser.add_argument("--approve", metavar="ID", help="Approve an approval")
    parser.add_argument("--reject", metavar="ID", help="Reject an approval")
    parser.add_argument("--reason", default="", help="Reason for action")
    parser.add_argument("--defer", metavar="ID", help="Defer an approval")
    parser.add_argument("--hours", type=int, default=24, help="Defer hours")
    parser.add_argument("--history", action="store_true", help="Show approval history")
    parser.add_argument("--stats", action="store_true", help="Show statistics")
    parser.add_argument("--expire", action="store_true", help="Expire stale approvals")
    args = parser.parse_args()

    if args.test:
        success = run_tests()
        sys.exit(0 if success else 1)

    mgr = HumanLoopManager()

    if args.pending:
        pending = mgr.get_pending()
        if not pending:
            print("  No pending approvals.")
        else:
            print(f"  Pending Approvals ({len(pending)}):")
            for a in pending:
                prio_icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "⚪"}.get(
                    a["priority"], "?")
                exp = a.get("expires_at", "never")[:19] if a.get("expires_at") else "never"
                print(f"\n  {prio_icon} [{a['id']}] {a['title']}")
                print(f"     Category: {a['category']} | Agent: {a['requesting_agent']}")
                print(f"     Expires: {exp}")
                print(f"     {a['description'][:100]}")

    elif args.approve:
        ok, msg = mgr.approve(args.approve, args.reason)
        print(f"  {'✅' if ok else '❌'} {msg}")

    elif args.reject:
        ok, msg = mgr.reject(args.reject, args.reason)
        print(f"  {'✅' if ok else '❌'} {msg}")

    elif args.defer:
        ok, msg = mgr.defer(args.defer, args.hours, args.reason)
        print(f"  {'✅' if ok else '❌'} {msg}")

    elif args.history:
        history = mgr.get_history()
        if not history:
            print("  No approval history.")
        else:
            for h in history:
                icon = {"approved": "✅", "rejected": "❌", "modified": "📝",
                        "deferred": "⏸️", "expired_reject": "⏰"}.get(h.get("action"), "?")
                print(f"  {icon} [{h.get('timestamp', '?')[:19]}] {h.get('action')}: "
                      f"{h.get('title', '?')} (by {h.get('action_by', '?')})")

    elif args.stats:
        stats = mgr.get_stats()
        print(f"  Total approvals: {stats['total']}")
        print(f"  Approved: {stats['approved']}")
        print(f"  Rejected: {stats['rejected']}")
        print(f"  Modified: {stats['modified']}")
        print(f"  Deferred: {stats['deferred']}")
        print(f"  Expired: {stats['expired']}")
        print(f"  Avg wait: {stats['avg_wait_time_s']:.0f}s")

    elif args.expire:
        expired = mgr.expire_stale()
        print(f"  Expired {len(expired)} approvals: {expired}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()

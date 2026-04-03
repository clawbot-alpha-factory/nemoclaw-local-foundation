"""
NemoClaw CEO Review Gate — CEOReviewerService

Executive oversight for significant agent actions. The executive_operator
reviews high-risk actions (external writes, deploys, emails, high-spend)
before execution. Low-risk actions (reads, heartbeats, internal compute)
bypass review automatically.

Integrates with:
- BrainService.analyze() for LLM-based CEO persona review
- ApprovalChainService rubric (spend, reversibility, external_impact, novelty, data_sensitivity)
- WebSocket manager for real-time notifications on blocked actions
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("cc.ceo_reviewer")

# ── Action Classification ─────────────────────────────────────────────

# Action types that always require CEO review
REVIEW_REQUIRED = frozenset({
    "external_write",
    "deploy",
    "email_send",
    "cold_email",
    "cold_email_blast",
    "payment",
    "publish",
})

# Action types that never require review
REVIEW_EXEMPT = frozenset({
    "read",
    "read_only",
    "memory_write",
    "heartbeat",
    "internal_compute",
    "queued",
})

# Maps real action types flowing through _act() to review categories.
# Actions in _act() use "browser", "scheduled", "queued" — these need
# mapping to risk categories based on their content.
ACTION_TYPE_CLASSIFIERS = {
    # browser actions with external side-effects
    "browser": lambda a: _classify_browser_action(a),
    # scheduled tasks — classify by skill_id / description keywords
    "scheduled": lambda a: _classify_scheduled_action(a),
    # queued tasks are always exempt
    "queued": lambda _: "queued",
}

# Keywords in descriptions/skill_ids that signal high-risk actions
HIGH_RISK_KEYWORDS = frozenset({
    "email", "send", "deploy", "publish", "payment", "cold_email",
    "outreach", "blast", "delete", "remove", "write_external",
})

LOW_RISK_KEYWORDS = frozenset({
    "read", "analyze", "report", "research", "audit", "review",
    "plan", "brainstorm", "document", "summarize",
})

# Spend threshold — actions above this always reviewed
SPEND_THRESHOLD = 10.0

# Timeout for LLM-based review (seconds)
REVIEW_TIMEOUT = 60

# Risk score threshold for auto-approve on timeout
TIMEOUT_AUTO_APPROVE_THRESHOLD = 3

# Persistence
PERSIST_PATH = Path.home() / ".nemoclaw" / "ceo-review-log.json"
MAX_REVIEW_LOG = 1000


def _classify_browser_action(action: dict[str, Any]) -> str:
    """Classify browser action by its intent."""
    url = action.get("url", "").lower()
    actions = action.get("browser_actions", [])
    desc = action.get("description", "").lower()

    # Any browser action that fills forms, clicks submit, or posts data
    for ba in actions:
        kind = ba.get("kind", "") if isinstance(ba, dict) else ""
        if kind in ("fill", "type"):
            return "external_write"
        if kind == "click":
            target = str(ba.get("ref", "")).lower() + str(ba.get("name", "")).lower()
            if any(w in target for w in ("submit", "send", "publish", "post", "delete")):
                return "external_write"

    # URL-based classification
    if any(w in url for w in ("mail", "email", "smtp")):
        return "email_send"
    if any(w in desc for w in HIGH_RISK_KEYWORDS):
        return "external_write"

    return "browser"  # Generic browser — first-time check still applies


def _classify_scheduled_action(action: dict[str, Any]) -> str:
    """Classify scheduled action by skill_id and description."""
    skill_id = action.get("skill_id", "").lower()
    desc = action.get("description", "").lower()
    combined = f"{skill_id} {desc}"

    if any(kw in combined for kw in HIGH_RISK_KEYWORDS):
        return "external_write"
    if any(kw in combined for kw in LOW_RISK_KEYWORDS):
        return "internal_compute"

    return "scheduled"  # Unknown — first-time check applies


# ── Data Classes ──────────────────────────────────────────────────────


@dataclass
class ReviewDecision:
    status: str  # APPROVED, REJECTED, MODIFY, ESCALATE
    reason: str = ""
    modifications: dict[str, Any] | None = None
    risk_score: float = 0.0
    reviewed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class GateResult:
    passed: bool
    blockers: list[str] = field(default_factory=list)
    checked_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ── Service ───────────────────────────────────────────────────────────


class CEOReviewerService:
    """Executive oversight gate for agent actions."""

    def __init__(self, brain_service=None, approval_chain_service=None):
        self.brain_service = brain_service
        self.approval_chain_service = approval_chain_service
        self.ws_manager = None  # Wired post-init from main.py
        self._seen_actions: set[str] = set()  # Track first-time action types per agent
        self._review_log: list[dict[str, Any]] = []
        self._load_review_log()
        logger.info("CEOReviewerService initialized — executive oversight active")

    # ── Public API ────────────────────────────────────────────────────

    def should_review(self, action_type: str, agent_id: str, estimated_cost: float = 0.0) -> bool:
        """Determine if an action requires CEO review before execution."""
        # Exempt actions never reviewed
        if action_type in REVIEW_EXEMPT:
            return False

        # Required actions always reviewed
        if action_type in REVIEW_REQUIRED:
            return True

        # High-spend actions always reviewed
        if estimated_cost > SPEND_THRESHOLD:
            return True

        # First-time action for this agent
        action_key = f"{agent_id}:{action_type}"
        if action_key not in self._seen_actions:
            self._seen_actions.add(action_key)
            logger.info(f"First-time action '{action_type}' for {agent_id} — requires review")
            return True

        return False

    def classify_action(self, action: dict[str, Any]) -> str:
        """Map a real _act() action to a review category.

        Actions flow through _act() as "browser", "scheduled", "queued".
        This classifies them into risk categories like "external_write",
        "email_send", "internal_compute" etc. for should_review().
        """
        raw_type = action.get("type", "")
        classifier = ACTION_TYPE_CLASSIFIERS.get(raw_type)
        if classifier:
            return classifier(action)
        return raw_type

    async def review_action(self, action: dict[str, Any], context: dict[str, Any]) -> ReviewDecision:
        """Review an action using rubric scoring + LLM CEO persona analysis."""
        action_type = action.get("type", "unknown")
        estimated_cost = action.get("estimated_cost", 0.0)

        # Step 1: Rubric scoring via approval_chain_service
        risk_score = 0.0
        rubric_decision = "auto_approved"
        if self.approval_chain_service:
            factors = self.approval_chain_service.derive_factors(action_type, estimated_cost)
            scoring = self.approval_chain_service.score_request(action_type, estimated_cost, factors)
            risk_score = scoring.get("risk_score", 0.0)
            rubric_decision = scoring.get("decision", "auto_approved")
            logger.info(f"CEO rubric: {action_type} risk_score={risk_score:.1f} decision={rubric_decision}")

        # Step 2: LLM review with CEO persona
        if self.brain_service and self.brain_service.is_available:
            prompt = self._build_review_prompt(action, context, risk_score, rubric_decision)
            try:
                llm_response = await asyncio.wait_for(
                    self.brain_service.analyze(prompt, context="ceo_review"),
                    timeout=REVIEW_TIMEOUT,
                )
                decision = self._parse_review_response(llm_response, risk_score)
            except asyncio.TimeoutError:
                logger.warning(f"CEO review timed out for {action_type} (risk={risk_score:.1f})")
                if risk_score < TIMEOUT_AUTO_APPROVE_THRESHOLD:
                    decision = ReviewDecision(
                        status="APPROVED",
                        reason=f"Auto-approved on timeout (risk_score {risk_score:.1f} < {TIMEOUT_AUTO_APPROVE_THRESHOLD})",
                        risk_score=risk_score,
                    )
                else:
                    decision = ReviewDecision(
                        status="ESCALATE",
                        reason=f"Escalated on timeout (risk_score {risk_score:.1f} >= {TIMEOUT_AUTO_APPROVE_THRESHOLD})",
                        risk_score=risk_score,
                    )
            except Exception as e:
                logger.error(f"CEO review failed for {action_type}: {e}")
                decision = self._rubric_fallback(rubric_decision, risk_score)
        else:
            decision = self._rubric_fallback(rubric_decision, risk_score)

        # Log and persist review
        entry = {
            "action_type": action_type,
            "agent_id": context.get("agent_id", "unknown"),
            "risk_score": risk_score,
            "decision": decision.status,
            "reason": decision.reason,
            "reviewed_at": decision.reviewed_at,
        }
        self._review_log.append(entry)
        self._save_review_log()
        logger.info(f"CEO decision: {decision.status} for {action_type} (agent={context.get('agent_id')}, risk={risk_score:.1f})")

        # WebSocket notification for blocked actions
        if decision.status in ("REJECTED", "ESCALATE"):
            await self._notify_blocked(entry)

        return decision

    def validate_phase_gate(
        self, mission_id: str, from_phase: str, to_phase: str,
        tasks: list[dict[str, Any]] | None = None,
        blockers: list[str] | None = None,
    ) -> GateResult:
        """Validate phase transition — all tasks complete, no blockers."""
        gate_blockers: list[str] = []

        # Check all tasks in current phase are complete
        if tasks:
            incomplete = [t.get("id", "?") for t in tasks if not t.get("completed", False)]
            if incomplete:
                gate_blockers.append(f"Incomplete tasks in {from_phase}: {', '.join(incomplete[:5])}")

        # Check for active blockers
        if blockers:
            gate_blockers.extend(blockers)

        passed = len(gate_blockers) == 0
        if not passed:
            logger.warning(f"Phase gate BLOCKED: {from_phase} → {to_phase} for mission {mission_id}: {gate_blockers}")
        else:
            logger.info(f"Phase gate PASSED: {from_phase} → {to_phase} for mission {mission_id}")

        return GateResult(passed=passed, blockers=gate_blockers)

    def get_review_log(self, limit: int = 50) -> list[dict[str, Any]]:
        """Return recent review decisions."""
        return self._review_log[-limit:]

    def get_stats(self) -> dict[str, Any]:
        """Return review statistics."""
        total = len(self._review_log)
        if total == 0:
            return {"total": 0, "approved": 0, "rejected": 0, "escalated": 0, "modified": 0}
        by_status: dict[str, int] = {}
        for entry in self._review_log:
            s = entry.get("decision", "UNKNOWN")
            by_status[s] = by_status.get(s, 0) + 1
        return {
            "total": total,
            "approved": by_status.get("APPROVED", 0),
            "rejected": by_status.get("REJECTED", 0),
            "escalated": by_status.get("ESCALATE", 0),
            "modified": by_status.get("MODIFY", 0),
            "first_time_actions_tracked": len(self._seen_actions),
        }

    # ── Persistence ───────────────────────────────────────────────────

    def _load_review_log(self) -> None:
        """Load persisted review log from disk."""
        if PERSIST_PATH.exists():
            try:
                data = json.loads(PERSIST_PATH.read_text())
                self._review_log = data.get("reviews", [])[-MAX_REVIEW_LOG:]
                self._seen_actions = set(data.get("seen_actions", []))
                logger.info(f"Loaded {len(self._review_log)} review entries, {len(self._seen_actions)} seen actions")
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"Failed to load review log: {e}")

    def _save_review_log(self) -> None:
        """Persist review log to disk."""
        try:
            PERSIST_PATH.parent.mkdir(parents=True, exist_ok=True)
            PERSIST_PATH.write_text(json.dumps({
                "reviews": self._review_log[-MAX_REVIEW_LOG:],
                "seen_actions": list(self._seen_actions),
                "saved_at": datetime.now(timezone.utc).isoformat(),
            }, indent=2, default=str))
        except OSError as e:
            logger.error(f"Failed to save review log: {e}")

    # ── WebSocket Notifications ───────────────────────────────────────

    async def _notify_blocked(self, entry: dict[str, Any]) -> None:
        """Push CEO review block to WebSocket clients via alerts channel."""
        if not self.ws_manager:
            return
        try:
            message = (
                f"CEO {entry['decision']}: {entry['action_type']} by {entry['agent_id']} "
                f"(risk={entry['risk_score']:.1f}) — {entry['reason']}"
            )
            await self.ws_manager.broadcast_alert(
                domain="ceo_review",
                message=message,
            )
        except Exception as e:
            logger.warning(f"Failed to broadcast CEO review alert: {e}")

    # ── Private ───────────────────────────────────────────────────────

    def _build_review_prompt(
        self, action: dict[str, Any], context: dict[str, Any],
        risk_score: float, rubric_decision: str,
    ) -> str:
        return (
            "You are the CEO of NemoClaw reviewing an agent action before execution.\n"
            "Evaluate this action and respond with exactly one of: APPROVED, REJECTED, MODIFY, ESCALATE\n"
            "followed by a brief reason on the next line.\n"
            "If MODIFY, add a third line starting with 'Modifications:' as JSON.\n\n"
            f"Action type: {action.get('type', 'unknown')}\n"
            f"Agent: {context.get('agent_id', 'unknown')}\n"
            f"Description: {action.get('description', action.get('skill_id', 'N/A'))}\n"
            f"Estimated cost: ${action.get('estimated_cost', 0.0):.2f}\n"
            f"Risk score: {risk_score:.1f}/100\n"
            f"Rubric decision: {rubric_decision}\n"
            f"Agent total cost so far: ${context.get('total_cost', 0.0):.2f}\n"
            f"Agent ticks: {context.get('ticks', 0)}\n\n"
            "Decision rules:\n"
            "- APPROVE routine operations with low risk\n"
            "- REJECT actions that seem wasteful, dangerous, or misaligned\n"
            "- MODIFY if the action needs parameter adjustments\n"
            "- ESCALATE if human oversight is needed (very high risk, unclear intent)\n"
        )

    def _parse_review_response(self, response: str, risk_score: float) -> ReviewDecision:
        """Parse LLM response into ReviewDecision."""
        lines = [l.strip() for l in response.strip().split("\n") if l.strip()]
        if not lines:
            return self._rubric_fallback("auto_approved", risk_score)

        first_line = lines[0].upper()
        reason = lines[1] if len(lines) > 1 else ""
        modifications = None

        if "REJECTED" in first_line:
            status = "REJECTED"
        elif "MODIFY" in first_line:
            status = "MODIFY"
            if len(lines) > 2 and lines[2].lower().startswith("modifications:"):
                try:
                    modifications = json.loads(lines[2].split(":", 1)[1].strip())
                except (json.JSONDecodeError, IndexError):
                    pass
        elif "ESCALATE" in first_line:
            status = "ESCALATE"
        else:
            status = "APPROVED"

        return ReviewDecision(status=status, reason=reason, modifications=modifications, risk_score=risk_score)

    def _rubric_fallback(self, rubric_decision: str, risk_score: float) -> ReviewDecision:
        """Fallback when LLM is unavailable — use rubric decision directly."""
        status_map = {
            "auto_approved": "APPROVED",
            "single_approval": "APPROVED",
            "chain_approval": "ESCALATE",
            "escalated": "ESCALATE",
        }
        status = status_map.get(rubric_decision, "APPROVED")
        return ReviewDecision(
            status=status,
            reason=f"Rubric-only fallback: {rubric_decision} (risk={risk_score:.1f})",
            risk_score=risk_score,
        )

"""
NemoClaw Execution Engine — FeedbackLoopService (E-4b)

4 implemented feedback loops (#30):
  1. Sales → Marketing (every 50 sends)
  2. Marketing → Sales (weekly)
  3. ClientSuccess → Sales (on churn signal)
  4. All → Strategy (weekly)

Each loop: auto-gather → analyze → recommend → (debate if controversial) → adjust.

NEW FILE: command-center/backend/app/services/feedback_loop_service.py
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("cc.feedback")


FEEDBACK_LOOPS = [
    {
        "loop_id": "sales-to-marketing",
        "name": "Sales → Marketing",
        "sender": "sales_outreach_lead",
        "receiver": "marketing_campaigns_lead",
        "trigger": "every_50_sends",
        "data_points": ["reply_rates_by_segment", "channel_performance", "lead_quality_signals"],
        "outcome": "Marketing adjusts targeting, content, channel mix",
    },
    {
        "loop_id": "marketing-to-sales",
        "name": "Marketing → Sales",
        "sender": "marketing_campaigns_lead",
        "receiver": "sales_outreach_lead",
        "trigger": "weekly_monday",
        "data_points": ["campaign_metrics", "intent_signals", "hot_leads"],
        "outcome": "Sales prioritizes hot leads, adjusts messaging",
    },
    {
        "loop_id": "cs-to-sales",
        "name": "ClientSuccess → Sales",
        "sender": "client_success_lead",
        "receiver": "sales_outreach_lead",
        "trigger": "on_churn_signal",
        "data_points": ["at_risk_clients", "reason_codes", "engagement_data"],
        "outcome": "Sales pauses outreach to account, retention activated",
    },
    {
        "loop_id": "all-to-strategy",
        "name": "All → Strategy",
        "sender": "all_agents",
        "receiver": "strategy_lead",
        "trigger": "weekly_friday",
        "data_points": ["insights", "metrics", "anomalies"],
        "outcome": "Strategy synthesizes weekly brief, updates priorities",
    },
]


class FeedbackExecution:
    """A single execution of a feedback loop."""

    def __init__(self, loop_id: str, sender: str, receiver: str):
        self.execution_id = str(uuid.uuid4())
        self.loop_id = loop_id
        self.sender = sender
        self.receiver = receiver
        self.status = "gathering"
        self.data_gathered: dict[str, Any] = {}
        self.recommendation: str = ""
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.completed_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "loop_id": self.loop_id,
            "sender": self.sender,
            "receiver": self.receiver,
            "status": self.status,
            "data_gathered": self.data_gathered,
            "recommendation": self.recommendation,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }


class FeedbackLoopService:
    """
    Manages the 4 feedback loops between agents.
    """

    def __init__(self, protocol_service=None):
        self.protocol_service = protocol_service
        self.loops = {fl["loop_id"]: fl for fl in FEEDBACK_LOOPS}
        self.executions: list[FeedbackExecution] = []
        logger.info("FeedbackLoopService initialized (%d loops)", len(self.loops))

    def get_loops(self) -> list[dict[str, Any]]:
        """Get all defined feedback loops."""
        return list(self.loops.values())

    def trigger_loop(self, loop_id: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
        """Manually trigger a feedback loop execution."""
        loop_def = self.loops.get(loop_id)
        if not loop_def:
            return {"success": False, "reason": f"Loop {loop_id} not found"}

        execution = FeedbackExecution(
            loop_id=loop_id,
            sender=loop_def["sender"],
            receiver=loop_def["receiver"],
        )

        # Simulate data gathering
        execution.data_gathered = data or {dp: f"synthetic_{dp}" for dp in loop_def["data_points"]}
        execution.status = "analyzing"

        # Generate recommendation (placeholder — real LLM analysis in later phases)
        execution.recommendation = (
            f"Based on {len(execution.data_gathered)} data points from "
            f"{loop_def['name']}: {loop_def['outcome']}"
        )
        execution.status = "completed"
        execution.completed_at = datetime.now(timezone.utc).isoformat()

        self.executions.append(execution)

        # Send via protocol if available
        if self.protocol_service:
            self.protocol_service.send(
                sender=loop_def["sender"],
                receiver=loop_def["receiver"],
                intent="inform",
                content=execution.recommendation,
                data=execution.data_gathered,
            )

        logger.info("Feedback loop executed: %s", loop_def["name"])
        return {"success": True, "execution": execution.to_dict()}

    def get_executions(self, loop_id: str = "") -> list[dict[str, Any]]:
        """Get feedback loop execution history."""
        execs = self.executions
        if loop_id:
            execs = [e for e in execs if e.loop_id == loop_id]
        return [e.to_dict() for e in execs]

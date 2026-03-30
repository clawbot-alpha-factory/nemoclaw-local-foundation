"""
NemoClaw Execution Engine — AgentProtocolService (E-4b)

7-intent messaging protocol (#27) with authority enforcement.
Task handoff (#28), conflict resolution (#3).

Intents: inform, request, propose, challenge, decide, delegate, escalate
Authority: L4 can propose/request. L3 decides within domain. L1-L2 decides anything.

NEW FILE: command-center/backend/app/services/agent_protocol_service.py
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("cc.protocol")


# ── Agent Authority Levels ─────────────────────────────────────────────

AGENT_LEVELS = {
    "executive_operator": 1,
    "strategy_lead": 2,
    "operations_lead": 2,
    "product_lead": 3,
    "growth_revenue_lead": 3,
    "narrative_content_lead": 3,
    "engineering_lead": 3,
    "sales_outreach_lead": 4,
    "marketing_campaigns_lead": 4,
    "client_success_lead": 4,
}

VALID_INTENTS = {"inform", "request", "propose", "challenge", "decide", "delegate", "escalate"}
DECISION_INTENTS = {"decide", "delegate"}  # require L1-L3

# Domain enforcement: L3 agents can only decide within their domain
AGENT_DOMAINS = {
    "executive_operator": "all",
    "strategy_lead": "all",
    "operations_lead": "all",
    "product_lead": "product",
    "growth_revenue_lead": "revenue",
    "narrative_content_lead": "content",
    "engineering_lead": "engineering",
    "sales_outreach_lead": "sales",
    "marketing_campaigns_lead": "marketing",
    "client_success_lead": "client_success",
}

# Rate limiting: max messages per agent per minute
RATE_LIMIT_PER_MINUTE = 60


class ProtocolMessage:
    """A single protocol message between agents."""

    def __init__(
        self,
        sender: str,
        receiver: str,
        intent: str,
        content: str,
        data: dict[str, Any] | None = None,
        evidence: str | None = None,
        trace_id: str = "",
    ):
        self.message_id = str(uuid.uuid4())
        self.sender = sender
        self.receiver = receiver
        self.intent = intent
        self.content = content
        self.data = data or {}
        self.evidence = evidence
        self.trace_id = trace_id
        self.parent_message_id = ""
        self.timestamp = datetime.now(timezone.utc).isoformat()
        self.status = "delivered"

    def to_dict(self) -> dict[str, Any]:
        return {
            "message_id": self.message_id,
            "sender": self.sender,
            "receiver": self.receiver,
            "intent": self.intent,
            "content": self.content,
            "data": self.data,
            "evidence": self.evidence,
            "trace_id": self.trace_id,
            "parent_message_id": self.parent_message_id,
            "timestamp": self.timestamp,
            "status": self.status,
        }


class AgentProtocolService:
    """
    Manages agent-to-agent protocol messaging with authority enforcement.
    """

    def __init__(self):
        self.inboxes: dict[str, list[ProtocolMessage]] = {}
        self.history: list[ProtocolMessage] = []
        self._rate_tracker: dict[str, list[float]] = {}  # agent_id → list of timestamps
        logger.info("AgentProtocolService initialized (7 intents, domain + rate enforcement)")

    def _check_rate_limit(self, agent_id: str) -> bool:
        """Check if agent is within rate limit."""
        import time
        now = time.time()
        timestamps = self._rate_tracker.get(agent_id, [])
        # Keep only last minute
        timestamps = [t for t in timestamps if now - t < 60]
        self._rate_tracker[agent_id] = timestamps
        return len(timestamps) < RATE_LIMIT_PER_MINUTE

    def _has_domain_authority(self, agent_id: str, target_domain: str) -> bool:
        """Check if agent has authority over a domain."""
        agent_domain = AGENT_DOMAINS.get(agent_id, "")
        if agent_domain == "all":
            return True
        if not target_domain:
            return True  # no domain specified = allowed
        return agent_domain == target_domain

    def send(
        self,
        sender: str,
        receiver: str,
        intent: str,
        content: str,
        data: dict[str, Any] | None = None,
        evidence: str | None = None,
        trace_id: str = "",
    ) -> dict[str, Any]:
        """Send a protocol message with authority enforcement."""

        # Validate intent
        if intent not in VALID_INTENTS:
            return {"success": False, "reason": f"Invalid intent: {intent}. Valid: {VALID_INTENTS}"}

        # Rate limit check
        if not self._check_rate_limit(sender):
            return {"success": False, "reason": f"Rate limit exceeded for {sender} ({RATE_LIMIT_PER_MINUTE}/min)"}

        import time
        self._rate_tracker.setdefault(sender, []).append(time.time())

        # Authority check
        sender_level = AGENT_LEVELS.get(sender, 99)

        if intent in DECISION_INTENTS and sender_level > 3:
            return {
                "success": False,
                "reason": f"Agent {sender} (L{sender_level}) cannot {intent}. Requires L1-L3.",
            }

        # Domain enforcement for decisions
        if intent in DECISION_INTENTS and sender_level == 3:
            target_domain = (data or {}).get("domain", "")
            if not self._has_domain_authority(sender, target_domain):
                return {
                    "success": False,
                    "reason": f"Agent {sender} cannot {intent} outside their domain ({AGENT_DOMAINS.get(sender, 'unknown')})",
                }

        if intent == "challenge" and not evidence:
            return {
                "success": False,
                "reason": "Challenge intent requires evidence field.",
            }

        if intent == "delegate":
            receiver_level = AGENT_LEVELS.get(receiver, 99)
            if receiver_level < sender_level:
                return {
                    "success": False,
                    "reason": f"Cannot delegate to higher authority: {receiver} (L{receiver_level}) > {sender} (L{sender_level})",
                }

        # Create and deliver
        msg = ProtocolMessage(
            sender=sender,
            receiver=receiver,
            intent=intent,
            content=content,
            data=data,
            evidence=evidence,
            trace_id=trace_id,
        )

        self.inboxes.setdefault(receiver, []).append(msg)
        self.history.append(msg)

        logger.info(
            "Protocol: %s → %s [%s] %s",
            sender, receiver, intent, content[:50],
        )
        return {"success": True, "message_id": msg.message_id, "message": msg.to_dict()}

    def get_inbox(self, agent_id: str, limit: int = 50) -> list[dict[str, Any]]:
        """Get messages for an agent."""
        msgs = self.inboxes.get(agent_id, [])
        return [m.to_dict() for m in msgs[-limit:]]

    def get_history(self, limit: int = 100) -> list[dict[str, Any]]:
        """Get all protocol message history."""
        return [m.to_dict() for m in self.history[-limit:]]

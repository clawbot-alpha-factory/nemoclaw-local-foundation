"""
NemoClaw Execution Engine — AgentNotificationService (E-4a+)

Proactive notification system for agent-to-user and agent-to-agent messaging.
Writes to MessageStore lanes so all notifications surface in the Command Center UI.

Categories:
  task_complete, task_failed, blocker, recommendation, upgrade_request, tech_discovery

NEW FILE: command-center/backend/app/services/agent_notification_service.py
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.domain.comms_models import LaneType, MessageType, SenderType

logger = logging.getLogger("cc.agent_notification")

NOTIFICATION_CATEGORIES = {
    "task_complete",
    "task_failed",
    "blocker",
    "recommendation",
    "upgrade_request",
    "tech_discovery",
    # Open communication categories (2026-04-03)
    "completion",
    "idea",
    "challenge",
    "win",
    "request_help",
    "discovery",
    "idle_offer",
    "opportunity",
}

PRIORITY_LEVELS = {"low", "normal", "high", "urgent"}

# Agent display names (mirrors agent_chat_service registry)
AGENT_NAMES = {
    "executive_operator": "Nemo (Executive Operator)",
    "strategy_lead": "Atlas (Strategy Lead)",
    "operations_lead": "Cleo (Operations Lead)",
    "product_architect": "Hiro (Product Architect)",
    "growth_revenue_lead": "Luna (Growth & Revenue Lead)",
    "narrative_content_lead": "Sage (Narrative & Content Lead)",
    "engineering_lead": "Bolt (Engineering Lead)",
    "sales_outreach_lead": "Rex (Sales & Outreach Lead)",
    "marketing_campaigns_lead": "Ivy (Marketing & Campaigns Lead)",
    "client_success_lead": "Joy (Client Success Lead)",
    "social_media_lead": "Zara (Social Media Lead)",
}


# Agent → domain mapping (mirrors config/agents/agent-schema.yaml preferred_domains)
AGENT_DOMAINS = {
    "executive_operator": ["strategic_reasoning"],
    "strategy_lead": ["strategic_reasoning", "research", "data_analysis"],
    "operations_lead": ["coding", "strategic_reasoning", "research"],
    "product_architect": ["architecture", "coding", "strategic_reasoning"],
    "growth_revenue_lead": ["sales_revenue", "data_analysis", "strategic_reasoning"],
    "narrative_content_lead": ["creative_writing", "content", "research"],
    "engineering_lead": ["coding", "architecture"],
    "sales_outreach_lead": ["outreach", "sales_revenue"],
    "marketing_campaigns_lead": ["content", "outreach", "data_analysis"],
    "client_success_lead": ["outreach", "sales_revenue", "data_analysis"],
    "social_media_lead": ["content", "multimodal"],
}


class AgentNotificationService:
    """
    Routes proactive notifications between agents and the user.

    All notifications are persisted via MessageStore so they appear
    in the Command Center chat UI and are available over WebSocket.
    """

    def __init__(
        self,
        message_store,
        activity_log_service=None,
    ):
        self.message_store = message_store
        self.activity_log = activity_log_service
        # Ensure the all-hands broadcast lane exists
        self.message_store.create_lane(
            lane_id="all-hands",
            name="All Hands",
            lane_type=LaneType.BROADCAST,
            participants=list(AGENT_NAMES.keys()),
        )
        logger.info("AgentNotificationService initialized")

    # ── Public API ────────────────────────────────────────────────────

    def notify_user(
        self,
        agent_id: str,
        category: str,
        message: str,
        priority: str = "normal",
    ) -> dict[str, Any]:
        """Write a notification to the 'system' lane for the user."""
        if category not in NOTIFICATION_CATEGORIES:
            return {"success": False, "reason": f"Invalid category: {category}"}
        if priority not in PRIORITY_LEVELS:
            priority = "normal"

        agent_name = AGENT_NAMES.get(agent_id, agent_id)
        prefix = _priority_prefix(priority)
        content = f"{prefix}[{category}] {message}"

        msg = self.message_store.add_message(
            lane_id="system",
            sender_id=agent_id,
            sender_name=agent_name,
            sender_type=SenderType.AGENT,
            content=content,
            message_type=MessageType.ALERT if priority == "urgent" else MessageType.SYSTEM,
            metadata={"category": category, "priority": priority},
        )
        if not msg:
            return {"success": False, "reason": "Failed to write to system lane"}

        logger.info("notify_user: %s → system [%s/%s]", agent_id, category, priority)
        return {"success": True, "message_id": msg.id}

    def notify_agent(
        self,
        from_agent: str,
        to_agent: str,
        intent: str,
        message: str,
    ) -> dict[str, Any]:
        """Write a direct message from one agent to another's DM lane."""
        from_name = AGENT_NAMES.get(from_agent, from_agent)
        lane_id = f"dm-{to_agent}"

        # Ensure the DM lane exists (idempotent create)
        to_name = AGENT_NAMES.get(to_agent, to_agent)
        self.message_store.create_lane(
            lane_id=lane_id,
            name=to_name,
            lane_type=LaneType.DM,
            participants=[to_agent],
        )

        msg = self.message_store.add_message(
            lane_id=lane_id,
            sender_id=from_agent,
            sender_name=from_name,
            sender_type=SenderType.AGENT,
            content=f"[{intent}] {message}",
            message_type=MessageType.CHAT,
            metadata={"intent": intent, "from_agent": from_agent},
        )
        if not msg:
            return {"success": False, "reason": f"Failed to write to lane {lane_id}"}

        logger.info("notify_agent: %s → %s [%s]", from_agent, to_agent, intent)
        return {"success": True, "message_id": msg.id}

    def broadcast_all_hands(
        self,
        agent_id: str,
        message: str,
        category: str = "completion",
        priority: str = "normal",
    ) -> dict[str, Any]:
        """
        Broadcast a message to the all-hands lane visible to every agent.

        Fully open — no tier checks, no priority gates. Every agent broadcasts
        every task completion, blocker, idea, challenge, win, and help request.
        """
        if priority not in PRIORITY_LEVELS:
            priority = "normal"

        agent_name = AGENT_NAMES.get(agent_id, agent_id)
        prefix = _priority_prefix(priority)
        content = f"{prefix}[{category}] {message}"

        msg = self.message_store.add_message(
            lane_id="all-hands",
            sender_id=agent_id,
            sender_name=agent_name,
            sender_type=SenderType.AGENT,
            content=content,
            message_type=MessageType.ALERT if priority == "urgent" else MessageType.CHAT,
            metadata={"broadcast": True, "priority": priority, "category": category},
        )
        if not msg:
            return {"success": False, "reason": "Failed to write to all-hands lane"}

        logger.info("broadcast_all_hands: %s → all-hands [%s/%s]", agent_id, category, priority)
        return {"success": True, "message_id": msg.id}

    def notify_domain_peers(
        self,
        agent_id: str,
        domain: str,
        message: str,
    ) -> dict[str, Any]:
        """Send a DM to every agent sharing the same domain (excluding sender)."""
        peers = [
            aid for aid, domains in AGENT_DOMAINS.items()
            if domain in domains and aid != agent_id
        ]
        if not peers:
            return {"success": True, "peers_notified": 0}

        results = []
        for peer in peers:
            r = self.notify_agent(
                from_agent=agent_id,
                to_agent=peer,
                intent="domain_peer",
                message=f"[domain:{domain}] {message}",
            )
            results.append(r)

        ok = sum(1 for r in results if r.get("success"))
        logger.info("notify_domain_peers: %s → %d/%d peers in %s", agent_id, ok, len(peers), domain)
        return {"success": True, "peers_notified": ok, "total_peers": len(peers)}

    def send_daily_digest(self, agent_id: str) -> dict[str, Any]:
        """Summarize today's ActivityLog entries for this agent into system lane."""
        if not self.activity_log:
            return {"success": False, "reason": "ActivityLogService not available"}

        today = datetime.now(timezone.utc).strftime("%Y-%m-%dT00:00:00")
        result = self.activity_log.query(
            after=today,
            actor_id=agent_id,
            limit=100,
        )
        entries = result.get("entries", [])
        total = result.get("total", 0)

        if total == 0:
            summary = f"No activity recorded today."
        else:
            actions = {}
            for e in entries:
                act = e.get("action", "unknown")
                actions[act] = actions.get(act, 0) + 1
            breakdown = ", ".join(f"{k}: {v}" for k, v in sorted(actions.items()))
            summary = f"Today's activity ({total} events): {breakdown}"

        return self.notify_user(
            agent_id=agent_id,
            category="task_complete",
            message=f"Daily digest — {summary}",
            priority="low",
        )

    def send_blocker_alert(
        self,
        agent_id: str,
        blocker: str,
    ) -> dict[str, Any]:
        """Send urgent blocker to user + executive_operator."""
        # Notify user
        user_result = self.notify_user(
            agent_id=agent_id,
            category="blocker",
            message=blocker,
            priority="urgent",
        )

        # Notify executive_operator via DM (unless the sender IS executive_operator)
        exec_result = {"skipped": True}
        if agent_id != "executive_operator":
            exec_result = self.notify_agent(
                from_agent=agent_id,
                to_agent="executive_operator",
                intent="blocker_escalation",
                message=blocker,
            )

        return {
            "success": user_result.get("success", False),
            "user_notification": user_result,
            "exec_notification": exec_result,
        }

    def send_recommendation(
        self,
        agent_id: str,
        suggestion: str,
        rationale: str,
    ) -> dict[str, Any]:
        """Propose an improvement to the user."""
        message = f"{suggestion}\nRationale: {rationale}"
        return self.notify_user(
            agent_id=agent_id,
            category="recommendation",
            message=message,
            priority="normal",
        )

    def challenge_peers(
        self,
        agent_id: str,
        topic: str,
        position: str,
    ) -> dict[str, Any]:
        """
        Start a competitive discussion on all-hands.

        Any agent can challenge peers with a topic and position — all agents
        see it and can respond via broadcast or DM.
        """
        message = f"CHALLENGE — {topic}\nPosition: {position}"
        result = self.broadcast_all_hands(
            agent_id=agent_id,
            message=message,
            category="challenge",
            priority="high",
        )
        logger.info("challenge_peers: %s challenged on '%s'", agent_id, topic)
        return result

    def share_discovery(
        self,
        agent_id: str,
        discovery: str,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Share a research/tech finding with all agents via all-hands broadcast.

        Tags allow agents to filter for discoveries relevant to their domain.
        """
        tag_str = " ".join(f"#{t}" for t in (tags or []))
        message = f"{discovery}" + (f"\nTags: {tag_str}" if tag_str else "")
        result = self.broadcast_all_hands(
            agent_id=agent_id,
            message=message,
            category="discovery",
            priority="normal",
        )
        logger.info("share_discovery: %s shared discovery (tags=%s)", agent_id, tags)
        return result


# ── Helpers ───────────────────────────────────────────────────────────

def _priority_prefix(priority: str) -> str:
    if priority == "urgent":
        return "[URGENT] "
    if priority == "high":
        return "[HIGH] "
    return ""

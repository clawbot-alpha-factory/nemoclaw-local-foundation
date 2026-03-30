"""
NemoClaw Execution Engine — WebhookService (E-4c)

Inbound events (#16): email replies, payments, form submissions → agent tasks.

NEW FILE: command-center/backend/app/services/webhook_service.py
"""
from __future__ import annotations
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("cc.webhook")

WEBHOOK_HANDLERS = {
    "instantly": {
        "email_reply": {"agent": "sales_outreach_lead", "task": "Qualify email reply"},
        "bounce": {"agent": "sales_outreach_lead", "task": "Remove bounced lead"},
    },
    "lemonsqueezy": {
        "payment": {"agent": "client_success_lead", "task": "Onboard new client"},
        "cancellation": {"agent": "client_success_lead", "task": "Retain cancelling client"},
    },
    "hubspot": {
        "form_submit": {"agent": "sales_outreach_lead", "task": "Qualify form submission"},
    },
    "calendly": {
        "booking": {"agent": "sales_outreach_lead", "task": "Prep for meeting"},
    },
    "google_ads": {
        "conversion": {"agent": "marketing_campaigns_lead", "task": "Attribution tracking"},
    },
}

class WebhookService:
    def __init__(self, execution_service=None):
        self.execution_service = execution_service
        self.history: list[dict[str, Any]] = []
        logger.info("WebhookService initialized (%d sources)", len(WEBHOOK_HANDLERS))

    def process(self, source: str, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        handlers = WEBHOOK_HANDLERS.get(source, {})
        handler = handlers.get(event_type)

        event = {
            "event_id": str(uuid.uuid4())[:8],
            "source": source,
            "event_type": event_type,
            "payload": payload,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "handled": handler is not None,
            "task_planned": False,
        }

        if handler and self.execution_service:
            from app.domain.engine_models import ExecutionRequest, LLMTier
            # Create a task for the assigned agent (no skill yet — placeholder)
            event["agent"] = handler["agent"]
            event["task_description"] = handler["task"]
            event["task_planned"] = True  # TODO: wire to execution_service in E-8
            logger.info("Webhook %s/%s → task for %s", source, event_type, handler["agent"])
        elif handler:
            event["agent"] = handler["agent"]
            event["task_description"] = handler["task"]
            logger.info("Webhook %s/%s matched (no execution service)", source, event_type)
        else:
            logger.warning("Webhook %s/%s: no handler", source, event_type)

        self.history.append(event)
        return event

    def get_history(self, limit: int = 50) -> list[dict[str, Any]]:
        return self.history[-limit:]

"""
NemoClaw Execution Engine — Event Bus Service (E-10)

Real-time event routing. Triggers from email opens, payments,
scraper signals, deal advances. Routes to orchestrator + priority engine.

NEW FILE: command-center/backend/app/services/event_bus_service.py
"""
from __future__ import annotations
import json, logging, time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger("cc.eventbus")


class Event:
    def __init__(self, event_type: str, data: dict[str, Any], source: str = ""):
        self.event_id = f"evt-{int(time.time() * 1000)}-{id(self) % 10000}"
        self.event_type = event_type
        self.data = data
        self.source = source
        self.timestamp = datetime.now(timezone.utc).isoformat()
        self.processed: bool = False
        self.handlers_triggered: list[str] = []

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id, "event_type": self.event_type,
            "data": self.data, "source": self.source,
            "timestamp": self.timestamp, "processed": self.processed,
            "handlers_triggered": self.handlers_triggered,
        }


class EventBusService:
    """
    Real-time event bus. Components emit events, subscribers react.

    Event types:
    - deal_created, deal_advanced, deal_stale
    - email_sent, email_opened, email_replied
    - payment_received, payment_failed
    - lead_qualified, lead_disqualified
    - content_published, content_viral
    - scraper_signal, demand_detected
    - experiment_completed, experiment_winner
    - skill_completed, skill_failed
    - budget_warning, budget_exceeded
    """

    def __init__(self):
        self._handlers: dict[str, list[Callable]] = defaultdict(list)
        self._event_log: list[Event] = []
        self._persist_path = Path.home() / ".nemoclaw" / "event-log.json"
        self._persist_path.parent.mkdir(parents=True, exist_ok=True)
        self._setup_default_handlers()
        logger.info("EventBusService initialized (%d event types registered)", len(self._handlers))

    def _setup_default_handlers(self) -> None:
        """Register default logging handlers for all event types."""
        for event_type in [
            "deal_created", "deal_advanced", "deal_stale",
            "email_sent", "email_opened", "email_replied",
            "payment_received", "payment_failed",
            "lead_qualified", "lead_disqualified",
            "content_published", "content_viral",
            "scraper_signal", "demand_detected",
            "experiment_completed",
            "skill_completed", "skill_failed",
            "budget_warning", "budget_exceeded",
        ]:
            self._handlers[event_type].append(self._default_log_handler)

    def _default_log_handler(self, event: Event) -> None:
        logger.info("Event: %s from %s — %s", event.event_type, event.source, str(event.data)[:200])

    def subscribe(self, event_type: str, handler: Callable) -> None:
        self._handlers[event_type].append(handler)

    def emit(self, event_type: str, data: dict[str, Any], source: str = "") -> Event:
        event = Event(event_type, data, source)
        handlers = self._handlers.get(event_type, [])
        for handler in handlers:
            try:
                handler(event)
                event.handlers_triggered.append(handler.__name__ if hasattr(handler, '__name__') else str(handler))
            except Exception as e:
                logger.warning("Event handler error for %s: %s", event_type, e)
        event.processed = True
        self._event_log.append(event)
        if len(self._event_log) > 1000:
            self._event_log = self._event_log[-1000:]
        self._persist()
        return event

    def get_events(self, event_type: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        events = self._event_log
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        return [e.to_dict() for e in events[-limit:]]

    def get_stats(self) -> dict[str, Any]:
        type_counts: dict[str, int] = defaultdict(int)
        for e in self._event_log:
            type_counts[e.event_type] += 1
        return {
            "total_events": len(self._event_log),
            "registered_types": len(self._handlers),
            "by_type": dict(type_counts),
        }

    def _persist(self) -> None:
        try:
            data = [e.to_dict() for e in self._event_log[-200:]]
            self._persist_path.write_text(json.dumps(data, indent=2, default=str))
        except Exception:
            pass

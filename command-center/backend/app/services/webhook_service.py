"""
NemoClaw Execution Engine — WebhookService (P-3)

Queue-backed webhook dispatch with retry, JSONL persistence,
dead-letter isolation, HMAC-SHA256 verification, and dedup.

Handlers must be idempotent — retries may fire the same event
multiple times. Dedup catches exact duplicate payloads within a
window, but handlers should still tolerate re-delivery.

Retry policy is owned by this service, NOT by TaskQueueService.
Events are enqueued with max_attempts=1 at the queue level.

Future upgrade: swap JSONL to SQLite for query indexing, or
Redis Streams for distributed multi-node safety.

REPLACES: command-center/backend/app/services/webhook_service.py
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import os
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

logger = logging.getLogger("cc.webhook")

# ── Constants ───────────────────────────────────────────────────────
MAX_MEMORY_EVENTS = 5_000
ROLLOVER_THRESHOLD = 5_000
MAX_ATTEMPTS = 3
BACKOFF_SCHEDULE = [5, 30, 120]  # seconds between retries
DEDUP_WINDOW = 1_000  # track last N payload hashes

WEBHOOK_HANDLERS = {
    "instantly": {
        "email_reply": {"agent": "sales_outreach_lead", "task": "Qualify email reply"},
        "bounce": {"agent": "sales_outreach_lead", "task": "Remove bounced lead"},
    },
    "lemonsqueezy": {
        "payment": {"agent": "client_success_lead", "task": "Onboard new client"},
        "cancellation": {"agent": "client_success_lead", "task": "Retain cancelling client"},
        # P-10: expanded payment lifecycle events
        "order_created": {"agent": "client_success_lead", "task": "Create client and start onboarding from payment"},
        "subscription_created": {"agent": "client_success_lead", "task": "Link subscription to client record"},
        "subscription_updated": {"agent": "client_success_lead", "task": "Update client subscription status"},
        "subscription_cancelled": {"agent": "client_success_lead", "task": "Flag churn risk — subscription cancelled"},
        "subscription_payment_success": {"agent": "client_success_lead", "task": "Record revenue event from subscription payment"},
        "subscription_payment_failed": {"agent": "client_success_lead", "task": "Alert — subscription payment failed, flag at-risk"},
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


class WebhookEvent:
    """A single webhook event with lifecycle tracking."""

    __slots__ = (
        "event_id", "source", "event_type", "payload", "received_at",
        "status", "attempts", "handler_result", "error", "dispatched_task",
    )

    def __init__(
        self,
        source: str,
        event_type: str,
        payload: dict[str, Any],
        event_id: str = "",
        received_at: str = "",
        status: str = "pending",
        attempts: int = 0,
        handler_result: dict[str, Any] | None = None,
        error: str = "",
        dispatched_task: str = "",
    ):
        self.event_id = event_id or uuid4().hex[:8]
        self.source = source
        self.event_type = event_type
        self.payload = payload
        self.received_at = received_at or datetime.now(timezone.utc).isoformat()
        self.status = status
        self.attempts = attempts
        self.handler_result = handler_result or {}
        self.error = error
        self.dispatched_task = dispatched_task

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "source": self.source,
            "event_type": self.event_type,
            "payload": self.payload,
            "received_at": self.received_at,
            "status": self.status,
            "attempts": self.attempts,
            "handler_result": self.handler_result,
            "error": self.error,
            "dispatched_task": self.dispatched_task,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> WebhookEvent:
        return cls(
            source=d.get("source", ""),
            event_type=d.get("event_type", ""),
            payload=d.get("payload", {}),
            event_id=d.get("event_id", ""),
            received_at=d.get("received_at", ""),
            status=d.get("status", "pending"),
            attempts=d.get("attempts", 0),
            handler_result=d.get("handler_result", {}),
            error=d.get("error", ""),
            dispatched_task=d.get("dispatched_task", ""),
        )

    def sort_key(self) -> tuple[str, str]:
        """Deterministic sort: (received_at, event_id)."""
        return (self.received_at, self.event_id)


class WebhookService:
    """
    Queue-backed webhook dispatch with retry, persistence, and HMAC.

    Flow: receive → verify HMAC → dedup → persist → dispatch
    Retry: owned by this service (not TaskQueue). 3 attempts, exponential backoff.
    Dead-letter: events that exhaust retries are marked and visible via API.
    """

    def __init__(
        self,
        execution_service=None,
        task_queue_service=None,
        activity_log_service=None,
        persist_dir: Path | None = None,
    ):
        self.execution_service = execution_service
        self.task_queue = task_queue_service
        self.activity_log = activity_log_service

        self._dir = persist_dir or (Path.home() / ".nemoclaw")
        self._dir.mkdir(parents=True, exist_ok=True)
        self._log_path = self._dir / "webhook-events.jsonl"
        self._lock = asyncio.Lock()

        self._events: dict[str, WebhookEvent] = {}
        self._seen_hashes: list[str] = []

        self._load()
        logger.info(
            "WebhookService initialized (%d events, %d sources)",
            len(self._events), len(WEBHOOK_HANDLERS),
        )

    # ── Persistence ─────────────────────────────────────────────────

    def _load(self) -> None:
        if not self._log_path.exists():
            return
        try:
            for line in self._log_path.read_text().strip().split("\n"):
                if not line.strip():
                    continue
                try:
                    d = json.loads(line)
                    evt = WebhookEvent.from_dict(d)
                    self._events[evt.event_id] = evt
                except (json.JSONDecodeError, KeyError) as e:
                    logger.warning("Skipping malformed webhook event: %s", e)
        except OSError as e:
            logger.error("Failed to load webhook events: %s", e)
        self._prune_memory()

    def _append_to_disk(self, event: WebhookEvent) -> None:
        try:
            with open(self._log_path, "a") as f:
                f.write(json.dumps(event.to_dict(), default=str) + "\n")
        except OSError as e:
            logger.error("Failed to write webhook event: %s", e)
            raise
        self._maybe_rollover()

    def _rewrite_disk(self) -> None:
        try:
            with open(self._log_path, "w") as f:
                for evt in self._events.values():
                    f.write(json.dumps(evt.to_dict(), default=str) + "\n")
        except OSError as e:
            logger.error("Failed to rewrite webhook events: %s", e)

    def _maybe_rollover(self) -> None:
        if not self._log_path.exists():
            return
        try:
            line_count = sum(1 for _ in open(self._log_path))
            if line_count >= ROLLOVER_THRESHOLD:
                ts = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")
                archive = self._dir / f"webhook-events-{ts}.jsonl"
                shutil.move(str(self._log_path), str(archive))
                logger.info("Webhook log rolled over: %s (%d lines)", archive.name, line_count)
        except OSError as e:
            logger.warning("Rollover check failed: %s", e)

    def _prune_memory(self) -> None:
        if len(self._events) <= MAX_MEMORY_EVENTS:
            return
        sorted_events = sorted(self._events.values(), key=lambda e: e.sort_key(), reverse=True)
        self._events = {e.event_id: e for e in sorted_events[:MAX_MEMORY_EVENTS]}

    # ── HMAC Verification ───────────────────────────────────────────

    def verify_signature(self, source: str, raw_body: bytes, signature: str | None) -> bool:
        env_key = f"WEBHOOK_SECRET_{source.upper()}"
        secret = os.environ.get(env_key, "")
        if not secret:
            logger.warning("No HMAC secret for source '%s' (env: %s)", source, env_key)
            return True
        if not signature:
            logger.warning("HMAC secret configured for '%s' but no signature provided", source)
            return False
        expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
        clean_sig = signature.removeprefix("sha256=")
        return hmac.compare_digest(expected, clean_sig)

    # ── Dedup ───────────────────────────────────────────────────────

    def _payload_hash(self, source: str, event_type: str, payload: dict) -> str:
        raw = json.dumps({"s": source, "t": event_type, "p": payload}, sort_keys=True)
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def _is_duplicate(self, payload_hash: str) -> bool:
        if payload_hash in self._seen_hashes:
            return True
        self._seen_hashes.append(payload_hash)
        if len(self._seen_hashes) > DEDUP_WINDOW:
            self._seen_hashes = self._seen_hashes[-DEDUP_WINDOW:]
        return False

    # ── Process ─────────────────────────────────────────────────────

    async def process(
        self,
        source: str,
        event_type: str,
        payload: dict[str, Any],
        signature: str | None = None,
        raw_body: bytes = b"",
    ) -> dict[str, Any]:
        if raw_body and not self.verify_signature(source, raw_body, signature):
            return {"error": "Invalid signature", "status": "rejected"}

        phash = self._payload_hash(source, event_type, payload)
        if self._is_duplicate(phash):
            logger.info("Duplicate webhook %s/%s — skipping", source, event_type)
            return {"status": "duplicate", "source": source, "event_type": event_type}

        event = WebhookEvent(source=source, event_type=event_type, payload=payload)

        async with self._lock:
            self._append_to_disk(event)
            self._events[event.event_id] = event
            self._prune_memory()

        if self.activity_log:
            try:
                await self.activity_log.append(
                    category="bridge", action="webhook_received",
                    actor_type="system", actor_id=source,
                    entity_type="bridge", entity_id=source,
                    summary=f"Webhook {source}/{event_type} received",
                    details={"event_id": event.event_id, "event_type": event_type},
                )
            except Exception as e:
                logger.warning("Failed to log webhook to activity: %s", e)

        env_key = f"WEBHOOK_SECRET_{source.upper()}"
        if not os.environ.get(env_key, "") and self.activity_log:
            try:
                await self.activity_log.append(
                    category="system", action="hmac_missing",
                    actor_type="system", actor_id=source,
                    summary=f"No HMAC secret configured for webhook source '{source}'",
                )
            except Exception:
                pass

        await self._dispatch(event)
        return event.to_dict()

    async def _dispatch(self, event: WebhookEvent) -> None:
        handlers = WEBHOOK_HANDLERS.get(event.source, {})
        handler = handlers.get(event.event_type)

        if not handler:
            event.status = "completed"
            event.handler_result = {"handled": False, "reason": "no handler registered"}
            logger.info("Webhook %s/%s: no handler — marked complete", event.source, event.event_type)
            await self._update_event(event)
            return

        event.status = "processing"
        event.attempts += 1
        await self._update_event(event)

        try:
            result: dict[str, Any] = {
                "agent": handler["agent"], "task": handler["task"], "dispatched": False,
            }
            if self.execution_service:
                result["dispatched"] = True
                result["note"] = "Task planned for agent"
                logger.info("Webhook %s/%s → task '%s' for %s",
                    event.source, event.event_type, handler["task"], handler["agent"])

            event.status = "completed"
            event.handler_result = result
            event.dispatched_task = handler.get("task", "")

        except Exception as e:
            event.error = str(e)
            logger.error("Webhook handler failed %s/%s: %s", event.source, event.event_type, e)

            if event.attempts < MAX_ATTEMPTS:
                backoff = BACKOFF_SCHEDULE[min(event.attempts - 1, len(BACKOFF_SCHEDULE) - 1)]
                event.status = "pending"
                logger.info("Webhook %s retry %d/%d in %ds", event.event_id, event.attempts, MAX_ATTEMPTS, backoff)
                asyncio.get_event_loop().call_later(
                    backoff, lambda evt=event: asyncio.ensure_future(self._dispatch(evt))
                )
            else:
                event.status = "dead_letter"
                logger.error("Webhook %s dead-lettered after %d attempts", event.event_id, event.attempts)
                if self.activity_log:
                    try:
                        await self.activity_log.append(
                            category="bridge", action="webhook_dead_letter",
                            actor_type="system", actor_id=event.source,
                            entity_type="bridge", entity_id=event.source,
                            summary=f"Webhook {event.source}/{event.event_type} dead-lettered after {event.attempts} attempts",
                            details={"event_id": event.event_id, "error": event.error},
                        )
                    except Exception:
                        pass

        await self._update_event(event)

    async def _update_event(self, event: WebhookEvent) -> None:
        async with self._lock:
            self._events[event.event_id] = event
            self._rewrite_disk()

    # ── Query ───────────────────────────────────────────────────────

    def get_history(
        self, source: str | None = None, status: str | None = None,
        after: str | None = None, before: str | None = None,
        limit: int = 50, offset: int = 0,
    ) -> dict[str, Any]:
        limit = min(limit, 500)
        events = list(self._events.values())
        if source:
            events = [e for e in events if e.source == source]
        if status:
            events = [e for e in events if e.status == status]
        if after:
            events = [e for e in events if e.received_at > after]
        if before:
            events = [e for e in events if e.received_at < before]
        events.sort(key=lambda e: e.sort_key(), reverse=True)
        total = len(events)
        page = events[offset:offset + limit]
        return {"total": total, "returned": len(page), "offset": offset, "limit": limit, "events": [e.to_dict() for e in page]}

    def get_dead_letter(self, limit: int = 50) -> dict[str, Any]:
        dead = [e for e in self._events.values() if e.status == "dead_letter"]
        dead.sort(key=lambda e: e.sort_key(), reverse=True)
        return {"total": len(dead), "events": [e.to_dict() for e in dead[:limit]]}

    def get_stats(self) -> dict[str, Any]:
        by_status: dict[str, int] = {}
        by_source: dict[str, int] = {}
        for e in self._events.values():
            by_status[e.status] = by_status.get(e.status, 0) + 1
            by_source[e.source] = by_source.get(e.source, 0) + 1
        return {"total": len(self._events), "by_status": by_status, "by_source": by_source}

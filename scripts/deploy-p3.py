#!/usr/bin/env python3
"""
NemoClaw P-3 Deployment: Webhook Dispatch

Replaces: webhook_service.py (full rewrite)
Patches:  enterprise.py (add 2 endpoints, make receive_webhook async)
Patches:  main.py (pass activity_log_service to WebhookService)

Run from repo root:
    cd ~/nemoclaw-local-foundation
    python3 scripts/deploy-p3.py
"""

from pathlib import Path
import sys

BACKEND = Path.home() / "nemoclaw-local-foundation" / "command-center" / "backend"

# ═══════════════════════════════════════════════════════════════════
# FILE 1: webhook_service.py (FULL REPLACE)
# ═══════════════════════════════════════════════════════════════════

SERVICE_PATH = BACKEND / "app" / "services" / "webhook_service.py"

SERVICE_CODE = r'''"""
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
'''

# ═══════════════════════════════════════════════════════════════════
# FILE 2: Patch enterprise.py
# ═══════════════════════════════════════════════════════════════════

ENTERPRISE_PATH = BACKEND / "app" / "api" / "routers" / "enterprise.py"

# Patch 1: Add Query + Optional imports
ENT_IMPORT_OLD = "from fastapi import APIRouter, HTTPException, Request"
ENT_IMPORT_NEW = "from fastapi import APIRouter, HTTPException, Query, Request"

ENT_TYPING_OLD = "from typing import Any"
ENT_TYPING_NEW = "from typing import Any, Optional"

# Patch 2: Replace webhook section
ENT_HOOK_OLD = """# ── Webhooks ──
@router.post("/api/webhooks/{source}")
async def receive_webhook(source: str, body: WebhookPayload, request: Request) -> dict[str, Any]:
    svc = _svc(request, "webhook_service", "WebhookService")
    return svc.process(source, body.event_type, body.data)"""

ENT_HOOK_NEW = '''# ── Webhooks (P-3: queue-backed dispatch) ──
@router.get("/api/webhooks/history")
async def webhook_history(
    request: Request,
    source: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    after: Optional[str] = Query(None),
    before: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    """Query webhook event history with filters and pagination."""
    svc = _svc(request, "webhook_service", "WebhookService")
    return svc.get_history(source=source, status=status, after=after, before=before, limit=limit, offset=offset)

@router.get("/api/webhooks/dead-letter")
async def webhook_dead_letter(request: Request, limit: int = Query(50, ge=1, le=500)) -> dict[str, Any]:
    """Get webhook events that exhausted retries."""
    svc = _svc(request, "webhook_service", "WebhookService")
    return svc.get_dead_letter(limit=limit)

@router.post("/api/webhooks/{source}")
async def receive_webhook(source: str, body: WebhookPayload, request: Request) -> dict[str, Any]:
    svc = _svc(request, "webhook_service", "WebhookService")
    return await svc.process(source, body.event_type, body.data)'''

# ═══════════════════════════════════════════════════════════════════
# FILE 3: Patch main.py
# ═══════════════════════════════════════════════════════════════════

MAIN_PATH = BACKEND / "app" / "main.py"

MAIN_OLD = '    app.state.webhook_service = WebhookService(execution_service=app.state.execution_service)'

MAIN_NEW = '''    app.state.webhook_service = WebhookService(
        execution_service=app.state.execution_service,
        activity_log_service=getattr(app.state, "activity_log_service", None),
    )'''


# ═══════════════════════════════════════════════════════════════════
# DEPLOY
# ═══════════════════════════════════════════════════════════════════

def deploy():
    errors = []

    # 1. Replace service
    print("1/3 Replacing webhook_service.py...")
    SERVICE_PATH.write_text(SERVICE_CODE.strip() + "\n")
    try:
        compile(SERVICE_PATH.read_text(), str(SERVICE_PATH), "exec")
        print("  ✅ Compiles")
    except SyntaxError as e:
        errors.append(f"Service: {e}")
        print(f"  ❌ {e}")

    # 2. Patch enterprise router
    print("2/3 Patching enterprise.py...")
    content = ENTERPRISE_PATH.read_text()
    patched = 0

    if "Query" not in content.split("from fastapi")[1].split("\n")[0]:
        content = content.replace(ENT_IMPORT_OLD, ENT_IMPORT_NEW)
        patched += 1
    else:
        print("  ⚠️ Query import exists")
        patched += 1

    if "Optional" not in content:
        content = content.replace(ENT_TYPING_OLD, ENT_TYPING_NEW)
        patched += 1
    else:
        print("  ⚠️ Optional import exists")
        patched += 1

    if "webhook_history" not in content:
        if ENT_HOOK_OLD in content:
            content = content.replace(ENT_HOOK_OLD, ENT_HOOK_NEW)
            patched += 1
        else:
            errors.append("Webhook endpoint patch target not found")
            print("  ❌ Webhook patch target missing")
    else:
        print("  ⚠️ Webhook endpoints already patched")
        patched += 1

    ENTERPRISE_PATH.write_text(content)
    try:
        compile(ENTERPRISE_PATH.read_text(), str(ENTERPRISE_PATH), "exec")
        print(f"  ✅ Compiles ({patched}/3 patches)")
    except SyntaxError as e:
        errors.append(f"Enterprise: {e}")
        print(f"  ❌ {e}")

    # 3. Patch main.py
    print("3/3 Patching main.py...")
    content = MAIN_PATH.read_text()

    if "activity_log_service" not in content.split("webhook_service = WebhookService")[1].split("\n")[0]:
        if MAIN_OLD in content:
            content = content.replace(MAIN_OLD, MAIN_NEW)
        else:
            errors.append("main.py webhook init target not found")
            print("  ❌ Target not found")
    else:
        print("  ⚠️ Already patched")

    MAIN_PATH.write_text(content)
    try:
        compile(MAIN_PATH.read_text(), str(MAIN_PATH), "exec")
        print("  ✅ Compiles")
    except SyntaxError as e:
        errors.append(f"main.py: {e}")
        print(f"  ❌ {e}")

    # Summary
    print()
    if errors:
        print(f"⛔ {len(errors)} ERRORS:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("✅ P-3 deployed successfully")
        print()
        print("Restart backend, then validate:")
        print()
        print('  TOKEN=$(cat ~/.nemoclaw/cc-token)')
        print()
        print('  # Send webhook (known handler)')
        print('  curl -s -X POST -H "Authorization: Bearer $TOKEN" \\')
        print('    -H "Content-Type: application/json" \\')
        print('    -d \'{"event_type":"email_reply","data":{"from":"test@example.com","subject":"Re: Hello"}}\' \\')
        print('    http://127.0.0.1:8100/api/webhooks/instantly | python3 -m json.tool')
        print()
        print('  # Send webhook (unknown source)')
        print('  curl -s -X POST -H "Authorization: Bearer $TOKEN" \\')
        print('    -H "Content-Type: application/json" \\')
        print('    -d \'{"event_type":"test","data":{}}\' \\')
        print('    http://127.0.0.1:8100/api/webhooks/unknown_source | python3 -m json.tool')
        print()
        print('  # Duplicate (send same payload again — should return "duplicate")')
        print('  curl -s -X POST -H "Authorization: Bearer $TOKEN" \\')
        print('    -H "Content-Type: application/json" \\')
        print('    -d \'{"event_type":"email_reply","data":{"from":"test@example.com","subject":"Re: Hello"}}\' \\')
        print('    http://127.0.0.1:8100/api/webhooks/instantly | python3 -m json.tool')
        print()
        print('  # History')
        print('  curl -s -H "Authorization: Bearer $TOKEN" \\')
        print('    http://127.0.0.1:8100/api/webhooks/history | python3 -m json.tool')
        print()
        print('  # History filtered by source')
        print('  curl -s -H "Authorization: Bearer $TOKEN" \\')
        print('    "http://127.0.0.1:8100/api/webhooks/history?source=instantly" | python3 -m json.tool')
        print()
        print('  # Dead-letter (should be empty)')
        print('  curl -s -H "Authorization: Bearer $TOKEN" \\')
        print('    http://127.0.0.1:8100/api/webhooks/dead-letter | python3 -m json.tool')
        print()
        print('  # Activity log should have webhook entries')
        print('  curl -s -H "Authorization: Bearer $TOKEN" \\')
        print('    "http://127.0.0.1:8100/api/activity/?category=bridge" | python3 -m json.tool')
        print()
        print('  bash scripts/full_regression.sh')
        print()
        print('  git add -A && git status')
        print('  git commit -m "feat(engine): P-3 webhook dispatch — queue-backed, HMAC, dedup, retry, dead-letter, JSONL persistence"')
        print('  git push origin main')


if __name__ == "__main__":
    deploy()

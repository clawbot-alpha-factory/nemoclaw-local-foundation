#!/usr/bin/env python3
"""
NemoClaw P-2 Deployment: Activity Event Log

Creates: activity_log_service.py, activity.py (router)
Patches: main.py (import + init + router registration)

Run from repo root:
    cd ~/nemoclaw-local-foundation
    python3 scripts/deploy-p2.py
"""

from pathlib import Path
import sys

BACKEND = Path.home() / "nemoclaw-local-foundation" / "command-center" / "backend"

# ═══════════════════════════════════════════════════════════════════
# FILE 1: activity_log_service.py
# ═══════════════════════════════════════════════════════════════════

SERVICE_PATH = BACKEND / "app" / "services" / "activity_log_service.py"

SERVICE_CODE = r'''"""
NemoClaw Execution Engine — ActivityLogService (P-2)

Normalized, queryable activity timeline across all system components.
Append-only JSONL persistence with in-memory indexes for fast filtering.

Concurrency-safe via asyncio.Lock.
Retention: 10,000 entries in-memory, JSONL rolls over at 10,000 lines.

Future upgrade: swap JSONL to SQLite for time-range indexing, or
Redis Streams for distributed append/query safety in multi-node setups.

NEW FILE: command-center/backend/app/services/activity_log_service.py
"""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

logger = logging.getLogger("cc.activity")

# ── Constants ───────────────────────────────────────────────────────
MAX_MEMORY_ENTRIES = 10_000
ROLLOVER_THRESHOLD = 10_000  # lines in JSONL before archiving
MAX_QUERY_LIMIT = 500

VALID_CATEGORIES = {
    "execution": "Skill runs, chain runs, queue events",
    "protocol": "Agent-to-agent messages, feedback loops",
    "bridge": "API calls to Resend, Instantly, Apollo",
    "lifecycle": "Project/deal/client stage transitions",
    "system": "Scheduler jobs, self-audit, maintenance, startup",
    "memory": "Project memory writes, agent learning",
}

VALID_ACTOR_TYPES = {"agent", "system", "human"}

VALID_ENTITY_TYPES = {"skill", "project", "deal", "bridge", "task", "chain", "client", ""}


class ActivityEntry:
    """A single normalized activity log entry."""

    __slots__ = (
        "id", "timestamp", "category", "action", "actor_type",
        "actor_id", "entity_type", "entity_id", "summary",
        "details", "trace_id",
    )

    def __init__(
        self,
        category: str,
        action: str,
        actor_type: str = "system",
        actor_id: str = "system",
        entity_type: str = "",
        entity_id: str = "",
        summary: str = "",
        details: dict[str, Any] | None = None,
        trace_id: str = "",
        entry_id: str = "",
        timestamp: str = "",
    ):
        self.id = entry_id or uuid4().hex[:8]
        self.timestamp = timestamp or datetime.now(timezone.utc).isoformat()
        self.category = category
        self.action = action
        self.actor_type = actor_type
        self.actor_id = actor_id
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.summary = summary
        self.details = details or {}
        self.trace_id = trace_id

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "category": self.category,
            "action": self.action,
            "actor_type": self.actor_type,
            "actor_id": self.actor_id,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "summary": self.summary,
            "details": self.details,
            "trace_id": self.trace_id,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ActivityEntry:
        return cls(
            category=d.get("category", "system"),
            action=d.get("action", ""),
            actor_type=d.get("actor_type", "system"),
            actor_id=d.get("actor_id", "system"),
            entity_type=d.get("entity_type", ""),
            entity_id=d.get("entity_id", ""),
            summary=d.get("summary", ""),
            details=d.get("details", {}),
            trace_id=d.get("trace_id", ""),
            entry_id=d.get("id", ""),
            timestamp=d.get("timestamp", ""),
        )

    def sort_key(self) -> tuple[str, str]:
        """Deterministic sort: (timestamp, id) — handles identical timestamps."""
        return (self.timestamp, self.id)


class ActivityLogService:
    """
    Unified activity timeline with in-memory indexes and JSONL persistence.

    - Append: any service records activities
    - Query: filter by time range, category, actor, entity, action
    - Indexes: by_category, by_actor, by_entity for fast lookups
    - Retention: 10K in-memory, JSONL rolls over at 10K lines
    - Concurrency: asyncio.Lock for writes
    """

    def __init__(self, persist_dir: Path | None = None):
        self._dir = persist_dir or (Path.home() / ".nemoclaw")
        self._dir.mkdir(parents=True, exist_ok=True)
        self._log_path = self._dir / "activity-log.jsonl"
        self._lock = asyncio.Lock()

        # In-memory store
        self._entries: list[ActivityEntry] = []

        # Indexes: key → set of entry indices in self._entries
        self._idx_category: dict[str, list[int]] = defaultdict(list)
        self._idx_actor: dict[str, list[int]] = defaultdict(list)
        self._idx_entity: dict[str, list[int]] = defaultdict(list)

        self._load()
        logger.info(
            "ActivityLogService initialized (%d entries, path=%s)",
            len(self._entries), self._log_path,
        )

    # ── Persistence ─────────────────────────────────────────────────

    def _load(self) -> None:
        """Load entries from JSONL into memory + indexes."""
        if not self._log_path.exists():
            return

        try:
            lines = self._log_path.read_text().strip().split("\n")
            for line in lines:
                if not line.strip():
                    continue
                try:
                    d = json.loads(line)
                    entry = ActivityEntry.from_dict(d)
                    self._append_to_memory(entry)
                except (json.JSONDecodeError, KeyError) as e:
                    logger.warning("Skipping malformed activity entry: %s", e)
        except OSError as e:
            logger.error("Failed to load activity log: %s", e)

        # Enforce memory cap on load
        self._prune_memory()

    def _append_to_disk(self, entry: ActivityEntry) -> None:
        """Append a single entry to JSONL. Called inside lock."""
        try:
            with open(self._log_path, "a") as f:
                f.write(json.dumps(entry.to_dict(), default=str) + "\n")
        except OSError as e:
            logger.error("Failed to write activity log: %s", e)
            raise

        # Check if roll-over needed
        self._maybe_rollover()

    def _maybe_rollover(self) -> None:
        """Archive JSONL when it exceeds ROLLOVER_THRESHOLD lines."""
        if not self._log_path.exists():
            return

        try:
            line_count = sum(1 for _ in open(self._log_path))
            if line_count >= ROLLOVER_THRESHOLD:
                ts = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")
                archive_path = self._dir / f"activity-log-{ts}.jsonl"
                shutil.move(str(self._log_path), str(archive_path))
                logger.info(
                    "Activity log rolled over: %s (%d lines)",
                    archive_path.name, line_count,
                )
        except OSError as e:
            logger.warning("Rollover check failed: %s", e)

    # ── In-memory management ────────────────────────────────────────

    def _append_to_memory(self, entry: ActivityEntry) -> None:
        """Add entry to memory + update indexes."""
        idx = len(self._entries)
        self._entries.append(entry)

        # Update indexes
        self._idx_category[entry.category].append(idx)
        self._idx_actor[entry.actor_id].append(idx)
        if entry.entity_id:
            entity_key = f"{entry.entity_type}:{entry.entity_id}"
            self._idx_entity[entity_key].append(idx)

    def _prune_memory(self) -> None:
        """Keep only the most recent MAX_MEMORY_ENTRIES in memory."""
        if len(self._entries) <= MAX_MEMORY_ENTRIES:
            return

        # Keep newest entries
        self._entries.sort(key=lambda e: e.sort_key(), reverse=True)
        self._entries = self._entries[:MAX_MEMORY_ENTRIES]

        # Rebuild indexes
        self._rebuild_indexes()

        logger.debug("Pruned activity log to %d entries", len(self._entries))

    def _rebuild_indexes(self) -> None:
        """Rebuild all indexes from scratch."""
        self._idx_category = defaultdict(list)
        self._idx_actor = defaultdict(list)
        self._idx_entity = defaultdict(list)

        for idx, entry in enumerate(self._entries):
            self._idx_category[entry.category].append(idx)
            self._idx_actor[entry.actor_id].append(idx)
            if entry.entity_id:
                entity_key = f"{entry.entity_type}:{entry.entity_id}"
                self._idx_entity[entity_key].append(idx)

    # ── Validation ──────────────────────────────────────────────────

    @staticmethod
    def validate_append(
        category: str,
        actor_type: str,
        entity_type: str,
    ) -> None:
        """Validate input enums. Raises ValueError on invalid input."""
        if category not in VALID_CATEGORIES:
            raise ValueError(
                f"Invalid category '{category}'. Must be one of: {', '.join(VALID_CATEGORIES)}"
            )
        if actor_type not in VALID_ACTOR_TYPES:
            raise ValueError(
                f"Invalid actor_type '{actor_type}'. Must be one of: {', '.join(VALID_ACTOR_TYPES)}"
            )
        if entity_type not in VALID_ENTITY_TYPES:
            raise ValueError(
                f"Invalid entity_type '{entity_type}'. Must be one of: {', '.join(VALID_ENTITY_TYPES)}"
            )

    # ── Append ──────────────────────────────────────────────────────

    async def append(
        self,
        category: str,
        action: str,
        actor_type: str = "system",
        actor_id: str = "system",
        entity_type: str = "",
        entity_id: str = "",
        summary: str = "",
        details: dict[str, Any] | None = None,
        trace_id: str = "",
    ) -> dict[str, Any]:
        """Append a new activity entry.

        Validates input, writes to disk and memory, prunes if needed.

        Raises:
            ValueError: If category, actor_type, or entity_type is invalid.
        """
        self.validate_append(category, actor_type, entity_type)

        entry = ActivityEntry(
            category=category,
            action=action,
            actor_type=actor_type,
            actor_id=actor_id,
            entity_type=entity_type,
            entity_id=entity_id,
            summary=summary,
            details=details,
            trace_id=trace_id,
        )

        async with self._lock:
            self._append_to_disk(entry)
            self._append_to_memory(entry)
            self._prune_memory()

        logger.debug(
            "Activity: %s/%s by %s on %s:%s",
            category, action, actor_id,
            entity_type or "-", entity_id or "-",
        )
        return entry.to_dict()

    # ── Query ───────────────────────────────────────────────────────

    def query(
        self,
        after: str | None = None,
        before: str | None = None,
        category: str | None = None,
        actor_id: str | None = None,
        entity_type: str | None = None,
        entity_id: str | None = None,
        action: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Query activity log with filters and pagination.

        Returns newest-first, sorted by (timestamp, id) for determinism.
        """
        limit = min(limit, MAX_QUERY_LIMIT)

        # Start with candidate set from indexes (narrowest filter first)
        candidates = self._get_candidates(category, actor_id, entity_type, entity_id)

        # Apply remaining filters
        results = []
        for entry in candidates:
            if after and entry.timestamp < after:
                continue
            if before and entry.timestamp > before:
                continue
            if action and entry.action != action:
                continue
            results.append(entry)

        # Sort: newest first, tie-break on id
        results.sort(key=lambda e: e.sort_key(), reverse=True)

        total = len(results)
        page = results[offset:offset + limit]

        return {
            "total": total,
            "returned": len(page),
            "offset": offset,
            "limit": limit,
            "entries": [e.to_dict() for e in page],
        }

    def _get_candidates(
        self,
        category: str | None,
        actor_id: str | None,
        entity_type: str | None,
        entity_id: str | None,
    ) -> list[ActivityEntry]:
        """Use indexes to narrow candidate set. Falls back to full scan."""
        # Collect index hits
        index_sets: list[set[int]] = []

        if category:
            if category not in VALID_CATEGORIES:
                raise ValueError(
                    f"Invalid category '{category}'. Must be one of: {', '.join(VALID_CATEGORIES)}"
                )
            index_sets.append(set(self._idx_category.get(category, [])))

        if actor_id:
            index_sets.append(set(self._idx_actor.get(actor_id, [])))

        if entity_id and entity_type:
            entity_key = f"{entity_type}:{entity_id}"
            index_sets.append(set(self._idx_entity.get(entity_key, [])))
        elif entity_type:
            # No entity_id filter — collect all entries with this entity_type
            matching = set()
            for key, indices in self._idx_entity.items():
                if key.startswith(f"{entity_type}:"):
                    matching.update(indices)
            if matching:
                index_sets.append(matching)

        if index_sets:
            # Intersect all index hits
            result_indices = index_sets[0]
            for s in index_sets[1:]:
                result_indices &= s
            return [self._entries[i] for i in result_indices if i < len(self._entries)]

        # No index filters — return all
        return list(self._entries)

    # ── Stats ───────────────────────────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        """Activity stats: counts by category, actor, and hourly for last 24h."""
        by_category: dict[str, int] = {}
        by_actor: dict[str, int] = {}
        by_hour: dict[str, int] = {}

        now = datetime.now(timezone.utc)

        for entry in self._entries:
            # By category
            by_category[entry.category] = by_category.get(entry.category, 0) + 1

            # By actor
            by_actor[entry.actor_id] = by_actor.get(entry.actor_id, 0) + 1

            # By hour (last 24h)
            try:
                ts = datetime.fromisoformat(entry.timestamp.replace("Z", "+00:00"))
                delta = (now - ts).total_seconds()
                if delta <= 86400:
                    hour_key = ts.strftime("%Y-%m-%d %H:00")
                    by_hour[hour_key] = by_hour.get(hour_key, 0) + 1
            except (ValueError, TypeError):
                pass

        return {
            "total": len(self._entries),
            "by_category": dict(sorted(by_category.items(), key=lambda x: x[1], reverse=True)),
            "by_actor": dict(sorted(by_actor.items(), key=lambda x: x[1], reverse=True)),
            "last_24h_by_hour": dict(sorted(by_hour.items())),
            "retention": {
                "max_memory": MAX_MEMORY_ENTRIES,
                "rollover_threshold": ROLLOVER_THRESHOLD,
            },
        }

    def get_categories(self) -> list[dict[str, str]]:
        """Return valid categories with descriptions."""
        return [
            {"category": k, "description": v}
            for k, v in VALID_CATEGORIES.items()
        ]
'''

# ═══════════════════════════════════════════════════════════════════
# FILE 2: activity.py (router)
# ═══════════════════════════════════════════════════════════════════

ROUTER_PATH = BACKEND / "app" / "api" / "routers" / "activity.py"

ROUTER_CODE = r'''"""
NemoClaw Execution Engine — Activity Router (P-2)

Unified activity timeline endpoints: query, stats, categories.
POST to append, GET to query with multi-axis filtering.

NEW FILE: command-center/backend/app/api/routers/activity.py
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app.auth import require_auth

logger = logging.getLogger("cc.activity.api")

router = APIRouter(prefix="/api/activity", tags=["activity"])


# ── Request Models ──────────────────────────────────────────────────

class ActivityAppend(BaseModel):
    category: str
    action: str
    actor_type: str = "system"
    actor_id: str = "system"
    entity_type: str = ""
    entity_id: str = ""
    summary: str = ""
    details: Optional[dict[str, Any]] = None
    trace_id: str = ""


# ── Service dependency ──────────────────────────────────────────────

def _svc(request: Request):
    svc = getattr(request.app.state, "activity_log_service", None)
    if not svc:
        raise HTTPException(status_code=503, detail="ActivityLogService not initialized")
    return svc


# ── Endpoints ───────────────────────────────────────────────────────

@router.get("/categories")
async def get_categories(
    _=Depends(require_auth),
    svc=Depends(_svc),
):
    """List valid activity categories with descriptions."""
    categories = svc.get_categories()
    return {"total": len(categories), "categories": categories}


@router.get("/stats")
async def get_stats(
    _=Depends(require_auth),
    svc=Depends(_svc),
):
    """Activity stats: counts by category, actor, and hourly for last 24h."""
    return svc.get_stats()


@router.get("/")
async def query_activity(
    after: Optional[str] = Query(None, description="ISO 8601 timestamp — return entries after this"),
    before: Optional[str] = Query(None, description="ISO 8601 timestamp — return entries before this"),
    category: Optional[str] = Query(None, description="execution, protocol, bridge, lifecycle, system, memory"),
    actor: Optional[str] = Query(None, description="Filter by actor_id (agent_id, system, etc.)"),
    entity_type: Optional[str] = Query(None, description="skill, project, deal, bridge, task, chain, client"),
    entity_id: Optional[str] = Query(None, description="Filter by entity ID"),
    action: Optional[str] = Query(None, description="Filter by action string"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    _=Depends(require_auth),
    svc=Depends(_svc),
):
    """Query the activity timeline with filters and pagination. Newest-first."""
    try:
        return svc.query(
            after=after,
            before=before,
            category=category,
            actor_id=actor,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            limit=limit,
            offset=offset,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/", status_code=201)
async def append_activity(
    body: ActivityAppend,
    _=Depends(require_auth),
    svc=Depends(_svc),
):
    """Append an activity entry to the timeline."""
    try:
        entry = await svc.append(
            category=body.category,
            action=body.action,
            actor_type=body.actor_type,
            actor_id=body.actor_id,
            entity_type=body.entity_type,
            entity_id=body.entity_id,
            summary=body.summary,
            details=body.details,
            trace_id=body.trace_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Disk write failed: {e}")

    return entry
'''

# ═══════════════════════════════════════════════════════════════════
# FILE 3: Patch main.py
# ═══════════════════════════════════════════════════════════════════

MAIN_PATH = BACKEND / "app" / "main.py"

# Patch 1: import
MAIN_IMPORT_OLD = "from app.api.routers import skill_wiring as skill_wiring_router"
MAIN_IMPORT_NEW = """from app.api.routers import skill_wiring as skill_wiring_router

# ── P-2: Activity Event Log ──
from app.api.routers import activity as activity_router"""

# Patch 2: init in lifespan
MAIN_INIT_OLD = '    logger.info("P-1: ProjectMemoryService initialized")\n\n    # ── CC-8: Client service ──'
MAIN_INIT_NEW = '''    logger.info("P-1: ProjectMemoryService initialized")

    # ── P-2: Activity Event Log ──
    from app.services.activity_log_service import ActivityLogService
    app.state.activity_log_service = ActivityLogService()
    logger.info("P-2: ActivityLogService initialized")

    # ── CC-8: Client service ──'''

# Patch 3: router registration
MAIN_ROUTER_OLD = "app.include_router(infra_router.router)  # Infra: Queue + Rate Limits"
MAIN_ROUTER_NEW = """app.include_router(infra_router.router)  # Infra: Queue + Rate Limits
app.include_router(activity_router.router)  # P-2: Activity Event Log"""


# ═══════════════════════════════════════════════════════════════════
# DEPLOY
# ═══════════════════════════════════════════════════════════════════

def deploy():
    errors = []

    # 1. Write service
    print("1/3 Writing activity_log_service.py...")
    SERVICE_PATH.write_text(SERVICE_CODE.strip() + "\n")
    try:
        compile(SERVICE_PATH.read_text(), str(SERVICE_PATH), "exec")
        print("  ✅ Compiles")
    except SyntaxError as e:
        errors.append(f"Service syntax error: {e}")
        print(f"  ❌ {e}")

    # 2. Write router
    print("2/3 Writing activity.py router...")
    ROUTER_PATH.write_text(ROUTER_CODE.strip() + "\n")
    try:
        compile(ROUTER_PATH.read_text(), str(ROUTER_PATH), "exec")
        print("  ✅ Compiles")
    except SyntaxError as e:
        errors.append(f"Router syntax error: {e}")
        print(f"  ❌ {e}")

    # 3. Patch main.py
    print("3/3 Patching main.py (import + init + router)...")
    content = MAIN_PATH.read_text()
    patched = 0

    if "activity_router" not in content:
        if MAIN_IMPORT_OLD in content:
            content = content.replace(MAIN_IMPORT_OLD, MAIN_IMPORT_NEW)
            patched += 1
        else:
            errors.append("Import patch target not found")
            print("  ❌ Import target missing")
    else:
        print("  ⚠️ Import already present")
        patched += 1

    if "ActivityLogService" not in content:
        if MAIN_INIT_OLD in content:
            content = content.replace(MAIN_INIT_OLD, MAIN_INIT_NEW)
            patched += 1
        else:
            errors.append("Init patch target not found")
            print("  ❌ Init target missing")
    else:
        print("  ⚠️ Init already present")
        patched += 1

    if "activity_router.router" not in content:
        if MAIN_ROUTER_OLD in content:
            content = content.replace(MAIN_ROUTER_OLD, MAIN_ROUTER_NEW)
            patched += 1
        else:
            errors.append("Router registration target not found")
            print("  ❌ Router registration target missing")
    else:
        print("  ⚠️ Router already registered")
        patched += 1

    MAIN_PATH.write_text(content)
    try:
        compile(MAIN_PATH.read_text(), str(MAIN_PATH), "exec")
        print(f"  ✅ Compiles ({patched}/3 patches applied)")
    except SyntaxError as e:
        errors.append(f"main.py syntax error: {e}")
        print(f"  ❌ {e}")

    # Summary
    print()
    if errors:
        print(f"⛔ {len(errors)} ERRORS:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("✅ P-2 deployed successfully")
        print()
        print("Next: restart backend, then validate:")
        print()
        print("  TOKEN=$(cat ~/.nemoclaw/cc-token)")
        print()
        print("  # Append activities")
        print('  curl -s -X POST -H "Authorization: Bearer $TOKEN" \\')
        print('    -H "Content-Type: application/json" \\')
        print("    -d '{\"category\":\"execution\",\"action\":\"skill_executed\",\"actor_type\":\"agent\",\"actor_id\":\"sales_outreach_lead\",\"entity_type\":\"skill\",\"entity_id\":\"i35-tone-calibrator\",\"summary\":\"Executed tone calibrator\",\"details\":{\"cost\":0.068}}' \\")
        print("    http://127.0.0.1:8100/api/activity | python3 -m json.tool")
        print()
        print('  curl -s -X POST -H "Authorization: Bearer $TOKEN" \\')
        print('    -H "Content-Type: application/json" \\')
        print("    -d '{\"category\":\"bridge\",\"action\":\"email_sent\",\"actor_type\":\"agent\",\"actor_id\":\"marketing_campaigns_lead\",\"entity_type\":\"bridge\",\"entity_id\":\"resend\",\"summary\":\"Sent campaign email\"}' \\")
        print("    http://127.0.0.1:8100/api/activity | python3 -m json.tool")
        print()
        print("  # Query all")
        print('  curl -s -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8100/api/activity | python3 -m json.tool')
        print()
        print("  # Query filtered")
        print('  curl -s -H "Authorization: Bearer $TOKEN" "http://127.0.0.1:8100/api/activity?category=execution" | python3 -m json.tool')
        print()
        print("  # Stats")
        print('  curl -s -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8100/api/activity/stats | python3 -m json.tool')
        print()
        print("  # Categories")
        print('  curl -s -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8100/api/activity/categories | python3 -m json.tool')
        print()
        print("  # Error: invalid category")
        print('  curl -s -H "Authorization: Bearer $TOKEN" "http://127.0.0.1:8100/api/activity?category=bogus" | python3 -m json.tool')
        print()
        print("  # Regression")
        print("  bash scripts/full_regression.sh")
        print()
        print("  # Commit")
        print('  git add -A && git status')
        print('  git commit -m "feat(engine): P-2 activity event log — unified timeline, indexes, rollover, multi-axis filtering"')
        print('  git push origin main')


if __name__ == "__main__":
    deploy()

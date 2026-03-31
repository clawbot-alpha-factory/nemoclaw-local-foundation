#!/usr/bin/env python3
"""
NemoClaw P-1 Deployment: Board/Project Scoped Memory

Writes: project_memory_service.py
Patches: projects.py (router), main.py (lifespan init)

Run from repo root:
    cd ~/nemoclaw-local-foundation
    python3 scripts/deploy-p1.py
"""

from pathlib import Path
import sys

BACKEND = Path.home() / "nemoclaw-local-foundation" / "command-center" / "backend"

# ── File 1: project_memory_service.py ───────────────────────────────

SERVICE_PATH = BACKEND / "app" / "services" / "project_memory_service.py"

SERVICE_CODE = r'''"""
NemoClaw Execution Engine — ProjectMemoryService (P-1)

Per-project shared memory: agents write to their namespace, all agents
on the project can read everything. Entries typed as 'operational' or
'chat' for filtered retrieval.

Concurrency-safe via per-project asyncio.Lock.
Retention: MAX_ENTRIES per project + MAX_AGE_DAYS TTL, pruned lazily on write.

Future upgrade: swap JSON persistence to SQLite or Redis for high
concurrency / multi-node environments.

NEW FILE: command-center/backend/app/services/project_memory_service.py
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

logger = logging.getLogger("cc.project_memory")

# ── Retention Policy (configurable) ─────────────────────────────────
MAX_ENTRIES = 500        # per project
MAX_AGE_DAYS = 90        # entries older than this are pruned
MAX_KEY_LENGTH = 200     # max user-provided key length

VALID_MEMORY_TYPES = {"operational", "chat"}


class ProjectMemoryEntry:
    """A single memory entry scoped to a project."""

    def __init__(
        self,
        project_id: str,
        agent_id: str,
        key: str,
        value: str,
        memory_type: str = "operational",
        importance: float = 1.0,
        source: str = "",
        entry_id: str = "",
        timestamp: float | None = None,
    ):
        self.id = entry_id or uuid4().hex[:8]
        self.project_id = project_id
        self.agent_id = agent_id
        self.key = key  # already namespaced: {agent_id}.{user_key}
        self.value = value
        self.memory_type = memory_type
        self.importance = max(0.0, min(1.0, importance))
        self.source = source
        self.timestamp = timestamp or time.time()
        self.access_count = 0

    def weighted_score(self) -> float:
        """Time-weighted importance score.

        Formula: score = importance × (1 / (1 + age_hours / 24))
        Recent entries score higher. Importance amplifies the signal.
        Decay halves roughly every 24 hours of age.
        """
        age_hours = (time.time() - self.timestamp) / 3600
        decay_factor = 1.0 / (1.0 + age_hours / 24.0)
        return self.importance * decay_factor

    def age_days(self) -> float:
        return (time.time() - self.timestamp) / 86400

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "agent_id": self.agent_id,
            "key": self.key,
            "value": self.value,
            "memory_type": self.memory_type,
            "importance": self.importance,
            "source": self.source,
            "timestamp": self.timestamp,
            "access_count": self.access_count,
            "age_hours": round((time.time() - self.timestamp) / 3600, 1),
            "weighted_score": round(self.weighted_score(), 4),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ProjectMemoryEntry:
        entry = cls(
            project_id=d["project_id"],
            agent_id=d["agent_id"],
            key=d["key"],
            value=d["value"],
            memory_type=d.get("memory_type", "operational"),
            importance=d.get("importance", 1.0),
            source=d.get("source", ""),
            entry_id=d.get("id", ""),
            timestamp=d.get("timestamp"),
        )
        entry.access_count = d.get("access_count", 0)
        return entry


class ProjectMemoryService:
    """
    Per-project shared memory with namespaced writes and universal reads.

    - Write: auto-namespaces key as {agent_id}.{key}
    - Read: any assigned agent reads all entries
    - Filter: by memory_type (operational/chat), by agent, by key prefix
    - Retention: MAX_ENTRIES cap + MAX_AGE_DAYS TTL, pruned on write
    - Concurrency: asyncio.Lock per project_id
    """

    def __init__(self, persist_dir: Path | None = None):
        self._dir = persist_dir or (Path.home() / ".nemoclaw" / "project-memory")
        self._dir.mkdir(parents=True, exist_ok=True)
        self._stores: dict[str, dict[str, ProjectMemoryEntry]] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._load_all()
        logger.info(
            "ProjectMemoryService initialized (%d projects, dir=%s)",
            len(self._stores), self._dir,
        )

    # ── Lock management ─────────────────────────────────────────────

    def _get_lock(self, project_id: str) -> asyncio.Lock:
        """Get or create a per-project lock."""
        if project_id not in self._locks:
            self._locks[project_id] = asyncio.Lock()
        return self._locks[project_id]

    # ── Persistence ─────────────────────────────────────────────────

    def _project_file(self, project_id: str) -> Path:
        return self._dir / f"{project_id}.json"

    def _load_all(self) -> None:
        """Load all project memories from disk on startup."""
        for path in self._dir.glob("*.json"):
            project_id = path.stem
            try:
                data = json.loads(path.read_text())
                self._stores[project_id] = {
                    k: ProjectMemoryEntry.from_dict(v)
                    for k, v in data.items()
                }
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning("Failed to load project memory %s: %s", project_id, e)
                self._stores[project_id] = {}

    def _save(self, project_id: str) -> None:
        """Persist project memory to disk. Called inside lock."""
        store = self._stores.get(project_id, {})
        data = {k: v.to_dict() for k, v in store.items()}
        try:
            self._project_file(project_id).write_text(
                json.dumps(data, indent=2, default=str)
            )
        except OSError as e:
            logger.error("Failed to save project memory %s: %s", project_id, e)
            raise

    # ── Key validation ──────────────────────────────────────────────

    @staticmethod
    def _validate_key(user_key: str) -> None:
        """Validate user-provided key before namespacing."""
        if not user_key or not user_key.strip():
            raise ValueError("Key cannot be empty")
        if len(user_key) > MAX_KEY_LENGTH:
            raise ValueError(f"Key exceeds {MAX_KEY_LENGTH} characters")
        if "." in user_key:
            raise ValueError(
                "Key must not contain dots — namespace is auto-applied from agent_id"
            )

    @staticmethod
    def _namespace_key(agent_id: str, user_key: str) -> str:
        """Auto-prefix key: {agent_id}.{user_key}"""
        return f"{agent_id}.{user_key}"

    # ── Retention / Pruning ─────────────────────────────────────────

    def _prune(self, project_id: str) -> int:
        """Remove expired entries and enforce max count. Returns pruned count."""
        store = self._stores.get(project_id, {})
        if not store:
            return 0

        now = time.time()
        max_age_seconds = MAX_AGE_DAYS * 86400
        pruned = 0

        # Age-based prune
        expired_keys = [
            k for k, v in store.items()
            if (now - v.timestamp) > max_age_seconds
        ]
        for k in expired_keys:
            del store[k]
            pruned += 1

        # Count-based prune: keep top MAX_ENTRIES by weighted_score
        if len(store) > MAX_ENTRIES:
            sorted_entries = sorted(
                store.items(),
                key=lambda kv: kv[1].weighted_score(),
                reverse=True,
            )
            keep = {k for k, _ in sorted_entries[:MAX_ENTRIES]}
            drop = [k for k in store if k not in keep]
            for k in drop:
                del store[k]
                pruned += 1

        if pruned:
            logger.debug("Pruned %d entries from project %s", pruned, project_id[:8])

        return pruned

    # ── Write ───────────────────────────────────────────────────────

    async def write(
        self,
        project_id: str,
        agent_id: str,
        key: str,
        value: str,
        memory_type: str = "operational",
        importance: float = 1.0,
        source: str = "",
    ) -> dict[str, Any]:
        """Write a memory entry to a project.

        Key is auto-namespaced as {agent_id}.{key}.
        Prunes expired/excess entries on every write.

        Raises:
            ValueError: If key is invalid or memory_type is not recognized.
        """
        # Validate inputs
        self._validate_key(key)
        if memory_type not in VALID_MEMORY_TYPES:
            raise ValueError(
                f"Invalid memory_type '{memory_type}'. Must be one of: {', '.join(VALID_MEMORY_TYPES)}"
            )
        if not agent_id or not agent_id.strip():
            raise ValueError("agent_id is required")

        namespaced_key = self._namespace_key(agent_id, key)

        async with self._get_lock(project_id):
            if project_id not in self._stores:
                self._stores[project_id] = {}

            entry = ProjectMemoryEntry(
                project_id=project_id,
                agent_id=agent_id,
                key=namespaced_key,
                value=value,
                memory_type=memory_type,
                importance=importance,
                source=source,
            )

            self._stores[project_id][namespaced_key] = entry
            self._prune(project_id)
            self._save(project_id)

        logger.debug(
            "Project %s: %s wrote %s (%s)",
            project_id[:8], agent_id, namespaced_key, memory_type,
        )
        return entry.to_dict()

    # ── Read ────────────────────────────────────────────────────────

    def read(
        self,
        project_id: str,
        memory_type: str | None = None,
        agent_id: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Read project memories with optional filters.

        All agents on a project can read all entries (universal reads).
        """
        store = self._stores.get(project_id, {})
        entries = list(store.values())

        if memory_type:
            if memory_type not in VALID_MEMORY_TYPES:
                raise ValueError(
                    f"Invalid memory_type '{memory_type}'. Must be one of: {', '.join(VALID_MEMORY_TYPES)}"
                )
            entries = [e for e in entries if e.memory_type == memory_type]

        if agent_id:
            entries = [e for e in entries if e.agent_id == agent_id]

        # Sort by weighted score descending
        entries.sort(key=lambda e: e.weighted_score(), reverse=True)

        # Track access
        for e in entries[:limit]:
            e.access_count += 1

        return [e.to_dict() for e in entries[:limit]]

    def top(
        self,
        project_id: str,
        limit: int = 10,
        memory_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get top memories by time-weighted score.

        Score formula: importance × (1 / (1 + age_hours / 24))
        """
        return self.read(project_id, memory_type=memory_type, limit=limit)

    # ── Forget ──────────────────────────────────────────────────────

    async def forget(self, project_id: str, entry_id: str) -> bool:
        """Remove a specific memory entry by ID."""
        async with self._get_lock(project_id):
            store = self._stores.get(project_id, {})
            target_key = None
            for k, v in store.items():
                if v.id == entry_id:
                    target_key = k
                    break

            if target_key:
                del store[target_key]
                self._save(project_id)
                logger.debug("Forgot entry %s from project %s", entry_id, project_id[:8])
                return True
        return False

    # ── Stats ───────────────────────────────────────────────────────

    def get_stats(self, project_id: str) -> dict[str, Any]:
        """Get memory stats for a project."""
        store = self._stores.get(project_id, {})
        entries = list(store.values())

        if not entries:
            return {
                "project_id": project_id,
                "total": 0,
                "by_type": {"operational": 0, "chat": 0},
                "by_agent": {},
                "oldest_hours": 0,
                "newest_hours": 0,
            }

        by_type: dict[str, int] = {"operational": 0, "chat": 0}
        by_agent: dict[str, int] = {}
        for e in entries:
            by_type[e.memory_type] = by_type.get(e.memory_type, 0) + 1
            by_agent[e.agent_id] = by_agent.get(e.agent_id, 0) + 1

        now = time.time()
        ages = [(now - e.timestamp) / 3600 for e in entries]

        return {
            "project_id": project_id,
            "total": len(entries),
            "by_type": by_type,
            "by_agent": by_agent,
            "oldest_hours": round(max(ages), 1),
            "newest_hours": round(min(ages), 1),
            "retention": {
                "max_entries": MAX_ENTRIES,
                "max_age_days": MAX_AGE_DAYS,
            },
        }

    def get_projects_with_memory(self) -> list[str]:
        """List project IDs that have stored memories."""
        return [pid for pid, store in self._stores.items() if store]
'''

# ── File 2: Patch projects.py router ────────────────────────────────

ROUTER_PATH = BACKEND / "app" / "api" / "routers" / "projects.py"

ROUTER_PATCH_OLD = '''class MilestoneCreate(BaseModel):
    title: str
    description: Optional[str] = None
    due_date: Optional[str] = None
    status: Optional[str] = "pending"


# --- Service dependency ---'''

ROUTER_PATCH_NEW = '''class MilestoneCreate(BaseModel):
    title: str
    description: Optional[str] = None
    due_date: Optional[str] = None
    status: Optional[str] = "pending"


class MemoryWrite(BaseModel):
    agent_id: str
    key: str
    value: str
    memory_type: Optional[str] = "operational"
    importance: Optional[float] = Field(default=1.0, ge=0.0, le=1.0)
    source: Optional[str] = ""


# --- Service dependency ---'''

ROUTER_APPEND_OLD = '''    if not milestone:
        raise HTTPException(status_code=500, detail="Failed to add milestone")
    return milestone'''

ROUTER_APPEND_NEW = '''    if not milestone:
        raise HTTPException(status_code=500, detail="Failed to add milestone")
    return milestone


# --- Memory endpoints (P-1) ---

def _mem_svc(request: Request):
    """Get ProjectMemoryService from app state."""
    svc = getattr(request.app.state, "project_memory_service", None)
    if not svc:
        raise HTTPException(status_code=503, detail="ProjectMemoryService not initialized")
    return svc


@router.get("/{project_id}/memory")
async def read_project_memory(
    project_id: str,
    type: Optional[str] = Query(None, description="operational or chat"),
    agent: Optional[str] = Query(None, description="Filter by agent_id"),
    limit: int = Query(50, ge=1, le=500),
    _=Depends(require_auth),
    svc=Depends(_svc),
    mem=Depends(_mem_svc),
):
    """Read project-scoped memory entries with optional filters."""
    existing = svc.get_project(project_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")

    try:
        entries = mem.read(project_id, memory_type=type, agent_id=agent, limit=limit)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    stats = mem.get_stats(project_id)
    return {
        "project_id": project_id,
        "total": stats["total"],
        "returned": len(entries),
        "entries": entries,
    }


@router.post("/{project_id}/memory", status_code=201)
async def write_project_memory(
    project_id: str,
    body: MemoryWrite,
    _=Depends(require_auth),
    svc=Depends(_svc),
    mem=Depends(_mem_svc),
):
    """Write a memory entry to a project. Key is auto-namespaced as {agent_id}.{key}."""
    existing = svc.get_project(project_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")

    try:
        entry = await mem.write(
            project_id=project_id,
            agent_id=body.agent_id,
            key=body.key,
            value=body.value,
            memory_type=body.memory_type or "operational",
            importance=body.importance if body.importance is not None else 1.0,
            source=body.source or "",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Disk write failed: {e}")

    return entry'''

# ── File 3: Patch main.py ──────────────────────────────────────────

MAIN_PATH = BACKEND / "app" / "main.py"

MAIN_PATCH_OLD = '''    from app.services.project_service import ProjectService
    app.state.project_service = ProjectService(Path(__file__).resolve().parents[3])
    logger.info("CC-7: ProjectService initialized")'''

MAIN_PATCH_NEW = '''    from app.services.project_service import ProjectService
    app.state.project_service = ProjectService(Path(__file__).resolve().parents[3])
    logger.info("CC-7: ProjectService initialized")

    # ── P-1: Project Scoped Memory ──
    from app.services.project_memory_service import ProjectMemoryService
    app.state.project_memory_service = ProjectMemoryService()
    logger.info("P-1: ProjectMemoryService initialized")'''


# ── Deploy ──────────────────────────────────────────────────────────

def deploy():
    errors = []

    # 1. Write service
    print("1/3 Writing project_memory_service.py...")
    SERVICE_PATH.write_text(SERVICE_CODE.strip() + "\n")
    try:
        compile(SERVICE_PATH.read_text(), str(SERVICE_PATH), "exec")
        print("  ✅ Compiles")
    except SyntaxError as e:
        errors.append(f"Service syntax error: {e}")
        print(f"  ❌ {e}")

    # 2. Patch router
    print("2/3 Patching projects.py router...")
    router_content = ROUTER_PATH.read_text()

    if ROUTER_PATCH_OLD not in router_content:
        # Check if already patched
        if "MemoryWrite" in router_content:
            print("  ⚠️ Already patched (MemoryWrite exists)")
        else:
            errors.append("Router patch target not found (MilestoneCreate block)")
            print("  ❌ Patch target not found")
    else:
        router_content = router_content.replace(ROUTER_PATCH_OLD, ROUTER_PATCH_NEW)

    if ROUTER_APPEND_OLD not in router_content:
        if "_mem_svc" in router_content:
            print("  ⚠️ Already patched (memory endpoints exist)")
        else:
            errors.append("Router append target not found")
            print("  ❌ Append target not found")
    else:
        router_content = router_content.replace(ROUTER_APPEND_OLD, ROUTER_APPEND_NEW)

    ROUTER_PATH.write_text(router_content)
    try:
        compile(ROUTER_PATH.read_text(), str(ROUTER_PATH), "exec")
        print("  ✅ Compiles")
    except SyntaxError as e:
        errors.append(f"Router syntax error: {e}")
        print(f"  ❌ {e}")

    # 3. Patch main.py
    print("3/3 Patching main.py...")
    main_content = MAIN_PATH.read_text()

    if MAIN_PATCH_OLD not in main_content:
        if "ProjectMemoryService" in main_content:
            print("  ⚠️ Already patched")
        else:
            errors.append("main.py patch target not found")
            print("  ❌ Patch target not found")
    else:
        main_content = main_content.replace(MAIN_PATCH_OLD, MAIN_PATCH_NEW)

    MAIN_PATH.write_text(main_content)
    try:
        compile(MAIN_PATH.read_text(), str(MAIN_PATH), "exec")
        print("  ✅ Compiles")
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
        print("✅ P-1 deployed successfully")
        print()
        print("Next steps:")
        print("  1. Restart backend (Ctrl+C → python3 run.py --reload)")
        print("  2. Run validation:")
        print('     TOKEN=$(cat ~/.nemoclaw/cc-token)')
        print()
        print("     # Create a test project first")
        print('     PROJECT_ID=$(curl -s -X POST -H "Authorization: Bearer $TOKEN" \\')
        print('       -H "Content-Type: application/json" \\')
        print('       -d \'{"name":"P1 Test Project"}\' \\')
        print('       http://127.0.0.1:8100/api/projects/ | python3 -c "import json,sys; print(json.load(sys.stdin)[\'id\'])")')
        print('     echo "Project: $PROJECT_ID"')
        print()
        print("     # Write memory")
        print('     curl -s -X POST -H "Authorization: Bearer $TOKEN" \\')
        print('       -H "Content-Type: application/json" \\')
        print('       -d \'{"agent_id":"sales_outreach_lead","key":"lead_quality","value":"Enterprise leads convert 3x better","memory_type":"operational","importance":0.9}\' \\')
        print('       http://127.0.0.1:8100/api/projects/$PROJECT_ID/memory | python3 -m json.tool')
        print()
        print("     # Read memory")
        print('     curl -s -H "Authorization: Bearer $TOKEN" \\')
        print('       "http://127.0.0.1:8100/api/projects/$PROJECT_ID/memory?type=operational" | python3 -m json.tool')
        print()
        print("  3. Run regression: bash scripts/full_regression.sh")
        print()
        print("  4. If all pass:")
        print('     git add -A && git status')
        print('     git commit -m "feat(engine): P-1 board/project scoped memory — per-project shared memory, namespace isolation, retention policy, concurrency locks"')
        print('     git push origin main')


if __name__ == "__main__":
    deploy()

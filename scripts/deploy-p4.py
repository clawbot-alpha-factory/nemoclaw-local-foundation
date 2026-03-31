#!/usr/bin/env python3
"""
NemoClaw P-4 Deployment: Task Dependencies + Blocked State

Patches: ops_service.py (depends_on, auto-unblock, cycle detection, reverse index)
Patches: ops.py (3 new endpoints)
Patches: priority_engine.py (skip blocked tasks)

Run from repo root:
    cd ~/nemoclaw-local-foundation
    python3 scripts/deploy-p4.py
"""

from pathlib import Path
import sys

BACKEND = Path.home() / "nemoclaw-local-foundation" / "command-center" / "backend"


def patch_file(path: Path, patches: list[tuple[str, str]], label: str) -> bool:
    """Apply a list of (old, new) string replacements to a file."""
    content = path.read_text()
    applied = 0
    for old, new in patches:
        if old in content:
            content = content.replace(old, new, 1)
            applied += 1
        elif new.split("\n")[0].strip() in content:
            print(f"  ⚠️ Patch {applied+1} already applied")
            applied += 1
        else:
            print(f"  ❌ Patch {applied+1} target not found in {label}")
            return False
    path.write_text(content)
    try:
        compile(path.read_text(), str(path), "exec")
        print(f"  ✅ {label} compiles ({applied} patches)")
        return True
    except SyntaxError as e:
        print(f"  ❌ {label} syntax error: {e}")
        return False


def deploy():
    errors = []

    # ═══════════════════════════════════════════════════════════════
    # 1. PATCH ops_service.py
    # ═══════════════════════════════════════════════════════════════
    print("1/3 Patching ops_service.py...")

    ops_path = BACKEND / "app" / "services" / "ops_service.py"
    ops = ops_path.read_text()

    # -- Patch 1a: Add threading import --
    ops = ops.replace(
        "import json\nimport logging\nfrom datetime import datetime, timezone\nfrom pathlib import Path\nfrom typing import Any, Optional\nfrom uuid import uuid4",
        "import json\nimport logging\nimport threading\nfrom datetime import datetime, timezone\nfrom pathlib import Path\nfrom typing import Any, Optional\nfrom uuid import uuid4",
    )

    # -- Patch 1b: Add blocked_failed to valid statuses --
    ops = ops.replace(
        'VALID_STATUSES = {"pending", "in_progress", "blocked", "completed", "cancelled"}',
        'VALID_STATUSES = {"pending", "in_progress", "blocked", "blocked_failed", "completed", "cancelled"}',
    )
    ops = ops.replace(
        'TERMINAL_STATUSES = {"completed", "cancelled"}',
        'TERMINAL_STATUSES = {"completed", "cancelled"}\nFAILED_STATUSES = {"cancelled"}  # deps in these states trigger blocked_failed\nMAX_CYCLE_DEPTH = 50',
    )

    # -- Patch 1c: Add lock + reverse index to __init__ --
    ops = ops.replace(
        "        self._load_tasks()\n        log.info(",
        "        self._dep_lock = threading.Lock()\n"
        "        self._dependents_of: dict[str, set[str]] = {}  # task_id → set of dependent task_ids\n"
        "        self._load_tasks()\n"
        "        self._rebuild_dependency_index()\n"
        "        log.info(",
    )

    # -- Patch 1d: Add dependency methods after _record_activity --
    dep_methods = '''
    # ── Dependency Management (P-4) ─────────────────────────────────────

    def _rebuild_dependency_index(self) -> None:
        """Build reverse index: task_id → set of tasks that depend on it."""
        self._dependents_of = {}
        for task in self.tasks.values():
            for dep_id in task.get("depends_on", []):
                self._dependents_of.setdefault(dep_id, set()).add(task["id"])

    def _detect_cycle(self, task_id: str, depends_on: list[str]) -> str | None:
        """DFS cycle detection. Returns cycle description or None."""
        visited: set[str] = set()

        def dfs(current: str, depth: int) -> bool:
            if depth > MAX_CYCLE_DEPTH:
                return True
            if current == task_id:
                return True
            if current in visited:
                return False
            visited.add(current)
            task = self.tasks.get(current)
            if not task:
                return False
            for dep in task.get("depends_on", []):
                if dfs(dep, depth + 1):
                    return True
            return False

        for dep_id in depends_on:
            visited.clear()
            if dfs(dep_id, 0):
                return f"Circular dependency detected: {task_id} → {dep_id} → ... → {task_id}"
        return None

    def _compute_blocked_fields(self, task: dict[str, Any]) -> None:
        """Compute blocked_by, blocked, depends_total, depends_completed."""
        deps = task.get("depends_on", [])
        if not deps:
            task["blocked_by"] = []
            task["blocked"] = False
            task["depends_total"] = 0
            task["depends_completed"] = 0
            return

        blocked_by = []
        completed_count = 0
        for dep_id in deps:
            dep_task = self.tasks.get(dep_id)
            if not dep_task:
                continue
            if dep_task.get("status") == "completed":
                completed_count += 1
            else:
                blocked_by.append(dep_id)

        task["blocked_by"] = blocked_by
        task["blocked"] = len(blocked_by) > 0
        task["depends_total"] = len(deps)
        task["depends_completed"] = completed_count

    def _auto_unblock_dependents(self, completed_task_id: str) -> list[str]:
        """After a task completes, auto-unblock its dependents. Returns unblocked task IDs."""
        unblocked: list[str] = []
        dependent_ids = self._dependents_of.get(completed_task_id, set())

        for dep_task_id in dependent_ids:
            dep_task = self.tasks.get(dep_task_id)
            if not dep_task or dep_task["status"] not in ("blocked", "blocked_failed"):
                continue

            self._compute_blocked_fields(dep_task)
            if not dep_task["blocked"]:
                now = datetime.now(timezone.utc).isoformat()
                old_status = dep_task["status"]
                dep_task["status"] = "pending"
                dep_task["updated_at"] = now
                dep_task["history"].append({
                    "timestamp": now,
                    "action": "auto_unblocked",
                    "from_status": old_status,
                    "to_status": "pending",
                    "trigger": completed_task_id,
                })
                unblocked.append(dep_task_id)
                log.info("Auto-unblocked task %s (dependency %s completed)", dep_task_id, completed_task_id)

        return unblocked

    def _propagate_failed_deps(self, failed_task_id: str) -> list[str]:
        """When a dep fails/cancels, mark dependents as blocked_failed."""
        affected: list[str] = []
        dependent_ids = self._dependents_of.get(failed_task_id, set())

        for dep_task_id in dependent_ids:
            dep_task = self.tasks.get(dep_task_id)
            if not dep_task or dep_task["status"] in TERMINAL_STATUSES:
                continue

            now = datetime.now(timezone.utc).isoformat()
            old_status = dep_task["status"]
            dep_task["status"] = "blocked_failed"
            dep_task["updated_at"] = now
            dep_task["history"].append({
                "timestamp": now,
                "action": "dependency_failed",
                "from_status": old_status,
                "to_status": "blocked_failed",
                "failed_dependency": failed_task_id,
            })
            affected.append(dep_task_id)
            log.info("Task %s marked blocked_failed (dependency %s failed)", dep_task_id, failed_task_id)

        return affected

    def force_unblock(self, task_id: str) -> dict[str, Any]:
        """Manually unblock a task, overriding dependency checks."""
        if task_id not in self.tasks:
            raise KeyError(f"Task {task_id} not found")

        task = self.tasks[task_id]
        if task["status"] not in ("blocked", "blocked_failed"):
            raise ValueError(f"Task {task_id} is not blocked (status: {task['status']})")

        now = datetime.now(timezone.utc).isoformat()
        old_status = task["status"]
        task["status"] = "pending"
        task["blocked_by"] = []
        task["blocked"] = False
        task["updated_at"] = now
        task["history"].append({
            "timestamp": now,
            "action": "force_unblocked",
            "from_status": old_status,
            "to_status": "pending",
        })
        self._record_activity("task_force_unblocked", task_id)
        self._save_tasks()
        log.info("Force-unblocked task %s", task_id)
        return task

    def get_dependency_graph(self, root_task_id: str | None = None, max_depth: int = 10) -> dict[str, Any]:
        """Get dependency graph, optionally rooted at a specific task."""
        graph: dict[str, Any] = {"nodes": [], "edges": []}
        visited: set[str] = set()

        def walk(task_id: str, depth: int) -> None:
            if task_id in visited or depth > max_depth:
                return
            visited.add(task_id)
            task = self.tasks.get(task_id)
            if not task:
                return
            self._compute_blocked_fields(task)
            graph["nodes"].append({
                "id": task_id,
                "title": task.get("title", ""),
                "status": task.get("status", ""),
                "blocked": task.get("blocked", False),
                "depends_total": task.get("depends_total", 0),
                "depends_completed": task.get("depends_completed", 0),
            })
            for dep_id in task.get("depends_on", []):
                graph["edges"].append({"from": dep_id, "to": task_id})
                walk(dep_id, depth + 1)
            # Also walk dependents
            for dep_task_id in self._dependents_of.get(task_id, set()):
                graph["edges"].append({"from": task_id, "to": dep_task_id})
                walk(dep_task_id, depth + 1)

        if root_task_id:
            walk(root_task_id, 0)
        else:
            # Walk all tasks that have dependencies
            for tid, task in self.tasks.items():
                if task.get("depends_on") or tid in self._dependents_of:
                    walk(tid, 0)

        # Deduplicate edges
        seen_edges: set[tuple[str, str]] = set()
        unique_edges = []
        for e in graph["edges"]:
            key = (e["from"], e["to"])
            if key not in seen_edges:
                seen_edges.add(key)
                unique_edges.append(e)
        graph["edges"] = unique_edges

        return graph

'''

    # Insert after _record_activity method
    ops = ops.replace(
        "    # ── Task Lifecycle ─────────────────────────────────────────────────────",
        dep_methods + "    # ── Task Lifecycle ─────────────────────────────────────────────────────",
    )

    # -- Patch 1e: Modify create_task to accept depends_on --
    ops = ops.replace(
        '''    def create_task(
        self,
        title: str,
        description: str = "",
        agent_id: Optional[str] = None,
        skill_id: Optional[str] = None,
        priority: str = "medium",
        tags: Optional[list[str]] = None,
    ) -> dict[str, Any]:''',
        '''    def create_task(
        self,
        title: str,
        description: str = "",
        agent_id: Optional[str] = None,
        skill_id: Optional[str] = None,
        priority: str = "medium",
        tags: Optional[list[str]] = None,
        depends_on: Optional[list[str]] = None,
    ) -> dict[str, Any]:''',
    )

    # Add dependency validation + initial blocked state in create_task body
    ops = ops.replace(
        '''        task_id = uuid4().hex[:8]
        now = datetime.now(timezone.utc).isoformat()
        task: dict[str, Any] = {
            "id": task_id,
            "title": title,
            "description": description,
            "status": "pending",''',
        '''        # Validate dependencies (P-4)
        deps = depends_on or []
        for dep_id in deps:
            if dep_id not in self.tasks:
                raise ValueError(f"Dependency task '{dep_id}' does not exist")

        task_id = uuid4().hex[:8]

        # Cycle detection
        if deps:
            cycle = self._detect_cycle(task_id, deps)
            if cycle:
                raise ValueError(cycle)

        # Determine initial status: blocked if any dep is incomplete
        initial_status = "pending"
        if deps:
            incomplete = [d for d in deps if self.tasks.get(d, {}).get("status") != "completed"]
            if incomplete:
                initial_status = "blocked"

        now = datetime.now(timezone.utc).isoformat()
        task: dict[str, Any] = {
            "id": task_id,
            "title": title,
            "description": description,
            "status": initial_status,''',
    )

    # Add depends_on field to task dict (after "tags" line)
    ops = ops.replace(
        '''            "tags": tags or [],
            "created_at": now,''',
        '''            "tags": tags or [],
            "depends_on": deps,
            "created_at": now,''',
    )

    # Add to_status in history and update reverse index after task creation
    ops = ops.replace(
        '''                    "to_status": "pending",
                }
            ],
        }
        self.tasks[task_id] = task
        self._record_activity("task_created", task_id, {"title": title, "agent_id": agent_id})
        self._save_tasks()
        log.info("Created task %s: %s", task_id, title)
        return task''',
        '''                    "to_status": initial_status,
                }
            ],
        }
        self.tasks[task_id] = task

        # Update reverse index (P-4)
        for dep_id in deps:
            self._dependents_of.setdefault(dep_id, set()).add(task_id)
        self._compute_blocked_fields(task)

        self._record_activity("task_created", task_id, {"title": title, "agent_id": agent_id, "depends_on": deps})
        self._save_tasks()
        log.info("Created task %s: %s (deps=%s, status=%s)", task_id, title, deps, initial_status)
        return task''',
    )

    # -- Patch 1f: Add auto-unblock trigger after status change in update_task --
    ops = ops.replace(
        '''                if status in TERMINAL_STATUSES:
                    task["completed_at"] = now''',
        '''                if status in TERMINAL_STATUSES:
                    task["completed_at"] = now
                # P-4: auto-unblock dependents on completion
                if status == "completed":
                    with self._dep_lock:
                        unblocked = self._auto_unblock_dependents(task_id)
                        if unblocked:
                            log.info("Auto-unblocked %d tasks after %s completed", len(unblocked), task_id)
                # P-4: propagate failure to dependents
                if status in FAILED_STATUSES:
                    with self._dep_lock:
                        affected = self._propagate_failed_deps(task_id)
                        if affected:
                            log.info("Marked %d tasks as blocked_failed after %s failed", len(affected), task_id)''',
    )

    # -- Patch 1g: Add computed fields to get_tasks results --
    ops = ops.replace(
        "            results.append(task)",
        "            self._compute_blocked_fields(task)\n            results.append(task)",
    )

    ops_path.write_text(ops)
    try:
        compile(ops_path.read_text(), str(ops_path), "exec")
        print("  ✅ ops_service.py compiles")
    except SyntaxError as e:
        errors.append(f"ops_service.py: {e}")
        print(f"  ❌ ops_service.py: {e}")

    # ═══════════════════════════════════════════════════════════════
    # 2. PATCH ops.py router
    # ═══════════════════════════════════════════════════════════════
    print("2/3 Patching ops.py router...")

    ops_router_path = BACKEND / "app" / "api" / "routers" / "ops.py"
    router = ops_router_path.read_text()

    # Fix pre-existing bug: PATCH handler passes dict but service expects kwargs
    router = router.replace(
        '''        task = svc.update_task(task_id=task_id, updates=updates)''',
        '''        # Remap router field names to service field names
        mapped = {}
        for k, v in updates.items():
            if k == "agent":
                mapped["agent_id"] = v
            elif k == "skill":
                mapped["skill_id"] = v
            else:
                mapped[k] = v
        task = svc.update_task(task_id=task_id, **mapped)''',
    )

    # Add depends_on to TaskCreate model
    router = router.replace(
        '''class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    agent: Optional[str] = None
    skill: Optional[str] = None
    priority: Optional[str] = "medium"
    status: Optional[str] = "pending"
    budget_limit: Optional[float] = None
    metadata: Optional[dict] = {}''',
        '''class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    agent: Optional[str] = None
    skill: Optional[str] = None
    priority: Optional[str] = "medium"
    status: Optional[str] = "pending"
    budget_limit: Optional[float] = None
    metadata: Optional[dict] = {}
    depends_on: Optional[List[str]] = None''',
    )

    # Update create_task call to pass depends_on
    router = router.replace(
        'task = svc.create_task(title=body.title, description=body.description, agent_id=body.assigned_agent if hasattr(body, "assigned_agent") else getattr(body, "agent", None), priority=getattr(body, "priority", "medium"))',
        'task = svc.create_task(title=body.title, description=body.description or "", agent_id=getattr(body, "agent", None), priority=getattr(body, "priority", "medium"), depends_on=body.depends_on)',
    )

    # Add new endpoints before budget endpoint
    new_endpoints = '''

# ── P-4: Task Dependency Endpoints ───────────────────────────────────────────

@router.get("/tasks/dependency-graph")
async def dependency_graph(
    root: Optional[str] = Query(None, description="Root task ID (optional)"),
    depth: int = Query(10, ge=1, le=50, description="Max traversal depth"),
    _=Depends(require_auth),
    svc=Depends(_svc),
):
    """Get the task dependency graph."""
    try:
        return svc.get_dependency_graph(root_task_id=root, max_depth=depth)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tasks/{task_id}/dependencies")
async def task_dependencies(
    task_id: str,
    _=Depends(require_auth),
    svc=Depends(_svc),
):
    """Get dependency tree for a specific task."""
    try:
        return svc.get_dependency_graph(root_task_id=task_id, max_depth=10)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tasks/{task_id}/force-unblock")
async def force_unblock_task(
    task_id: str,
    _=Depends(require_auth),
    svc=Depends(_svc),
):
    """Manually unblock a blocked task, overriding dependency checks."""
    try:
        return svc.force_unblock(task_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

'''

    router = router.replace(
        "# ── GET /api/operations/budget",
        new_endpoints + "# ── GET /api/operations/budget",
    )

    ops_router_path.write_text(router)
    try:
        compile(ops_router_path.read_text(), str(ops_router_path), "exec")
        print("  ✅ ops.py compiles")
    except SyntaxError as e:
        errors.append(f"ops.py: {e}")
        print(f"  ❌ ops.py: {e}")

    # ═══════════════════════════════════════════════════════════════
    # 3. PATCH priority_engine.py
    # ═══════════════════════════════════════════════════════════════
    print("3/3 Patching priority_engine.py...")

    pe_path = BACKEND / "app" / "services" / "priority_engine.py"
    pe = pe_path.read_text()

    # Add blocked field to PriorityItem
    pe = pe.replace(
        "    def __init__(self, item_id: str, task_type: str, description: str,",
        "    blocked: bool = False\n\n    def __init__(self, item_id: str, task_type: str, description: str,",
    )

    # Filter blocked in get_top
    pe = pe.replace(
        '        items = self._queue\n        if agent:\n            items = [i for i in items if i.agent == agent]',
        '        # P-4: exclude blocked tasks before scoring\n'
        '        items = [i for i in self._queue if not i.blocked]\n'
        '        if agent:\n            items = [i for i in items if i.agent == agent]',
    )

    # Filter blocked in pop_next
    pe = pe.replace(
        '        items = self._queue if not agent else [i for i in self._queue if i.agent == agent]',
        '        # P-4: exclude blocked tasks\n'
        '        pool = [i for i in self._queue if not i.blocked]\n'
        '        items = pool if not agent else [i for i in pool if i.agent == agent]',
    )

    pe_path.write_text(pe)
    try:
        compile(pe_path.read_text(), str(pe_path), "exec")
        print("  ✅ priority_engine.py compiles")
    except SyntaxError as e:
        errors.append(f"priority_engine.py: {e}")
        print(f"  ❌ priority_engine.py: {e}")

    # ═══════════════════════════════════════════════════════════════
    # SUMMARY
    # ═══════════════════════════════════════════════════════════════
    print()
    if errors:
        print(f"⛔ {len(errors)} ERRORS:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("✅ P-4 deployed successfully")
        print()
        print("Restart backend, then validate:")
        print()
        print('  TOKEN=$(cat ~/.nemoclaw/cc-token)')
        print()
        print('  # 1. Create independent task')
        print('  TASK_A=$(curl -s -X POST -H "Authorization: Bearer $TOKEN" \\')
        print('    -H "Content-Type: application/json" \\')
        print('    -d \'{"title":"Research competitors","priority":"high"}\' \\')
        print("    http://127.0.0.1:8100/api/ops/tasks | python3 -c \"import json,sys; print(json.load(sys.stdin)['id'])\")")
        print('  echo "Task A: $TASK_A"')
        print()
        print('  # 2. Create dependent task (should be blocked)')
        print('  TASK_B=$(curl -s -X POST -H "Authorization: Bearer $TOKEN" \\')
        print('    -H "Content-Type: application/json" \\')
        print('    -d "{\\\"title\\\":\\\"Draft outreach\\\",\\\"depends_on\\\":[\\\"$TASK_A\\\"]}" \\')
        print("    http://127.0.0.1:8100/api/ops/tasks | python3 -c \"import json,sys; d=json.load(sys.stdin); print(d['id'], d['status'], d.get('blocked_by'))\")")
        print()
        print('  # 3. Complete Task A')
        print('  curl -s -X PATCH -H "Authorization: Bearer $TOKEN" \\')
        print('    -H "Content-Type: application/json" \\')
        print('    -d \'{"status":"completed"}\' \\')
        print('    http://127.0.0.1:8100/api/ops/tasks/$TASK_A | python3 -m json.tool')
        print()
        print('  # 4. Check Task B — should be pending (auto-unblocked)')
        print('  curl -s -H "Authorization: Bearer $TOKEN" \\')
        print('    "http://127.0.0.1:8100/api/ops/tasks?status=pending" | python3 -m json.tool')
        print()
        print('  # 5. Dependency graph')
        print('  curl -s -H "Authorization: Bearer $TOKEN" \\')
        print('    http://127.0.0.1:8100/api/ops/tasks/dependency-graph | python3 -m json.tool')
        print()
        print('  # 6. Invalid dep (should 400)')
        print('  curl -s -X POST -H "Authorization: Bearer $TOKEN" \\')
        print('    -H "Content-Type: application/json" \\')
        print('    -d \'{"title":"Bad task","depends_on":["nonexistent"]}\' \\')
        print('    http://127.0.0.1:8100/api/ops/tasks | python3 -m json.tool')
        print()
        print('  # 7. Regression')
        print('  cd ~/nemoclaw-local-foundation && bash scripts/full_regression.sh')
        print()
        print('  # 8. Commit')
        print('  git add -A && git status')
        print('  git commit -m "feat(engine): P-4 task dependencies — blocked state, auto-unblock, cycle detection, reverse index, force-unblock"')
        print('  git push origin main')


if __name__ == "__main__":
    deploy()

"""
NemoClaw Command Center — Mission Manager Service

Production-grade Asana-backed mission lifecycle management with:
- 5-phase state machine: CREATED -> PLANNING -> EXECUTING -> REVIEWING -> COMPLETED
- Local artifact persistence in ~/.nemoclaw/missions/{id}/
- Vector memory knowledge accumulation on mission completion
- Event bus integration for cross-service notification
- Heartbeat logging (Asana + local JSONL)
- Task sync from Asana on phase transitions

Wiring (main.py):
    svc = MissionManagerService(
        asana_bridge=app.state.asana_bridge,
        execution_service=app.state.execution_service,
        repo_root=Path(...),
    )
    # Post-init (optional):
    svc.event_bus = app.state.event_bus
    svc.vector_memory = app.state.vector_memory
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.domain.mission_models import (
    Mission,
    MissionPhase,
    MissionTask,
    PHASE_TRANSITIONS,
)
from app.services.bridges.asana_bridge import AsanaBridge

logger = logging.getLogger("cc.missions")

MISSIONS_DIR = Path.home() / ".nemoclaw" / "missions"

# Asana project sections — aligned with phase names for clean mapping
PHASE_SECTIONS = ["Planning", "Executing", "Reviewing", "Done"]


class MissionManagerService:
    """Orchestrates mission lifecycle with Asana project backing and knowledge accumulation."""

    def __init__(
        self,
        asana_bridge: AsanaBridge,
        execution_service: Any = None,
        repo_root: Path | None = None,
    ):
        self.asana = asana_bridge
        self.execution_service = execution_service
        self.repo_root = repo_root or Path.home() / "nemoclaw-local-foundation"
        self._missions_dir = MISSIONS_DIR
        self._missions_dir.mkdir(parents=True, exist_ok=True)
        self._missions: dict[str, Mission] = {}
        self._section_cache: dict[str, dict[str, str]] = {}  # mission_id -> {section_name: gid}

        # Injected post-init by main.py
        self.event_bus: Any = None
        self.vector_memory: Any = None

        self._load_existing()
        logger.info("MissionManagerService initialized (%d existing missions)", len(self._missions))

    # ── Persistence ───────────────────────────────────────────────────

    def _load_existing(self) -> None:
        """Load missions from disk on startup."""
        if not self._missions_dir.is_dir():
            return
        for mission_dir in sorted(self._missions_dir.iterdir()):
            manifest = mission_dir / "mission.json"
            if not manifest.is_file():
                continue
            try:
                data = json.loads(manifest.read_text())
                mission = Mission(**data)
                self._missions[mission.id] = mission
                if "sections" in data:
                    self._section_cache[mission.id] = data["sections"]
            except Exception as e:
                logger.warning("Failed to load mission from %s: %s", mission_dir, e)

    def _persist(self, mission: Mission) -> None:
        """Write mission state to disk."""
        mission_dir = self._missions_dir / mission.id
        mission_dir.mkdir(parents=True, exist_ok=True)
        data = json.loads(mission.model_dump_json())
        # Include section cache for reload
        if mission.id in self._section_cache:
            data["sections"] = self._section_cache[mission.id]
        (mission_dir / "mission.json").write_text(json.dumps(data, indent=2, default=str))

    # ── Create ────────────────────────────────────────────────────────

    async def create_mission(self, goal: str, lead_agent: str = "ceo") -> Mission:
        """Create a new mission backed by an Asana project.

        1. Auto-detect workspace from Asana token.
        2. Create Asana project with phase-based sections.
        3. Create initial planning task in Backlog.
        4. Persist mission locally + emit event.

        Raises:
            RuntimeError: If no Asana workspaces found.
        """
        workspaces = await self.asana.get_workspaces()
        if not workspaces:
            raise RuntimeError("No Asana workspaces found for the configured token")
        workspace_gid = workspaces[0]["gid"]

        project_name = f"[NemoClaw] {goal[:80]}"
        project = await self.asana.create_project(
            workspace_gid=workspace_gid,
            name=project_name,
            sections=PHASE_SECTIONS,
        )

        mission = Mission(
            goal=goal,
            lead_agent=lead_agent,
            asana_project_gid=project["gid"],
            asana_project_url=project.get("url", f"https://app.asana.com/0/{project['gid']}"),
            workspace_gid=workspace_gid,
            local_dir=str(self._missions_dir / "placeholder"),  # overwritten below
        )
        mission.local_dir = str(self._missions_dir / mission.id)
        Path(mission.local_dir).mkdir(parents=True, exist_ok=True)

        self._missions[mission.id] = mission
        self._section_cache[mission.id] = project.get("sections", {})

        # Create seed planning task
        planning_gid = self._section_cache[mission.id].get("Planning")
        if planning_gid:
            task = await self.asana.create_task(
                project_gid=project["gid"],
                section_gid=planning_gid,
                name=f"Plan: {goal[:100]}",
                notes=f"Mission: {mission.id}\nLead: {lead_agent}\nGoal: {goal}",
                assignee_name=lead_agent,
            )
            mission.tasks.append(MissionTask(
                task_gid=task["gid"],
                name=task.get("name", ""),
                assignee=lead_agent,
                section="Planning",
            ))

        self._persist(mission)
        self._emit("mission_created", {
            "mission_id": mission.id,
            "goal": goal,
            "lead_agent": lead_agent,
            "asana_url": mission.asana_project_url,
        })

        logger.info("Created mission %s: goal=%s asana=%s", mission.id, goal[:60], project["gid"])
        return mission

    # ── Phase Advancement ─────────────────────────────────────────────

    async def advance_phase(self, mission_id: str, to_phase: MissionPhase) -> Mission:
        """Advance mission to a specific phase with validation.

        Validates against PHASE_TRANSITIONS state machine.
        Syncs tasks from Asana on every transition.
        On COMPLETED: triggers vector memory knowledge accumulation.

        Raises:
            ValueError: If mission not found or invalid transition.
        """
        mission = self._get_or_raise(mission_id)
        self._validate_transition(mission, to_phase)

        old_phase = mission.phase
        mission.phase = to_phase
        mission.updated_at = datetime.now(timezone.utc)

        # Sync task state from Asana
        if mission.asana_project_gid:
            await self._sync_tasks(mission)

        self._persist(mission)

        self._emit("mission_phase_changed", {
            "mission_id": mission_id,
            "from_phase": old_phase.value,
            "to_phase": to_phase.value,
            "task_count": len(mission.tasks),
            "tasks_completed": sum(1 for t in mission.tasks if t.completed),
        })

        logger.info("Mission %s: %s -> %s", mission_id, old_phase.value, to_phase.value)

        # Post-completion hook
        if to_phase == MissionPhase.COMPLETED:
            await self._on_mission_completed(mission)

        return mission

    async def _on_mission_completed(self, mission: Mission) -> None:
        """Post-completion: accumulate knowledge from mission artifacts into vector memory."""
        mission_dir = Path(mission.local_dir) if mission.local_dir else None
        if not mission_dir or not mission_dir.is_dir():
            logger.info("Mission %s completed — no local_dir for knowledge accumulation", mission.id)
            return

        if not self.vector_memory:
            logger.debug("Mission %s completed — vector_memory not wired, skipping accumulation", mission.id)
            return

        try:
            count = self.vector_memory.accumulate_from_mission(mission_dir)
            logger.info("Mission %s: accumulated %d knowledge items into vector memory", mission.id, count)
            self._emit("mission_knowledge_accumulated", {
                "mission_id": mission.id,
                "items_added": count,
                "source_dir": str(mission_dir),
            })
        except Exception as e:
            logger.error("Knowledge accumulation failed for mission %s: %s", mission.id, e)

    # ── Convenience Phase Methods ─────────────────────────────────────

    async def plan_mission(self, mission_id: str) -> Mission:
        """Advance to PLANNING and create initial Asana tasks."""
        mission = self._get_or_raise(mission_id)
        self._validate_transition(mission, MissionPhase.PLANNING)

        mission.phase = MissionPhase.PLANNING
        mission.updated_at = datetime.now(timezone.utc)

        sections = self._section_cache.get(mission_id, {})
        planning_gid = sections.get("Planning")

        task = await self.asana.create_task(
            project_gid=mission.asana_project_gid,
            section_gid=planning_gid,
            name=f"Plan: {mission.goal[:80]}",
            notes=f"Mission goal: {mission.goal}\nLead: {mission.lead_agent}",
            assignee_name=mission.lead_agent,
        )

        mission.tasks.append(MissionTask(
            task_gid=task["gid"],
            name=task.get("name", ""),
            assignee=mission.lead_agent,
            section="Planning",
        ))

        self._persist(mission)
        self._emit("mission_phase_changed", {
            "mission_id": mission_id,
            "from_phase": MissionPhase.CREATED.value,
            "to_phase": MissionPhase.PLANNING.value,
        })
        logger.info("Mission %s advanced to PLANNING", mission_id)
        return mission

    async def execute_mission(self, mission_id: str) -> Mission:
        """Advance to EXECUTING."""
        return await self.advance_phase(mission_id, MissionPhase.EXECUTING)

    async def complete_mission(self, mission_id: str) -> Mission:
        """Advance to COMPLETED — triggers knowledge accumulation."""
        return await self.advance_phase(mission_id, MissionPhase.COMPLETED)

    # ── Heartbeat ─────────────────────────────────────────────────────

    async def heartbeat(self, mission_id: str, agent_id: str, message: str) -> dict[str, Any]:
        """Post a heartbeat comment on the first active task.

        Also persists to local heartbeats.jsonl for offline audit.

        Raises:
            ValueError: If mission not found.
        """
        mission = self._get_or_raise(mission_id)

        # Find first incomplete task
        target_task = None
        for task in mission.tasks:
            if not task.completed:
                target_task = task
                break

        if not target_task:
            if mission.tasks:
                target_task = mission.tasks[0]
            else:
                return {"status": "no_tasks", "message": "No tasks to comment on"}

        comment = await self.asana.add_comment(
            task_gid=target_task.task_gid,
            text=f"[{agent_id}] {message}",
        )

        self._write_heartbeat(mission, agent_id, message)

        return {
            "status": "ok",
            "comment_gid": comment.get("gid"),
            "task_gid": target_task.task_gid,
            "task_name": target_task.name,
        }

    # ── Query Methods ─────────────────────────────────────────────────

    def list_missions(self, lead_agent: str | None = None) -> list[dict[str, Any]]:
        """List all missions, optionally filtered by lead agent."""
        missions = list(self._missions.values())
        if lead_agent:
            missions = [m for m in missions if m.lead_agent == lead_agent]
        return [
            self._mission_summary(m)
            for m in sorted(missions, key=lambda m: m.created_at, reverse=True)
        ]

    def get_mission(self, mission_id: str) -> dict[str, Any]:
        """Get a single mission with full details."""
        mission = self._get_or_raise(mission_id)
        return self._mission_summary(mission)

    def get_active_missions(self) -> list[dict[str, Any]]:
        """Return missions not yet completed."""
        active = [m for m in self._missions.values() if m.phase != MissionPhase.COMPLETED]
        return [
            self._mission_summary(m)
            for m in sorted(active, key=lambda m: m.updated_at, reverse=True)
        ]

    def get_mission_artifacts(self, mission_id: str) -> list[dict[str, Any]]:
        """List artifact files in a mission's local directory.

        Raises:
            ValueError: If mission not found.
        """
        mission = self._get_or_raise(mission_id)
        mission_dir = Path(mission.local_dir) if mission.local_dir else None
        if not mission_dir or not mission_dir.is_dir():
            return []
        artifacts = []
        for f in sorted(mission_dir.iterdir()):
            if f.is_file() and f.name != "mission.json":
                artifacts.append({
                    "name": f.name,
                    "size_bytes": f.stat().st_size,
                    "modified": datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc).isoformat(),
                })
        return artifacts

    # ── Asana Sync ────────────────────────────────────────────────────

    async def _sync_tasks(self, mission: Mission) -> None:
        """Refresh mission task list from Asana project."""
        if not mission.asana_project_gid:
            return
        try:
            asana_tasks = await self.asana.get_project_tasks(mission.asana_project_gid)
            synced: list[MissionTask] = []
            for t in asana_tasks:
                section_name = None
                for m in t.get("memberships", []):
                    sec = m.get("section", {})
                    if sec.get("name"):
                        section_name = sec["name"]
                        break
                synced.append(MissionTask(
                    task_gid=t["gid"],
                    name=t.get("name", ""),
                    assignee=t.get("assignee", {}).get("name") if t.get("assignee") else None,
                    completed=t.get("completed", False),
                    section=section_name,
                ))
            mission.tasks = synced
            logger.debug("Synced %d tasks for mission %s", len(synced), mission.id)
        except Exception as e:
            logger.warning("Failed to sync tasks for mission %s: %s", mission.id, e)

    # ── Local Logging ─────────────────────────────────────────────────

    def _write_heartbeat(self, mission: Mission, agent_id: str, message: str) -> None:
        """Append heartbeat to local JSONL log for offline audit."""
        if not mission.local_dir:
            return
        log_path = Path(mission.local_dir) / "heartbeats.jsonl"
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent_id": agent_id,
            "phase": mission.phase.value,
            "message": message,
        }
        try:
            with open(log_path, "a") as f:
                f.write(json.dumps(record) + "\n")
        except OSError as e:
            logger.debug("Failed to write heartbeat log: %s", e)

    # ── Events ────────────────────────────────────────────────────────

    def _emit(self, event_type: str, data: dict[str, Any]) -> None:
        """Emit event to event bus if wired."""
        if not self.event_bus:
            return
        try:
            self.event_bus.emit(event_type, data)
        except Exception as e:
            logger.debug("Event emission failed for %s: %s", event_type, e)

    # ── Helpers ────────────────────────────────────────────────────────

    def _get_or_raise(self, mission_id: str) -> Mission:
        mission = self._missions.get(mission_id)
        if not mission:
            raise ValueError(f"Mission not found: {mission_id}")
        return mission

    def _validate_transition(self, mission: Mission, to_phase: MissionPhase) -> None:
        allowed = PHASE_TRANSITIONS.get(mission.phase, [])
        if to_phase not in allowed:
            raise ValueError(
                f"Cannot transition from {mission.phase.value} to {to_phase.value}. "
                f"Allowed: {[p.value for p in allowed]}"
            )

    @staticmethod
    def _mission_summary(mission: Mission) -> dict[str, Any]:
        """Convert Mission to API-friendly dict."""
        return {
            "id": mission.id,
            "goal": mission.goal,
            "lead_agent": mission.lead_agent,
            "phase": mission.phase.value,
            "asana_project_gid": mission.asana_project_gid,
            "asana_project_url": mission.asana_project_url,
            "local_dir": mission.local_dir,
            "task_count": len(mission.tasks),
            "tasks_completed": sum(1 for t in mission.tasks if t.completed),
            "created_at": mission.created_at.isoformat(),
            "updated_at": mission.updated_at.isoformat(),
        }

"""
NemoClaw Execution Engine — Deliverable Service (E-11)

Tracks client deliverables through: planned → in_production → review →
delivered → satisfaction_checked.

NEW FILE: command-center/backend/app/services/deliverable_service.py
"""
from __future__ import annotations
import json, logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("cc.deliverables")

DELIVERY_STAGES = ["planned", "in_production", "review", "delivered", "satisfaction_checked"]


class Deliverable:
    def __init__(self, deliverable_id: str, client_id: str, title: str,
                 description: str = "", due_date: str = "", agent: str = "client_success_lead"):
        self.deliverable_id = deliverable_id
        self.client_id = client_id
        self.title = title
        self.description = description
        self.due_date = due_date
        self.agent = agent
        self.stage = "planned"
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.updated_at = self.created_at
        self.satisfaction_score: float | None = None
        self.notes: list[str] = []

    def advance(self, new_stage: str) -> dict[str, Any] | None:
        if new_stage not in DELIVERY_STAGES:
            return {"error": f"Invalid stage: {new_stage}"}
        curr_idx = DELIVERY_STAGES.index(self.stage)
        new_idx = DELIVERY_STAGES.index(new_stage)
        if new_idx <= curr_idx:
            return {"error": f"Cannot go backwards: {self.stage} → {new_stage}"}
        self.stage = new_stage
        self.updated_at = datetime.now(timezone.utc).isoformat()
        return {"deliverable_id": self.deliverable_id, "new_stage": new_stage}

    def to_dict(self) -> dict[str, Any]:
        return {
            "deliverable_id": self.deliverable_id, "client_id": self.client_id,
            "title": self.title, "description": self.description,
            "due_date": self.due_date, "stage": self.stage, "agent": self.agent,
            "created_at": self.created_at, "updated_at": self.updated_at,
            "satisfaction_score": self.satisfaction_score, "notes": self.notes,
        }


class DeliverableService:
    def __init__(self, global_state=None, event_bus=None):
        self.global_state = global_state
        self.event_bus = event_bus
        self._deliverables: dict[str, Deliverable] = {}
        self._persist_path = Path.home() / ".nemoclaw" / "deliverables.json"
        self._persist_path.parent.mkdir(parents=True, exist_ok=True)
        self._load()
        logger.info("DeliverableService initialized (%d deliverables)", len(self._deliverables))

    def _load(self) -> None:
        if self._persist_path.exists():
            try:
                data = json.loads(self._persist_path.read_text())
                for d in data:
                    dl = Deliverable(d["deliverable_id"], d["client_id"], d["title"],
                                    d.get("description", ""), d.get("due_date", ""), d.get("agent", ""))
                    dl.stage = d.get("stage", "planned")
                    dl.created_at = d.get("created_at", dl.created_at)
                    dl.updated_at = d.get("updated_at", dl.updated_at)
                    dl.satisfaction_score = d.get("satisfaction_score")
                    dl.notes = d.get("notes", [])
                    self._deliverables[dl.deliverable_id] = dl
            except Exception as e:
                logger.warning("Failed to load deliverables: %s", e)

    def _save(self) -> None:
        try:
            self._persist_path.write_text(json.dumps([d.to_dict() for d in self._deliverables.values()], indent=2, default=str))
        except Exception:
            pass

    def create(self, deliverable_id: str, client_id: str, title: str,
               description: str = "", due_date: str = "") -> dict[str, Any]:
        if deliverable_id in self._deliverables:
            return {"error": "Deliverable already exists"}
        dl = Deliverable(deliverable_id, client_id, title, description, due_date)
        self._deliverables[deliverable_id] = dl
        self._save()
        if self.event_bus:
            self.event_bus.emit("deliverable_created", {"deliverable_id": deliverable_id, "client_id": client_id})
        return dl.to_dict()

    def advance(self, deliverable_id: str, new_stage: str) -> dict[str, Any]:
        dl = self._deliverables.get(deliverable_id)
        if not dl:
            return {"error": "Deliverable not found"}
        result = dl.advance(new_stage)
        if result and "error" not in result:
            self._save()
            if self.event_bus:
                self.event_bus.emit("deliverable_advanced", {"deliverable_id": deliverable_id, "stage": new_stage})
        return result or {}

    def get(self, deliverable_id: str) -> dict[str, Any] | None:
        dl = self._deliverables.get(deliverable_id)
        return dl.to_dict() if dl else None

    def get_by_client(self, client_id: str) -> list[dict[str, Any]]:
        return [d.to_dict() for d in self._deliverables.values() if d.client_id == client_id]

    def get_overdue(self) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc).isoformat()
        return [d.to_dict() for d in self._deliverables.values()
                if d.due_date and d.due_date < now and d.stage not in ("delivered", "satisfaction_checked")]

    def get_stats(self) -> dict[str, Any]:
        by_stage = {s: 0 for s in DELIVERY_STAGES}
        for d in self._deliverables.values():
            by_stage[d.stage] = by_stage.get(d.stage, 0) + 1
        return {"total": len(self._deliverables), "by_stage": by_stage, "overdue": len(self.get_overdue())}

    # ── File Storage ──────────────────────────────────────────────────

    _FILES_ROOT = Path.home() / ".nemoclaw" / "deliverables"

    def _project_dir(self, project_id: str) -> Path:
        d = self._FILES_ROOT / project_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def store_file(
        self, project_id: str, agent_id: str, filename: str, content: bytes | str,
    ) -> dict[str, Any]:
        """Save a deliverable file to ~/.nemoclaw/deliverables/{project_id}/."""
        dest = self._project_dir(project_id) / filename
        if isinstance(content, str):
            dest.write_text(content, encoding="utf-8")
        else:
            dest.write_bytes(content)
        logger.info("Stored file: %s/%s (by %s)", project_id, filename, agent_id)
        return {
            "project_id": project_id,
            "filename": filename,
            "agent_id": agent_id,
            "size": dest.stat().st_size,
            "path": str(dest),
        }

    def list_files(self, project_id: str) -> list[dict[str, Any]]:
        """List all deliverable files for a project."""
        d = self._FILES_ROOT / project_id
        if not d.exists():
            return []
        files = []
        for f in sorted(d.iterdir()):
            if f.is_file():
                stat = f.stat()
                files.append({
                    "filename": f.name,
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                })
        return files

    def get_file(self, project_id: str, filename: str) -> dict[str, Any] | None:
        """Read a deliverable file's content."""
        fpath = self._FILES_ROOT / project_id / filename
        if not fpath.exists() or not fpath.is_file():
            return None
        try:
            content = fpath.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = fpath.read_bytes().hex()
        stat = fpath.stat()
        return {
            "filename": filename,
            "project_id": project_id,
            "size": stat.st_size,
            "content": content,
        }

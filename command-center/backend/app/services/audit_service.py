"""
NemoClaw Execution Engine — AuditService (E-4c)

Immutable audit log (#44): every decision, action, spend, approval.
Append-only, timestamped, exportable.

NEW FILE: command-center/backend/app/services/audit_service.py
"""
from __future__ import annotations
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("cc.audit")

class AuditService:
    def __init__(self, persist_path: Path | None = None):
        self.persist_path = persist_path or (Path.home() / ".nemoclaw" / "audit-log.jsonl")
        self.persist_path.parent.mkdir(parents=True, exist_ok=True)
        self._entries: list[dict[str, Any]] = []
        self._load()
        logger.info("AuditService initialized (%d entries)", len(self._entries))

    def _load(self):
        if self.persist_path.exists():
            try:
                for line in self.persist_path.read_text().strip().split("\n"):
                    if line:
                        self._entries.append(json.loads(line))
            except (json.JSONDecodeError, OSError):
                pass

    def log(self, action: str, agent_id: str = "", details: dict[str, Any] | None = None, trace_id: str = "") -> dict[str, Any]:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "agent_id": agent_id,
            "trace_id": trace_id,
            "details": details or {},
        }
        self._entries.append(entry)
        with open(self.persist_path, "a") as f:
            f.write(json.dumps(entry, default=str) + "\n")
        return entry

    def get_log(self, limit: int = 100, action: str = "", agent_id: str = "") -> list[dict[str, Any]]:
        entries = self._entries
        if action:
            entries = [e for e in entries if e.get("action") == action]
        if agent_id:
            entries = [e for e in entries if e.get("agent_id") == agent_id]
        return entries[-limit:]

    def export(self) -> str:
        return "\n".join(json.dumps(e, default=str) for e in self._entries)

"""
NemoClaw Execution Engine — KnowledgeBaseService (E-4b)

Organizational knowledge (#43): company-wide facts shared by all agents.
Different from per-agent memory — this is global truth.

Persistence: JSON file at ~/.nemoclaw/knowledge-base.json

NEW FILE: command-center/backend/app/services/knowledge_base_service.py
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("cc.kb")


class KnowledgeBaseService:
    """
    Global knowledge base accessible by all agents.

    Stores company facts, ICP definitions, pricing, policies.
    """

    def __init__(self, persist_path: Path | None = None):
        self.persist_path = persist_path or (Path.home() / ".nemoclaw" / "knowledge-base.json")
        self.persist_path.parent.mkdir(parents=True, exist_ok=True)
        self.entries: dict[str, dict[str, Any]] = {}
        self._load()
        logger.info("KnowledgeBaseService initialized (%d entries)", len(self.entries))

    def _load(self):
        if self.persist_path.exists():
            try:
                self.entries = json.loads(self.persist_path.read_text())
            except (json.JSONDecodeError, OSError):
                self.entries = {}

    def _save(self):
        self.persist_path.write_text(json.dumps(self.entries, indent=2, default=str))

    def add(self, key: str, value: str, category: str = "general", added_by: str = "") -> dict[str, Any]:
        """Add a knowledge entry."""
        entry_id = str(uuid.uuid4())[:8]
        entry = {
            "id": entry_id,
            "key": key,
            "value": value,
            "category": category,
            "added_by": added_by,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self.entries[entry_id] = entry
        self._save()
        logger.info("KB entry added: %s = %s", key, value[:50])
        return entry

    def get(self, entry_id: str) -> dict[str, Any] | None:
        return self.entries.get(entry_id)

    def search(self, query: str = "", category: str = "") -> list[dict[str, Any]]:
        """Search knowledge base."""
        results = list(self.entries.values())
        if category:
            results = [e for e in results if e.get("category") == category]
        if query:
            q = query.lower()
            results = [
                e for e in results
                if q in e.get("key", "").lower() or q in e.get("value", "").lower()
            ]
        return results

    def update(self, entry_id: str, value: str) -> dict[str, Any] | None:
        entry = self.entries.get(entry_id)
        if not entry:
            return None
        entry["value"] = value
        entry["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._save()
        return entry

    def delete(self, entry_id: str) -> bool:
        if entry_id in self.entries:
            del self.entries[entry_id]
            self._save()
            return True
        return False

    def get_all(self) -> list[dict[str, Any]]:
        return list(self.entries.values())

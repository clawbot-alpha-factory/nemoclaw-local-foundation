"""
NemoClaw Execution Engine — WorkspaceService (E-4b)

Shared workflow workspace (#29): per-workflow key-value store.
Namespaced writes (sales.*, marketing.*). Universal reads. Versioned.

NEW FILE: command-center/backend/app/services/workspace_service.py
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("cc.workspace")


class WorkspaceService:
    """
    Per-workflow shared key-value store.

    Agents write to their namespace (e.g., sales.leads).
    All agents can read all keys.
    Versioned: each write creates a new version.
    """

    def __init__(self, persist_dir: Path | None = None):
        self.persist_dir = persist_dir or (Path.home() / ".nemoclaw" / "workspaces")
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.workspaces: dict[str, dict[str, Any]] = {}
        logger.info("WorkspaceService initialized")

    def write(
        self,
        workflow_id: str,
        key: str,
        value: Any,
        agent_id: str = "",
    ) -> dict[str, Any]:
        """Write a key-value pair to a workflow workspace."""
        ws = self.workspaces.setdefault(workflow_id, {})

        # Namespace the key
        namespaced_key = f"{agent_id}.{key}" if agent_id else key

        entry = {
            "value": value,
            "written_by": agent_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version": ws.get(namespaced_key, {}).get("version", 0) + 1,
        }

        ws[namespaced_key] = entry
        self._persist(workflow_id)

        logger.debug("Workspace %s: %s wrote %s", workflow_id[:8], agent_id, namespaced_key)
        return {"key": namespaced_key, **entry}

    def read(self, workflow_id: str, key: str | None = None, namespace: str = "") -> dict[str, Any]:
        """Read from workspace. Filter by key, namespace, or return all."""
        ws = self.workspaces.get(workflow_id, {})
        if key:
            return ws.get(key, {})
        if namespace:
            return {k: v for k, v in ws.items() if k.startswith(f"{namespace}.")}
        return dict(ws)

    def read_all(self, workflow_id: str, namespace: str = "") -> dict[str, Any]:
        """Read entire workspace, optionally filtered by namespace."""
        return self.read(workflow_id, namespace=namespace)

    def _persist(self, workflow_id: str):
        """Save workspace to disk."""
        path = self.persist_dir / f"{workflow_id}.json"
        ws = self.workspaces.get(workflow_id, {})
        path.write_text(json.dumps(ws, indent=2, default=str))

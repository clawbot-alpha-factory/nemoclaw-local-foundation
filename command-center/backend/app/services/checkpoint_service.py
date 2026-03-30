"""
NemoClaw Execution Engine — CheckpointService (E-4a)

Crash recovery: agent state to JSON, resume from checkpoint.
Clean shutdown → state save. Restart → recovery scan.

Persistence: JSON files in ~/.nemoclaw/checkpoints/engine/

NEW FILE: command-center/backend/app/services/checkpoint_service.py
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("cc.checkpoint")


class CheckpointService:
    """
    Saves and restores agent loop state for crash recovery.

    Each agent gets a checkpoint file with:
      - Loop state (running/idle/acting)
      - Current task (if any)
      - Last tick timestamp
      - Cumulative stats
    """

    def __init__(self, checkpoint_dir: Path | None = None):
        self.checkpoint_dir = checkpoint_dir or (
            Path.home() / ".nemoclaw" / "checkpoints" / "engine"
        )
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        logger.info("CheckpointService initialized (dir=%s)", self.checkpoint_dir)

    def _agent_file(self, agent_id: str) -> Path:
        return self.checkpoint_dir / f"{agent_id}.json"

    def save(self, agent_id: str, state: dict[str, Any]):
        """Save agent checkpoint."""
        state["_checkpoint_time"] = datetime.now(timezone.utc).isoformat()
        state["_agent_id"] = agent_id

        path = self._agent_file(agent_id)
        path.write_text(json.dumps(state, indent=2, default=str))
        logger.debug("Checkpoint saved: %s", agent_id)

    def load(self, agent_id: str) -> dict[str, Any] | None:
        """Load agent checkpoint (returns None if not found)."""
        path = self._agent_file(agent_id)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text())
            logger.debug("Checkpoint loaded: %s", agent_id)
            return data
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load checkpoint for %s: %s", agent_id, e)
            return None

    def delete(self, agent_id: str) -> bool:
        """Delete an agent checkpoint."""
        path = self._agent_file(agent_id)
        if path.exists():
            path.unlink()
            return True
        return False

    def list_checkpoints(self) -> list[dict[str, Any]]:
        """List all saved checkpoints."""
        checkpoints = []
        for path in self.checkpoint_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text())
                checkpoints.append({
                    "agent_id": path.stem,
                    "checkpoint_time": data.get("_checkpoint_time", "unknown"),
                    "loop_state": data.get("loop_state", "unknown"),
                    "file_size_bytes": path.stat().st_size,
                })
            except Exception:
                checkpoints.append({
                    "agent_id": path.stem,
                    "checkpoint_time": "error",
                    "loop_state": "error",
                })
        return checkpoints

    def save_all(self, agents: dict[str, dict[str, Any]]):
        """Save checkpoints for multiple agents (clean shutdown)."""
        for agent_id, state in agents.items():
            self.save(agent_id, state)
        logger.info("All checkpoints saved (%d agents)", len(agents))

"""
NemoClaw Execution Engine — ConfigService (E-4c)

Single source of runtime configuration (#12).
Adjustable via API without restart.

NEW FILE: command-center/backend/app/services/config_service.py
"""
from __future__ import annotations
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("cc.config")

DEFAULT_CONFIG = {
    "execution_mode": "conservative",
    "tick_interval_seconds": 60,
    "spend_ceiling_daily": 20.0,
    "volume_cap_outreach": 50,
    "volume_cap_social": 5,
    "max_actions_per_hour": 30,
    "max_concurrent_agents": 3,
    "llm_default_tier": "standard",
    "auto_revert_aggressive_multiplier": 2.0,
    "checkpoint_interval_ticks": 10,
    "feedback_loop_enabled": True,
    "debate_max_rounds": 6,
}

class ConfigService:
    def __init__(self, persist_path: Path | None = None):
        self.persist_path = persist_path or (Path.home() / ".nemoclaw" / "engine-config.json")
        self.persist_path.parent.mkdir(parents=True, exist_ok=True)
        self.config: dict[str, Any] = dict(DEFAULT_CONFIG)
        self._load()
        logger.info("ConfigService initialized (%d keys)", len(self.config))

    def _load(self):
        if self.persist_path.exists():
            try:
                saved = json.loads(self.persist_path.read_text())
                self.config.update(saved)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Failed to load config, using defaults: %s", e)

    def _save(self):
        self.persist_path.write_text(json.dumps(self.config, indent=2))

    def get(self, key: str, default: Any = None) -> Any:
        return self.config.get(key, default)

    def get_all(self) -> dict[str, Any]:
        return dict(self.config)

    def set(self, key: str, value: Any) -> dict[str, Any]:
        old = self.config.get(key)
        self.config[key] = value
        self._save()
        logger.info("Config updated: %s = %s (was %s)", key, value, old)
        return {"key": key, "value": value, "previous": old}

    def update(self, updates: dict[str, Any]) -> dict[str, Any]:
        changes = []
        for key, value in updates.items():
            old = self.config.get(key)
            self.config[key] = value
            changes.append({"key": key, "value": value, "previous": old})
        self._save()
        return {"updated": len(changes), "changes": changes}

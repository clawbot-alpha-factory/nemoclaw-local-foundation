"""
NemoClaw Execution Engine — SecretManager (E-4c)

Secrets (#26): encrypted at rest (Fernet), scoped access, access audit log.

NEW FILE: command-center/backend/app/services/secret_manager.py
"""
from __future__ import annotations
import base64
import hashlib
import json
import logging
import os
try:
    from cryptography.fernet import Fernet
    HAS_FERNET = True
except ImportError:
    HAS_FERNET = False
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("cc.secrets")

class SecretManager:
    def __init__(self, persist_dir: Path | None = None):
        self.persist_dir = persist_dir or (Path.home() / ".nemoclaw" / "secrets")
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self._secrets_file = self.persist_dir / "vault.json"
        self._access_log_file = self.persist_dir / "access.log"
        self._secrets: dict[str, dict[str, Any]] = {}
        self._key = self._derive_key()
        self._load()
        logger.info("SecretManager initialized (%d secrets)", len(self._secrets))

    def _derive_key(self) -> bytes:
        machine_id = os.environ.get("NEMOCLAW_SECRET_KEY", "nemoclaw-dev-key-change-in-prod")
        return hashlib.sha256(machine_id.encode()).digest()

    def _encrypt(self, plaintext: str) -> str:
        if HAS_FERNET:
            f = Fernet(base64.urlsafe_b64encode(self._key[:32]))
            return f.encrypt(plaintext.encode()).decode()
        # Fallback: base64 encoding (dev only — install cryptography for production)
        return "b64:" + base64.urlsafe_b64encode(plaintext.encode()).decode()

    def _decrypt(self, ciphertext: str) -> str:
        if ciphertext.startswith("b64:"):
            return base64.urlsafe_b64decode(ciphertext[4:]).decode()
        if HAS_FERNET:
            f = Fernet(base64.urlsafe_b64encode(self._key[:32]))
            return f.decrypt(ciphertext.encode()).decode()
        return ciphertext

    def _load(self):
        if self._secrets_file.exists():
            try:
                self._secrets = json.loads(self._secrets_file.read_text())
            except (json.JSONDecodeError, OSError):
                self._secrets = {}

    def _save(self):
        self._secrets_file.write_text(json.dumps(self._secrets, indent=2))

    def _log_access(self, action: str, key: str, agent_id: str):
        entry = f"{datetime.now(timezone.utc).isoformat()} | {action} | {key} | {agent_id}\n"
        with open(self._access_log_file, "a") as f:
            f.write(entry)

    def store(self, key: str, value: str, scope: list[str] | None = None, stored_by: str = "") -> dict[str, Any]:
        encrypted = self._encrypt(value)
        self._secrets[key] = {
            "value": encrypted,
            "scope": scope or ["all"],
            "stored_by": stored_by,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._save()
        self._log_access("store", key, stored_by)
        logger.info("Secret stored: %s (scope=%s)", key, scope)
        return {"key": key, "scope": scope or ["all"], "stored": True}

    def retrieve(self, key: str, agent_id: str = "") -> dict[str, Any]:
        secret = self._secrets.get(key)
        if not secret:
            return {"key": key, "found": False}
        scope = secret.get("scope", ["all"])
        if "all" not in scope and agent_id not in scope:
            self._log_access("denied", key, agent_id)
            return {"key": key, "found": True, "allowed": False, "reason": f"Agent {agent_id} not in scope {scope}"}
        value = self._decrypt(secret["value"])
        self._log_access("retrieve", key, agent_id)
        return {"key": key, "found": True, "allowed": True, "value": value}

    def list_keys(self) -> list[dict[str, Any]]:
        return [
            {"key": k, "scope": v.get("scope", []), "created_at": v.get("created_at")}
            for k, v in self._secrets.items()
        ]

    def delete(self, key: str) -> bool:
        if key in self._secrets:
            del self._secrets[key]
            self._save()
            return True
        return False

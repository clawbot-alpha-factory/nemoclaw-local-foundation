"""
Command Center backend configuration.
Reads from environment and provides defaults for local development.
"""

import os
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """CC-1 backend settings. All paths resolve relative to the repo root."""

    # ── Paths ──────────────────────────────────────────────────────────
    repo_root: Path = Path.home() / "nemoclaw-local-foundation"
    nemoclaw_home: Path = Path.home() / ".nemoclaw"

    # ── Server ─────────────────────────────────────────────────────────
    host: str = "127.0.0.1"
    port: int = 8100
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]  # Override via CC_CORS_ORIGINS env var for production

    # ── Auth ───────────────────────────────────────────────────────────
    auth_token: str = ""  # Set via CC_AUTH_TOKEN env var or generated on first run
    auth_secret: str = "nemoclaw-cc-dev-secret"  # Override in production

    # ── State Aggregator ───────────────────────────────────────────────
    scan_interval_seconds: int = 10  # How often to rescan filesystem
    ws_broadcast_interval_seconds: int = 10  # How often to push state to WS clients

    # ── Derived paths ──────────────────────────────────────────────────
    @property
    def skills_dir(self) -> Path:
        return self.repo_root / "skills"

    @property
    def agents_dir(self) -> Path:
        return self.repo_root / "config" / "agents"

    @property
    def scripts_dir(self) -> Path:
        return self.repo_root / "scripts"

    @property
    def docs_dir(self) -> Path:
        return self.repo_root / "docs"

    @property
    def config_dir(self) -> Path:
        return self.repo_root / "config"

    @property
    def budget_config(self) -> Path:
        return self.repo_root / "config" / "budget-config.yaml"

    @property
    def routing_config(self) -> Path:
        return self.repo_root / "config" / "routing-config.yaml"

    @property
    def integration_logs_dir(self) -> Path:
        return self.nemoclaw_home / "integrations"

    @property
    def checkpoint_dir(self) -> Path:
        return self.nemoclaw_home / "checkpoints"

    class Config:
        env_prefix = "CC_"
        env_file = ".env"


settings = Settings()


def ensure_directories() -> None:
    """Create required runtime directories if they don't exist."""
    settings.nemoclaw_home.mkdir(parents=True, exist_ok=True)
    settings.integration_logs_dir.mkdir(parents=True, exist_ok=True)
    settings.checkpoint_dir.mkdir(parents=True, exist_ok=True)

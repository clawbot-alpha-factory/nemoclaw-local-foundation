"""
NemoClaw Command Center — Settings Router
"""

import logging
import platform
import subprocess
import time
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException, Request
from pydantic import BaseModel

from app.auth import require_auth

log = logging.getLogger("cc.settings.api")

router = APIRouter(prefix="/api/settings", tags=["settings"])

_start_time = time.time()


class ThemeRequest(BaseModel):
    theme: str  # "light" or "dark"


class BrainIntervalRequest(BaseModel):
    interval: int  # seconds


def _get_settings(request: Request):
    """Get settings from app state."""
    settings = getattr(request.app.state, "settings", None)
    if not settings:
        raise HTTPException(status_code=503, detail="Settings not initialized")
    return settings


def _run_cmd(cmd: list[str], fallback: str = "unknown") -> str:
    """Run a shell command and return stripped stdout or fallback."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            return result.stdout.strip()
        return fallback
    except Exception:
        return fallback


@router.get("/")
async def get_settings(
    _=Depends(require_auth),
    settings=Depends(_get_settings),
):
    """Return current system settings (token, theme, intervals)."""
    return {
        "token": getattr(settings, "token", None),
        "theme": getattr(settings, "theme", "dark"),
        "intervals": {
            "brain": getattr(settings, "brain_interval", 300),
        },
    }


@router.get("/token")
async def get_token(
    settings=Depends(_get_settings),
):
    """Return current active token (for auto-setup). No auth required."""
    token = getattr(settings, "token", None)
    if not token:
        raise HTTPException(status_code=404, detail="No active token configured")
    return {"token": token}


@router.post("/theme")
async def set_theme(
    body: ThemeRequest,
    _=Depends(require_auth),
    settings=Depends(_get_settings),
):
    """Set theme preference (light/dark)."""
    if body.theme not in ("light", "dark"):
        raise HTTPException(
            status_code=400,
            detail="Theme must be 'light' or 'dark'",
        )
    settings.theme = body.theme
    log.info("Theme updated to: %s", body.theme)
    return {"theme": settings.theme, "message": f"Theme set to {body.theme}"}


@router.get("/system")
async def get_system_info():
    """Return system info (python version, node version, git info, uptime). No auth required."""
    python_version = platform.python_version()
    node_version = _run_cmd(["node", "--version"], fallback="not installed")
    git_branch = _run_cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"], fallback="unknown")
    git_commit = _run_cmd(["git", "rev-parse", "--short", "HEAD"], fallback="unknown")
    git_dirty = _run_cmd(["git", "status", "--porcelain"], fallback="")

    uptime_seconds = time.time() - _start_time
    uptime_hours = round(uptime_seconds / 3600, 2)

    return {
        "python_version": python_version,
        "node_version": node_version,
        "platform": platform.platform(),
        "architecture": platform.machine(),
        "git": {
            "branch": git_branch,
            "commit": git_commit,
            "dirty": len(git_dirty) > 0 if git_dirty else False,
        },
        "uptime": {
            "seconds": round(uptime_seconds),
            "hours": uptime_hours,
        },
    }


@router.post("/brain/interval")
async def update_brain_interval(
    body: BrainIntervalRequest,
    _=Depends(require_auth),
    settings=Depends(_get_settings),
):
    """Update auto-insight interval (in seconds)."""
    if body.interval < 10:
        raise HTTPException(
            status_code=400,
            detail="Interval must be at least 10 seconds",
        )
    if body.interval > 86400:
        raise HTTPException(
            status_code=400,
            detail="Interval must not exceed 86400 seconds (24 hours)",
        )

    old_interval = getattr(settings, "brain_interval", None)
    settings.brain_interval = body.interval
    log.info("Brain interval updated: %s -> %s seconds", old_interval, body.interval)

    return {
        "interval": settings.brain_interval,
        "previous": old_interval,
        "message": f"Auto-insight interval set to {body.interval}s",
    }
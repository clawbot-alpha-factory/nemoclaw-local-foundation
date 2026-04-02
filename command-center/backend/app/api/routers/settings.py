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


@router.get("/nvidia/health")
async def nvidia_health():
    """Live health check for NVIDIA NIM API models."""
    import httpx
    import sys
    from pathlib import Path

    # Load NVIDIA API key
    repo = Path(__file__).resolve().parents[4]
    sys.path.insert(0, str(repo))
    try:
        from lib.routing import get_api_key
        api_key = get_api_key("nvidia")
    except Exception:
        api_key = ""

    if not api_key:
        return {"status": "no_key", "models": {}}

    models = {
        "embed_1b": {"url": "https://integrate.api.nvidia.com/v1/embeddings", "model": "nvidia/llama-nemotron-embed-1b-v2", "payload": {"input": ["test"], "model": "nvidia/llama-nemotron-embed-1b-v2", "encoding_format": "float", "input_type": "passage"}},
        "rerank_1b": {"url": "https://ai.api.nvidia.com/v1/retrieval/nvidia/llama-nemotron-rerank-1b-v2/reranking", "model": "nvidia/llama-nemotron-rerank-1b-v2", "payload": {"model": "nvidia/llama-nemotron-rerank-1b-v2", "query": {"text": "test"}, "passages": [{"text": "hello"}]}},
        "safety_4b": {"url": "https://integrate.api.nvidia.com/v1/chat/completions", "model": "nvidia/nemotron-content-safety-reasoning-4b", "payload": {"model": "nvidia/nemotron-content-safety-reasoning-4b", "messages": [{"role": "user", "content": "test"}], "max_tokens": 5}},
        "nemotron_9b": {"url": "https://integrate.api.nvidia.com/v1/chat/completions", "model": "nvidia/nvidia-nemotron-nano-9b-v2", "payload": {"model": "nvidia/nvidia-nemotron-nano-9b-v2", "messages": [{"role": "user", "content": "hi"}], "max_tokens": 5}},
        "nemotron_30b": {"url": "https://integrate.api.nvidia.com/v1/chat/completions", "model": "nvidia/nemotron-3-nano-30b-a3b", "payload": {"model": "nvidia/nemotron-3-nano-30b-a3b", "messages": [{"role": "user", "content": "hi"}], "max_tokens": 5}},
    }

    results = {}
    async with httpx.AsyncClient(timeout=10.0) as client:
        for name, cfg in models.items():
            try:
                resp = await client.post(
                    cfg["url"],
                    headers={"Authorization": f"Bearer {api_key}"},
                    json=cfg["payload"],
                )
                results[name] = {
                    "status": "up" if resp.status_code == 200 else "error",
                    "code": resp.status_code,
                    "model": cfg["model"],
                }
            except Exception as e:
                results[name] = {"status": "down", "error": str(e), "model": cfg["model"]}

    up_count = sum(1 for r in results.values() if r["status"] == "up")
    return {"status": "healthy" if up_count >= 4 else "degraded", "up": up_count, "total": len(models), "models": results}
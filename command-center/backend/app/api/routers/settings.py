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

from app.auth import require_auth, get_active_token

log = logging.getLogger("cc.settings.api")

router = APIRouter(prefix="/api/settings", tags=["settings"])

_start_time = time.time()


class ThemeRequest(BaseModel):
    theme: str  # "light" or "dark"


class BrainIntervalRequest(BaseModel):
    interval: int  # seconds


# Provider → env var mapping for the API Keys panel
KEY_REGISTRY = [
    {"provider": "anthropic", "key_name": "ANTHROPIC_API_KEY"},
    {"provider": "openai", "key_name": "OPENAI_API_KEY"},
    {"provider": "google", "key_name": "GOOGLE_API_KEY"},
    {"provider": "apify", "key_name": "APIFY_API_TOKEN"},
    {"provider": "supabase", "key_name": "SUPABASE_ANON_KEY"},
    {"provider": "linkedin", "key_name": "LINKEDIN_CLIENT_ID"},
    {"provider": "meta", "key_name": "META_APP_ID"},
    {"provider": "youtube", "key_name": "YOUTUBE_API_KEY"},
    {"provider": "heygen", "key_name": "HEYGEN_API_KEY"},
    {"provider": "elevenlabs", "key_name": "ELEVENLABS_API_KEY"},
    {"provider": "resend", "key_name": "RESEND_API_KEY"},
    {"provider": "instantly", "key_name": "INSTANTLY_API_KEY"},
    {"provider": "langfuse", "key_name": "LANGFUSE_SECRET_KEY"},
]


def _mask_key(value: Optional[str]) -> Optional[str]:
    """Mask an API key for safe display: first4***...last3."""
    if not value:
        return None
    if len(value) < 10:
        return "****"
    return f"{value[:4]}***...{value[-3:]}"


def _load_env_keys() -> dict:
    """Load all env keys from config/.env via config_loader."""
    import sys
    from pathlib import Path
    repo = Path(__file__).resolve().parents[4]
    sys.path.insert(0, str(repo))
    from lib.config_loader import load_env
    return load_env()


# Module-level settings store (app.state.settings was never initialized)
_settings_store: dict = {"theme": "dark", "brain_interval": 300}


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
):
    """Return current system settings (token, theme, intervals)."""
    return {
        "token": get_active_token(),
        "theme": _settings_store["theme"],
        "intervals": {
            "brain": _settings_store["brain_interval"],
        },
    }


@router.get("/token")
async def get_token():
    """Return current active token (for auto-setup). No auth required."""
    token = get_active_token()
    return {"token": token}


@router.post("/theme")
async def set_theme(
    body: ThemeRequest,
    _=Depends(require_auth),
):
    """Set theme preference (light/dark)."""
    if body.theme not in ("light", "dark"):
        raise HTTPException(
            status_code=400,
            detail="Theme must be 'light' or 'dark'",
        )
    _settings_store["theme"] = body.theme
    log.info("Theme updated to: %s", body.theme)
    return {"theme": body.theme, "message": f"Theme set to {body.theme}"}


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

    old_interval = _settings_store["brain_interval"]
    _settings_store["brain_interval"] = body.interval
    log.info("Brain interval updated: %s -> %s seconds", old_interval, body.interval)

    return {
        "interval": body.interval,
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


# ─── API Keys ─────────────────────────────────────────────────────────────────


@router.get("/api-keys")
async def get_api_keys():
    """Return configured API keys with masked values."""
    env = _load_env_keys()
    keys = []
    for entry in KEY_REGISTRY:
        raw = env.get(entry["key_name"], "")
        configured = bool(raw)
        keys.append({
            "provider": entry["provider"],
            "configured": configured,
            "masked_key": _mask_key(raw) if configured else None,
            "last_tested": None,
            "status": "connected" if configured else "missing",
        })
    return {"keys": keys}


@router.post("/api-keys/{provider}/test")
def test_api_key(provider: str):
    """Test if a provider's API key is valid. Sync def so SDK calls run in threadpool."""
    registry_entry = next((e for e in KEY_REGISTRY if e["provider"] == provider), None)
    if not registry_entry:
        raise HTTPException(status_code=404, detail=f"Unknown provider: {provider}")

    env = _load_env_keys()
    raw_key = env.get(registry_entry["key_name"], "")
    if not raw_key:
        return {"provider": provider, "success": False, "error": "Key not configured"}

    try:
        if provider == "anthropic":
            import anthropic
            client = anthropic.Anthropic(api_key=raw_key)
            client.messages.create(
                model="claude-haiku-4-20250414",
                max_tokens=1,
                messages=[{"role": "user", "content": "hi"}],
            )
        elif provider == "openai":
            import openai
            client = openai.OpenAI(api_key=raw_key)
            client.models.list()
        else:
            # No cheap validation endpoint — key existence is sufficient
            return {"provider": provider, "success": True}
    except Exception as e:
        return {"provider": provider, "success": False, "error": str(e)}

    return {"provider": provider, "success": True}
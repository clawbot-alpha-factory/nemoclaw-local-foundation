"""
NemoClaw Execution Engine — Marketplace Router (P-8)

Discover, install, update, and uninstall skills from GitHub repos.

NEW FILE: command-center/backend/app/api/routers/marketplace.py
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from app.auth import require_auth

logger = logging.getLogger("cc.marketplace.api")

router = APIRouter(prefix="/api/marketplace", tags=["marketplace"])


class SourceAdd(BaseModel):
    url: str
    name: str = ""


def _svc(request: Request):
    svc = getattr(request.app.state, "skill_marketplace_service", None)
    if not svc:
        raise HTTPException(503, "SkillMarketplaceService not initialized")
    return svc


@router.get("/sources")
async def list_sources(_=Depends(require_auth), svc=Depends(_svc)):
    """List registered skill source repos."""
    sources = svc.get_sources()
    return {"total": len(sources), "sources": sources}


@router.post("/sources", status_code=201)
async def add_source(body: SourceAdd, _=Depends(require_auth), svc=Depends(_svc)):
    """Add a GitHub repo as a skill source."""
    if not body.url:
        raise HTTPException(400, "URL is required")
    return svc.add_source(body.url, body.name)


@router.get("/discover")
async def discover_skills(
    force: bool = Query(False, description="Force refresh (bypass cache)"),
    _=Depends(require_auth),
    svc=Depends(_svc),
):
    """Scan all source repos for available skills."""
    skills = svc.discover(force=force)
    return {"total": len(skills), "skills": skills}


@router.get("/preview/{skill_id}")
async def preview_skill(skill_id: str, _=Depends(require_auth), svc=Depends(_svc)):
    """Preview skill metadata without installing."""
    result = svc.preview(skill_id)
    if "error" in result:
        raise HTTPException(404, result["error"])
    return result


@router.post("/install/{skill_id}")
async def install_skill(skill_id: str, _=Depends(require_auth), svc=Depends(_svc)):
    """Validate and install a skill from the marketplace."""
    result = svc.install(skill_id)
    if result.get("status") == "error":
        raise HTTPException(400, result.get("detail", "Install failed"))
    return result


@router.post("/uninstall/{skill_id}")
async def uninstall_skill(skill_id: str, _=Depends(require_auth), svc=Depends(_svc)):
    """Soft-delete an installed marketplace skill."""
    result = svc.uninstall(skill_id)
    if result.get("status") == "error":
        raise HTTPException(400, result.get("detail", "Uninstall failed"))
    return result


@router.post("/update/{skill_id}")
async def update_skill(skill_id: str, _=Depends(require_auth), svc=Depends(_svc)):
    """Update an installed skill to latest version (backup + reinstall)."""
    result = svc.update(skill_id)
    if result.get("status") == "error":
        raise HTTPException(400, result.get("detail", "Update failed"))
    return result


@router.get("/updates")
async def check_updates(_=Depends(require_auth), svc=Depends(_svc)):
    """Check all installed skills for available updates."""
    updates = svc.check_updates()
    return {"total": len(updates), "updates": updates}


@router.get("/stats")
async def marketplace_stats(_=Depends(require_auth), svc=Depends(_svc)):
    """Marketplace statistics."""
    return svc.get_stats()

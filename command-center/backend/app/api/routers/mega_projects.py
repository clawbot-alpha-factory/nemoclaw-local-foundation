"""
NemoClaw Command Center — Mega Projects Router (E-13)
API for tier 3/4 mega-project orchestration.
"""

import logging
from typing import Optional, List

from fastapi import APIRouter, Depends, Query, HTTPException, Request
from pydantic import BaseModel, Field

from app.auth import require_auth

log = logging.getLogger("cc.mega_projects.api")

router = APIRouter(prefix="/api/mega-projects", tags=["mega-projects"])


# ── Request/Response Models ───────────────────────────────────────────


class MegaProjectCreate(BaseModel):
    name: str
    description: str
    template_id: str
    budget_usd: Optional[float] = None
    objectives: Optional[List[str]] = []
    timeline_weeks: Optional[int] = None


# ── Service dependency ────────────────────────────────────────────────


def _svc(request: Request):
    """Get MegaProjectService from app state."""
    svc = getattr(request.app.state, "mega_project_service", None)
    if not svc:
        raise HTTPException(status_code=503, detail="MegaProjectService not initialized")
    return svc


# ── Endpoints ─────────────────────────────────────────────────────────


@router.get("/templates")
async def list_templates(
    _=Depends(require_auth),
    svc=Depends(_svc),
):
    """List available mega project templates."""
    templates = svc.list_templates()
    return {"total": len(templates), "templates": templates}


@router.get("/templates/{template_id}")
async def get_template(
    template_id: str,
    _=Depends(require_auth),
    svc=Depends(_svc),
):
    """Get a single template with full details."""
    t = svc.get_template(template_id)
    if not t:
        raise HTTPException(status_code=404, detail=f"Template '{template_id}' not found")
    return t


@router.post("/", status_code=201)
async def create_mega_project(
    body: MegaProjectCreate,
    _=Depends(require_auth),
    svc=Depends(_svc),
):
    """Create a new mega project from a template."""
    mega = svc.create_mega_project(
        name=body.name,
        description=body.description,
        template_id=body.template_id,
        budget_usd=body.budget_usd or 0,
        objectives=body.objectives,
        timeline_weeks=body.timeline_weeks,
    )
    if not mega:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to create mega project — check template_id '{body.template_id}'",
        )
    return mega


@router.get("/")
async def list_mega_projects(
    status: Optional[str] = Query(None, description="planning/active/paused/completed/cancelled"),
    tier: Optional[int] = Query(None, description="Project tier (3 or 4)"),
    _=Depends(require_auth),
    svc=Depends(_svc),
):
    """List all mega projects with optional filters."""
    items = svc.list_mega_projects(status=status, tier=tier)
    return {"total": len(items), "items": items}


@router.get("/{project_id}")
async def get_mega_project(
    project_id: str,
    _=Depends(require_auth),
    svc=Depends(_svc),
):
    """Get a single mega project."""
    mega = svc.get_mega_project(project_id)
    if not mega:
        raise HTTPException(status_code=404, detail=f"Mega project '{project_id}' not found")
    return mega


@router.get("/{project_id}/dashboard")
async def get_dashboard(
    project_id: str,
    _=Depends(require_auth),
    svc=Depends(_svc),
):
    """Get dashboard view with progress, budget, and phase summary."""
    dashboard = svc.get_dashboard(project_id)
    if not dashboard:
        raise HTTPException(status_code=404, detail=f"Mega project '{project_id}' not found")
    return dashboard


@router.post("/{project_id}/pause")
async def pause_project(
    project_id: str,
    _=Depends(require_auth),
    svc=Depends(_svc),
):
    """Pause an active mega project."""
    mega = svc.pause_project(project_id)
    if not mega:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot pause project '{project_id}' — not found or not in pausable state",
        )
    return {"detail": "Project paused", "id": project_id, "status": mega["status"]}


@router.post("/{project_id}/resume")
async def resume_project(
    project_id: str,
    _=Depends(require_auth),
    svc=Depends(_svc),
):
    """Resume a paused mega project."""
    mega = svc.resume_project(project_id)
    if not mega:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot resume project '{project_id}' — not found or not paused",
        )
    return {"detail": "Project resumed", "id": project_id, "status": mega["status"]}


@router.post("/{project_id}/cancel")
async def cancel_project(
    project_id: str,
    _=Depends(require_auth),
    svc=Depends(_svc),
):
    """Cancel a mega project."""
    mega = svc.cancel_project(project_id)
    if not mega:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel project '{project_id}' — not found or already completed/cancelled",
        )
    return {"detail": "Project cancelled", "id": project_id, "status": mega["status"]}

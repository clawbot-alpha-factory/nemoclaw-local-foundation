"""
NemoClaw Command Center — Projects Router
"""

import logging
from typing import Optional, List

from fastapi import APIRouter, Depends, Query, HTTPException, Request
from pydantic import BaseModel, Field

from app.auth import require_auth

log = logging.getLogger("cc.projects.api")

router = APIRouter(prefix="/api/projects", tags=["projects"])


# --- Request/Response Models ---

class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None
    template_id: Optional[str] = None
    status: Optional[str] = "planning"
    priority: Optional[str] = "medium"
    tags: Optional[List[str]] = []
    metadata: Optional[dict] = {}


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    tags: Optional[List[str]] = None
    metadata: Optional[dict] = None


class MilestoneCreate(BaseModel):
    title: str
    description: Optional[str] = None
    due_date: Optional[str] = None
    status: Optional[str] = "pending"


# --- Service dependency ---

def _svc(request: Request):
    """Get ProjectService from app state."""
    svc = getattr(request.app.state, "project_service", None)
    if not svc:
        raise HTTPException(status_code=503, detail="ProjectService not initialized")
    return svc


# --- Endpoints ---

@router.get("/templates")
async def list_templates(
    _=Depends(require_auth),
    svc=Depends(_svc),
):
    """List available project templates."""
    templates = svc.list_templates()
    return {"total": len(templates), "templates": templates}


@router.get("/")
async def list_projects(
    status: Optional[str] = Query(None, description="planning/active/paused/completed/archived"),
    priority: Optional[str] = Query(None, description="critical/high/medium/low"),
    tag: Optional[str] = Query(None, description="Filter by tag"),
    search: Optional[str] = Query(None, description="Free-text search"),
    sort_by: Optional[str] = Query(None, description="Field to sort by"),
    order: Optional[str] = Query("asc", description="asc or desc"),
    limit: Optional[int] = Query(None, description="Max results"),
    offset: Optional[int] = Query(0, description="Offset for pagination"),
    _=Depends(require_auth),
    svc=Depends(_svc),
):
    """List all projects with optional filters."""
    projects = svc.list_projects(status=status, tag=tag)
    return {"total": len(projects), "projects": projects}


@router.post("/", status_code=201)
async def create_project(
    body: ProjectCreate,
    _=Depends(require_auth),
    svc=Depends(_svc),
):
    """Create a new project, optionally from a template."""
    if body.template_id:
        project = svc.create_from_template(
            template_key=body.template_id,
            name=body.name,
            description=body.description,
        )
    else:
        project = svc.create_project(
            name=body.name,
            description=body.description,
            status=body.status or "planning",
            tags=body.tags,
        )
    if not project:
        raise HTTPException(status_code=400, detail="Failed to create project")
    return project


@router.get("/{project_id}")
async def get_project(
    project_id: str,
    _=Depends(require_auth),
    svc=Depends(_svc),
):
    """Get a single project by ID."""
    project = svc.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    return project


@router.patch("/{project_id}")
async def update_project(
    project_id: str,
    body: ProjectUpdate,
    _=Depends(require_auth),
    svc=Depends(_svc),
):
    """Update an existing project."""
    existing = svc.get_project(project_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")

    updates = body.dict(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    project = svc.update_project(project_id, updates)
    if not project:
        raise HTTPException(status_code=500, detail="Failed to update project")
    return project


@router.delete("/{project_id}")
async def delete_project(
    project_id: str,
    _=Depends(require_auth),
    svc=Depends(_svc),
):
    """Delete a project by ID."""
    existing = svc.get_project(project_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")

    success = svc.delete_project(project_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete project")
    return {"detail": f"Project '{project_id}' deleted", "id": project_id}


@router.get("/{project_id}/skills")
async def project_skills(
    project_id: str,
    _=Depends(require_auth),
    svc=Depends(_svc),
):
    """List skills linked to a project."""
    existing = svc.get_project(project_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")

    skills = svc.get_skills_for_project(project_id)
    return {"project_id": project_id, "total": len(skills), "skills": skills}


@router.post("/{project_id}/milestones", status_code=201)
async def add_milestone(
    project_id: str,
    body: MilestoneCreate,
    _=Depends(require_auth),
    svc=Depends(_svc),
):
    """Add a milestone to a project."""
    existing = svc.get_project(project_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")

    milestone = svc.add_milestone(
        project_id=project_id,
        title=body.title,
        description=body.description,
        due_date=body.due_date,
        status=body.status,
    )
    if not milestone:
        raise HTTPException(status_code=500, detail="Failed to add milestone")
    return milestone
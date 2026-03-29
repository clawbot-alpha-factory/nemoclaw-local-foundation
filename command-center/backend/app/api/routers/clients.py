"""
NemoClaw Command Center — Clients Router
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException, Request
from pydantic import BaseModel

from app.auth import require_auth

log = logging.getLogger("cc.clients.api")

router = APIRouter(prefix="/api/clients", tags=["clients"])


class ClientCreateRequest(BaseModel):
    name: str
    email: Optional[str] = None
    company: Optional[str] = None
    phone: Optional[str] = None
    status: Optional[str] = "active"
    notes: Optional[str] = None
    tags: Optional[list[str]] = []
    metadata: Optional[dict] = {}


class ClientUpdateRequest(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    company: Optional[str] = None
    phone: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None
    tags: Optional[list[str]] = None
    metadata: Optional[dict] = None


class DeliverableCreateRequest(BaseModel):
    title: str
    description: Optional[str] = None
    type: Optional[str] = None
    status: Optional[str] = "pending"
    due_date: Optional[str] = None
    project_id: Optional[str] = None
    metadata: Optional[dict] = {}


def _svc(request: Request):
    """Get ClientService from app state."""
    svc = getattr(request.app.state, "client_service", None)
    if not svc:
        raise HTTPException(status_code=503, detail="ClientService not initialized")
    return svc


@router.get("/health")
async def client_health_scores(
    _=Depends(require_auth),
    svc=Depends(_svc),
):
    """Client health scores overview."""
    scores = svc.compute_all_health_scores()
    return {"total": len(scores), "health_scores": scores}


@router.get("/")
async def list_clients(
    status: Optional[str] = Query(None, description="active/inactive/archived"),
    company: Optional[str] = Query(None),
    tag: Optional[str] = Query(None),
    search: Optional[str] = Query(None, description="Free-text search"),
    sort_by: Optional[str] = Query(None, description="Field to sort by"),
    sort_order: Optional[str] = Query("asc", description="asc or desc"),
    limit: Optional[int] = Query(50, ge=1, le=500),
    offset: Optional[int] = Query(0, ge=0),
    _=Depends(require_auth),
    svc=Depends(_svc),
):
    """List all clients with optional filters."""
    result = svc.list_clients(status=status, tag=tag)
    return result


@router.post("/", status_code=201)
async def create_client(
    body: ClientCreateRequest,
    _=Depends(require_auth),
    svc=Depends(_svc),
):
    """Create a new client."""
    client = svc.create_client(name=body.name, company=body.company, email=body.email, phone=body.phone, status=body.status or "prospect")
    return {"client": client}


@router.get("/{client_id}")
async def get_client(
    client_id: str,
    _=Depends(require_auth),
    svc=Depends(_svc),
):
    """Get single client detail."""
    client = svc.get_client(client_id)
    if not client:
        raise HTTPException(status_code=404, detail=f"Client '{client_id}' not found")
    return {"client": client}


@router.patch("/{client_id}")
async def update_client(
    client_id: str,
    body: ClientUpdateRequest,
    _=Depends(require_auth),
    svc=Depends(_svc),
):
    """Update client fields."""
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    client = svc.update_client(client_id, updates)
    if not client:
        raise HTTPException(status_code=404, detail=f"Client '{client_id}' not found")
    return {"client": client}


@router.get("/{client_id}/projects")
async def client_projects(
    client_id: str,
    status: Optional[str] = Query(None),
    _=Depends(require_auth),
    svc=Depends(_svc),
):
    """Get projects belonging to a client."""
    client = svc.get_client(client_id)
    if not client:
        raise HTTPException(status_code=404, detail=f"Client '{client_id}' not found")
    projects = svc.get_client_projects(client_id)
    return {"client_id": client_id, "total": len(projects), "projects": projects}


@router.get("/{client_id}/deliverables")
async def client_deliverables(
    client_id: str,
    status: Optional[str] = Query(None),
    type: Optional[str] = Query(None),
    _=Depends(require_auth),
    svc=Depends(_svc),
):
    """Get deliverables for a client."""
    client = svc.get_client(client_id)
    if not client:
        raise HTTPException(status_code=404, detail=f"Client '{client_id}' not found")
    deliverables = svc.list_deliverables(client_id=client_id)
    return {"client_id": client_id, "total": len(deliverables), "deliverables": deliverables}


@router.post("/{client_id}/deliverables", status_code=201)
async def add_deliverable(
    client_id: str,
    body: DeliverableCreateRequest,
    _=Depends(require_auth),
    svc=Depends(_svc),
):
    """Add a deliverable to a client."""
    client = svc.get_client(client_id)
    if not client:
        raise HTTPException(status_code=404, detail=f"Client '{client_id}' not found")
    deliverable = svc.create_deliverable(client_id=client_id, **body.model_dump())
    return {"deliverable": deliverable}
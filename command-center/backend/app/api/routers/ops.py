"""
NemoClaw Command Center — Operations Router (CC-Ops)
"""

import logging
from typing import Optional, List

from fastapi import APIRouter, Depends, Query, HTTPException, Request
from pydantic import BaseModel

from app.auth import require_auth

log = logging.getLogger("cc.ops.api")

router = APIRouter(prefix="/api/ops", tags=["operations"])


# ── Request / Response Models ────────────────────────────────────────────────

class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    agent: Optional[str] = None
    skill: Optional[str] = None
    priority: Optional[str] = "medium"
    status: Optional[str] = "pending"
    budget_limit: Optional[float] = None
    metadata: Optional[dict] = {}


class TaskUpdate(BaseModel):
    status: Optional[str] = None
    agent: Optional[str] = None
    skill: Optional[str] = None
    priority: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    budget_limit: Optional[float] = None
    metadata: Optional[dict] = None


# ── Service dependency ───────────────────────────────────────────────────────

def _svc(request: Request):
    """Get OpsService from app state."""
    svc = getattr(request.app.state, "ops_service", None)
    if not svc:
        raise HTTPException(status_code=503, detail="OpsService not initialized")
    return svc


# ── GET /api/operations/dashboard ────────────────────────────────────────────

@router.get("/dashboard")
async def get_dashboard(
    _=Depends(require_auth),
    svc=Depends(_svc),
):
    """Summary cards: task counts by status, budget overview, recent activity."""
    try:
        dashboard = svc.get_dashboard()
        return dashboard
    except Exception as e:
        log.error("Failed to build dashboard: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Dashboard error: {str(e)}")


# ── GET /api/operations/tasks ────────────────────────────────────────────────

@router.get("/tasks")
async def list_tasks(
    status: Optional[str] = Query(None, description="pending/in_progress/completed/failed/cancelled"),
    agent: Optional[str] = Query(None, description="Filter by assigned agent"),
    skill: Optional[str] = Query(None, description="Filter by skill"),
    priority: Optional[str] = Query(None, description="critical/high/medium/low"),
    search: Optional[str] = Query(None, description="Free-text search in title/description"),
    sort_by: Optional[str] = Query("created_at", description="Field to sort by"),
    sort_order: Optional[str] = Query("desc", description="asc or desc"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=200, description="Items per page"),
    _=Depends(require_auth),
    svc=Depends(_svc),
):
    """List tasks with optional filters, search, sorting, and pagination."""
    try:
        result = svc.get_tasks(status=status, agent_id=agent, priority=priority, skill_id=skill)
        return result
    except Exception as e:
        log.error("Failed to list tasks: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Task listing error: {str(e)}")


# ── POST /api/operations/tasks ───────────────────────────────────────────────

@router.post("/tasks", status_code=201)
async def create_task(
    body: TaskCreate,
    _=Depends(require_auth),
    svc=Depends(_svc),
):
    """Create a new task."""
    try:
        task = svc.create_task(title=body.title, description=body.description, agent_id=body.assigned_agent if hasattr(body, "assigned_agent") else getattr(body, "agent", None), priority=getattr(body, "priority", "medium"))
        log.info("Task created: %s (agent=%s, skill=%s)", task.get("id"), body.agent, body.skill)
        return task
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log.error("Failed to create task: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Task creation error: {str(e)}")


# ── PATCH /api/operations/tasks/{task_id} ────────────────────────────────────

@router.patch("/tasks/{task_id}")
async def update_task(
    task_id: str,
    body: TaskUpdate,
    _=Depends(require_auth),
    svc=Depends(_svc),
):
    """Update task status, assignment, or other fields."""
    updates = body.dict(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    try:
        task = svc.update_task(task_id=task_id, updates=updates)
        if task is None:
            raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
        log.info("Task updated: %s fields=%s", task_id, list(updates.keys()))
        return task
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log.error("Failed to update task %s: %s", task_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Task update error: {str(e)}")


# ── GET /api/operations/budget ───────────────────────────────────────────────

@router.get("/budget")
async def get_budget(
    period: Optional[str] = Query("30d", description="Time period: 7d/30d/90d/all"),
    provider: Optional[str] = Query(None, description="Filter by provider"),
    _=Depends(require_auth),
    svc=Depends(_svc),
):
    """Budget breakdown by provider with spend trends."""
    try:
        budget = svc.get_budget_overview()
        return budget
    except Exception as e:
        log.error("Failed to fetch budget: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Budget error: {str(e)}")


# ── GET /api/operations/activity ─────────────────────────────────────────────

@router.get("/activity")
async def get_activity(
    limit: int = Query(50, ge=1, le=500, description="Number of recent events"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    agent: Optional[str] = Query(None, description="Filter by agent"),
    _=Depends(require_auth),
    svc=Depends(_svc),
):
    """Recent activity feed across operations."""
    try:
        activity = svc.get_activity_feed(limit=limit)
        return activity
    except Exception as e:
        log.error("Failed to fetch activity: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Activity feed error: {str(e)}")
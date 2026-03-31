"""
NemoClaw Execution Engine — Activity Router (P-2)

Unified activity timeline endpoints: query, stats, categories.
POST to append, GET to query with multi-axis filtering.

NEW FILE: command-center/backend/app/api/routers/activity.py
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app.auth import require_auth

logger = logging.getLogger("cc.activity.api")

router = APIRouter(prefix="/api/activity", tags=["activity"])


# ── Request Models ──────────────────────────────────────────────────

class ActivityAppend(BaseModel):
    category: str
    action: str
    actor_type: str = "system"
    actor_id: str = "system"
    entity_type: str = ""
    entity_id: str = ""
    summary: str = ""
    details: Optional[dict[str, Any]] = None
    trace_id: str = ""


# ── Service dependency ──────────────────────────────────────────────

def _svc(request: Request):
    svc = getattr(request.app.state, "activity_log_service", None)
    if not svc:
        raise HTTPException(status_code=503, detail="ActivityLogService not initialized")
    return svc


# ── Endpoints ───────────────────────────────────────────────────────

@router.get("/categories")
async def get_categories(
    _=Depends(require_auth),
    svc=Depends(_svc),
):
    """List valid activity categories with descriptions."""
    categories = svc.get_categories()
    return {"total": len(categories), "categories": categories}


@router.get("/stats")
async def get_stats(
    _=Depends(require_auth),
    svc=Depends(_svc),
):
    """Activity stats: counts by category, actor, and hourly for last 24h."""
    return svc.get_stats()


@router.get("/")
async def query_activity(
    after: Optional[str] = Query(None, description="ISO 8601 timestamp — return entries after this"),
    before: Optional[str] = Query(None, description="ISO 8601 timestamp — return entries before this"),
    category: Optional[str] = Query(None, description="execution, protocol, bridge, lifecycle, system, memory"),
    actor: Optional[str] = Query(None, description="Filter by actor_id (agent_id, system, etc.)"),
    entity_type: Optional[str] = Query(None, description="skill, project, deal, bridge, task, chain, client"),
    entity_id: Optional[str] = Query(None, description="Filter by entity ID"),
    action: Optional[str] = Query(None, description="Filter by action string"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    _=Depends(require_auth),
    svc=Depends(_svc),
):
    """Query the activity timeline with filters and pagination. Newest-first."""
    try:
        return svc.query(
            after=after,
            before=before,
            category=category,
            actor_id=actor,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            limit=limit,
            offset=offset,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/", status_code=201)
async def append_activity(
    body: ActivityAppend,
    _=Depends(require_auth),
    svc=Depends(_svc),
):
    """Append an activity entry to the timeline."""
    try:
        entry = await svc.append(
            category=body.category,
            action=body.action,
            actor_type=body.actor_type,
            actor_id=body.actor_id,
            entity_type=body.entity_type,
            entity_id=body.entity_id,
            summary=body.summary,
            details=body.details,
            trace_id=body.trace_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Disk write failed: {e}")

    return entry

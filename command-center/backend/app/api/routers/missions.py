"""
NemoClaw Command Center — Missions Router

5 endpoints for Asana-backed mission lifecycle management.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from app.auth import require_auth

from app.domain.mission_models import (
    HeartbeatRequest,
    MissionAdvanceRequest,
    MissionCreateRequest,
)

logger = logging.getLogger("cc.api.missions")

router = APIRouter(prefix="/api/missions", tags=["missions"], dependencies=[Depends(require_auth)])


def _svc(request: Request):
    svc = getattr(request.app.state, "mission_manager_service", None)
    if not svc:
        raise HTTPException(503, "MissionManagerService not initialized")
    return svc


@router.post("")
async def create_mission(body: MissionCreateRequest, request: Request) -> dict[str, Any]:
    """Create a new mission backed by an Asana project."""
    svc = _svc(request)
    try:
        mission = await svc.create_mission(body.goal, body.lead_agent)
        return {
            "id": mission.id,
            "goal": mission.goal,
            "phase": mission.phase.value,
            "asana_project_url": mission.asana_project_url,
        }
    except Exception as e:
        logger.error("Failed to create mission: %s", e)
        raise HTTPException(500, str(e))


@router.get("")
async def list_missions(request: Request) -> dict[str, Any]:
    """List all missions."""
    svc = _svc(request)
    missions = svc.list_missions()
    return {"total": len(missions), "missions": missions}


@router.get("/{mission_id}")
async def get_mission(mission_id: str, request: Request) -> dict[str, Any]:
    """Get mission details including Asana link."""
    svc = _svc(request)
    try:
        return svc.get_mission(mission_id)
    except ValueError:
        raise HTTPException(404, f"Mission not found: {mission_id}")


@router.post("/{mission_id}/advance")
async def advance_phase(mission_id: str, body: MissionAdvanceRequest, request: Request) -> dict[str, Any]:
    """Advance mission to next phase."""
    svc = _svc(request)
    try:
        mission = await svc.advance_phase(mission_id, body.to_phase)
        return {
            "id": mission.id,
            "phase": mission.phase.value,
            "updated_at": mission.updated_at.isoformat(),
        }
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/{mission_id}/heartbeat")
async def heartbeat(mission_id: str, body: HeartbeatRequest, request: Request) -> dict[str, Any]:
    """Post a heartbeat comment on the mission's active task."""
    svc = _svc(request)
    try:
        return await svc.heartbeat(mission_id, body.agent_id, body.message)
    except ValueError:
        raise HTTPException(404, f"Mission not found: {mission_id}")

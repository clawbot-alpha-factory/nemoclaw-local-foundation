"""
NemoClaw Command Center — Skills Router (CC-5)
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException, Request
from pydantic import BaseModel

from app.auth import require_auth

log = logging.getLogger("cc.skills.api")

router = APIRouter(prefix="/api/skills", tags=["skills"])


class DryRunRequest(BaseModel):
    inputs: dict = {}


def _svc(request: Request):
    """Get SkillService from app state."""
    svc = getattr(request.app.state, "skill_service", None)
    if not svc:
        raise HTTPException(status_code=503, detail="SkillService not initialized")
    return svc


@router.get("/")
async def list_skills(
    status: Optional[str] = Query(None, description="built or registered"),
    domain: Optional[str] = Query(None),
    skill_type: Optional[str] = Query(None),
    agent: Optional[str] = Query(None),
    priority: Optional[str] = Query(None, description="critical/high/medium/low"),
    health: Optional[str] = Query(None, description="healthy/missing_dependencies/misconfigured/unused/not_built"),
    search: Optional[str] = Query(None, description="Free-text search"),
    _=Depends(require_auth),
    svc=Depends(_svc),
):
    """List all skills with optional filters."""
    catalog = svc.get_catalog(status, domain, skill_type, agent, priority, health, search)
    return {"total": len(catalog), "skills": catalog}


@router.get("/stats")
async def skill_stats(_=Depends(require_auth), svc=Depends(_svc)):
    """Summary counts by status, domain, priority, health, agent."""
    return svc.get_stats()


@router.get("/graph")
async def skill_graph(_=Depends(require_auth), svc=Depends(_svc)):
    """Dependency graph: nodes, edges, risk detection."""
    return svc.get_graph()


@router.get("/agents/{agent_id}")
async def skills_by_agent(agent_id: str, _=Depends(require_auth), svc=Depends(_svc)):
    """Skills assigned to a specific agent."""
    result = svc.get_by_agent(agent_id)
    if result["total"] == 0:
        raise HTTPException(status_code=404, detail=f"No skills found for agent '{agent_id}'")
    return result


@router.get("/{skill_id}")
async def get_skill(skill_id: str, _=Depends(require_auth), svc=Depends(_svc)):
    """Full detail for a single skill."""
    skill = svc.get_skill(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_id}' not found")
    return skill


@router.post("/{skill_id}/dry-run")
async def dry_run_skill(
    skill_id: str,
    body: DryRunRequest,
    _=Depends(require_auth),
    svc=Depends(_svc),
):
    """Validate skill inputs and show dependency chain without executing."""
    result = svc.dry_run(skill_id, body.inputs)
    if "error" in result and "input_schema" not in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.post("/reload")
async def reload_skills(_=Depends(require_auth), svc=Depends(_svc)):
    """Hot-reload all skills from disk."""
    svc.reload()
    stats = svc.get_stats()
    return {"status": "reloaded", "total": stats["total"], "by_status": stats["by_status"]}

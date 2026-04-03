"""
NemoClaw Execution Engine — Skill Wiring Router (E-9)

6 endpoints for agent-skill mapping and chain execution.

NEW FILE: command-center/backend/app/api/routers/skill_wiring.py
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from app.auth import require_auth

logger = logging.getLogger("cc.api.wiring")

router = APIRouter(prefix="/api/skill-wiring", tags=["skill-wiring"], dependencies=[Depends(require_auth)])


def _get_mapping(request: Request):
    svc = getattr(request.app.state, "skill_agent_mapping", None)
    if svc is None:
        raise HTTPException(503, "SkillAgentMappingService not initialized")
    return svc


def _get_chain_wiring(request: Request):
    svc = getattr(request.app.state, "skill_chain_wiring", None)
    if svc is None:
        raise HTTPException(503, "SkillChainWiringService not initialized")
    return svc


@router.get("/agent/{agent_id}/skills")
async def get_agent_skills(agent_id: str, request: Request) -> dict[str, Any]:
    """Get all skills assigned to an agent."""
    svc = _get_mapping(request)
    skills = svc.get_agent_skills(agent_id)
    return {"agent": agent_id, "skills": skills, "count": len(skills)}


@router.get("/skill/{skill_id}/agents")
async def get_skill_agents(skill_id: str, request: Request) -> dict[str, Any]:
    """Get all agents that can execute a skill."""
    svc = _get_mapping(request)
    agents = svc.get_skill_agents(skill_id)
    return {"skill": skill_id, "agents": agents, "shared": len(agents) > 1}


@router.get("/stats")
async def get_mapping_stats(request: Request) -> dict[str, Any]:
    """Get mapping + chain stats."""
    mapping = _get_mapping(request)
    chain = _get_chain_wiring(request)
    return {
        "mapping": mapping.get_stats(),
        "chains": chain.get_stats(),
    }


@router.get("/chains")
async def get_chains(request: Request) -> dict[str, Any]:
    """Get all chain definitions."""
    svc = _get_chain_wiring(request)
    return {"chains": svc.get_chains()}


@router.get("/analyzer-routes")
async def get_analyzer_routes(request: Request) -> dict[str, Any]:
    """Get analyzer → skill routing map."""
    svc = _get_chain_wiring(request)
    return {"routes": svc.get_analyzer_routes()}


class ChainExecuteRequest(BaseModel):
    chain: str
    inputs: dict[str, Any] = {}


@router.post("/chains/execute")
async def execute_chain(body: ChainExecuteRequest, request: Request) -> dict[str, Any]:
    """Execute a skill chain."""
    svc = _get_chain_wiring(request)
    result = await svc.execute_chain(body.chain, body.inputs)
    return result

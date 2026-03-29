"""
State API router.

Provides REST endpoints for the aggregated system state.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ..auth import require_auth
from ..models import SystemState
from ..state_aggregator import aggregator

router = APIRouter(prefix="/api/state", tags=["state"])


@router.get("", response_model=SystemState)
async def get_state(_: str = Depends(require_auth)) -> SystemState:
    """Get the current aggregated system state."""
    return aggregator.state


@router.get("/skills")
async def get_skills(_: str = Depends(require_auth)):
    """Get skills summary."""
    return aggregator.state.skills


@router.get("/agents")
async def get_agents(_: str = Depends(require_auth)):
    """Get agents summary."""
    return aggregator.state.agents


@router.get("/ma-systems")
async def get_ma_systems(_: str = Depends(require_auth)):
    """Get multi-agent systems summary."""
    return aggregator.state.ma_systems


@router.get("/bridges")
async def get_bridges(_: str = Depends(require_auth)):
    """Get bridges summary."""
    return aggregator.state.bridges


@router.get("/budget")
async def get_budget(_: str = Depends(require_auth)):
    """Get budget summary."""
    return aggregator.state.budget


@router.get("/health")
async def get_health(_: str = Depends(require_auth)):
    """Get health summary."""
    return aggregator.state.health


@router.get("/validation")
async def get_validation(_: str = Depends(require_auth)):
    """Get validation summary."""
    return aggregator.state.validation


@router.post("/refresh", response_model=SystemState)
async def refresh_state(_: str = Depends(require_auth)) -> SystemState:
    """Force an immediate state rescan."""
    return await aggregator.force_scan()

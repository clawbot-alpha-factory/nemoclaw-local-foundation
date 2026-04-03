"""
CEO Review Gate API — E-4d

Endpoints for querying CEO review decisions, stats, and phase gate validation.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app.auth import require_auth

router = APIRouter(prefix="/api/ceo-review", tags=["ceo-review"])


def _svc(request: Request):
    svc = getattr(request.app.state, "ceo_reviewer_service", None)
    if not svc:
        raise HTTPException(status_code=503, detail="CEOReviewerService not initialized")
    return svc


# ── Models ────────────────────────────────────────────────────────────


class PhaseGateRequest(BaseModel):
    mission_id: str
    from_phase: str
    to_phase: str
    tasks: list[dict] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)


class SimulateReviewRequest(BaseModel):
    action_type: str
    agent_id: str = "unknown"
    estimated_cost: float = 0.0


# ── Endpoints ─────────────────────────────────────────────────────────


@router.get("/log")
async def get_review_log(
    limit: int = Query(50, ge=1, le=500),
    _=Depends(require_auth),
    svc=Depends(_svc),
):
    """Return recent CEO review decisions."""
    log = svc.get_review_log(limit=limit)
    return {"items": log, "total": len(log)}


@router.get("/stats")
async def get_review_stats(
    _=Depends(require_auth),
    svc=Depends(_svc),
):
    """Return aggregate review statistics."""
    return svc.get_stats()


@router.post("/simulate")
async def simulate_review(
    body: SimulateReviewRequest,
    _=Depends(require_auth),
    svc=Depends(_svc),
):
    """Check whether an action would trigger CEO review (dry-run)."""
    would_review = svc.should_review(body.action_type, body.agent_id, body.estimated_cost)
    return {
        "would_review": would_review,
        "action_type": body.action_type,
        "agent_id": body.agent_id,
        "estimated_cost": body.estimated_cost,
    }


@router.post("/phase-gate")
async def validate_phase_gate(
    body: PhaseGateRequest,
    _=Depends(require_auth),
    svc=Depends(_svc),
):
    """Validate a workflow phase transition."""
    result = svc.validate_phase_gate(
        mission_id=body.mission_id,
        from_phase=body.from_phase,
        to_phase=body.to_phase,
        tasks=body.tasks,
        blockers=body.blockers,
    )
    return {
        "passed": result.passed,
        "blockers": result.blockers,
        "checked_at": result.checked_at,
    }

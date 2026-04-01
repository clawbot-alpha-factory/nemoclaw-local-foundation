"""
NemoClaw Command Center — Skill Request Router
Agent-initiated skill request workflow API.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.auth import require_auth

log = logging.getLogger("cc.skill_requests.api")

router = APIRouter(prefix="/api/skill-requests", tags=["skill-requests"])


class SkillRequestCreate(BaseModel):
    requesting_agent: str
    capability_needed: str
    context: str
    priority: str = "medium"


class SkillRequestReview(BaseModel):
    reviewer_agent: str
    approved: bool
    notes: str = ""
    rejection_reason: str = ""


def _svc(request: Request):
    svc = getattr(request.app.state, "skill_request_service", None)
    if not svc:
        raise HTTPException(status_code=503, detail="SkillRequestService not initialized")
    return svc


@router.get("/", dependencies=[Depends(require_auth)])
async def list_requests(request: Request):
    svc = _svc(request)
    return {"requests": [vars(r) for r in svc.get_all()], "stats": svc.get_stats()}


@router.get("/pending", dependencies=[Depends(require_auth)])
async def list_pending(request: Request):
    svc = _svc(request)
    return {"requests": [vars(r) for r in svc.get_pending()]}


@router.post("/", dependencies=[Depends(require_auth)])
async def create_request(body: SkillRequestCreate, request: Request):
    svc = _svc(request)
    request_id = svc.submit_request(
        body.requesting_agent, body.capability_needed, body.context, body.priority
    )
    return {"request_id": request_id, "status": "pending"}


@router.get("/{request_id}", dependencies=[Depends(require_auth)])
async def get_request(request_id: str, request: Request):
    svc = _svc(request)
    req = svc.get_request(request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    return vars(req)


@router.post("/{request_id}/review", dependencies=[Depends(require_auth)])
async def review_request(request_id: str, body: SkillRequestReview, request: Request):
    svc = _svc(request)
    req, error = svc.review_request(
        request_id, body.reviewer_agent, body.approved, body.notes, body.rejection_reason
    )
    if error:
        raise HTTPException(status_code=404, detail=error)
    return vars(req)

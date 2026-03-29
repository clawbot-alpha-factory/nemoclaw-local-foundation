"""
NemoClaw Command Center — Approvals Router
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException, Request
from pydantic import BaseModel

from app.auth import require_auth

log = logging.getLogger("cc.approvals.api")

router = APIRouter(prefix="/api/approvals", tags=["approvals"])


class ApprovalCreateRequest(BaseModel):
    title: str
    description: str = ""
    category: str = "general"
    priority: str = "medium"
    requested_by: str = ""
    metadata: dict = {}


class ApproveRequest(BaseModel):
    notes: str = ""
    approved_by: str = ""


class RejectRequest(BaseModel):
    reason: str
    rejected_by: str = ""


class EscalateRequest(BaseModel):
    escalate_to: str
    reason: str = ""
    escalated_by: str = ""


def _svc(request: Request):
    """Get ApprovalService from app state."""
    svc = getattr(request.app.state, "approval_service", None)
    if not svc:
        raise HTTPException(status_code=503, detail="ApprovalService not initialized")
    return svc


@router.get("/")
async def list_approvals(
    status: Optional[str] = Query(None, description="pending/approved/rejected/escalated"),
    priority: Optional[str] = Query(None, description="critical/high/medium/low"),
    category: Optional[str] = Query(None, description="Filter by category"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    _=Depends(require_auth),
    svc=Depends(_svc),
):
    """List approvals with optional filters."""
    try:
        results = svc.list_all(status=status, priority=priority, category=category)
        return {
            "total": len(results),
            "approvals": results,
            "limit": limit,
            "offset": offset,
        }
    except Exception as e:
        log.error("Failed to list approvals: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/")
async def create_approval(
    body: ApprovalCreateRequest,
    _=Depends(require_auth),
    svc=Depends(_svc),
):
    """Create a new approval request."""
    try:
        approval = svc.create(title=body.title, description=body.description, requested_by=body.requested_by, priority=body.priority, category=body.category)
        return {"status": "created", "approval": approval}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log.error("Failed to create approval: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/queue")
async def approval_queue(
    limit: int = Query(50, ge=1, le=500),
    _=Depends(require_auth),
    svc=Depends(_svc),
):
    """Get pending approvals sorted by priority (critical first)."""
    try:
        queue = svc.get_queue()
        return {
            "total": len(queue),
            "queue": queue,
        }
    except Exception as e:
        log.error("Failed to get approval queue: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/audit")
async def audit_trail(
    approval_id: Optional[str] = Query(None, description="Filter by approval ID"),
    action: Optional[str] = Query(None, description="Filter by action type"),
    actor: Optional[str] = Query(None, description="Filter by actor"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    _=Depends(require_auth),
    svc=Depends(_svc),
):
    """Get audit trail for approvals."""
    try:
        trail = svc.get_audit_trail(approval_id=approval_id, action=action, actor=actor, limit=limit)
        return {"total": len(trail), "entries": trail}
    except Exception as e:
        log.error("Failed to get audit trail: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{approval_id}")
async def get_approval(
    approval_id: str,
    _=Depends(require_auth),
    svc=Depends(_svc),
):
    """Get single approval detail."""
    try:
        approval = svc.get(approval_id)
        if not approval:
            raise HTTPException(status_code=404, detail=f"Approval '{approval_id}' not found")
        return {"approval": approval}
    except HTTPException:
        raise
    except Exception as e:
        log.error("Failed to get approval %s: %s", approval_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{approval_id}/approve")
async def approve_approval(
    approval_id: str,
    body: ApproveRequest,
    _=Depends(require_auth),
    svc=Depends(_svc),
):
    """Approve an approval request with optional notes."""
    try:
        result = svc.approve(
            approval_id=approval_id,
            notes=body.notes,
            approved_by=body.approved_by,
        )
        if not result:
            raise HTTPException(status_code=404, detail=f"Approval '{approval_id}' not found")
        return {"status": "approved", "approval": result}
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log.error("Failed to approve %s: %s", approval_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{approval_id}/reject")
async def reject_approval(
    approval_id: str,
    body: RejectRequest,
    _=Depends(require_auth),
    svc=Depends(_svc),
):
    """Reject an approval request with a reason."""
    try:
        result = svc.reject(
            approval_id=approval_id,
            reason=body.reason,
            rejected_by=body.rejected_by,
        )
        if not result:
            raise HTTPException(status_code=404, detail=f"Approval '{approval_id}' not found")
        return {"status": "rejected", "approval": result}
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log.error("Failed to reject %s: %s", approval_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{approval_id}/escalate")
async def escalate_approval(
    approval_id: str,
    body: EscalateRequest,
    _=Depends(require_auth),
    svc=Depends(_svc),
):
    """Escalate an approval request to a higher authority."""
    try:
        result = svc.escalate(
            approval_id=approval_id,
            escalate_to=body.escalate_to,
            reason=body.reason,
            escalated_by=body.escalated_by,
        )
        if not result:
            raise HTTPException(status_code=404, detail=f"Approval '{approval_id}' not found")
        return {"status": "escalated", "approval": result}
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log.error("Failed to escalate %s: %s", approval_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
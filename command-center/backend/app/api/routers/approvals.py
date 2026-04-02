"""
NemoClaw Command Center — Approvals Router (CC-9)

19 endpoints serving the Approvals tab:
  Queue, Blockers, History, Audit views + CRUD + bulk operations.

Response shapes match the frontend contract in approvals-api.ts.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException, Request
from pydantic import BaseModel, Field

from app.auth import require_auth

log = logging.getLogger("cc.approvals.api")

router = APIRouter(prefix="/api/approvals", tags=["approvals"])


# ── Request Models ────────────────────────────────────────────────────

class ApprovalCreateRequest(BaseModel):
    title: str
    description: str = ""
    category: str = "general"
    priority: str = "medium"
    requester: str = ""
    assignee: str = ""
    metadata: dict = {}


class ApproveRequest(BaseModel):
    notes: str = ""


class RejectRequest(BaseModel):
    reason: str


class EscalateRequest(BaseModel):
    escalated_to: str
    notes: str = ""


class BulkApproveRequest(BaseModel):
    ids: list[str] = Field(..., min_length=1)
    notes: str = "Bulk approved"


class BulkRejectRequest(BaseModel):
    ids: list[str] = Field(..., min_length=1)
    reason: str = "Bulk rejected"


# ── Service Injection ─────────────────────────────────────────────────

def _svc(request: Request):
    """Get ApprovalService from app state."""
    svc = getattr(request.app.state, "approval_service", None)
    if not svc:
        raise HTTPException(status_code=503, detail="ApprovalService not initialized")
    return svc


# ── 1. List Approvals ─────────────────────────────────────────────────
# GET /api/approvals/
# Frontend expects: { items: Approval[], total: number }

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
        page = results[offset:offset + limit]
        return {"items": page, "total": len(results)}
    except Exception as e:
        log.error("Failed to list approvals: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ── 2. Create Approval ───────────────────────────────────────────────
# POST /api/approvals/
# Frontend expects: flat Approval object

@router.post("/")
async def create_approval(
    body: ApprovalCreateRequest,
    _=Depends(require_auth),
    svc=Depends(_svc),
):
    """Create a new approval request."""
    try:
        approval = svc.create(
            title=body.title,
            description=body.description,
            requested_by=body.requester,
            priority=body.priority,
            category=body.category,
            assignee=body.assignee or None,
            metadata=body.metadata,
        )
        return approval
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log.error("Failed to create approval: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ── 3. Approval Queue ────────────────────────────────────────────────
# GET /api/approvals/queue
# Frontend expects: Approval[] (flat array)

@router.get("/queue")
async def approval_queue(
    limit: int = Query(50, ge=1, le=500),
    _=Depends(require_auth),
    svc=Depends(_svc),
):
    """Get pending approvals sorted by priority (critical first)."""
    try:
        queue = svc.get_queue()
        return queue[:limit]
    except Exception as e:
        log.error("Failed to get approval queue: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ── 4. Blockers ──────────────────────────────────────────────────────
# GET /api/approvals/blockers
# Frontend expects: Approval[] (flat array of blocker-category items)

@router.get("/blockers")
async def get_blockers(
    limit: int = Query(50, ge=1, le=500),
    _=Depends(require_auth),
    svc=Depends(_svc),
):
    """Get pending approvals that are blockers (account_creation, login, api_key, etc.)."""
    try:
        blockers = svc.get_blockers()
        return blockers[:limit]
    except Exception as e:
        log.error("Failed to get blockers: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ── 5. History ───────────────────────────────────────────────────────
# GET /api/approvals/history
# Frontend expects: { items: Approval[], total: number }

@router.get("/history")
async def get_history(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    _=Depends(require_auth),
    svc=Depends(_svc),
):
    """Get resolved approvals (approved/rejected), newest first."""
    try:
        history = svc.get_history(limit=limit, offset=offset)
        all_resolved = svc.list_all(status="approved") + svc.list_all(status="rejected")
        return {"items": history, "total": len(all_resolved)}
    except Exception as e:
        log.error("Failed to get history: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ── 6. Audit Trail ──────────────────────────────────────────────────
# GET /api/approvals/audit
# Frontend expects: { items: AuditEntry[], total: number }

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
        return {"items": trail, "total": len(trail)}
    except Exception as e:
        log.error("Failed to get audit trail: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ── 7. Stats ─────────────────────────────────────────────────────────
# GET /api/approvals/stats

@router.get("/stats")
async def get_stats(
    _=Depends(require_auth),
    svc=Depends(_svc),
):
    """Get summary statistics for approvals."""
    try:
        return svc.get_stats()
    except Exception as e:
        log.error("Failed to get stats: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ── 8. Get Single Approval ──────────────────────────────────────────
# GET /api/approvals/{approval_id}
# Frontend expects: flat Approval object

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
        return approval
    except HTTPException:
        raise
    except Exception as e:
        log.error("Failed to get approval %s: %s", approval_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ── 9. Approve ───────────────────────────────────────────────────────
# POST /api/approvals/{approval_id}/approve
# Frontend expects: flat Approval object

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
            approved_by="operator",
        )
        if not result:
            raise HTTPException(status_code=404, detail=f"Approval '{approval_id}' not found")
        return result
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log.error("Failed to approve %s: %s", approval_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ── 10. Reject ───────────────────────────────────────────────────────
# POST /api/approvals/{approval_id}/reject
# Frontend expects: flat Approval object

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
            notes=body.reason,
            rejected_by="operator",
        )
        if not result:
            raise HTTPException(status_code=404, detail=f"Approval '{approval_id}' not found")
        return result
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log.error("Failed to reject %s: %s", approval_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ── 11. Escalate ─────────────────────────────────────────────────────
# POST /api/approvals/{approval_id}/escalate
# Frontend expects: flat Approval object

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
            escalated_by="operator",
            notes=body.notes,
        )
        if not result:
            raise HTTPException(status_code=404, detail=f"Approval '{approval_id}' not found")
        return result
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log.error("Failed to escalate %s: %s", approval_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ── 12. Bulk Approve ─────────────────────────────────────────────────
# POST /api/approvals/bulk/approve

@router.post("/bulk/approve")
async def bulk_approve(
    body: BulkApproveRequest,
    _=Depends(require_auth),
    svc=Depends(_svc),
):
    """Approve multiple pending approvals at once."""
    try:
        result = svc.bulk_approve(ids=body.ids, notes=body.notes)
        return result
    except Exception as e:
        log.error("Bulk approve failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ── 13. Bulk Reject ──────────────────────────────────────────────────
# POST /api/approvals/bulk/reject

@router.post("/bulk/reject")
async def bulk_reject(
    body: BulkRejectRequest,
    _=Depends(require_auth),
    svc=Depends(_svc),
):
    """Reject multiple pending approvals at once."""
    try:
        result = svc.bulk_reject(ids=body.ids, reason=body.reason)
        return result
    except Exception as e:
        log.error("Bulk reject failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

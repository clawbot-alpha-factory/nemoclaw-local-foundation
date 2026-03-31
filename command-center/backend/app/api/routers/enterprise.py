"""
NemoClaw Execution Engine — Enterprise Router (E-4c)

14 endpoints for guardrails, alerts, webhooks, config, SLA, audit, approvals.

NEW FILE: command-center/backend/app/api/routers/enterprise.py
"""
from __future__ import annotations
import logging
from typing import Any, Optional
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

logger = logging.getLogger("cc.api.enterprise")
router = APIRouter(tags=["enterprise"])

def _svc(request: Request, attr: str, name: str):
    svc = getattr(request.app.state, attr, None)
    if svc is None:
        raise HTTPException(503, f"{name} not initialized")
    return svc

class ModeRequest(BaseModel):
    mode: str

class ConfigUpdate(BaseModel):
    updates: dict[str, Any]

class WebhookPayload(BaseModel):
    event_type: str
    data: dict[str, Any] = {}

class SLASetRequest(BaseModel):
    target: str
    deadline_hours: float
    metric_name: str = "tasks"

class ApprovalSubmit(BaseModel):
    action: str
    amount: float
    requested_by: str
    chain_type: str = ""

# ── Engine Mode ──
@router.post("/api/engine/mode")
async def set_mode(body: ModeRequest, request: Request) -> dict[str, Any]:
    config = _svc(request, "config_service", "ConfigService")
    valid = {"conservative", "balanced", "aggressive"}
    if body.mode not in valid:
        raise HTTPException(400, f"Invalid mode. Valid: {valid}")
    result = config.set("execution_mode", body.mode)
    audit = getattr(request.app.state, "audit_service", None)
    if audit:
        audit.log("mode_change", details={"mode": body.mode})
    return result

# ── Config ──
@router.get("/api/engine/config")
async def get_config(request: Request) -> dict[str, Any]:
    return _svc(request, "config_service", "ConfigService").get_all()

@router.post("/api/engine/config")
async def update_config(body: ConfigUpdate, request: Request) -> dict[str, Any]:
    return _svc(request, "config_service", "ConfigService").update(body.updates)

# ── Alerts ──
@router.get("/api/engine/alerts")
async def get_alerts(request: Request, severity: str = "") -> dict[str, Any]:
    alerts = _svc(request, "alert_service", "AlertService").get_alerts(severity=severity)
    return {"alerts": alerts, "total": len(alerts)}

# ── Webhooks (P-3: queue-backed dispatch) ──
@router.get("/api/webhooks/history")
async def webhook_history(
    request: Request,
    source: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    after: Optional[str] = Query(None),
    before: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    """Query webhook event history with filters and pagination."""
    svc = _svc(request, "webhook_service", "WebhookService")
    return svc.get_history(source=source, status=status, after=after, before=before, limit=limit, offset=offset)

@router.get("/api/webhooks/dead-letter")
async def webhook_dead_letter(request: Request, limit: int = Query(50, ge=1, le=500)) -> dict[str, Any]:
    """Get webhook events that exhausted retries."""
    svc = _svc(request, "webhook_service", "WebhookService")
    return svc.get_dead_letter(limit=limit)

@router.post("/api/webhooks/{source}")
async def receive_webhook(source: str, body: WebhookPayload, request: Request) -> dict[str, Any]:
    svc = _svc(request, "webhook_service", "WebhookService")
    return await svc.process(source, body.event_type, body.data)

# ── SLA ──
@router.get("/api/sla/projects")
async def get_all_slas(request: Request) -> dict[str, Any]:
    slas = _svc(request, "sla_service", "SLAService").get_all()
    return {"slas": slas, "total": len(slas)}

@router.get("/api/sla/{project_id}")
async def get_sla(project_id: str, request: Request) -> dict[str, Any]:
    sla = _svc(request, "sla_service", "SLAService").get_sla(project_id)
    if not sla:
        raise HTTPException(404, "SLA not found")
    return sla

@router.post("/api/sla/{project_id}/set")
async def set_sla(project_id: str, body: SLASetRequest, request: Request) -> dict[str, Any]:
    return _svc(request, "sla_service", "SLAService").set_sla(project_id, body.target, body.deadline_hours, body.metric_name)

# ── Audit ──
@router.get("/api/audit/log")
async def get_audit_log(request: Request, limit: int = 100, action: str = "") -> dict[str, Any]:
    entries = _svc(request, "audit_service", "AuditService").get_log(limit=limit, action=action)
    return {"entries": entries, "total": len(entries)}

@router.get("/api/audit/export")
async def export_audit(request: Request) -> dict[str, Any]:
    data = _svc(request, "audit_service", "AuditService").export()
    return {"format": "jsonl", "data": data}

# ── Approvals ──
@router.get("/api/engine/approvals/pending")
async def get_pending_approvals(request: Request) -> dict[str, Any]:
    pending = _svc(request, "approval_chain_service", "ApprovalChainService").get_pending()
    return {"pending": pending, "total": len(pending)}

@router.post("/api/engine/approvals/submit")
async def submit_approval(body: ApprovalSubmit, request: Request) -> dict[str, Any]:
    return _svc(request, "approval_chain_service", "ApprovalChainService").submit(**body.model_dump())

@router.post("/api/engine/approvals/{request_id}/approve")
async def approve_request(request_id: str, request: Request, approver: str = "") -> dict[str, Any]:
    result = _svc(request, "approval_chain_service", "ApprovalChainService").approve(request_id, approver)
    if not result.get("success"):
        raise HTTPException(400, result)
    return result

@router.post("/api/engine/approvals/{request_id}/reject")
async def reject_request(request_id: str, request: Request, rejector: str = "", reason: str = "") -> dict[str, Any]:
    result = _svc(request, "approval_chain_service", "ApprovalChainService").reject(request_id, rejector, reason)
    if not result.get("success"):
        raise HTTPException(400, result)
    return result

@router.get("/api/engine/approvals/chains")
async def get_chains(request: Request) -> dict[str, Any]:
    return _svc(request, "approval_chain_service", "ApprovalChainService").get_chains()

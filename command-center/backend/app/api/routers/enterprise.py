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

class RubricScoreRequest(BaseModel):
    action: str
    amount: float = 0.0
    factors: dict[str, float] = {}

class RubricSubmitRequest(BaseModel):
    action: str
    amount: float = 0.0
    requested_by: str
    factors: dict[str, float] = {}
    request_id: str = ""

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
    return {"items": pending, "total": len(pending)}

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


# ── Rubric Scoring (P-5) ──
@router.post("/api/engine/approvals/score")
async def score_approval(body: RubricScoreRequest, request: Request) -> dict[str, Any]:
    """Dry-run rubric score simulation — no side effects."""
    svc = _svc(request, "approval_chain_service", "ApprovalChainService")
    return svc.simulate_score(body.action, body.amount, body.factors or None)

@router.post("/api/engine/approvals/submit-scored")
async def submit_scored_approval(body: RubricSubmitRequest, request: Request) -> dict[str, Any]:
    """Submit approval with rubric scoring. Scores first, then routes based on risk level."""
    svc = _svc(request, "approval_chain_service", "ApprovalChainService")
    return svc.submit_with_rubric(
        action=body.action, amount=body.amount,
        requested_by=body.requested_by,
        user_factors=body.factors or None,
        request_id=body.request_id,
    )

@router.get("/api/engine/approvals/score-history")
async def score_history(request: Request, limit: int = 50) -> dict[str, Any]:
    """Get recent rubric scoring decisions."""
    svc = _svc(request, "approval_chain_service", "ApprovalChainService")
    history = svc.get_score_history(limit=limit)
    return {"total": len(history), "entries": history}

@router.get("/api/engine/approvals/chains")
async def get_chains(request: Request) -> dict[str, Any]:
    return _svc(request, "approval_chain_service", "ApprovalChainService").get_chains()


# ── Connectivity Audit ──

@router.get("/api/audit/connectivity")
async def audit_connectivity(request: Request) -> dict[str, Any]:
    """Check all agent wiring: loops, events, tools, messaging."""
    from app.services.agent_loop_service import LOOP_AGENTS

    agent_loop_svc = getattr(request.app.state, "agent_loop_service", None)
    notification_svc = getattr(request.app.state, "notification_service", None)
    tool_access_svc = getattr(request.app.state, "tool_access_service", None)
    event_bus = getattr(request.app.state, "event_bus", None)
    task_dispatch_svc = getattr(request.app.state, "task_dispatch_service", None)

    agents = []
    for agent_id in LOOP_AGENTS:
        loop_running = False
        if agent_loop_svc:
            loop = agent_loop_svc.loops.get(agent_id)
            loop_running = bool(loop and loop._running)

        events_subscribed = bool(event_bus and hasattr(event_bus, "_subscribers") and event_bus._subscribers)

        tools_accessible = bool(tool_access_svc)

        messaging_active = bool(notification_svc)

        agents.append({
            "id": agent_id,
            "loop_running": loop_running,
            "events_subscribed": events_subscribed,
            "tools_accessible": tools_accessible,
            "messaging_active": messaging_active,
        })

    return {
        "agents": agents,
        "services": {
            "agent_loop_service": agent_loop_svc is not None,
            "notification_service": notification_svc is not None,
            "tool_access_service": tool_access_svc is not None,
            "event_bus": event_bus is not None,
            "task_dispatch_service": task_dispatch_svc is not None,
        },
        "total_agents": len(agents),
        "loops_running": sum(1 for a in agents if a["loop_running"]),
    }

"""
NemoClaw Execution Engine — Lifecycle Router (E-11)

6 endpoints: onboarding, deliverables, churn/health, competitors.

NEW FILE: command-center/backend/app/api/routers/lifecycle.py
"""
from __future__ import annotations
import logging
from typing import Any
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger("cc.api.lifecycle")
router = APIRouter(prefix="/api/lifecycle", tags=["lifecycle"])

def _svc(request, attr):
    svc = getattr(request.app.state, attr, None)
    if svc is None:
        raise HTTPException(503, f"{attr} not initialized")
    return svc

class OnboardingStart(BaseModel):
    client_id: str; client_name: str; service_id: str = ""

class OnboardingAdvance(BaseModel):
    client_id: str; new_stage: str

class HealthUpdate(BaseModel):
    client_id: str; factor: str; value: float

@router.get("/onboarding")
async def get_onboarding(request: Request) -> dict[str, Any]:
    svc = _svc(request, "onboarding_service")
    return {"onboarding": svc.get_all(), "stats": svc.get_stats(), "due_actions": svc.get_due_actions()}

@router.post("/onboarding/start")
async def start_onboarding(body: OnboardingStart, request: Request) -> dict[str, Any]:
    return _svc(request, "onboarding_service").start_onboarding(body.client_id, body.client_name, body.service_id)

@router.get("/deliverables")
async def get_deliverables(request: Request, client_id: str | None = None) -> dict[str, Any]:
    svc = _svc(request, "deliverable_service")
    if client_id:
        return {"deliverables": svc.get_by_client(client_id)}
    return {"stats": svc.get_stats(), "overdue": svc.get_overdue()}

@router.get("/health")
async def get_health(request: Request) -> dict[str, Any]:
    svc = _svc(request, "churn_service")
    return {"stats": svc.get_stats(), "at_risk": svc.get_at_risk()}

@router.post("/health/update")
async def update_health(body: HealthUpdate, request: Request) -> dict[str, Any]:
    return _svc(request, "churn_service").update_health(body.client_id, body.factor, body.value)

@router.get("/competitors")
async def get_competitors(request: Request, limit: int = 20) -> dict[str, Any]:
    return {"intel": _svc(request, "churn_service").get_competitor_intel(limit)}

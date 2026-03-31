"""
NemoClaw Execution Engine — Revenue Router (E-10)

8 endpoints: pipeline, catalog, A/B tests, attribution, events.

NEW FILE: command-center/backend/app/api/routers/revenue.py
"""
from __future__ import annotations
import logging
from typing import Any
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger("cc.api.revenue")
router = APIRouter(prefix="/api/revenue", tags=["revenue"])

def _svc(request, attr):
    svc = getattr(request.app.state, attr, None)
    if svc is None:
        raise HTTPException(503, f"{attr} not initialized")
    return svc

class DealCreate(BaseModel):
    deal_id: str; lead_name: str; value: float = 0; agent: str = ""; source: str = ""

class DealAdvance(BaseModel):
    deal_id: str; new_stage: str

@router.get("/pipeline")
async def get_pipeline(request: Request) -> dict[str, Any]:
    return _svc(request, "pipeline_service").get_pipeline()

@router.post("/pipeline/deals")
async def create_deal(body: DealCreate, request: Request) -> dict[str, Any]:
    return _svc(request, "pipeline_service").create_deal(body.deal_id, body.lead_name, body.value, body.agent, body.source)

@router.post("/pipeline/advance")
async def advance_deal(body: DealAdvance, request: Request) -> dict[str, Any]:
    return _svc(request, "pipeline_service").advance_deal(body.deal_id, body.new_stage)

@router.get("/pipeline/forecast")
async def get_forecast(request: Request) -> dict[str, Any]:
    return _svc(request, "pipeline_service").get_forecast()

@router.get("/catalog")
async def get_catalog(request: Request) -> dict[str, Any]:
    return {"items": _svc(request, "catalog_service").get_catalog()}

@router.get("/ab-tests")
async def get_ab_tests(request: Request) -> dict[str, Any]:
    return {"experiments": _svc(request, "ab_test_service").get_all()}

@router.get("/attribution")
async def get_attribution(request: Request) -> dict[str, Any]:
    return _svc(request, "attribution_service").get_stats()

@router.get("/events")
async def get_events(request: Request, event_type: str | None = None, limit: int = 50) -> dict[str, Any]:
    return {"events": _svc(request, "event_bus").get_events(event_type, limit), "stats": _svc(request, "event_bus").get_stats()}

"""
NemoClaw Execution Engine — Autonomous Router (E-12)

5 endpoints: dashboard, ROI, daily summary, self-audit, improvement tasks.

NEW FILE: command-center/backend/app/api/routers/autonomous.py
"""
from __future__ import annotations
import logging
from typing import Any
from fastapi import APIRouter, HTTPException, Request

logger = logging.getLogger("cc.api.autonomous")
router = APIRouter(prefix="/api/autonomous", tags=["autonomous"])

def _svc(request, attr):
    svc = getattr(request.app.state, attr, None)
    if svc is None:
        raise HTTPException(503, f"{attr} not initialized")
    return svc

@router.get("/dashboard")
async def get_dashboard(request: Request) -> dict[str, Any]:
    """Complete system metrics dashboard."""
    return _svc(request, "metrics_service").get_dashboard()

@router.get("/roi")
async def get_roi(request: Request) -> dict[str, Any]:
    """ROI report across all channels."""
    return _svc(request, "metrics_service").get_roi_report()

@router.get("/daily-summary")
async def get_daily_summary(request: Request) -> dict[str, Any]:
    """Quick daily summary for executive review."""
    return _svc(request, "metrics_service").get_daily_summary()

@router.post("/self-audit")
async def run_self_audit(request: Request) -> dict[str, Any]:
    """Run weekly self-audit."""
    return _svc(request, "self_improvement").run_weekly_audit()

@router.get("/improvement-tasks")
async def get_improvement_tasks(request: Request) -> dict[str, Any]:
    """Get pending improvement tasks from all audits."""
    svc = _svc(request, "self_improvement")
    return {"tasks": svc.get_improvement_tasks(), "stats": svc.get_stats()}


@router.post("/loop/start")
async def start_loop(request: Request) -> dict[str, Any]:
    """Start the autonomous execution loop."""
    return await _svc(request, "autonomous_loop").start()

@router.post("/loop/stop")
async def stop_loop(request: Request) -> dict[str, Any]:
    """Stop the autonomous execution loop."""
    return await _svc(request, "autonomous_loop").stop()

@router.get("/loop/status")
async def get_loop_status(request: Request) -> dict[str, Any]:
    """Get autonomous loop status + heartbeat."""
    return _svc(request, "autonomous_loop").get_status()

@router.get("/scheduler")
async def get_scheduler(request: Request) -> dict[str, Any]:
    """Get all scheduled jobs."""
    return _svc(request, "autonomous_scheduler").get_stats()

@router.get("/decision-log")
async def get_decision_log(request: Request, limit: int = 50) -> dict[str, Any]:
    """Get decision→action→result chain log."""
    return {"log": _svc(request, "autonomous_loop").get_decision_log(limit)}

"""
NemoClaw Execution Engine — Autonomous Router (E-12)

5 endpoints: dashboard, ROI, daily summary, self-audit, improvement tasks.

NEW FILE: command-center/backend/app/api/routers/autonomous.py
"""
from __future__ import annotations
import logging
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from app.auth import require_auth

logger = logging.getLogger("cc.api.autonomous")
router = APIRouter(prefix="/api/autonomous", tags=["autonomous"], dependencies=[Depends(require_auth)])

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




# ── Metrics Time-Range Aggregation (P-6) ──

@router.get("/metrics/range")
async def metrics_range(
    request: Request,
    after: str = "",
    before: str = "",
) -> dict[str, Any]:
    """Query metric snapshots within a date range."""
    if not after or not before:
        raise HTTPException(400, "Both 'after' and 'before' query params required (ISO date)")
    svc = _svc(request, "metrics_service")
    try:
        snapshots = svc.query_range(after, before)
        return {"after": after, "before": before, "count": len(snapshots), "snapshots": snapshots}
    except ValueError as e:
        raise HTTPException(400, str(e))

@router.get("/metrics/aggregate")
async def metrics_aggregate(
    request: Request,
    preset: str = "",
    after: str = "",
    before: str = "",
) -> dict[str, Any]:
    """Aggregate metrics over a time range or preset period."""
    svc = _svc(request, "metrics_service")
    try:
        if preset:
            # Preset returns comparison (includes aggregation for both periods)
            return svc.get_period_preset(preset)
        elif after and before:
            return svc.aggregate(after, before)
        else:
            raise HTTPException(400, "Provide 'preset' (24h/7d/30d/90d) or 'after' + 'before' params")
    except ValueError as e:
        raise HTTPException(400, str(e))

@router.get("/metrics/compare")
async def metrics_compare(
    request: Request,
    preset: str = "",
    a_after: str = "",
    a_before: str = "",
    b_after: str = "",
    b_before: str = "",
) -> dict[str, Any]:
    """Compare metrics between two time periods."""
    svc = _svc(request, "metrics_service")
    try:
        if preset:
            return svc.get_period_preset(preset)
        elif a_after and a_before and b_after and b_before:
            return svc.compare_periods(a_after, a_before, b_after, b_before)
        else:
            raise HTTPException(400, "Provide 'preset' or all four params: a_after, a_before, b_after, b_before")
    except ValueError as e:
        raise HTTPException(400, str(e))

@router.get("/prompt-optimization")
async def get_prompt_optimization(request: Request) -> dict[str, Any]:
    """Get prompt optimization stats and variants."""
    svc = _svc(request, "prompt_optimization")
    return {"stats": svc.get_stats(), "optimizations": svc.get_all_optimizations()}

@router.post("/prompt-optimization/{skill_id}/suggest")
async def suggest_prompt_variant(skill_id: str, request: Request) -> dict[str, Any]:
    """Generate a new prompt variant suggestion via LLM."""
    svc = _svc(request, "prompt_optimization")
    return await svc.generate_variant_suggestion(skill_id)

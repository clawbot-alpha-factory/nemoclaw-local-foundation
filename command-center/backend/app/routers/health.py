"""
Health check router.

Provides unauthenticated health probe endpoints for the backend itself.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter

from ..state_aggregator import aggregator
from ..websocket_manager import ws_manager

router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("")
async def health_check():
    """Basic liveness probe."""
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "version": "cc-1.0.0",
    }


@router.get("/ready")
async def readiness_check():
    """Readiness probe — checks if state aggregator has run at least once."""
    state = aggregator.state
    has_data = state.timestamp is not None and state.skills.total_built > 0

    return {
        "ready": has_data,
        "timestamp": datetime.now().isoformat(),
        "last_scan": state.timestamp.isoformat() if state.timestamp else None,
        "ws_clients": ws_manager.connection_count,
        "skills_count": state.skills.total_built,
        "agents_count": state.agents.total,
    }


@router.get("/debug")
async def debug_state():
    """Raw state dump for debugging. No auth required in dev."""
    state = aggregator.state
    return {
        "state_version": state.state_version,
        "timestamp": state.timestamp.isoformat() if state.timestamp else None,
        "ws_clients": ws_manager.connection_count,
        "narrative": state.narrative,
        "counts": {
            "skills_built": state.skills.total_built,
            "skills_registered": state.skills.total_registered,
            "agents": state.agents.total,
            "ma_systems": state.ma_systems.total,
            "ma_tests": state.ma_systems.total_tests,
            "bridges": state.bridges.total,
            "bridges_connected": state.bridges.connected,
            "frameworks": state.frameworks.total,
        },
        "health_overall": state.health.overall,
        "validation": {
            "passed": state.validation.passed,
            "warnings": state.validation.warnings,
            "failed": state.validation.failed,
        },
        "budget": {
            p.provider: f"${p.spent:.2f}/${p.limit:.2f} ({p.percent_used:.0f}%)"
            for p in state.budget.providers
        },
        "git": {
            "branch": state.git_branch,
            "commit": state.git_commit,
        },
        "pinchtab": state.pinchtab_status,
    }

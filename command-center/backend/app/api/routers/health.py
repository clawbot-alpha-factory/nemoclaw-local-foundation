"""
Health check router.

Provides unauthenticated health probe endpoints for the backend itself.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Request

from app.services.state_aggregator import aggregator
from app.adapters.websocket_manager import ws_manager

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


@router.get("/metrics")
async def prometheus_metrics():
    """Prometheus-compatible metrics endpoint.

    Frozen metric names — stable contract, no churn.
    Removal requires 2-version deprecation notice.
    """
    from fastapi.responses import PlainTextResponse

    state = aggregator.state
    lines = []

    # Counters
    lines.append(f"# HELP nemoclaw_skills_built_total Total built skills")
    lines.append(f"# TYPE nemoclaw_skills_built_total gauge")
    lines.append(f"nemoclaw_skills_built_total {state.skills.total_built}")

    lines.append(f"# HELP nemoclaw_agents_total Total active agents")
    lines.append(f"# TYPE nemoclaw_agents_total gauge")
    lines.append(f"nemoclaw_agents_total {state.agents.total}")

    lines.append(f"# HELP nemoclaw_ma_tests_total Total MA system test checks")
    lines.append(f"# TYPE nemoclaw_ma_tests_total gauge")
    lines.append(f"nemoclaw_ma_tests_total {state.ma_systems.total_tests}")

    # Budget gauges (per provider)
    lines.append(f"# HELP nemoclaw_llm_cost_usd LLM spend per provider")
    lines.append(f"# TYPE nemoclaw_llm_cost_usd gauge")
    for p in state.budget.providers:
        lines.append(f'nemoclaw_llm_cost_usd{{provider="{p.provider}"}} {p.spent:.4f}')

    lines.append(f"# HELP nemoclaw_provider_budget_remaining_usd Budget remaining per provider")
    lines.append(f"# TYPE nemoclaw_provider_budget_remaining_usd gauge")
    for p in state.budget.providers:
        remaining = p.limit - p.spent
        lines.append(f'nemoclaw_provider_budget_remaining_usd{{provider="{p.provider}"}} {remaining:.4f}')

    # System health
    lines.append(f"# HELP nemoclaw_system_health_score Overall system health 0-1")
    lines.append(f"# TYPE nemoclaw_system_health_score gauge")
    health_val = 1.0 if state.health.overall == "healthy" else (0.5 if state.health.overall == "warning" else 0.0)
    lines.append(f"nemoclaw_system_health_score {health_val}")

    # Validation
    lines.append(f"# HELP nemoclaw_validation_passed Validation checks passed")
    lines.append(f"# TYPE nemoclaw_validation_passed gauge")
    lines.append(f"nemoclaw_validation_passed {state.validation.passed}")

    lines.append(f"# HELP nemoclaw_validation_failed Validation checks failed")
    lines.append(f"# TYPE nemoclaw_validation_failed gauge")
    lines.append(f"nemoclaw_validation_failed {state.validation.failed}")

    # WebSocket
    lines.append(f"# HELP nemoclaw_ws_clients Connected WebSocket clients")
    lines.append(f"# TYPE nemoclaw_ws_clients gauge")
    lines.append(f"nemoclaw_ws_clients {ws_manager.connection_count}")

    return PlainTextResponse("\n".join(lines) + "\n", media_type="text/plain")


@router.get("/persistence")
async def persistence_status(request: Request):
    """Counts of items restored from disk on startup."""
    wf_svc = getattr(request.app.state, "task_workflow_service", None)
    mp_svc = getattr(request.app.state, "message_pool", None)
    ws_svc = getattr(request.app.state, "workspace_service", None)
    return {
        "workflows": len(wf_svc._workflows) if wf_svc else 0,
        "messages": len(mp_svc._pool) if mp_svc else 0,
        "workspaces": len(ws_svc.workspaces) if ws_svc else 0,
    }


@router.get("/breakers")
async def breaker_states(request: Request):
    """All circuit breaker states — failure, step, cost, repetition."""
    exec_svc = getattr(request.app.state, "execution_service", None)
    result = {}

    # Failure-based (SkillCircuitBreaker)
    if exec_svc and exec_svc.circuit_breaker:
        cb = exec_svc.circuit_breaker
        result["failure_breaker"] = {"stats": cb.get_stats(), "all_states": cb.get_all_states()}
    else:
        result["failure_breaker"] = None

    # Execution-scoped breakers
    if exec_svc:
        result["step_limit"] = exec_svc.step_breaker.get_state()
        result["cost_ceiling"] = exec_svc.cost_breaker.get_state()
        result["repetition"] = exec_svc.repetition_detector.get_state()
    else:
        result["step_limit"] = None
        result["cost_ceiling"] = None
        result["repetition"] = None

    return result


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

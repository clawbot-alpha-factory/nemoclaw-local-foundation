"""
Agents Router (CC-4)

Rich agent profiles, org hierarchy, and workload metrics:
  GET  /api/agents/              — all agents with profiles + activity
  GET  /api/agents/{id}          — single agent full profile
  GET  /api/agents/{id}/activity — agent activity metrics
  GET  /api/agents/org           — org hierarchy / authority map
  GET  /api/agents/workload      — team workload overview

NEW FILE: command-center/backend/app/routers/agents.py
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.auth import require_auth

logger = logging.getLogger("cc.agents")

router = APIRouter(prefix="/api/agents", tags=["agents"])


def _get_agent_service(request: Request):
    service = getattr(request.app.state, "agent_chat_service", None)
    if not service:
        raise HTTPException(status_code=503, detail="AgentChatService not initialized")
    return service


def _get_store(request: Request):
    return getattr(request.app.state, "message_store", None)


def _build_agent_profile(agent, store=None) -> dict[str, Any]:
    """Build rich agent profile from AgentPersona + optional activity data."""
    raw = agent.raw

    # Skills breakdown
    raw_skills = raw.get("skills", {})
    if isinstance(raw_skills, dict):
        primary_skills = raw_skills.get("primary", [])
        future_skills = raw_skills.get("future", [])
    else:
        primary_skills = raw_skills if isinstance(raw_skills, list) else []
        future_skills = []

    # Decisions
    decides = raw.get("decides", [])

    # Failure modes
    failure_modes = raw.get("failure_modes", [])

    # Metrics definitions
    metrics_defs = raw.get("metrics", [])

    # Memory access
    memory_access = raw.get("memory_access", {})

    # Authority
    authority_level = raw.get("authority_level", 3)
    title = raw.get("title", agent.role)

    # Constraints
    constraints = raw.get("constraints", [])

    # Character name from identity block (e.g. "Tariq", "Nadia")
    character_name = getattr(agent, "character_name", "") or agent.display_name
    character = getattr(agent, "character", "")
    role_display = getattr(agent, "role_display", agent.display_name)
    title_short = getattr(agent, "title_short", title)

    profile = {
        "id": agent.id,
        "name": f"{character_name} ({role_display})" if character_name and character_name != role_display else agent.display_name,
        "character_name": character_name,
        "character": character,
        "role_display": role_display,
        "title": title_short or title,
        "role": agent.description,
        "avatar": agent.avatar,
        "lane_id": agent.lane_id,
        "authority_level": authority_level,
        "capabilities": agent.capabilities,
        "decides": decides,
        "skills": {
            "primary": primary_skills,
            "future": future_skills,
            "primary_count": len(primary_skills),
            "future_count": len(future_skills),
            "total": len(primary_skills) + len(future_skills),
        },
        "failure_modes": failure_modes,
        "metrics_tracked": metrics_defs,
        "memory_access": memory_access,
        "constraints": constraints,
        "family": agent.family,
    }

    # Activity data from MessageStore
    if store:
        activity = _compute_activity(agent.id, agent.lane_id, store)
        profile["activity"] = activity

    return profile


def _compute_activity(agent_id: str, lane_id: str, store) -> dict[str, Any]:
    """Compute activity metrics for an agent from MessageStore."""
    now = datetime.now(timezone.utc)
    day_ago = now - timedelta(hours=24)
    week_ago = now - timedelta(days=7)

    # Get all messages in agent's DM lane
    all_msgs = store.get_messages(lane_id, limit=500)

    # Agent messages
    agent_msgs = [m for m in all_msgs if m.sender_id == agent_id]
    user_msgs = [m for m in all_msgs if m.sender_type.value == "user"]

    # Messages in last 24h
    recent_agent = [m for m in agent_msgs if m.timestamp > day_ago]
    recent_user = [m for m in user_msgs if m.timestamp > day_ago]

    # Response time calculation (time between user msg and agent reply)
    response_times = []
    for i, msg in enumerate(all_msgs):
        if msg.sender_id == agent_id and i > 0:
            prev = all_msgs[i - 1]
            if prev.sender_type.value == "user":
                delta = (msg.timestamp - prev.timestamp).total_seconds()
                if delta > 0 and delta < 300:  # ignore gaps > 5min
                    response_times.append(delta)

    avg_response = (
        round(sum(response_times) / len(response_times), 1)
        if response_times
        else None
    )

    # Check broadcast/group participation
    broadcast_msgs = 0
    for lid, msg_ids in store._lane_index.items():
        if lid.startswith("dm-"):
            continue
        for mid in msg_ids:
            msg = store._messages.get(mid)
            if msg and msg.sender_id == agent_id:
                broadcast_msgs += 1

    return {
        "total_messages": len(agent_msgs),
        "messages_24h": len(recent_agent),
        "conversations": len(user_msgs),
        "conversations_24h": len(recent_user),
        "avg_response_seconds": avg_response,
        "broadcast_messages": broadcast_msgs,
        "last_active": (
            agent_msgs[-1].timestamp.isoformat() if agent_msgs else None
        ),
        "status": _derive_status(agent_msgs, now),
    }


def _derive_status(agent_msgs, now) -> str:
    """Derive agent status from message history."""
    if not agent_msgs:
        return "idle"
    last = agent_msgs[-1].timestamp
    delta = (now - last).total_seconds()
    if delta < 300:
        return "active"
    elif delta < 3600:
        return "recent"
    else:
        return "idle"


# ------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------


@router.get("/", dependencies=[Depends(require_auth)])
async def list_agents(request: Request):
    """List all agents with full profiles and activity data."""
    service = _get_agent_service(request)
    store = _get_store(request)

    agents = []
    for agent in service.agents.values():
        profile = _build_agent_profile(agent, store)
        agents.append(profile)

    # Sort by authority level (highest first)
    agents.sort(key=lambda a: a["authority_level"])

    return {
        "agents": agents,
        "total": len(agents),
        "available": service.is_available,
    }


@router.get("/org", dependencies=[Depends(require_auth)])
async def org_hierarchy(request: Request):
    """Return organizational hierarchy."""
    service = _get_agent_service(request)

    levels: dict[int, list[dict]] = {}
    for agent in service.agents.values():
        lvl = agent.raw.get("authority_level", 3)
        if lvl not in levels:
            levels[lvl] = []
        levels[lvl].append({
            "id": agent.id,
            "name": agent.display_name,
            "title": agent.raw.get("title", agent.role),
            "avatar": agent.avatar,
            "authority_level": lvl,
        })

    # Authority labels
    level_labels = {
        1: "Executive",
        2: "Leadership",
        3: "Execution",
    }

    hierarchy = []
    for lvl in sorted(levels.keys()):
        hierarchy.append({
            "level": lvl,
            "label": level_labels.get(lvl, f"Level {lvl}"),
            "agents": levels[lvl],
        })

    return {"hierarchy": hierarchy}


@router.get("/workload", dependencies=[Depends(require_auth)])
async def team_workload(request: Request):
    """Team-wide workload overview."""
    service = _get_agent_service(request)
    store = _get_store(request)

    workload = []
    total_msgs = 0
    active_count = 0

    for agent in service.agents.values():
        activity = _compute_activity(agent.id, agent.lane_id, store) if store else {}
        total_msgs += activity.get("total_messages", 0)
        if activity.get("status") in ("active", "recent"):
            active_count += 1

        primary_skills = []
        raw_skills = agent.raw.get("skills", {})
        if isinstance(raw_skills, dict):
            primary_skills = raw_skills.get("primary", [])

        workload.append({
            "id": agent.id,
            "name": agent.display_name,
            "avatar": agent.avatar,
            "title": agent.raw.get("title", ""),
            "status": activity.get("status", "idle"),
            "messages_24h": activity.get("messages_24h", 0),
            "avg_response_seconds": activity.get("avg_response_seconds"),
            "total_messages": activity.get("total_messages", 0),
            "skills_assigned": len(primary_skills),
            "capabilities_count": len(agent.capabilities),
        })

    # Sort by activity (most active first)
    workload.sort(key=lambda w: w["messages_24h"], reverse=True)

    return {
        "team": workload,
        "summary": {
            "total_agents": len(workload),
            "active_now": active_count,
            "total_messages": total_msgs,
        },
    }


@router.get("/{agent_id}", dependencies=[Depends(require_auth)])
async def get_agent(agent_id: str, request: Request):
    """Get full profile for a single agent."""
    service = _get_agent_service(request)
    store = _get_store(request)

    agent = service.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")

    return _build_agent_profile(agent, store)


@router.get("/{agent_id}/activity", dependencies=[Depends(require_auth)])
async def get_agent_activity(agent_id: str, request: Request):
    """Get activity metrics for a single agent."""
    service = _get_agent_service(request)
    store = _get_store(request)

    agent = service.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")

    if not store:
        return {"activity": {}, "message": "MessageStore not available"}

    return {"agent_id": agent_id, "activity": _compute_activity(agent_id, agent.lane_id, store)}


# ------------------------------------------------------------------
# Work Log Endpoints
# ------------------------------------------------------------------


def _get_work_log_service(request: Request):
    svc = getattr(request.app.state, "work_log_service", None)
    if not svc:
        raise HTTPException(status_code=503, detail="WorkLogService not initialized")
    return svc


@router.get("/{agent_id}/work-log", dependencies=[Depends(require_auth)])
async def get_agent_work_log(
    agent_id: str,
    request: Request,
    period: str = "today",
):
    """Get work log summary for an agent (today/week/all)."""
    svc = _get_work_log_service(request)
    if period not in ("today", "week", "all"):
        raise HTTPException(status_code=400, detail="period must be today, week, or all")
    return svc.get_agent_summary(agent_id, period=period)


@router.get("/{agent_id}/work-log/export", dependencies=[Depends(require_auth)])
async def export_agent_work_log(
    agent_id: str,
    request: Request,
    format: str = "markdown",
):
    """Export all work logs for an agent."""
    svc = _get_work_log_service(request)
    if format not in ("markdown", "json"):
        raise HTTPException(status_code=400, detail="format must be markdown or json")
    return svc.export_logs(agent_id, fmt=format)


# ------------------------------------------------------------------
# Task Assignment
# ------------------------------------------------------------------


class AssignTaskRequest(BaseModel):
    goal: str = Field(..., min_length=1, max_length=4000)
    project_id: Optional[str] = None


def _get_task_dispatch_service(request: Request):
    svc = getattr(request.app.state, "task_dispatch_service", None)
    if not svc:
        raise HTTPException(status_code=503, detail="TaskDispatchService not initialized")
    return svc


@router.post("/{agent_id}/assign-task", dependencies=[Depends(require_auth)])
async def assign_task(agent_id: str, body: AssignTaskRequest, request: Request):
    """Assign a task to an agent. Returns workflow details."""
    # Validate agent exists
    service = _get_agent_service(request)
    agent = service.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")

    dispatch_svc = _get_task_dispatch_service(request)
    result = await dispatch_svc.dispatch_task(
        agent_id=agent_id,
        goal=body.goal,
        source="api",
        project_id=body.project_id,
    )

    if result.get("status") == "failed":
        raise HTTPException(status_code=422, detail=result.get("error", "Dispatch failed"))

    return result

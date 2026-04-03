"""
NemoClaw Command Center — Mission Domain Models

Pydantic models for Asana-backed mission lifecycle management.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


class MissionPhase(str, Enum):
    CREATED = "created"
    PLANNING = "planning"
    EXECUTING = "executing"
    REVIEWING = "reviewing"
    COMPLETED = "completed"


PHASE_TRANSITIONS: dict[MissionPhase, list[MissionPhase]] = {
    MissionPhase.CREATED: [MissionPhase.PLANNING],
    MissionPhase.PLANNING: [MissionPhase.EXECUTING],
    MissionPhase.EXECUTING: [MissionPhase.REVIEWING],
    MissionPhase.REVIEWING: [MissionPhase.COMPLETED, MissionPhase.EXECUTING],
    MissionPhase.COMPLETED: [],
}


class MissionTask(BaseModel):
    task_gid: str
    name: str
    assignee: str | None = None
    completed: bool = False
    section: str | None = None


class Mission(BaseModel):
    id: str = Field(default_factory=lambda: f"mission-{uuid.uuid4().hex[:8]}")
    goal: str
    lead_agent: str
    phase: MissionPhase = MissionPhase.CREATED
    asana_project_gid: str | None = None
    asana_project_url: str | None = None
    workspace_gid: str | None = None
    tasks: list[MissionTask] = Field(default_factory=list)
    local_dir: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ── Request Models ────────────────────────────────────────────────────


class MissionCreateRequest(BaseModel):
    goal: str
    lead_agent: str = "ceo"


class MissionAdvanceRequest(BaseModel):
    to_phase: MissionPhase


class HeartbeatRequest(BaseModel):
    agent_id: str
    message: str

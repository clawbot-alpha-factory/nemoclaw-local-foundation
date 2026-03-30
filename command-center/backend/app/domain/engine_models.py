"""
NemoClaw Execution Engine — Data Models (E-2)

Pydantic models for execution state, chains, dead letter queue,
LLM routing tiers, and trace context.

NEW FILE: command-center/backend/app/domain/engine_models.py
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ── Enums ──────────────────────────────────────────────────────────────


class ExecutionStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    DEAD_LETTER = "dead_letter"


class ExecutionMode(str, Enum):
    CONSERVATIVE = "conservative"
    BALANCED = "balanced"
    AGGRESSIVE = "aggressive"


class LLMTier(str, Enum):
    """4-tier routing: simple → standard → complex → critical."""
    LIGHTWEIGHT = "lightweight"      # GPT-4o-mini
    STANDARD = "standard"            # GPT-4o
    COMPLEX = "complex"              # Opus → GPT-4o review → Opus finalize
    CRITICAL = "critical"            # Opus → dual review → GPT-5.4 → Opus finalize


class ChainStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PARTIAL = "partial"


# ── LLM Routing ───────────────────────────────────────────────────────


class LLMModelConfig(BaseModel):
    """Single model in a routing tier."""
    provider: str = "openai"           # openai, anthropic, nvidia
    model: str = "gpt-4o-mini"
    cost_per_call: float = 0.001
    timeout_seconds: int = 15
    max_retries: int = 2


class LLMTierConfig(BaseModel):
    """Full config for one routing tier."""
    tier: LLMTier
    primary: LLMModelConfig
    fallback: list[LLMModelConfig] = Field(default_factory=list)
    quality_threshold: float = 7.0     # min self-eval score (1-10)
    max_retry_loops: int = 2
    daily_cap_per_agent: float = 1.0   # USD
    daily_cap_system: float = 5.0      # USD


class LLMRoutingDecision(BaseModel):
    """Logged for every LLM call."""
    trace_id: str = ""
    tier: LLMTier = LLMTier.LIGHTWEIGHT
    model_used: str = ""
    provider: str = ""
    cost: float = 0.0
    latency_ms: int = 0
    quality_score: float = 0.0
    retry_count: int = 0
    fallback_used: bool = False
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ── Trace Context ──────────────────────────────────────────────────────


class TraceContext(BaseModel):
    """Propagates through every task, skill, bridge call, protocol message."""
    trace_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    parent_id: str | None = None
    agent_id: str = ""
    phase: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ── Execution Models ───────────────────────────────────────────────────


class ExecutionRequest(BaseModel):
    """Request to execute a single skill."""
    skill_id: str
    inputs: dict[str, str] = Field(default_factory=dict)
    agent_id: str = ""
    tier: LLMTier = LLMTier.STANDARD
    priority: int = 5                  # 1=highest, 10=lowest
    trace: TraceContext | None = None


class TaskExecution(BaseModel):
    """Tracks a single skill execution through its lifecycle."""
    execution_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    skill_id: str = ""
    inputs: dict[str, str] = Field(default_factory=dict)
    agent_id: str = ""
    status: ExecutionStatus = ExecutionStatus.QUEUED
    tier: LLMTier = LLMTier.STANDARD
    priority: int = 5
    trace: TraceContext = Field(default_factory=TraceContext)

    # Lifecycle timestamps
    queued_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None

    # Results
    output_path: str | None = None
    envelope_path: str | None = None
    error: str | None = None
    retry_count: int = 0
    max_retries: int = 3
    cost: float = 0.0

    # Process tracking
    thread_id: str | None = None
    pid: int | None = None


class DeadLetterEntry(BaseModel):
    """Execution that failed max_retries times — isolated for review."""
    entry_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    execution: TaskExecution
    failure_reason: str = ""
    attempts: int = 0
    escalated: bool = False
    escalated_to: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ── Chain Models ───────────────────────────────────────────────────────


class ChainStep(BaseModel):
    """One step in a skill chain."""
    skill_id: str
    inputs: dict[str, str] = Field(default_factory=dict)
    execution_id: str | None = None
    status: ExecutionStatus = ExecutionStatus.QUEUED
    output_path: str | None = None
    envelope_path: str | None = None
    error: str | None = None


class ChainRequest(BaseModel):
    """Request to run a chain of skills."""
    chain: list[str]                   # Skill IDs in order
    initial_inputs: dict[str, str] = Field(default_factory=dict)
    agent_id: str = ""
    tier: LLMTier = LLMTier.STANDARD
    trace: TraceContext | None = None


class ChainExecution(BaseModel):
    """Tracks a multi-skill chain through its lifecycle."""
    chain_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    steps: list[ChainStep] = Field(default_factory=list)
    status: ChainStatus = ChainStatus.QUEUED
    agent_id: str = ""
    tier: LLMTier = LLMTier.STANDARD
    trace: TraceContext = Field(default_factory=TraceContext)
    current_step: int = 0

    queued_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    total_cost: float = 0.0
    error: str | None = None


# ── Engine State ───────────────────────────────────────────────────────


class EngineState(BaseModel):
    """Overall execution engine state — exposed via /api/execution/status."""
    mode: ExecutionMode = ExecutionMode.CONSERVATIVE
    active_executions: int = 0
    queued_executions: int = 0
    completed_today: int = 0
    failed_today: int = 0
    dead_letter_count: int = 0
    total_cost_today: float = 0.0
    uptime_seconds: int = 0

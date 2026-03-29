"""
Command Center state models.
Defines the normalized state shape that the aggregator produces
and the frontend consumes.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ── Enums ──────────────────────────────────────────────────────────────


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    WARNING = "warning"
    ERROR = "error"
    UNKNOWN = "unknown"


class SkillStatus(str, Enum):
    BUILT = "built"
    REGISTERED = "registered"
    FAILED = "failed"


class BridgeStatus(str, Enum):
    CONNECTED = "connected"
    MOCKED = "mocked"
    ERROR = "error"
    UNCONFIGURED = "unconfigured"


# ── Component Models ───────────────────────────────────────────────────


class SkillInfo(BaseModel):
    skill_id: str
    family: str = ""
    name: str = ""
    status: SkillStatus = SkillStatus.BUILT
    provider: str = ""
    last_run: datetime | None = None
    validation_score: str = ""


class SkillsSummary(BaseModel):
    total_built: int = 0
    total_registered: int = 0
    skills: list[SkillInfo] = Field(default_factory=list)
    families: dict[str, int] = Field(default_factory=dict)


class AgentInfo(BaseModel):
    agent_id: str
    name: str = ""
    role: str = ""
    capabilities: list[str] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)
    status: HealthStatus = HealthStatus.UNKNOWN


class AgentsSummary(BaseModel):
    total: int = 0
    agents: list[AgentInfo] = Field(default_factory=list)


class MASystemInfo(BaseModel):
    system_id: str
    name: str = ""
    test_count: int = 0
    status: HealthStatus = HealthStatus.UNKNOWN


class MASummary(BaseModel):
    total: int = 0
    total_tests: int = 0
    systems: list[MASystemInfo] = Field(default_factory=list)


class BridgeInfo(BaseModel):
    bridge_id: str
    name: str = ""
    api: str = ""
    test_count: int = 0
    test_pass: int = 0
    status: BridgeStatus = BridgeStatus.UNCONFIGURED
    has_api_key: bool = False


class BridgesSummary(BaseModel):
    total: int = 0
    total_tests: int = 0
    connected: int = 0
    bridges: list[BridgeInfo] = Field(default_factory=list)


class ProviderBudget(BaseModel):
    provider: str
    spent: float = 0.0
    limit: float = 30.0
    percent_used: float = 0.0
    currency: str = "USD"


class BudgetSummary(BaseModel):
    total_spent: float = 0.0
    total_limit: float = 0.0
    providers: list[ProviderBudget] = Field(default_factory=list)


class HealthDomain(BaseModel):
    domain: str
    status: HealthStatus = HealthStatus.UNKNOWN
    message: str = ""
    last_check: datetime | None = None


class HealthSummary(BaseModel):
    overall: HealthStatus = HealthStatus.UNKNOWN
    domains: list[HealthDomain] = Field(default_factory=list)


class ValidationSummary(BaseModel):
    total_checks: int = 0
    passed: int = 0
    warnings: int = 0
    failed: int = 0


class FrameworksSummary(BaseModel):
    total: int = 0
    framework_ids: list[str] = Field(default_factory=list)


# ── Top-Level State ────────────────────────────────────────────────────


class SystemState(BaseModel):
    """
    The complete normalized system state.
    Produced by the state aggregator every scan_interval_seconds.
    Broadcast to all connected WebSocket clients.
    """

    timestamp: datetime = Field(default_factory=datetime.now)
    state_version: int = 0  # Monotonic counter — ensures clients never apply stale state
    version: str = "cc-1.0.0"

    skills: SkillsSummary = Field(default_factory=SkillsSummary)
    agents: AgentsSummary = Field(default_factory=AgentsSummary)
    ma_systems: MASummary = Field(default_factory=MASummary)
    bridges: BridgesSummary = Field(default_factory=BridgesSummary)
    budget: BudgetSummary = Field(default_factory=BudgetSummary)
    health: HealthSummary = Field(default_factory=HealthSummary)
    validation: ValidationSummary = Field(default_factory=ValidationSummary)
    frameworks: FrameworksSummary = Field(default_factory=FrameworksSummary)

    # System narrative — rule-based insights for the Home tab
    narrative: list[str] = Field(default_factory=list)

    # Metadata
    repo_root: str = ""
    git_branch: str = ""
    git_commit: str = ""
    pinchtab_status: str = "unknown"


# ── WebSocket Messages ─────────────────────────────────────────────────


class WSMessageType(str, Enum):
    STATE_UPDATE = "state_update"
    HEALTH_ALERT = "health_alert"
    ERROR = "error"
    CONNECTED = "connected"


class WSMessage(BaseModel):
    type: WSMessageType
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)

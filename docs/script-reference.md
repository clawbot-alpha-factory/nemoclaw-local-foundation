# Script Reference

Complete reference for all scripts in the NemoClaw Local Foundation system.

## Core Execution Scripts

### skill-runner.py (v4.0)
**Purpose**: Main skill execution engine. Runs any skill through the LangGraph StateGraph pipeline.

```bash
python3 scripts/skill-runner.py skills/<family>/<skill-id>/skill.yaml --input "Your prompt"
python3 scripts/skill-runner.py skills/<family>/<skill-id>/skill.yaml --input "Your prompt" --depth detailed
```

**Key behaviors**:
- Resolves provider/model via 9-alias routing (`routing-config.yaml`)
- Enforces per-provider budget limits (`budget-config.yaml`)
- SqliteSaver checkpointing for state recovery
- `call_resolved` returns `(result, provider, model)` tuple
- Output keys follow pattern: `step_1_output`, `generated_{thing}`, `improved_{thing}`, `artifact_path`

### validate.py
**Purpose**: 31-check validation suite. Must pass before any commit.

```bash
python3 scripts/validate.py
# Expected: 27 passed, 4 warnings (OpenShell refs), 0 failures
```

**Check categories**: Skill YAML schema, step configuration, routing config, budget config, file structure, naming conventions. 4 warnings are permanent OpenShell infrastructure references (cosmetic).

### test-all.py
**Purpose**: Full regression test runner across all 30 skills.

```bash
python3 scripts/test-all.py
```

### new-skill.py (v2.0)
**Purpose**: Skill scaffolding generator. Creates directory structure and template files.

```bash
python3 scripts/new-skill.py <skill-id> --family <family-code>
```

### obs.py
**Purpose**: Observability and structured logging utility.

```bash
python3 scripts/obs.py
```

---

## Production Operations

### prod-ops.py
**Purpose**: Production operations hub. 14 commands for system management.

```bash
python3 scripts/prod-ops.py status       # One-screen system overview
python3 scripts/prod-ops.py health       # 11-domain health dashboard
python3 scripts/prod-ops.py agents       # Agent roster + performance + compliance
python3 scripts/prod-ops.py run "GOAL"   # Full workflow: decompose → assign → execute → review
python3 scripts/prod-ops.py approvals    # View and manage human-in-the-loop approvals
python3 scripts/prod-ops.py costs        # Budget status + circuit breaker state
python3 scripts/prod-ops.py lessons      # Learning cycle: extract → store → apply
python3 scripts/prod-ops.py report       # SCQA executive report
```

### framework_library.py
**Purpose**: 15 production frameworks (FW-001 through FW-015) sourced from agency-agents assessment. Indexed by domain and skill ID.

```python
from framework_library import get_framework, get_frameworks_for_skill, get_frameworks_for_domain

fw = get_framework("FW-001")              # MEDDPICC Deal Qualification
fws = get_frameworks_for_skill("k40")     # Frameworks for Deal Qualifier skill
fws = get_frameworks_for_domain("sales")  # All sales frameworks
```

---

## Multi-Agent System Scripts (MA-1 through MA-20)

All MA scripts live in `scripts/` and follow consistent patterns:
- Import: `sys.path.insert(0, str(REPO / "scripts"))` then `from module import Class`
- Data storage: `~/.nemoclaw/<subsystem>/`
- Test execution: Each script has a `--test` flag or embedded test suite

### MA-1: agent_registry.py
**Purpose**: Agent identity, capabilities, authority levels, domain assignments.
**Tests**: 8/8
**Key API**:
```python
registry = AgentRegistry()
agent = registry.get_agent("growth_revenue_lead")
# Returns: Agent schema with capabilities, authority, domains
```

### MA-2: agent_memory.py
**Purpose**: 3-layer memory system — working, episodic, shared workspace.
**Tests**: Verified
**Key API**:
```python
memory = AgentMemory(agent_id)
memory.working.store(key, value)
memory.episodic.record(event)
# SharedWorkspaceMemory.write() requires domain_patterns for permission check
```

### MA-3: agent_messaging.py
**Purpose**: Agent-to-agent communication via typed message channels.
**Tests**: 14/14
**Key API**:
```python
channel = MessageChannel(channel_id)
channel.add_message(Message(sender, content, msg_type))
# Uses add_message(Message(...)) not .send()
```

### MA-4: decision_log.py
**Purpose**: Auditable decision tracking with rationale, alternatives, and outcomes.
**Tests**: 12/12
**Key API**:
```python
log = DecisionLog()
log.record(decision_type, rationale, alternatives, agent_id)
```

### MA-5: task_decomposer.py
**Purpose**: Goal → task plan decomposition with parallel execution support.
**Tests**: 5/5
**Key API**:
```python
decomposer = TaskDecomposer()
plan, source, error = decomposer.decompose(goal)
# Returns 3-tuple: (TaskPlan, source_string, error_or_None)
# Templates: market_to_product, validate_and_scope, research_and_document, full_product_pipeline
# Parallel execution capped at 5 concurrent tasks per wave
# Cost gating: auto-execute ≤$15, approval required >$15
```

### MA-6: cost_governor.py
**Purpose**: Circuit breaker + per-agent cost ledger.
**Tests**: 19/19
**Key API**:
```python
governor = CostGovernor()
governor.breaker  # CircuitBreaker: CLOSED/OPEN/HALF_OPEN, trips at 150%
governor.ledger   # AgentLedger: per-agent cost tracking
```

### MA-7: interaction_modes.py
**Purpose**: 5 structured interaction modes between agents.
**Tests**: 26/26
**Key API**:
```python
engine = InteractionEngine()
result = engine.start_session(mode, topic, participants)
# Modes: brainstorm (LLM), critique, debate, synthesis (LLM), reflection
# 4 chaining pipelines available
# Returns (SessionResult, errors)
```

### MA-8: behavior_guard.py
**Purpose**: 12 behavioral rules across 7 categories with graduated enforcement.
**Tests**: 25/25
**Key API**:
```python
guard = BehaviorGuard()
result = guard.check(agent_id, action_type, context)
# Graduated: warn 3x then block
# AUTO_ESCALATE_THRESHOLD = 5
```

### MA-9: failure_recovery.py
**Purpose**: 6 failure categories with configurable retry and cascading blast radius.
**Tests**: 26/26
**Key API**:
```python
recovery = FailureRecovery()
# 6 categories: resource, agent, logic, system, transient, external
# Escalation thresholds: resource=1, agent=2, logic=3, system=3, transient=5
# CRITICAL: Cascading blast radius check runs BEFORE escalation threshold
# _make_key uses `or "none"` not `.get(key, "none")` for None handling
```

### MA-10: conflict_resolution.py
**Purpose**: 6 conflict types, 6 resolution strategies, batch resolution.
**Tests**: 26/26
**Key API**:
```python
resolver = ConflictResolver()
result = resolver.resolve(conflict, strategy, votes, force)
# Auto-resolve minor conflicts with audit logging
# Batch resolution with critical-first ordering
```

### MA-11: peer_review.py
**Purpose**: Smart reviewer selection with domain-weighted scoring.
**Tests**: 28/28
**Key API**:
```python
review = PeerReview()
review.submit_review(reviewer_id, artifact, scores)
# CRITICAL: Self-review check BEFORE assignment check
# Scoring: domain(+3), capability(+2), authority(+1), accuracy(+1), workload(-1)
# Import: sys.path.insert(0, str(REPO / "scripts")) then from conflict_resolution import
```

### MA-12: agent_performance.py
**Purpose**: 5-dimension performance metrics with role-specific weight profiles.
**Tests**: 30/30
**Key API**:
```python
perf = AgentPerformance()
# 5 dimensions, 7 role-specific weight profiles, 5 org goal profiles
# MIN_SAMPLE_THRESHOLD = 3
# Recovery credit: failed-but-recovered = 0.5
# Decision accuracy: 70% outcome + 30% confidence accuracy
```

### MA-13: learning_loop.py
**Purpose**: Cross-system learning extraction with decay.
**Tests**: 32/32
**Key API**:
```python
loop = LearningLoop()
lesson_id, is_new, actual_occurrences = loop.store.add(lesson)
# CRITICAL: Critical priority checked BEFORE auto_apply flag
# Source priority: MA-9(5) > MA-4(4) > MA-12(3) > MA-11(2) > MA-8(2) > MA-10(1)
# Learning decay: 90-day half-life, expire at 0.1
```

### MA-14: system_health.py
**Purpose**: 11 health domains with multi-factor alerting.
**Tests**: 30/30
**Key API**:
```python
health = SystemHealth()
status = health.check_all()
# 11 domains, weights sum to 1.0
# Multi-factor alert: 3+ degraded domains → system-wide alert
# JSON export ready for web dashboard
```

### MA-15: quality_gate.py
**Purpose**: Mandatory output quality validation with type-specific thresholds.
**Tests**: 29/29
**Key API**:
```python
gate = QualityGate()
result = gate.validate(output, output_type)
# Mandatory for all outputs, block on failure
# Type-specific min_length: research=500, product_spec=800
# Max 3 revisions then escalate
```

### MA-16: human_loop.py
**Purpose**: Human-in-the-loop approval system with expiry.
**Tests**: 28/28
**Key API**:
```python
hitl = HumanLoop()
# 4 actions: approve, reject, modify, defer
# 6 categories with configurable expiry (4h-72h)
# Expiry actions: reject, defer, escalate per category
```

### MA-17: context_manager.py
**Purpose**: Context window budget management with priority-based pruning.
**Tests**: 32/32
**Key API**:
```python
ctx = ContextManager()
# Pool budgets 10x: default 80K, research 160K, analysis 200K
# Soft enforcement: only ephemeral items rejected on overflow
# Priority-based pruning (critical items never pruned)
```

### MA-18: internal_competition.py
**Purpose**: Internal competition for high-value task assignment.
**Tests**: 32/32
**Key API**:
```python
comp = InternalCompetition()
# Auto-trigger: tasks above $5 + all critical priority
# 2 default competitors, 3 for critical
# Tiebreak: score gap < 0.05 → faster generation wins
```

### MA-19: access_control.py
**Purpose**: Role-based access control with temporary grants.
**Tests**: 34/34
**Key API**:
```python
acl = AccessControl()
# 6 access domains, 7 role permission sets
# Block + auto-escalate on unauthorized access
# Temporary grants with expiry, only authority level 1 can grant
```

### MA-20: integration_test.py
**Purpose**: End-to-end integration test across all 19 MA systems.
**Tests**: 37/37

```bash
python3 scripts/integration_test.py --test
# 10 phases, 37 checks
# decompose() returns 3-tuple (plan, source, error)
# Channel uses add_message(Message(...)) not .send()
# SharedWorkspaceMemory needs domain_patterns for write permission
```

---

## Key Integration Patterns

| Pattern | Rule |
|---|---|
| `call_resolved` returns | `(result, provider, model)` tuple — always unpack all 3 |
| `decompose()` returns | `(plan, source, error)` tuple — always unpack all 3 |
| Channel messaging | `channel.add_message(Message(...))` not `.send()` |
| Workspace writes | `SharedWorkspaceMemory.write()` requires `domain_patterns` |
| Module imports | `sys.path.insert(0, str(REPO / "scripts"))` then `from module import Class` |
| Key construction | `_make_key` uses `or "none"` for None values in `join()` |
| Output keys | `step_1_output`, `generated_{thing}`, `improved_{thing}`, `artifact_path` |
| Quality thresholds | `min()` scoring, never weighted average |
| Shell commands | Single quotes for anything containing `$` |

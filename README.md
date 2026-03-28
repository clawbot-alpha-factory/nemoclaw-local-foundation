# NemoClaw Local Foundation

A LangGraph-based AI skill execution and multi-agent orchestration system. Built as the technical backbone for an autonomous AI company operating locally on MacBook.

## System Overview

| Metric | Count |
|---|---|
| Skills | 30 (Tiers 1–3 complete) |
| Multi-Agent Systems | 20/20 |
| Agents | 7 (fully configured) |
| Production Frameworks | 15 |
| Total Tests | 497+ |
| Validation | 27 passed, 4 warnings, 0 failures |

## Architecture

**Runtime**: MacBook M1 16GB, macOS Sequoia, Python 3.12.13 (`.venv312`)

**Core Stack**:
- LangGraph StateGraph with SqliteSaver checkpointing
- Direct API calls to Anthropic / OpenAI / Google via LangChain
- 9-alias routing architecture (`routing-config.yaml`)
- Per-provider budget enforcement (`budget-config.yaml`)

**Design Philosophy**: Premium quality with no shortcuts. Every skill passes validation before commit. Specs approved before code is written. All commits are atomic (docs + code + tests together).

## Quick Start

```bash
# Activate environment
source .venv312/bin/activate

# Run a skill
python3 scripts/skill-runner.py skills/<family>/<skill-id>/skill.yaml --input "Your prompt here"

# System status
python3 scripts/prod-ops.py status

# Full validation
python3 scripts/validate.py
```

## Skills (30)

### Tier 1 — Foundation (10 skills)
| ID | Name | Family | Domain |
|---|---|---|---|
| a01-general-qa | General Q&A | A01 | Execution |
| b05-summarizer | Document Summarizer | B05 | Execution |
| c09-market-analyst | Market Analyst | C09 | Intelligence |
| d11-video-script-writer | Video Script Writer | D11 | Content |
| e15-brand-voice-auditor | Brand Voice Auditor | E15 | Validation |
| f24-agent-router | Agent Router | F24 | Orchestration |
| g26-skill-spec-writer | Skill Spec Writer | G26 | Meta |
| g26-skill-template-gen | Skill Template Generator | G26 | Meta |
| h30-cold-email-writer | Cold Email Writer | H30 | Outreach |
| i35-tone-calibrator | Tone Calibrator | I35 | Content |

### Tier 2 — Expansion (10 skills)
| ID | Name | Family | Domain |
|---|---|---|---|
| j36-biz-idea-validator | Business Idea Validator | J36 | Planning |
| j36-mvp-scope-definer | MVP Scope Definer | J36 | Planning |
| And 8 additional skills completing Tier 2 coverage | | | |

### Tier 3 — Specialization (10 skills)
10 additional skills built and validated across intelligence, content, and execution domains.

## Multi-Agent Systems (20/20)

| # | System | Script | Tests | Purpose |
|---|---|---|---|---|
| MA-1 | Agent Schema & Registry | `agent_registry.py` | 8/8 | Agent identity, capabilities, authority levels |
| MA-2 | 3-Layer Memory | `agent_memory.py` | Verified | Working, episodic, shared workspace memory |
| MA-3 | Message Protocol | `agent_messaging.py` | 14/14 | Agent-to-agent communication channels |
| MA-4 | Decision Log | `decision_log.py` | 12/12 | Auditable decision tracking with rationale |
| MA-5 | Task Decomposition | `task_decomposer.py` | 5/5 | Goal → task plan with parallel execution |
| MA-6 | Cost Governance | `cost_governor.py` | 19/19 | Circuit breaker + per-agent cost tracking |
| MA-7 | Interaction Modes | `interaction_modes.py` | 26/26 | Brainstorm, critique, debate, synthesis, reflection |
| MA-8 | Behavior Rules | `behavior_guard.py` | 25/25 | 12 rules, graduated enforcement, auto-escalation |
| MA-9 | Failure Recovery | `failure_recovery.py` | 26/26 | 6 failure categories, cascading blast radius checks |
| MA-10 | Conflict Resolution | `conflict_resolution.py` | 26/26 | 6 conflict types, 6 strategies, batch resolution |
| MA-11 | Peer Review | `peer_review.py` | 28/28 | Smart reviewer selection, domain-weighted scoring |
| MA-12 | Agent Performance | `agent_performance.py` | 30/30 | 5 dimensions, 7 role profiles, recovery credit |
| MA-13 | Learning Loop | `learning_loop.py` | 32/32 | Cross-system learning with 90-day decay |
| MA-14 | System Health | `system_health.py` | 30/30 | 11 health domains, multi-factor alerting |
| MA-15 | Output Quality Gate | `quality_gate.py` | 29/29 | Mandatory output validation, type-specific thresholds |
| MA-16 | Human-in-the-Loop | `human_loop.py` | 28/28 | 6 approval categories with configurable expiry |
| MA-17 | Context Window Mgmt | `context_manager.py` | 32/32 | Pool budgets, priority-based pruning |
| MA-18 | Internal Competition | `internal_competition.py` | 32/32 | Auto-trigger on high-value tasks, tiebreaking |
| MA-19 | Security & Access | `access_control.py` | 34/34 | 6 domains, 7 role permission sets, temporary grants |
| MA-20 | Integration Test | `integration_test.py` | 37/37 | 10-phase validation across all 19 MA systems |

## Agents (7)

| Agent | Role | Authority | Key Capabilities |
|---|---|---|---|
| `strategic_oversight_lead` | CEO-level strategic direction | 1 | Strategy, governance, final approval |
| `growth_revenue_lead` | Revenue and growth execution | 2 | Sales, marketing, pipeline, outreach |
| `product_delivery_lead` | Product development and delivery | 2 | Product specs, MVP scoping, roadmaps |
| `narrative_content_lead` | Content and brand voice | 3 | Writing, SEO, social, brand consistency |
| `intelligence_research_lead` | Market and competitive intelligence | 3 | Research, analysis, data synthesis |
| `operations_systems_lead` | Internal systems and automation | 3 | Tooling, workflows, infrastructure |
| `quality_validation_lead` | Quality assurance and validation | 3 | Testing, review, compliance, standards |

## Production Operations

### Operations Hub (`prod-ops.py`)

```bash
python3 scripts/prod-ops.py status       # One-screen system overview
python3 scripts/prod-ops.py health       # 11-domain health dashboard
python3 scripts/prod-ops.py agents       # Roster + performance + compliance
python3 scripts/prod-ops.py run "GOAL"   # Full workflow execution
python3 scripts/prod-ops.py approvals    # Manage human approvals
python3 scripts/prod-ops.py costs        # Budget + circuit breaker status
python3 scripts/prod-ops.py lessons      # Learning cycle review
python3 scripts/prod-ops.py report       # SCQA executive report
```

### Framework Library (`framework_library.py`)

15 production frameworks (FW-001 through FW-015) indexed by domain and skill ID. Sourced from agency-agents assessment.

```python
from framework_library import get_framework, get_frameworks_for_domain
fw = get_framework("FW-001")  # MEDDPICC Deal Qualification
fws = get_frameworks_for_domain("sales")
```

## Core Scripts

| Script | Version | Purpose |
|---|---|---|
| `skill-runner.py` | v4.0 | Skill execution engine |
| `validate.py` | — | 31-check validation suite (27 pass, 4 warn) |
| `test-all.py` | — | Full regression test runner |
| `new-skill.py` | v2.0 | Skill scaffolding generator |
| `obs.py` | — | Observability and logging |
| `prod-ops.py` | — | Production operations hub (14 commands) |
| `integration_test.py` | — | MA-20 integration test (37 checks) |
| `framework_library.py` | — | 15 production frameworks |

## Configuration

| File | Purpose |
|---|---|
| `routing-config.yaml` | 9-alias model routing (provider + model per alias) |
| `budget-config.yaml` | Per-provider spending limits and tracking |
| `skill-yaml-schema-v2` | Skill definition schema |

## Budget Status

| Provider | Used | Limit | % |
|---|---|---|---|
| Anthropic | ~$9.60 | $30 | 32% |
| OpenAI | ~$0.33 | $30 | 1% |
| Google | ~$0.00 | $30 | 0% |

## Validation

```bash
python3 scripts/validate.py
# Result: 27 passed, 4 warnings (expected — OpenShell refs), 0 failures
```

The 4 warnings are permanent OpenShell infrastructure references. These are cosmetic and do not affect functionality.

## Project Structure

```
nemoclaw-local-foundation/
├── skills/                    # 30 skills organized by family
│   ├── a01-general-qa/
│   ├── b05-summarizer/
│   └── ...
├── scripts/                   # Core execution and MA systems
│   ├── skill-runner.py        # v4.0 execution engine
│   ├── validate.py            # 31-check validation
│   ├── prod-ops.py            # Production operations hub
│   ├── integration_test.py    # MA-20 integration test
│   ├── framework_library.py   # 15 production frameworks
│   ├── agent_registry.py      # MA-1
│   ├── agent_memory.py        # MA-2
│   ├── agent_messaging.py     # MA-3
│   ├── decision_log.py        # MA-4
│   ├── task_decomposer.py     # MA-5
│   ├── cost_governor.py       # MA-6
│   ├── interaction_modes.py   # MA-7
│   ├── behavior_guard.py      # MA-8
│   ├── failure_recovery.py    # MA-9
│   ├── conflict_resolution.py # MA-10
│   ├── peer_review.py         # MA-11
│   ├── agent_performance.py   # MA-12
│   ├── learning_loop.py       # MA-13
│   ├── system_health.py       # MA-14
│   ├── quality_gate.py        # MA-15
│   ├── human_loop.py          # MA-16
│   ├── context_manager.py     # MA-17
│   ├── internal_competition.py # MA-18
│   └── access_control.py      # MA-19
├── docs/                      # Architecture and reference docs
├── config/                    # Routing and budget configs
└── README.md
```

## Development Workflow

1. **Spec** → Write skill spec using `g26-skill-spec-writer`
2. **Review** → ❌ Required Fixes / ⚠️ Recommended Improvements
3. **Approval** → User approves spec before any code
4. **Build** → Generate with `g26-skill-template-gen` or manual build
5. **Test** → Real execution with `skill-runner.py`
6. **Validate** → `validate.py` (31/31 or 27 pass + 4 warn)
7. **Commit** → Atomic commit (docs + code + tests)
8. **Push** → `git push` after every validated fix

## Key Patterns

- **H2-scoped extraction**: `##\s` not `##?` for section headers
- **Depth-driven tokens**: overview=12K, strategic=16K, detailed=20K
- **min() scoring**: Never weighted average for quality gates
- **Hard-fail over silent degradation**: Every skill hard-fails on integrity violations
- **Tuple returns**: `call_resolved` returns `(result, provider, model)`
- **LangChain wrappers**: All LLM calls go through LangChain
- **Single quotes for shell**: Prevents `$variable` expansion in output

## Repo

- **GitHub**: [clawbot-alpha-factory/nemoclaw-local-foundation](https://github.com/clawbot-alpha-factory/nemoclaw-local-foundation)
- **Latest commit**: `3bf4496` (Production Operations Hub + Framework Library)
- **Status**: Clean, fully pushed

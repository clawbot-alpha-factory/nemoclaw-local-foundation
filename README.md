# NemoClaw Local Foundation

A LangGraph-based AI skill execution and multi-agent orchestration system. Built as the technical backbone for an autonomous AI company operating locally on MacBook.

## System Overview

| Metric | Value |
|---|---|
| Skills Built | 30 |
| Skills Registered | 15 (k40-k54, awaiting agent build) |
| Multi-Agent Systems | 20/20 |
| Agents | 7 (fully configured) |
| Production Frameworks | 15 |
| Health Domains | 12 |
| Integration Test | 50/50 (11 phases) |
| Validation | 27 passed, 4 warnings, 0 failures |

## Architecture

**Runtime**: MacBook M1 16GB, macOS Sequoia, Python 3.12.13 (`.venv312`)

**Core Stack**:
- LangGraph StateGraph with SqliteSaver checkpointing
- Direct API calls to Anthropic / OpenAI / Google via LangChain
- 9-alias routing architecture (`routing-config.yaml`)
- Per-provider budget enforcement (`budget-config.yaml`)
- PinchTab browser automation via HTTP API (`web_browser.py`)

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

# Integration test
python3 scripts/integration_test.py --test

# Browser bridge test
python3 scripts/web_browser.py --test
```

## Skills (30 Built)

### A01 — Architecture & System Design (3 skills)
| ID | Name |
|---|---|
| a01-api-surface-designer | API Surface Designer |
| a01-arch-spec-writer | Architecture Spec Writer |
| a01-sys-context-mapper | System Context Mapper |

### B05 — Implementation & Code (4 skills)
| ID | Name |
|---|---|
| b05-bug-fix-impl | Bug Fix Implementation |
| b05-feature-impl-writer | Feature Implementation Writer |
| b05-scaffold-gen | Scaffold Generator |
| b05-script-automator | Script Automator |

### B06 — DevOps & Release (2 skills)
| ID | Name |
|---|---|
| b06-cicd-designer | CI/CD Designer |
| b06-release-notes-gen | Release Notes Generator |

### C07 — Documentation (4 skills)
| ID | Name |
|---|---|
| c07-api-doc-gen | API Documentation Generator |
| c07-decision-record-writer | Decision Record Writer |
| c07-runbook-author | Runbook Author |
| c07-setup-guide-writer | Setup Guide Writer |

### D11 — Content Creation (2 skills)
| ID | Name |
|---|---|
| d11-copywriting-specialist | Copywriting Specialist |
| d11-video-script-writer | Video Script Writer |

### E08 — Intelligence & Analysis (3 skills)
| ID | Name |
|---|---|
| e08-comp-intel-synth | Competitive Intelligence Synthesizer |
| e08-kb-article-writer | Knowledge Base Article Writer |
| e08-meeting-summary-gen | Meeting Summary Generator |

### E12 — Research (2 skills)
| ID | Name |
|---|---|
| e12-market-research-analyst | Market Research Analyst |
| e12-tech-trend-scanner | Tech Trend Scanner |

### F09 — Product & Pricing (2 skills)
| ID | Name |
|---|---|
| f09-pricing-strategist | Pricing Strategist |
| f09-product-req-writer | Product Requirements Writer |

### G25 — System Utilities (2 skills)
| ID | Name |
|---|---|
| g25-output-format-enforcer | Output Format Enforcer |
| g25-sys-prompt-designer | System Prompt Designer |

### G26 — Meta / Skill Factory (2 skills)
| ID | Name |
|---|---|
| g26-skill-spec-writer | Skill Spec Writer |
| g26-skill-template-gen | Skill Template Generator |

### I35 — Content Transformation (1 skill)
| ID | Name |
|---|---|
| i35-tone-calibrator | Tone Calibrator (gold standard reference) |

### J36 — Business Planning (2 skills)
| ID | Name |
|---|---|
| j36-biz-idea-validator | Business Idea Validator |
| j36-mvp-scope-definer | MVP Scope Definer |

### Research (1 skill)
| ID | Name |
|---|---|
| research-brief | Research Brief |

## Registered Skills (15 — Awaiting Agent Build)

### k40-k49: Growth & Content (from Framework Library)
| ID | Name | Agent | Framework |
|---|---|---|---|
| k40 | Deal Qualifier (MEDDPICC) | growth_revenue_lead | FW-001 |
| k41 | PPC Campaign Architect | growth_revenue_lead | FW-011 |
| k42 | Paid Social Planner | growth_revenue_lead | — |
| k43 | Pipeline Analyzer | growth_revenue_lead | FW-004 |
| k44 | Content Strategy Planner | narrative_content_lead | FW-008 |
| k45 | SEO Audit Writer | narrative_content_lead | FW-010 |
| k46 | LinkedIn Content Writer | narrative_content_lead | FW-009 |
| k47 | Account Expansion Planner | growth_revenue_lead | — |
| k48 | Ad Creative Writer | growth_revenue_lead | FW-012 |
| k49 | AI Citation Optimizer | narrative_content_lead | FW-014 |

### k50-k54: Web-Aware Skills (require PinchTab)
| ID | Name | Agent | PinchTab Actions |
|---|---|---|---|
| k50 | Web Deep Researcher | intelligence_research_lead | navigate, text, scroll |
| k51 | Competitor Intelligence Scraper | intelligence_research_lead | navigate, snapshot, text, click |
| k52 | Web Lead Enricher | growth_revenue_lead | navigate, fill, click, text |
| k53 | Social Media Publisher | narrative_content_lead | navigate, fill, click, screenshot |
| k54 | Analytics Dashboard Reader | operations_systems_lead | navigate, text, click, screenshot |

## Multi-Agent Systems (20/20)

| # | System | Script | Tests | Purpose |
|---|---|---|---|---|
| MA-1 | Agent Schema & Registry | `agent_registry.py` | 8/8 | Agent identity, capabilities, authority levels |
| MA-2 | 3-Layer Memory | `agent_memory.py` | Verified | Working, episodic, shared workspace memory |
| MA-3 | Message Protocol | `agent_messaging.py` | 14/14 | Agent-to-agent communication channels |
| MA-4 | Decision Log | `decision_log.py` | 12/12 | Auditable decision tracking with rationale |
| MA-5 | Task Decomposition | `task_decomposer.py` | 5/5 | Goal → task plan with parallel execution |
| MA-6 | Cost Governance | `cost_governor.py` | 28/28 | Circuit breaker, per-agent cost + browser action tracking |
| MA-7 | Interaction Modes | `interaction_modes.py` | 26/26 | Brainstorm, critique, debate, synthesis, reflection |
| MA-8 | Behavior Rules | `behavior_guard.py` | 35/35 | 16 rules (8 categories incl. web safety), graduated enforcement |
| MA-9 | Failure Recovery | `failure_recovery.py` | 26/26 | 6 failure categories, cascading blast radius checks |
| MA-10 | Conflict Resolution | `conflict_resolution.py` | 26/26 | 6 conflict types, 6 strategies, batch resolution |
| MA-11 | Peer Review | `peer_review.py` | 28/28 | Smart reviewer selection, domain-weighted scoring |
| MA-12 | Agent Performance | `agent_performance.py` | 30/30 | 5 dimensions, 7 role profiles, recovery credit |
| MA-13 | Learning Loop | `learning_loop.py` | 32/32 | Cross-system learning with 90-day decay |
| MA-14 | System Health | `system_health.py` | 37/37 | 12 health domains (incl. browser), multi-factor alerting |
| MA-15 | Output Quality Gate | `quality_gate.py` | 29/29 | Mandatory output validation, type-specific thresholds |
| MA-16 | Human-in-the-Loop | `human_loop.py` | 28/28 | 6 approval categories with configurable expiry |
| MA-17 | Context Window Mgmt | `context_manager.py` | 32/32 | Pool budgets, priority-based pruning |
| MA-18 | Internal Competition | `internal_competition.py` | 32/32 | Auto-trigger on high-value tasks, tiebreaking |
| MA-19 | Security & Access | `access_control.py` | 44/44 | 7 domains (incl. web), per-agent permissions, temp grants |
| MA-20 | Integration Test | `integration_test.py` | 50/50 | 11-phase validation across 19 MA systems + browser |

## Agents (7)

| Agent | Role | Authority | Web Access |
|---|---|---|---|
| `strategic_oversight_lead` | CEO-level strategic direction | 1 | Full (incl. eval) |
| `growth_revenue_lead` | Revenue and growth execution | 2 | Full (no eval) |
| `product_delivery_lead` | Product development and delivery | 2 | Navigate + text |
| `narrative_content_lead` | Content and brand voice | 3 | Full (no eval) |
| `intelligence_research_lead` | Market and competitive intelligence | 3 | Navigate + text |
| `operations_systems_lead` | Internal systems and automation | 3 | Navigate + text |
| `quality_validation_lead` | Quality assurance and validation | 3 | Navigate + text |

## Production Operations

### Operations Hub (`prod-ops.py`)

```bash
python3 scripts/prod-ops.py status       # One-screen system overview
python3 scripts/prod-ops.py health       # 12-domain health dashboard
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

## Browser Automation (PinchTab)

NemoClaw agents can control Chrome via [PinchTab](https://github.com/pinchtab/pinchtab) — a 12MB Go binary providing HTTP-based browser control with accessibility-first element refs.

**What it enables**: Navigate websites, extract content (~800 tokens/page), fill forms, click buttons, take screenshots, read dashboards, post to social media — all governed by MA systems.

**Install**:
```bash
curl -fsSL https://pinchtab.com/install.sh | bash
pinchtab  # Start server (select Guard DOWN for development)
```

**Python Bridge** (`scripts/web_browser.py`, 40/40 tests):
```python
from web_browser import PinchTabClient
browser = PinchTabClient(agent_id="growth_revenue_lead")
ok, result = browser.navigate("https://example.com")
ok, text = browser.text()
ok, snap = browser.snapshot(interactive=True)
ok, result = browser.click("e5")
```

**Governance**: All browser actions governed by:
- **MA-19**: Web access domain — per-agent permissions (navigate, text, click, fill, screenshot, eval)
- **MA-8**: 4 web safety rules — block payment forms, block destructive actions, require screenshot before submit, require approval for first login
- **MA-14**: Browser health domain — PinchTab server, instance count, memory usage, error rate monitoring
- **MA-6**: Browser action budgets — navigations/hour, clicks/task, text extractions/hour, screenshots/hour

**Configuration**: `config/pinchtab-config.yaml` — per-agent profiles, rate limits, blocked domains, scheduler settings.

## Core Scripts

| Script | Purpose |
|---|---|
| `skill-runner.py` | v4.0 skill execution engine |
| `validate.py` | 31-check validation suite (27 pass, 4 warn) |
| `test-all.py` | Full regression test runner |
| `new-skill.py` | v2.0 skill scaffolding generator |
| `obs.py` | Observability and logging |
| `prod-ops.py` | Production operations hub (14 commands) |
| `integration_test.py` | MA-20 integration test (50 checks, 11 phases) |
| `framework_library.py` | 15 production frameworks |
| `web_browser.py` | PinchTab browser bridge (40 tests) |

## Configuration

| File | Purpose |
|---|---|
| `routing-config.yaml` | 9-alias model routing (provider + model per alias) |
| `budget-config.yaml` | Per-provider spending limits and tracking |
| `skill-yaml-schema-v2` | Skill definition schema |
| `pinchtab-config.yaml` | PinchTab per-agent profiles, rate limits, safety rules |

## Budget Status

| Provider | Used | Limit | % |
|---|---|---|---|
| Anthropic | ~$9.72 | $30 | 32% |
| OpenAI | ~$0.33 | $30 | 1% |
| Google | ~$0.00 | $30 | 0% |

## Validation

```bash
python3 scripts/validate.py
# Result: 27 passed, 4 warnings (expected — OpenShell refs), 0 failures
```

The 4 warnings are permanent OpenShell infrastructure references from the original NemoClaw stack. These are cosmetic and do not affect functionality.

## Project Structure

```
nemoclaw-local-foundation/
├── skills/                       # 30 skills organized by family
│   ├── a01-*/                    # Architecture & system design (3)
│   ├── b05-*/                    # Implementation & code (4)
│   ├── b06-*/                    # DevOps & release (2)
│   ├── c07-*/                    # Documentation (4)
│   ├── d11-*/                    # Content creation (2)
│   ├── e08-*/                    # Intelligence & analysis (3)
│   ├── e12-*/                    # Research (2)
│   ├── f09-*/                    # Product & pricing (2)
│   ├── g25-*/                    # System utilities (2)
│   ├── g26-*/                    # Meta / skill factory (2)
│   ├── i35-tone-calibrator/      # Content transformation (1)
│   ├── j36-*/                    # Business planning (2)
│   └── research-brief/           # Research brief (1)
├── scripts/                      # 33 scripts — execution + MA systems
│   ├── skill-runner.py           # v4.0 execution engine
│   ├── validate.py               # 31-check validation
│   ├── prod-ops.py               # Production operations hub
│   ├── integration_test.py       # MA-20 (50 checks, 11 phases)
│   ├── framework_library.py      # 15 production frameworks
│   ├── web_browser.py            # PinchTab bridge (40 tests)
│   ├── agent_registry.py         # MA-1
│   ├── agent_memory.py           # MA-2
│   ├── agent_messaging.py        # MA-3
│   ├── decision_log.py           # MA-4
│   ├── task_decomposer.py        # MA-5
│   ├── cost_governor.py          # MA-6 (28 tests)
│   ├── interaction_modes.py      # MA-7
│   ├── behavior_guard.py         # MA-8 (35 tests)
│   ├── failure_recovery.py       # MA-9
│   ├── conflict_resolution.py    # MA-10
│   ├── peer_review.py            # MA-11
│   ├── agent_performance.py      # MA-12
│   ├── learning_loop.py          # MA-13
│   ├── system_health.py          # MA-14 (37 tests)
│   ├── quality_gate.py           # MA-15
│   ├── human_loop.py             # MA-16
│   ├── context_manager.py        # MA-17
│   ├── internal_competition.py   # MA-18
│   └── access_control.py         # MA-19 (44 tests)
├── config/                       # Routing, budget, PinchTab configs
│   └── pinchtab-config.yaml      # Browser automation config
├── docs/                         # Architecture, reference, catalogs
│   ├── architecture-lock.md      # Locked decisions (L-001 to L-413)
│   ├── script-reference.md       # Full script API reference
│   ├── skill-catalog-k40-k49.yaml  # 10 registered skills
│   └── skill-catalog-k50-k54.yaml  # 5 web-aware registered skills
└── README.md
```

## Development Workflow

1. **Spec** → Write skill spec using `g26-skill-spec-writer`
2. **Review** → ❌ Required Fixes / ⚠️ Recommended Improvements
3. **Approval** → User approves spec before any code
4. **Build** → Generate with `g26-skill-template-gen` or manual build
5. **Test** → Real execution with `skill-runner.py`
6. **Validate** → `validate.py` (27 pass + 4 warn)
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
- **Browser via bridge**: All PinchTab calls through `PinchTabClient`, never raw HTTP

## Repo

- **GitHub**: [clawbot-alpha-factory/nemoclaw-local-foundation](https://github.com/clawbot-alpha-factory/nemoclaw-local-foundation)
- **Latest commit**: `407e076` (Integration test Phase 11 — browser automation, 50/50)
- **Status**: Clean, fully pushed

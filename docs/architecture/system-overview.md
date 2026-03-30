# System Architecture Overview

> **Location:** `docs/architecture/system-overview.md`
> **Version:** 1.0
> **Date:** 2026-03-24
> **Phase:** 12 — Documentation Consolidation
> **Status:** Current — reflects system as built through Phase 11

---

## What This System Is

A local MacBook-based AI agent foundation built on LangGraph with direct API access to three inference providers (Anthropic, OpenAI, Google). It executes structured workflows called Skills through a governed routing and budget system, with full audit logging, checkpoint-based state persistence, and automated validation.

The system started as a NemoClaw/OpenShell local build and migrated to a custom LangGraph + Direct API architecture in Phase 6. The NemoClaw sandbox is retained but not required for inference or skill execution. See `architecture-lock.md` for the full migration rationale.

---

## Architecture Layers

The system is organized in seven layers. Each layer has a clear responsibility and documented boundary.

```
┌─────────────────────────────────────────────────────────┐
│  Layer 7: Observability & Validation                    │
│  obs.py, validate.py (31 checks), validation-runs.jsonl │
├─────────────────────────────────────────────────────────┤
│  Layer 6: External Tools                                │
│  tools.py, Asana, 16-tool registry (Phase 12 expansion) │
├─────────────────────────────────────────────────────────┤
│  Layer 5: Skills                                        │
│  skill-runner.py, skill.yaml, LangGraph StateGraph      │
├─────────────────────────────────────────────────────────┤
│  Layer 4: Budget Enforcement                            │
│  budget-enforcer.py, budget-config.yaml, spend tracking │
├─────────────────────────────────────────────────────────┤
│  Layer 3: Model Routing                                 │
│  routing-config.yaml, 9 aliases, 10 task classes        │
├─────────────────────────────────────────────────────────┤
│  Layer 2: Inference Providers                           │
│  Anthropic (langchain), OpenAI (langchain), Google API  │
├─────────────────────────────────────────────────────────┤
│  Layer 1: Local Environment                             │
│  MacBook M1, Python 3.12 venv, Docker Desktop, config   │
└─────────────────────────────────────────────────────────┘
```

---

## Layer 1 — Local Environment

The foundation layer. Everything runs on a MacBook Apple Silicon M1 with 16GB RAM, macOS Sequoia.

**Key components:**

- Python 3.12.13 virtual environment at `.venv313/` — isolated from system Python 3.14
- Docker Desktop 29+ — required for NemoClaw sandbox (retained, not required for inference)
- `config/.env` — all API keys and credentials, gitignored
- `config/.env.example` — placeholder template, committed

**Documented in:** `docs/setup/local-environment-setup.md`, `docs/setup/restart-recovery-runbook.md`

---

## Layer 2 — Inference Providers

Three providers, each accessed via direct API calls. No proxy, no sandbox interception.

| Provider | Library | Models Used |
|---|---|---|
| OpenAI | langchain-openai | gpt-5.4-mini, gpt-5.4, o3 |
| Anthropic | langchain-anthropic | claude-haiku-4-5-20251001, claude-sonnet-4-6, claude-opus-4-6 |
| Google | google-generativeai | gemini-2.5-flash, gemini-2.5-pro-preview-03-25 |

API keys: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY` (all in `config/.env`)

**Documented in:** `docs/architecture/routing-system.md`

---

## Layer 3 — Model Routing

Every inference call is routed through an alias system. A task class determines which alias handles it. The alias resolves to a specific provider and model.

**9 routing aliases:**

| Alias | Provider | Model | Role |
|---|---|---|---|
| cheap_openai | OpenAI | gpt-5.4-mini | Default — short, structured, cheap |
| reasoning_openai | OpenAI | gpt-5.4 | Heavy reasoning, coding, agentic |
| reasoning_o3 | OpenAI | o3 | Deep STEM reasoning — expensive |
| cheap_claude | Anthropic | claude-haiku-4-5-20251001 | Moderate complexity, fast |
| reasoning_claude | Anthropic | claude-sonnet-4-6 | Complex reasoning, synthesis |
| premium_claude | Anthropic | claude-opus-4-6 | Highest quality — critical outputs |
| cheap_google | Google | gemini-2.5-flash | Fast multimodal, long context |
| reasoning_google | Google | gemini-2.5-pro-preview-03-25 | Google flagship reasoning |
| fallback_openai | OpenAI | gpt-5.4-mini | Emergency fallback |

**10 task classes** map to aliases:

| Task Class | Routes To |
|---|---|
| general_short | cheap_openai |
| structured_short | cheap_openai |
| moderate | cheap_claude |
| complex_reasoning | reasoning_claude |
| code | reasoning_openai |
| agentic | reasoning_claude |
| long_document | reasoning_google |
| vision | cheap_google |
| deep_reasoning | reasoning_o3 |
| premium | premium_claude |

**Config file:** `config/routing/routing-config.yaml`

**Documented in:** `docs/architecture/routing-system.md`

---

## Layer 4 — Budget Enforcement

Every inference call passes through budget enforcement before execution. Spend is tracked cumulatively across sessions per provider.

| Provider | Budget | Warn At | Hard Stop |
|---|---|---|---|
| Anthropic | $30.00 | 90% ($27.00) | 100% ($30.00) |
| OpenAI | $30.00 | 90% ($27.00) | 100% ($30.00) |
| Google | $30.00 | 90% ($27.00) | 100% ($30.00) |

**Budget files:**

| File | Location | Purpose |
|---|---|---|
| budget-config.yaml | config/routing/ | Budget limits and thresholds |
| provider-spend.json | ~/.nemoclaw/logs/ | Cumulative spend per provider |
| provider-usage.jsonl | ~/.nemoclaw/logs/ | Per-call usage log |
| budget-audit.log | ~/.nemoclaw/logs/ | Threshold warnings and hard stops |

**Enforcement script:** `scripts/budget-enforcer.py`

**Documented in:** `docs/architecture/budget-system.md`

---

## Layer 5 — Skills

Skills are structured multi-step workflows executed as LangGraph StateGraphs. Each skill is defined by a `skill.yaml` that specifies inputs, outputs, steps, task class routing, validation rules, and approval boundaries.

**Execution flow:**

1. `skill-runner.py` reads `skill.yaml` and builds a LangGraph StateGraph
2. Each step calls the budget enforcer to resolve its task class to an alias and model
3. The inference call is made, cost is tracked, and the result flows to the next step
4. State is checkpointed after each step via LangGraph SqliteSaver
5. The final step writes an artifact to the skill's outputs directory

**Current skills:**

| Skill | Steps | Status |
|---|---|---|
| research-brief | 5 (validate → research → structure → validate → write) | Production — tested |

**Key files:**

| File | Purpose |
|---|---|
| skills/skill-runner.py | LangGraph skill execution engine v4.0 |
| skills/research-brief/skill.yaml | Skill definition |
| skills/research-brief/outputs/ | Artifact output directory (gitignored) |

**State persistence:** LangGraph SqliteSaver at `~/.nemoclaw/checkpoints/langgraph.db`

**Resume:** `--thread-id THREAD_ID --resume` passed to skill-runner.py

**Documented in:** `docs/architecture/skill-system.md`

---

## Layer 6 — External Tools

External tools are third-party services integrated into the system. The integration framework is built; most tools are Phase 12 placeholders.

**Active now:** GitHub (no key needed), Asana (validated)

**Framework:** `scripts/tools.py` defines the standard wrapper — credential loading, validation, audit logging, error handling.

**Registry:** 16 tools across 5 tiers, documented in `docs/extensions/external-tools-registry.md`

**Audit log:** `~/.nemoclaw/logs/tools-audit.log`

**Documented in:** `docs/extensions/external-tools-registry.md`

---

## Layer 7 — Observability & Validation

The system provides runtime visibility through three scripts and structured log files.

**Scripts:**

| Script | Purpose |
|---|---|
| validate.py | 31-check system validation across 6 categories |
| obs.py | Unified system observer — health, spend, recent runs, checkpoints, failures |
| budget-status.py | Provider spend summary with visual budget bars |

**Validation categories (31 checks):**

| Category | Checks | Covers |
|---|---|---|
| 1 — Environment | 5 | Docker, Python, openshell, Node |
| 2 — NemoClaw Runtime | 5 | Gateway, sandbox, inference, permissions |
| 3 — API Keys | 7 | All 6 keys present + Asana validation |
| 4 — Budget System | 5 | Spend file, 3 provider budgets, usage log |
| 5 — Routing System | 3 | Enforcer runs, 2 route spot-checks |
| 6 — Skill System | 6 | obs.py, graph patterns, runner, skill.yaml, outputs, checkpoint DB |

**Log files (all under `~/.nemoclaw/logs/`):**

| Log | Format | Purpose |
|---|---|---|
| provider-spend.json | JSON | Cumulative spend per provider |
| provider-usage.jsonl | JSONL | Every inference call with cost |
| budget-audit.log | Text | Budget threshold events |
| tools-audit.log | Text | External tool call events |
| validation-runs.jsonl | JSONL | Validation run history |

**Documented in:** `docs/architecture/validation-system.md`

---

## Data Flow — Skill Execution

This is the end-to-end flow when a skill runs:

```
User invokes skill-runner.py
        │
        ▼
skill-runner.py reads skill.yaml
        │
        ▼
LangGraph StateGraph built from steps
        │
        ▼
For each step:
   ├── Read task_class from skill.yaml step definition
   ├── budget-enforcer.py resolves task_class → alias → model
   ├── Budget check: spend < limit? ──No──► fallback or halt
   │                                  Yes
   ├── Inference call via langchain (provider-specific)
   ├── Cost logged to provider-usage.jsonl
   ├── Spend updated in provider-spend.json
   ├── Step result stored in SkillState
   └── Checkpoint saved to langgraph.db
        │
        ▼
Final step writes artifact to skills/{name}/outputs/
        │
        ▼
Skill complete — thread ID printed for resume reference
```

---

## Configuration Map

| Config File | Location | Controls |
|---|---|---|
| .env | config/ | All API keys and credentials |
| .env.example | config/ | Placeholder template (committed) |
| routing-config.yaml | config/routing/ | 9 aliases, 10 task classes, provider mapping |
| budget-config.yaml | config/routing/ | Per-provider budgets, thresholds, log config |
| skill.yaml | skills/{name}/ | Per-skill definition |
| sandbox-policy.yaml | docs/architecture/ | OpenShell sandbox policy (reference only) |

**Documented in:** `docs/reference/config-reference.md`

---

## Repo Structure

```
nemoclaw-local-foundation/
├── README.md
├── openclaw.json/              # Directory containing openclaw.json and .bak
├── config/
│   ├── .env                          # API keys (gitignored)
│   ├── .env.example                  # Placeholder template
│   └── routing/
│       ├── routing-config.yaml       # Model routing
│       └── budget-config.yaml        # Budget limits
├── scripts/
│   ├── validate.py                   # 31-check validation
│   ├── obs.py                        # System observer
│   ├── budget-enforcer.py            # Routing + budget enforcement
│   ├── budget-status.py              # Spend status display
│   ├── tools.py                      # External tools framework
│   └── fix-sandbox-permissions.sh    # Sandbox permission fix
├── skills/
│   ├── skill-runner.py               # LangGraph skill engine v4.0
│   ├── research-brief/
│   │   ├── skill.yaml                # Skill definition
│   │   └── outputs/                  # Artifacts (gitignored)
│   └── graph-validation/
│       └── validate_graph.py         # Phase 9 graph test harness
├── docs/
│   ├── architecture/
│   │   ├── system-overview.md        # This document
│   │   ├── architecture-lock.md      # Locked decisions
│   │   ├── routing-system.md         # Routing system doc
│   │   ├── budget-system.md          # Budget system doc
│   │   ├── skill-system.md           # Skill system doc
│   │   ├── validation-system.md      # Validation system doc
│   │   ├── graph-validation-report.md
│   │   ├── sandbox-policy.yaml       # OpenShell policy (reference)
│   │   └── langgraph-graph-validation-results.json
│   ├── reference/
│   │   ├── script-reference.md       # All scripts documented
│   │   ├── config-reference.md       # All config files documented
│   │   └── design-decisions-log.md   # Planning-to-reality drift
│   ├── setup/
│   │   ├── local-environment-setup.md
│   │   └── restart-recovery-runbook.md
│   ├── extensions/
│   │   └── external-tools-registry.md
│   ├── troubleshooting/
│   │   └── startup-and-failure-point-map.md
│   └── archive/
│       └── checkpoint_utils_deprecated.py
└── checkpoints/                      # (gitignored directory marker)
```

---

## Key Commands

```bash
# Full validation (run after every change)
python3 scripts/validate.py

# System health overview
python3 scripts/obs.py

# Budget status
python3 scripts/budget-status.py

# Tool status
python3 scripts/tools.py

# Run a skill
.venv313/bin/python skills/skill-runner.py \
  --skill research-brief \
  --input topic "your topic" \
  --input depth standard

# Resume a paused skill
.venv313/bin/python skills/skill-runner.py \
  --skill research-brief \
  --thread-id THREAD_ID --resume

# Fix sandbox permissions (after restart)
bash scripts/fix-sandbox-permissions.sh

# Graph validation
.venv313/bin/python skills/graph-validation/validate_graph.py
```

---

## Cross-Reference Index

| Topic | Document |
|---|---|
| Architecture migration rationale | `docs/architecture/architecture-lock.md` |
| Routing aliases, task classes, fallback | `docs/architecture/routing-system.md` |
| Budget limits, spend tracking, thresholds | `docs/architecture/budget-system.md` |
| Skill creation, execution, resume | `docs/architecture/skill-system.md` |
| 31-check validation breakdown | `docs/architecture/validation-system.md` |
| Graph validation results | `docs/architecture/graph-validation-report.md` |
| Script usage reference | `docs/reference/script-reference.md` |
| Config file reference | `docs/reference/config-reference.md` |
| Planning vs reality drift | `docs/reference/design-decisions-log.md` |
| External tools and activation | `docs/extensions/external-tools-registry.md` |
| Environment setup | `docs/setup/local-environment-setup.md` |
| Cold start and recovery | `docs/setup/restart-recovery-runbook.md` |
| Failure points and troubleshooting | `docs/troubleshooting/startup-and-failure-point-map.md` |

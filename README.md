# NemoClaw Local Foundation

**Status:** Phase 12 — Documentation Consolidation Complete
**Runtime:** Python 3.12.13 via .venv312
**Execution:** LangGraph StateGraph + Direct Anthropic, OpenAI, Google API
**Validation:** 31/31 checks passing
**Repo:** github.com/clawbot-alpha-factory/nemoclaw-local-foundation

---

## What This Is

A local MacBook-based AI agent foundation built on LangGraph with direct API access to three inference providers. It includes a 9-alias model routing system across 3 providers, per-provider budget enforcement with audit logging, checkpoint-based workflow state, a Skill-based execution architecture, an external tools framework with 16 registered tools, and automated 31-check system validation.

This project started as a NemoClaw/OpenShell local build and migrated to a custom LangGraph + Direct API architecture in Phase 6. The NemoClaw sandbox is retained but not required for inference. See `docs/architecture/architecture-lock.md` for the full rationale.

---

## Stack

| Layer | Technology |
|---|---|
| Agent execution | LangGraph StateGraph |
| State persistence | LangGraph SqliteSaver |
| Inference — Anthropic | langchain-anthropic (claude-opus-4-6, claude-sonnet-4-6, claude-haiku-4-5) |
| Inference — OpenAI | langchain-openai (gpt-5.4, gpt-5.4-mini, o3) |
| Inference — Google | google-generativeai (gemini-2.5-pro, gemini-2.5-flash) |
| Model routing | 9 aliases, 10 task classes — routing-config.yaml |
| Budget enforcement | $10/provider, 90% warn, 100% hard stop — budget-config.yaml |
| External tools | 16-tool registry, Asana active — tools.py |
| Audit logging | provider-usage.jsonl, budget-audit.log, tools-audit.log |
| Validation | 31 checks across 6 categories — validate.py |
| Observability | obs.py (dashboard), budget-status.py (spend) |
| Python runtime | 3.12.13 via .venv312 |
| Machine | MacBook Apple Silicon M1, 16GB RAM, macOS Sequoia |

---

## Quick Start

### 1. Prerequisites

- macOS Apple Silicon
- Docker Desktop 29+
- Homebrew
- Python 3.12: `brew install python@3.12`
- Node.js 20+: `brew install node`

### 2. Clone and configure

```bash
git clone https://github.com/clawbot-alpha-factory/nemoclaw-local-foundation.git
cd nemoclaw-local-foundation
cp config/.env.example config/.env
# Edit config/.env — add your API keys for OpenAI, Anthropic, Google, NGC, NVIDIA, Asana
```

### 3. Create Python 3.12 virtual environment

```bash
/opt/homebrew/bin/python3.12 -m venv .venv312
.venv312/bin/pip install langgraph langgraph-checkpoint-sqlite langchain-openai langchain-anthropic pyyaml
```

### 4. Load environment and validate

```bash
set -a && source config/.env && set +a
python3 scripts/validate.py
# Expected: 31 passed, 0 warnings, 0 failed
```

### 5. Run a Skill

```bash
.venv312/bin/python skills/skill-runner.py \
  --skill research-brief \
  --input topic "your topic here" \
  --input depth standard
```

### 6. Check system status

```bash
python3 scripts/obs.py          # Full dashboard
python3 scripts/budget-status.py # Budget summary
python3 scripts/tools.py         # Tool status
```

---

## Model Routing

9 aliases across 3 providers. Each skill step declares a task class that routes to an alias.

| Alias | Provider | Model | Role |
|---|---|---|---|
| cheap_openai | OpenAI | gpt-5.4-mini | Default — short, structured, cheap |
| reasoning_openai | OpenAI | gpt-5.4 | Heavy reasoning, coding |
| reasoning_o3 | OpenAI | o3 | Deep STEM reasoning — expensive |
| cheap_claude | Anthropic | claude-haiku-4-5-20251001 | Moderate complexity, fast |
| reasoning_claude | Anthropic | claude-sonnet-4-6 | Complex reasoning, synthesis |
| premium_claude | Anthropic | claude-opus-4-6 | Highest quality — critical outputs |
| cheap_google | Google | gemini-2.5-flash | Fast multimodal, long context |
| reasoning_google | Google | gemini-2.5-pro-preview-03-25 | Google flagship reasoning |
| fallback_openai | OpenAI | gpt-5.4-mini | Emergency fallback |

Full details: `docs/architecture/routing-system.md`

---

## Budget Controls

| Provider | Budget | Warning | Hard Stop |
|---|---|---|---|
| Anthropic | $10.00 | 90% | 100% → fallback |
| OpenAI | $10.00 | 90% | 100% → fallback |
| Google | $10.00 | 90% | 100% → fallback |

Cost estimates use 2x real pricing as a conservative buffer. All calls logged to `~/.nemoclaw/logs/provider-usage.jsonl`.

Full details: `docs/architecture/budget-system.md`

---

## Skills

| Skill | Description | Steps | Status |
|---|---|---|---|
| research-brief | Takes a topic, produces structured research brief | 5 | Production — tested |

Full details: `docs/architecture/skill-system.md`

---

## Scripts

| Script | Runtime | Purpose |
|---|---|---|
| scripts/validate.py | python3 | 31-check system validation |
| scripts/obs.py | python3 | System health dashboard |
| scripts/budget-enforcer.py | python3 | Routing + budget enforcement |
| scripts/budget-status.py | python3 | Provider spend display |
| scripts/tools.py | python3 | External tools status |
| scripts/fix-sandbox-permissions.sh | bash | Fix openclaw.json ownership |
| skills/skill-runner.py | .venv312 | LangGraph skill execution engine v3.0 |

Full details: `docs/reference/script-reference.md`

---

## Documentation Index

### Architecture

| Document | Purpose |
|---|---|
| [System Overview](docs/architecture/system-overview.md) | How all components connect — read this first |
| [Architecture Lock](docs/architecture/architecture-lock.md) | All locked decisions with rationale |
| [Routing System](docs/architecture/routing-system.md) | 9 aliases, 10 task classes, fallback behavior |
| [Budget System](docs/architecture/budget-system.md) | Spend tracking, thresholds, reset procedures |
| [Skill System](docs/architecture/skill-system.md) | Skill creation, execution, resume, skill.yaml spec |
| [Validation System](docs/architecture/validation-system.md) | All 31 checks documented |
| [Graph Validation Report](docs/architecture/graph-validation-report.md) | Phase 9 LangGraph pattern test results |
| [Sandbox Policy Design](docs/architecture/sandbox-policy-design.md) | OpenShell policy explanation (reference) |

### Reference

| Document | Purpose |
|---|---|
| [Script Reference](docs/reference/script-reference.md) | Every script with usage, flags, output |
| [Config Reference](docs/reference/config-reference.md) | Every config file field by field |
| [Design Decisions Log](docs/reference/design-decisions-log.md) | Planning docs vs implemented reality |

### Setup & Operations

| Document | Purpose |
|---|---|
| [Local Environment Setup](docs/setup/local-environment-setup.md) | Prerequisites and installation |
| [Restart & Recovery Runbook](docs/setup/restart-recovery-runbook.md) | Cold start, verification, recovery |

### Extensions & Troubleshooting

| Document | Purpose |
|---|---|
| [External Tools Registry](docs/extensions/external-tools-registry.md) | 16 tools, activation timeline |
| [Startup & Failure Point Map](docs/troubleshooting/startup-and-failure-point-map.md) | Known failure points and fixes |

---

## Phase History

| Phase | What Was Built |
|---|---|
| 1–5 | NemoClaw/OpenShell exploration, stack understanding, local setup |
| 6 | Architecture migration to LangGraph + Direct API |
| 7 | Budget enforcement, routing system, state persistence |
| 8 | 9-alias routing, 3-provider expansion, architecture lock v1 |
| 9 | Graph validation — 5 LangGraph patterns confirmed |
| 10 | Observability — obs.py, budget-status.py |
| 10.5 | External tools framework, Asana integration, 31-check validation |
| 11 | Restart and recovery runbook — tested end-to-end |
| 12 | Documentation consolidation — 17-step architecture doc overhaul |

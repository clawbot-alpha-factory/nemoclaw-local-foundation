# NemoClaw Local Foundation

**Status:** Phase 8 — Architecture Locked  
**Runtime:** Python 3.12.13 via .venv312  
**Execution:** LangGraph + Direct Anthropic and OpenAI API  
**Repo:** github.com/clawbot-alpha-factory/nemoclaw-local-foundation  

---

## What This Is

A local Mac-based AI agent foundation built on LangGraph with direct API access to Anthropic and OpenAI. It includes a governed model routing system, budget enforcement, audit logging, checkpoint-based workflow state, and a Skill-based execution architecture.

This project started as a NemoClaw/OpenShell local build and migrated to a custom LangGraph + Direct API architecture in Phase 6. See `docs/architecture/architecture-lock.md` for the full rationale and comparison.

---

## Stack

| Layer | Technology |
|---|---|
| Agent execution | LangGraph StateGraph |
| State persistence | LangGraph SqliteSaver |
| Anthropic inference | langchain-anthropic — direct API |
| OpenAI inference | langchain-openai — direct API |
| Model routing | 5-alias system — routing-config.yaml |
| Budget enforcement | budget-enforcer.py — reads from YAML configs |
| Audit logging | provider-usage.jsonl, budget-audit.log |
| Validation | scripts/validate.py — 25 checks |
| Python runtime | 3.12.13 via .venv312 |

---

## Quick Start

### 1. Prerequisites

- macOS Apple Silicon
- Docker Desktop 29+
- Homebrew
- Python 3.12 via Homebrew: `brew install python@3.12`

### 2. Clone and configure

    git clone https://github.com/clawbot-alpha-factory/nemoclaw-local-foundation.git
    cd nemoclaw-local-foundation
    cp config/.env.example config/.env
    # Edit config/.env and add your API keys

### 3. Create Python 3.12 virtual environment

    /opt/homebrew/bin/python3.12 -m venv .venv312
    .venv312/bin/pip install langgraph langgraph-checkpoint-sqlite langchain-openai langchain-anthropic pyyaml

### 4. Validate the system

    python3 scripts/validate.py

### 5. Run a Skill

    .venv312/bin/python skills/skill-runner.py \
      --skill research-brief \
      --input topic "your topic here" \
      --input depth standard

### 6. Check budget status

    python3 scripts/budget-status.py

---

## Model Routing

| Alias | Provider | Model | Use Case |
|---|---|---|---|
| cheap_openai | OpenAI | gpt-4o-mini | Default — short, structured, cheap |
| cheaper_claude | Anthropic | claude-haiku-4-5-20251001 | Moderate complexity |
| reasoning_claude | Anthropic | claude-sonnet-4-6 | Complex reasoning, code, synthesis |
| vision_openai | OpenAI | gpt-4o | Vision tasks |
| fallback_openai | OpenAI | gpt-4o | Fallback when Claude unavailable |

---

## Skills

| Skill | Description | Status |
|---|---|---|
| research-brief | Takes a topic, produces structured research brief | ✅ Validated |

---

## Key Scripts

| Script | Purpose |
|---|---|
| scripts/validate.py | 25-check system validation |
| scripts/budget-status.py | Provider spend and budget status |
| scripts/budget-enforcer.py | Route a task class and enforce budget |
| scripts/fix-sandbox-permissions.sh | Fix openclaw.json ownership after restart |

---

## Key Docs

| Document | Purpose |
|---|---|
| docs/architecture/architecture-lock.md | Locked architecture decisions |
| docs/troubleshooting/startup-and-failure-point-map.md | 10 failure points and fixes |
| docs/setup/local-environment-setup.md | Environment setup guide |
| skills/research-brief/README.md | Research brief Skill usage |

---

## Budget Controls

- $10.00 per provider — Anthropic and OpenAI tracked separately
- 90% warning threshold — prints alert and writes to audit log
- 100% hard stop — auto-routes to fallback, no override
- All calls logged to ~/.nemoclaw/logs/provider-usage.jsonl

---

## Architecture

See `docs/architecture/architecture-lock.md` for the full architecture comparison between the original NemoClaw/OpenShell path and the current LangGraph + Direct API path, including gains, losses, and replacement safety controls.

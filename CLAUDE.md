# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

NemoClaw Local Foundation is a LangGraph-based AI skill execution and multi-agent orchestration system running locally on macOS. It combines a Python backend (FastAPI) with a Next.js frontend dashboard ("Command Center"), 115+ composable skills, 11 autonomous agents with a 4-tier authority hierarchy, and 20 multi-agent subsystems (MA-1 through MA-20).

## Common Commands

### Validation & Testing
```bash
# Run 31-check system validation (environment, runtime, API keys, budget, routing, skills)
python3 scripts/validate.py

# Run a single skill
python3 skills/skill-runner.py --skill SKILL_ID --input key1 value1 --input key2 value2

# Run a single skill from a chained envelope
python3 skills/skill-runner.py --skill SKILL_ID --input-from path/to/envelope.json

# Run full skill regression suite (all skills with test-input.json)
python3 scripts/test-all.py
python3 scripts/test-all.py --skill SKILL_ID    # single skill
python3 scripts/test-all.py --dry-run            # preview only

# Shell-based regression (alternative)
bash scripts/test-all.sh [--dry-run]

# Full enterprise regression (endpoints, skill compilation, golden output, persistence)
bash scripts/full_regression.sh

# P-1 through P-10 feature validation
bash scripts/validate-p1-p10.sh

# MA-20 integration test (all 19 MA systems, 7 agents end-to-end)
python3 scripts/integration_test.py --test
python3 scripts/integration_test.py --summary    # quick pass/fail
```

### Command Center (Web Dashboard)
```bash
# Backend (FastAPI)
cd command-center/backend && pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend (Next.js)
cd command-center/frontend && npm install
npm run dev          # http://localhost:3000
npm run build        # production build
npm run lint         # lint check
```

### Production Operations
```bash
python3 scripts/prod-ops.py status       # full system status
python3 scripts/prod-ops.py health       # health dashboard
python3 scripts/prod-ops.py agents       # agent roster + performance
python3 scripts/prod-ops.py costs        # budget report by provider
python3 scripts/prod-ops.py validate     # run 31-check validation
python3 scripts/prod-ops.py integration  # run MA-20 test
python3 scripts/prod-ops.py run GOAL     # execute multi-agent workflow
```

### Skill Generation
```bash
# Generate a new skill from template (v2 schema)
python3 scripts/new-skill.py \
  --id h35-tone-calibrator \
  --name "Tone Calibrator" \
  --family 35 --domain H --tag customer-facing \
  --skill-type transformer \
  --step-names "Parse,Rewrite,Evaluate,Improve,Validate" \
  --llm-steps "2,3,4" --critic-steps "3"
```

### Workflow Orchestration
```bash
python3 scripts/orchestrator.py --workflow workflows/pipeline-v2.yaml
python3 scripts/orchestrator.py --plan "Research AI agents..." --dry-run
python3 scripts/orchestrator.py --list-skills
```

## Architecture

### Runtime Stack
- **Python 3.12+** with virtual environment at `.venv313/`
- **LangGraph StateGraph** with **SqliteSaver** checkpointing (`~/.nemoclaw/checkpoints/langgraph.db`)
- **9-alias LLM routing** across Anthropic, OpenAI, Google (configured in `config/routing/routing-config.yaml`)
- **Per-provider budget enforcement** at $30 each (configured in `config/routing/budget-config.yaml`)
- API keys loaded from `config/.env`

### Shared Routing Module
- **`lib/routing.py`** (v1.1.0) — All LLM calls route through this module (enforces L-003)
  - `resolve_alias(task_class)` → (provider, model, cost) from `routing-config.yaml`
  - `call_llm(messages, task_class, max_tokens)` → routes to correct provider
  - Thread-safe caching, error handling for missing config, defensive fallbacks
  - Loaded by all 115 skill `run.py` files via `from lib.routing import call_llm`

### Gamification System
- **`scripts/agent_performance.py`** — GamificationEngine class
  - Employee of the Month: highest 30-day composite score
  - 10 achievement badges (Revenue Champion, Quality King, Speed Demon, etc.)
  - Rivalry tracking: head-to-head agent comparisons
  - Leaderboard: real-time ranking of all 11 agents
  - Persistence: `~/.nemoclaw/gamification/` (leaderboard.json, awards.jsonl, achievements.json)

### Core Execution Flow
1. `skills/skill-runner.py` (v4.0) reads `skill.yaml` and builds a LangGraph StateGraph
2. Steps are dispatched by `step_type`: `llm`/`critic` make LLM calls, `local` does not
3. Routing resolves task_class → alias → (provider, model) via `routing-config.yaml`
4. Budget enforcement tracks per-provider spend with circuit breaker at 150%
5. Critic loop pattern: Generate → Critic (score) → if score < threshold, Improve → re-evaluate
6. On completion, writes artifact file + JSON envelope to `skills/<id>/outputs/`
7. Envelope enables skill chaining via `--input-from`

### Skill Anatomy
Each skill lives in `skills/<family>-<id>/` with:
- `skill.yaml` — Schema v2 definition (identity, inputs, outputs, steps, transitions, contracts, critic_loop)
- `run.py` — Execution engine
- `test-input.json` — Test input (`{"inputs": {"key": "value"}}`)
- `outputs/` — Execution artifacts and envelopes

Skill types: `executor`, `planner`, `evaluator`, `transformer`, `router`. Families span A01 (architecture) through J36 (business planning), plus registered K40-K54 and business/content/revenue domain skills.

### Command Center Architecture
- **Backend** (`command-center/backend/app/`): FastAPI with 70+ services, WebSocket broadcasting
  - `services/state_aggregator.py` scans the repo filesystem every 10s, building a `SystemState` object
  - `services/brain_service.py` provides LLM-powered system analysis (auto-insights every 5min)
  - WebSocket channels: `/ws` (legacy), `/ws/state`, `/ws/chat`, `/ws/alerts`
  - Auth: local bearer token (`auth.py`)
- **Frontend** (`command-center/frontend/src/`): Next.js + React + Zustand + Tailwind
  - `hooks/useWebSocket.ts` — auto-reconnecting WebSocket (exponential backoff 3s → 30s)
  - `lib/store.ts` — Zustand state store
  - 12 tabs: Home, Comms, Agents, Skills, Ops, Execution, Approvals, Clients, Projects, Settings, etc.

### Multi-Agent System (MA-1 through MA-20)
All implemented in `scripts/` as Python modules:
- **MA-1** Agent Registry — identity, capabilities, authority levels (3-tier: executive → strategy/ops → specialists)
- **MA-2** 3-Layer Memory — working + episodic + shared workspace
- **MA-3** Message Protocol — typed agent-to-agent channels
- **MA-5** Task Decomposition — goal → parallel task plan (5 tasks/wave, <$15 auto-exec)
- **MA-6** Cost Governance — circuit breaker (CLOSED/OPEN/HALF_OPEN), per-agent ledger
- **MA-8** Behavior Rules — 16 rules across 8 categories with graduated enforcement
- **MA-14** System Health — 12 health domains with composite scoring
- **MA-16** Human-in-the-Loop — 6 approval categories with configurable expiry
- **MA-19** Access Control — 7 domains with role-based permissions
- **MA-20** Integration Test — validates all 19 systems end-to-end

### 11 Agents
Defined in `config/agents/agent-schema.yaml` with skill-to-agent mapping in `config/agents/capability-registry.yaml`. Authority levels: L1 (Tariq/executive_operator), L2 (Nadia/strategy_lead, Khalid/operations_lead), L3 (Layla/product_architect, Omar/growth_revenue_lead, Yasmin/narrative_content_lead, Faisal/engineering_lead), L4 (Hassan/sales_outreach_lead, Rania/marketing_campaigns_lead, Amira/client_success_lead, Zara/social_media_lead). Each agent has `owns`/`forbidden` domain boundaries, Jordanian identity with cartoon character persona, self-promotion system, skill library access, and autonomous self-improvement capability.

### Browser Automation
PinchTab integration (`config/pinchtab-config.yaml`) at `localhost:9867`. Per-agent browser profiles, rate limits, blocked domains (banking/gov/payment). Script bridge: `scripts/web_browser.py`.

## Key Configuration Files
- `config/routing/routing-config.yaml` — 9 LLM aliases (cheap_openai, reasoning_claude, etc.) and task routing rules
- `config/routing/budget-config.yaml` — Per-provider spend limits and thresholds
- `config/agents/agent-schema.yaml` — 7 agents with authority hierarchy and domain boundaries
- `config/agents/capability-registry.yaml` — Skill-to-agent mapping with fallbacks
- `config/pinchtab-config.yaml` — Browser automation config
- `config/.env` — API keys (Anthropic, OpenAI, Google, Asana, etc.)

## Architecture Lock Decisions
413 locked decisions documented in `docs/architecture-lock.md`. Key locks:
- **L-001**: Python 3.12.13 via .venv313
- **L-002**: LangGraph StateGraph + SqliteSaver (no custom graph engine)
- **L-003**: 9-alias routing (never hardcode provider/model in skills)
- **L-004**: Per-provider budget enforcement with circuit breaker
- **L-005**: skill-runner.py v4.0 as sole execution entry point
- **L-006**: validate.py 31-check validation suite
- **L-010**: Section extraction uses H2 heading regex (not H1)
- **L-400 to L-413**: PinchTab 0.8.6 browser automation locks

## Conventions
- Skill IDs follow `<family>-<name>` pattern (e.g., `a01-arch-spec-writer`, `f09-pricing-strategist`)
- Skill YAML uses Schema v2: `step_type` must be `local`, `llm`, or `critic` (never `makes_llm_call`)
- Family numbers are zero-padded (F01-F99), domains are single letters A-L
- Skill step names must be semantic (3+ words, no "TODO" or "processing step")
- LLM calls go through the routing system — never hardcode a model in a skill
- Checkpoint DB is deleted between test runs to prevent stale cache loops
- Regression results saved to `scripts/regression-results.json`
- Provider usage logged to `~/.nemoclaw/logs/provider-usage.jsonl`
- Validation runs logged to `~/.nemoclaw/logs/validation-runs.jsonl`

# Architecture Lock Document

> **Location:** `docs/architecture/architecture-lock.md`
> **Version:** 3.0
> **Date:** 2026-03-28
> **Status:** LOCKED
> **Phase:** MA-4 — Multi-Agent System
> **Supersedes:** v2.0 (Phase 12)

---

## Purpose

This document formally locks all architectural decisions for the NemoClaw local foundation. It defines what was decided, when, why, and what each decision means for future work.

This is the single authoritative record of locked decisions. If a document elsewhere contradicts this file, this file wins.

---

## Locked Decision 1 — Architecture Path

**Decision:** Custom LangGraph + Direct API on host Mac

**Locked in:** Phase 6

**What this means:**

- Skills execute as LangGraph StateGraphs on the host MacBook
- Inference calls go directly to provider APIs via langchain (no proxy, no sandbox)
- The NemoClaw/OpenShell sandbox is retained but not required for any workflow
- The system does not depend on NemoClaw upstream stability

**Original path:** NemoClaw/OpenShell sandbox with inference.local proxy

**Why it changed:** NemoClaw is alpha with active macOS support gaps. The OpenShell sandbox blocked native Mac execution and full internet access. LangGraph provides superior graph primitives. 4 of 5 governance components were portable without the sandbox.

**What was lost:** OS-level network policy, filesystem sandboxing, Landlock isolation, governed credential injection. Replaced by application-layer controls (budget enforcement, audit logging, approval boundaries).

**Full comparison:** See the Architecture Comparison table below.

---

## Locked Decision 2 — State Persistence

**Decision:** LangGraph SqliteSaver — single checkpoint system

**Locked in:** Phase 7

**Database:** `~/.nemoclaw/checkpoints/langgraph.db`

**What this means:**

- All workflow state flows through SkillState TypedDict in skill-runner.py
- Checkpoints are saved after every step via SqliteSaver
- Resume uses `--thread-id THREAD_ID --resume`
- checkpoint_utils.py is deprecated — moved to `docs/archive/`, must not be called

---

## Locked Decision 3 — Python Runtime

**Decision:** Python 3.12.13 via .venv313

**Locked in:** Phase 7

**Location:** `~/nemoclaw-local-foundation/.venv313/bin/python`

**What this means:**

- All skill execution uses .venv313/bin/python
- System Python 3.14 must not be used for LangGraph workloads (Pydantic V1 incompatibility)
- .venv313/ is gitignored — recreated on each new machine
- Scripts that don't import LangGraph (validate.py, obs.py, budget-enforcer.py, budget-status.py, tools.py) run on system python3

**Setup:**

```bash
/opt/homebrew/bin/python3.12 -m venv .venv313
.venv313/bin/pip install langgraph langgraph-checkpoint-sqlite langchain-openai langchain-anthropic pyyaml
```

---

## Locked Decision 4 — Model Routing

**Decision:** 9-alias routing system with provider-suffixed names, 10 task classes, 3 providers

**Locked in:** Phase 8 (expanded from 5 aliases to 9 in Phase 8)

**Config:** `config/routing/routing-config.yaml` (source of truth)

**What this means:**

- Every inference call routes through a task class → alias → provider + model chain
- 9 aliases: cheap_openai, reasoning_openai, reasoning_o3, cheap_claude, reasoning_claude, premium_claude, cheap_google, reasoning_google, fallback_openai
- 10 task classes: general_short, structured_short, moderate, complex_reasoning, code, agentic, long_document, vision, deep_reasoning, premium
- 3 providers: OpenAI, Anthropic, Google
- Default alias: cheap_openai
- Global fallback: fallback_openai (gpt-5.4-mini)

**Full doc:** `docs/architecture/routing-system.md`

---

## Locked Decision 5 — Budget Enforcement

**Decision:** Per-provider cumulative budget with $30 limits, 90% warning, 100% hard stop

**Locked in:** Phase 7 (expanded to 3 providers in Phase 8)

**Config:** `config/routing/budget-config.yaml` (source of truth)

**What this means:**

- Every inference call passes through budget enforcement before execution
- Spend is tracked cumulatively across sessions in `~/.nemoclaw/logs/provider-spend.json`
- Cost estimates use 2x real pricing as a conservative buffer
- At 90%: warning printed and logged
- At 100%: call blocked, routed to fallback_openai, event logged
- Manual reset required (no automated monthly cycle)

**Full doc:** `docs/architecture/budget-system.md`

---

## Locked Decision 6 — Skill Execution

**Decision:** Skills defined by skill.yaml + run.py, executed by skill-runner.py v4.0 as LangGraph StateGraphs

**Locked in:** Phase 9

**What this means:**

- Each skill is a directory under `skills/` containing a `skill.yaml` and an `outputs/` directory
- skill-runner.py reads the YAML, builds a StateGraph, executes steps sequentially
- Each step declares a task_class that routes through the budget enforcer
- State is checkpointed after every step
- 5 graph patterns validated: linear chain, conditional branching, early exit, state accumulation, checkpoint resume

**Full doc:** `docs/architecture/skill-system.md`

---

## Locked Decision 7 — External Tools Framework

**Decision:** Standard tool wrapper pattern via scripts/tools.py, credential validation at startup, audit logging for all tool calls

**Locked in:** Phase 10.5

**What this means:**

- All tool API keys stored in config/.env following the same pattern as provider keys
- tools.py validates credentials and logs all tool calls to `~/.nemoclaw/logs/tools-audit.log`
- 16 tools registered across 5 tiers
- Active now: GitHub (no key), Asana (validated)
- Remaining tools activate in Phase 12+ alongside the skills that need them

**Full doc:** `docs/extensions/external-tools-registry.md`

---

## Locked Decision 8 — Validation System

**Decision:** 31-check validation across 6 categories, run via validate.py

**Locked in:** Phase 10.5 (expanded from 20 checks in Phase 7, to 25 in Phase 8, to 31 in Phase 10.5)

**What this means:**

- validate.py is the authoritative health check for the entire system
- 6 categories: Environment, NemoClaw Runtime, API Keys, Budget System, Routing System, Skill System
- Must show 31/31 before pushing code or running skills
- Results logged to `~/.nemoclaw/logs/validation-runs.jsonl`

**Full doc:** `docs/architecture/validation-system.md`

---

## Locked Decision 9 — Observability

**Decision:** Three observability scripts (obs.py, budget-status.py, validate.py) plus structured log files

**Locked in:** Phase 10

**What this means:**

- obs.py: unified dashboard (health, spend, recent runs, checkpoints, failures, last validation)
- budget-status.py: provider spend with visual bars
- validate.py: 31-check pass/fail health
- Log files under `~/.nemoclaw/logs/`: provider-spend.json, provider-usage.jsonl, budget-audit.log, tools-audit.log, validation-runs.jsonl

**Full doc:** `docs/reference/script-reference.md`

---

## Architecture Comparison — Original vs Current

| Dimension | Original NemoClaw/OpenShell Path | Current LangGraph + Direct API Path |
|---|---|---|
| Runtime environment | OpenShell sandbox — K8s pod inside Docker | Host Mac — Python 3.12 venv |
| Inference origination | inference.local inside sandbox | Direct API via langchain |
| Agent execution | OpenClaw inside OpenShell | LangGraph StateGraph |
| State persistence | checkpoint_utils.py — custom JSON | LangGraph SqliteSaver — SQLite DB |
| Network governance | OpenShell network policy — allowlists | None — full internet access |
| Filesystem governance | OpenShell Landlock + seccomp | None — full filesystem access |
| Credential handling | OpenShell-managed token injection | Direct from config/.env |
| Policy enforcement | OpenShell policy YAML — runtime enforced | Budget enforcer — application-layer |
| Model routing | Not applicable (single model) | 9 aliases, 10 task classes, 3 providers |
| Budget control | Not applicable | $30/provider, 90% warn, 100% hard stop |
| Skill system | Not applicable | skill.yaml + skill-runner.py + LangGraph |
| External tools | Not applicable | 16-tool registry, tools.py framework |
| Validation | Not applicable | 31 checks across 6 categories |
| Observability | Not applicable | obs.py, budget-status.py, 5 log files |

---

## Replacement Safety Controls

| Lost Control | Replacement | Strength |
|---|---|---|
| Network policy | Budget enforcer controls which providers are called | Application-layer only |
| Credential isolation | config/.env gitignored, never committed | Developer-discipline dependent |
| Execution boundaries | requires_human_approval per skill step | Application-layer only |
| Audit trail | provider-usage.jsonl + budget-audit.log + tools-audit.log | Strong — append-only logs |
| Spend control | Hard stop at $30/provider | Strong — enforced before every call |

These controls are weaker than OS-level enforcement. This is an accepted tradeoff.

---

## What This Document Does Not Lock

| Topic | Status | When It Will Be Locked |
|---|---|---|
| Multi-agent architecture | MA-1 through MA-4 complete (7 agents, memory, messaging, decisions) | Locked MA-1 (2026-03-28) |
| Per-alias fallback chains | Planned, not implemented | When provider outages become operationally frequent |
| Complexity pre-classifier | Planned, not implemented | When multiple skills run diverse inputs |
| Token-proportional cost tracking | Planned, not implemented | When monthly spend exceeds $50 |
| Automated budget reset | Planned, not implemented | When monthly cycles become operationally important |
| Additional skills | 30 built across 10 families (Tiers 1-3) | Tier 1 (Phase 13), Tier 2-3 (Phase 14-15) |

---

## Locked Decisions Summary

| # | Decision | Value | Locked In |
|---|---|---|---|
| 1 | Architecture path | LangGraph + Direct API | Phase 6 |
| 2 | State persistence | LangGraph SqliteSaver | Phase 7 |
| 3 | Python runtime | 3.12.13 via .venv313 | Phase 7 |
| 4 | Model routing | 9 aliases, 10 task classes, 3 providers | Phase 8 |
| 5 | Budget enforcement | $30/provider, 90% warn, 100% stop | Phase 7 (updated MA-4) |
| 6 | Skill execution | skill.yaml + run.py + skill-runner.py v4.0 | Phase 9 (updated Tier 1) |
| 7 | External tools framework | tools.py + 16-tool registry | Phase 10.5 |
| 8 | Validation system | 31 checks, 6 categories | Phase 10.5 |
| 9 | Observability | 3 scripts + 5 log files | Phase 10 |
| 10 | Skill execution v4.0 | 5-step pipeline, critic loop, envelope output, checkpoint backup | Tier 1 |
| 11 | Budget increase | $30/provider (was $10), token limits cheap=8K reasoning=16K | Phase 5 |
| 12 | Opus → Sonnet reroute | Opus 4-12x estimated cost, Sonnet for all except critical | Phase 5 |
| 13 | Multi-agent architecture | 7 agents, 3-level authority, domain enforcement | MA-1 |
| 14 | 3-layer memory | Private + shared + long-term, conflict escalation, decay | MA-2 |
| 15 | Structured messaging | 11 intents, voting, withdrawal, chat mode | MA-3 |
| 16 | Decision lifecycle | Proposed→decided→evaluated→learned, dependencies, velocity | MA-4 |

---

## Document Cross-References

| Topic | Document |
|---|---|
| Full system map | `docs/architecture/system-overview.md` |
| Routing details | `docs/architecture/routing-system.md` |
| Budget details | `docs/architecture/budget-system.md` |
| Skill details | `docs/architecture/skill-system.md` |
| Validation details | `docs/architecture/validation-system.md` |
| Script usage | `docs/reference/script-reference.md` |
| Config files | `docs/reference/config-reference.md` |
| Planning vs reality | `docs/reference/design-decisions-log.md` |
| Cold start / recovery | `docs/setup/restart-recovery-runbook.md` |
| Environment setup | `docs/setup/local-environment-setup.md` |
| External tools | `docs/extensions/external-tools-registry.md` |
| Troubleshooting | `docs/troubleshooting/startup-and-failure-point-map.md` |

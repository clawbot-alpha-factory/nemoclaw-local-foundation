# Architecture Lock Document

**Version:** 1.0  
**Date:** 2026-03-23  
**Status:** LOCKED  
**Phase:** 8 — Architecture Lock and Documentation Cleanup  

---

## Purpose

This document formally locks the current architecture path for the NemoClaw-first project.  
It supersedes all earlier references to NemoClaw/OpenShell as the primary runtime.  
It defines the single state system, documents the architecture shift, and states what was gained, what was lost, and what replacement controls exist.

---

## Architecture Path: Custom LangGraph + Direct API

This project is no longer on the NemoClaw/OpenShell architecture path.

The project mandate and early documentation assumed NemoClaw and OpenShell as the runtime foundation.  
That assumption is no longer accurate. The architecture shifted during Phase 6 for deliberate, documented reasons.  
This document locks that shift formally.

### Why the Shift Happened

- NemoClaw is an alpha/early preview project — interfaces unstable, local macOS support gaps active
- OpenShell sandbox prevented native Mac execution and full internet access
- inference.local proxy bound inference origination to the sandbox network namespace
- Extraction cost was low — 4 of 5 governance components were already fully portable
- LangGraph provides superior graph primitives — conditional branching, parallelism, human-in-the-loop
- Direct API calls are transparent, credential-controlled, and not dependent on upstream alpha stability

---

## Architecture Comparison

| Dimension | Original NemoClaw/OpenShell Path | Current LangGraph + Direct API Path |
|---|---|---|
| Runtime environment | OpenShell sandbox — Kubernetes pod inside Docker Desktop | Host Mac — Python 3.12 venv, no container required |
| Inference origination | inference.local inside sandbox — OpenShell proxy intercepts | Direct API — langchain-anthropic, langchain-openai |
| Agent execution | OpenClaw inside OpenShell governed runtime | LangGraph StateGraph — nodes, edges, shared state |
| State persistence | checkpoint_utils.py — custom JSON files | LangGraph SqliteSaver — ~/.nemoclaw/checkpoints/langgraph.db |
| Network governance | OpenShell network policy — allowlists per binary | None — full Mac internet access |
| Filesystem governance | OpenShell Landlock + seccomp sandbox | None — full Mac filesystem access |
| Credential handling | openshell-managed token — gateway injects credentials | Direct from config/.env — project-managed |
| Policy enforcement | OpenShell policy YAML — runtime enforced | Budget enforcer only — application-layer |
| Python version | System Python 3.14 — Pydantic V1 compatibility risk | Python 3.12.13 via .venv312 — isolated, stable |
| Upgrade surface | NemoClaw upstream alpha — fast-moving, unstable | LangGraph + langchain — stable, versioned, documented |

---

## What Was Gained

- Full Mac and internet freedom — no sandbox constraint on agent access
- Direct, transparent API calls — credentials visible and controlled by the project
- LangGraph graph primitives — conditional branching, parallelism, human-in-the-loop available
- Stable, documented upstream — LangGraph has active maintenance and real community
- Python 3.12 — stable, fully supported, no Pydantic compatibility risk
- Single checkpoint system — no dual-state ambiguity
- No dependency on NemoClaw alpha stability or upstream API changes

---

## What Was Lost

- OpenShell network policy — agents can now call any endpoint without OS-level enforcement
- OpenShell filesystem sandbox — agents have full host filesystem access
- Landlock + seccomp execution isolation — no kernel-level constraint on agent behavior
- Governed credential injection — credentials are now application-managed, not runtime-managed

---

## Replacement Safety Controls

The losses above are real. These are the controls that replace them at the application layer.

| Lost Control | Replacement Control | Strength |
|---|---|---|
| Network policy | Budget enforcer — controls which providers can be called | Application-layer only |
| Credential isolation | config/.env gitignored — never committed | Developer-discipline dependent |
| Execution boundaries | requires_human_approval per skill step | Application-layer only |
| Audit trail | provider-usage.jsonl + budget-audit.log — every call logged | Strong — append-only logs |
| Spend control | Hard stop at $10/provider — no unbounded API calls | Strong — enforced before every call |

These replacement controls are weaker than OS-level enforcement.  
A bug or malicious skill could bypass them.  
This is an accepted tradeoff given the sandboxed execution decision made in Phase 6.

---

## LangGraph State — Single Source of Truth

**Decision locked:** LangGraph SqliteSaver is the single checkpoint and state persistence system.

- checkpoint_utils.py is deprecated — moved to docs/archive/
- checkpoint_utils.py must not be called by any new code
- All workflow state flows through SkillState TypedDict in skill-runner.py
- Checkpoint database: ~/.nemoclaw/checkpoints/langgraph.db
- Resume pattern: --thread-id THREAD_ID --resume passed to skill-runner.py

---

## Python 3.12 — Locked Runtime

**Decision locked:** Python 3.12.13 via .venv312 is the required runtime for all skill execution.

- Location: ~/nemoclaw-local-foundation/.venv312/bin/python
- All skill runner invocations must use this interpreter
- System Python 3.14 must not be used for LangGraph workloads
- .venv312/ is gitignored — each developer must recreate it

Setup command for new environment:

    /opt/homebrew/bin/python3.12 -m venv ~/nemoclaw-local-foundation/.venv312
    ~/nemoclaw-local-foundation/.venv312/bin/pip install langgraph langgraph-checkpoint-sqlite langchain-openai langchain-anthropic pyyaml

---

## What This Document Does Not Lock

- Multi-agent architecture — not yet collaboratively defined
- Future Skill selection — not yet collaboratively chosen
- Observability design — Phase 10
- Non-linear graph patterns — Phase 9

---

## Locked Decisions Summary

| Decision | Value | Locked In |
|---|---|---|
| Architecture path | Custom LangGraph + Direct API | Phase 6 |
| State persistence | LangGraph SqliteSaver — single system | Phase 7 |
| checkpoint_utils.py | Deprecated — do not use | Phase 7 |
| Python runtime | 3.12.13 via .venv312 | Phase 7 |
| Inference origination | Direct langchain-anthropic / langchain-openai | Phase 6 |
| Budget enforcement | budget-enforcer.py reading from YAML configs | Phase 7 |
| Routing config | routing-config.yaml is single source of truth | Phase 7 |
| OpenShell dependency | Removed — not required for any workflow | Phase 6 |

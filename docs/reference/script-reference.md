# Script Reference

> **Location:** `docs/reference/script-reference.md`
> **Version:** 2.0
> **Date:** 2026-03-28
> **Phase:** MA-4 — Multi-Agent System

---

## Purpose

This document is a quick reference for every script in the NemoClaw local foundation. Each entry covers purpose, usage, Python runtime requirement, output, and related docs.

---

## scripts/validate.py

**Purpose:** Runs 31 health checks across 6 categories to verify the entire system is operational.

**Runtime:** System python3 (no LangGraph imports)

**Usage:**

```bash
python3 scripts/validate.py
```

**Output:** Per-check pass/fail with summary line. Appends result to `~/.nemoclaw/logs/validation-runs.jsonl`.

**When to run:** After every reboot, config change, code change, phase completion, and before pushing to GitHub.

**Flags:** None — runs all 31 checks every time.

**Exit code:** 0 if all checks pass, non-zero if any fail.

**Full doc:** `docs/architecture/validation-system.md`

---

## scripts/obs.py

**Purpose:** Unified system observer. Displays a dashboard of system health, provider spend, recent runs, checkpoint state, skill output history, failure summary, and last validation result.

**Runtime:** System python3 (no LangGraph imports)

**Usage:**

```bash
python3 scripts/obs.py
```

**Output sections:**

| Section | What It Shows |
|---|---|
| SYSTEM HEALTH | Docker, Python venv, gateway, API keys |
| PROVIDER USAGE & BUDGET | Per-provider spend with visual bars |
| RECENT RUNS | Last 5 inference sessions with call count and cost |
| CHECKPOINT STATE | Database location and thread count |
| SKILL OUTPUT HISTORY | Last 5 skill artifacts with size |
| FAILURE SUMMARY | Fallback events in last 24 hours |
| LAST VALIDATION RUN | Most recent validate.py result |

**When to run:** For a quick system overview. Part of the cold start procedure in the restart-recovery-runbook.

**Full doc:** `docs/architecture/system-overview.md` (Layer 7)

---

## scripts/budget-enforcer.py

**Purpose:** Routes a task class to a model alias and enforces provider budget limits. This is called by skill-runner.py before every inference call — not typically run directly.

**Runtime:** System python3 (no LangGraph imports)

**Usage (direct — for testing):**

```bash
python3 scripts/budget-enforcer.py --task-class complex_reasoning
```

**What it does:**

1. Reads `config/routing/routing-config.yaml` to resolve task class → alias → provider + model
2. Reads `~/.nemoclaw/logs/provider-spend.json` for current spend
3. Checks spend against limits in `config/routing/budget-config.yaml`
4. If under budget: prints alias and model, returns them
5. If at warning (90%): prints warning, logs to budget-audit.log, proceeds
6. If at hard stop (100%): routes to fallback_openai, logs exhaustion event

**Output:** Alias name, model string, estimated cost, budget remaining.

**Full doc:** `docs/architecture/budget-system.md`, `docs/architecture/routing-system.md`

---

## scripts/budget-status.py

**Purpose:** Displays current provider spend against budget limits with visual progress bars.

**Runtime:** System python3 (no LangGraph imports)

**Usage:**

```bash
python3 scripts/budget-status.py
```

**Output:**

```
===========================================================
  NemoClaw Provider Budget Status
===========================================================
  ANTHROPIC  | $ 0.626 / $30.00 |   6.3% | █░░░░░░░░░░░░░░░░░░░ | active
  OPENAI     | $ 0.121 / $30.00 |   1.2% | ░░░░░░░░░░░░░░░░░░░░ | active
  GOOGLE     | $ 0.008 / $30.00 |   0.1% | ░░░░░░░░░░░░░░░░░░░░ | active
===========================================================
```

**When to run:** After skill runs to check spend, during cold start verification, whenever you want a quick spend summary.

**Full doc:** `docs/architecture/budget-system.md`

---

## scripts/tools.py

**Purpose:** External tools framework. Validates configured tool credentials, displays tool status, and defines the standard wrapper interface for tool integrations.

**Runtime:** System python3 (no LangGraph imports)

**Usage:**

```bash
python3 scripts/tools.py
```

**Output:** Per-tool status showing which tools are active, which have valid credentials, and which are Phase 12 placeholders.

**Audit log:** Tool calls are logged to `~/.nemoclaw/logs/tools-audit.log`.

**When to run:** During cold start verification, after adding new tool credentials, to check integration status.

**Full doc:** `docs/extensions/external-tools-registry.md`

---

## scripts/fix-sandbox-permissions.sh

**Purpose:** Fixes the known issue where `openclaw.json` inside the NemoClaw sandbox resets to root ownership after every container restart, preventing OpenClaw from writing model defaults.

**Runtime:** Bash (calls `docker exec` and `kubectl`)

**Usage:**

```bash
bash scripts/fix-sandbox-permissions.sh
```

**What it does:**

1. Finds the openshell-cluster-nemoclaw container ID
2. Runs `chmod 644` on `/sandbox/.openclaw/openclaw.json` inside the sandbox
3. Runs `chown sandbox:sandbox` on the same file
4. Verifies the fix

**When to run:** After every Mac reboot, Docker restart, sandbox restart, or `nemoclaw onboard`.

**Prerequisites:** Docker must be running, sandbox must be started.

**Full doc:** `docs/troubleshooting/startup-and-failure-point-map.md` (Maintenance Step 1)

---

## skills/skill-runner.py

**Purpose:** LangGraph skill execution engine v4.0. Reads a skill.yaml + run.py definition, builds a LangGraph StateGraph, executes steps with budget-enforced routing, checkpoints state, and writes output artifacts.

**Runtime:** `.venv313/bin/python` (requires LangGraph, langchain-openai, langchain-anthropic)

**Usage — new run:**

```bash
~/nemoclaw-local-foundation/.venv313/bin/python \
  ~/nemoclaw-local-foundation/skills/skill-runner.py \
  --skill research-brief \
  --input topic "your topic" \
  --input depth standard
```

**Usage — resume interrupted run:**

```bash
~/nemoclaw-local-foundation/.venv313/bin/python \
  ~/nemoclaw-local-foundation/skills/skill-runner.py \
  --skill research-brief \
  --thread-id skill-research-brief-20260324-121719-ad57cb1c \
  --resume
```

**Flags:**

| Flag | Required | Description |
|---|---|---|
| --skill | Yes | Skill name (must match directory under skills/) |
| --input | Yes (repeatable) | Key-value input pair: `--input key "value"` |
| --thread-id | No | Thread ID for resuming a previous run |
| --resume | No | Resume from last checkpoint instead of starting fresh |

**Output:** Step-by-step progress with budget info, then final artifact path and thread ID.

**Full doc:** `docs/architecture/skill-system.md`

---

## skills/graph-validation/validate_graph.py

**Purpose:** Phase 9 test harness that validates 5 LangGraph graph patterns: conditional branching, error branches, retry paths, fallback paths, and parallel nodes.

**Runtime:** `.venv313/bin/python` (requires LangGraph)

**Usage:**

```bash
~/nemoclaw-local-foundation/.venv313/bin/python \
  ~/nemoclaw-local-foundation/skills/graph-validation/validate_graph.py
```

**Output:** Pass/fail for each of the 5 patterns. Results also written to `docs/architecture/langgraph-graph-validation-results.json`.

**When to run:** After upgrading LangGraph, after changes to skill-runner.py, during validation (called by validate.py check [27]).

**Full doc:** `docs/architecture/graph-validation-report.md`

---

## Python Runtime Summary

| Script | Python | Why |
|---|---|---|
| validate.py | System python3 | No LangGraph imports |
| obs.py | System python3 | No LangGraph imports |
| budget-enforcer.py | System python3 | No LangGraph imports |
| budget-status.py | System python3 | No LangGraph imports |
| tools.py | System python3 | No LangGraph imports |
| fix-sandbox-permissions.sh | Bash | Shell script |
| skill-runner.py | .venv313/bin/python | Imports LangGraph, langchain |
| validate_graph.py | .venv313/bin/python | Imports LangGraph |


---

## scripts/agent_registry.py

**Purpose:** MA-1 Agent Registry — enforcement engine for 7-agent AI company. Validates domain boundaries, memory write permissions, authority hierarchy, capability ownership.

**Added:** MA-1 (2026-03-28)

**Usage:**
```bash
python3 scripts/agent_registry.py --summary
python3 scripts/agent_registry.py --validate-action strategy_lead market_research
python3 scripts/agent_registry.py --validate-memory engineering_lead market_overview
python3 scripts/agent_registry.py --validate-override executive_operator strategy_lead
python3 scripts/agent_registry.py --agent-caps strategy_lead
python3 scripts/agent_registry.py --find-task "pricing strategy"
```

**Config:** `config/agents/agent-schema.yaml`, `config/agents/capability-registry.yaml`

---

## scripts/agent_memory.py

**Purpose:** MA-2 Three-layer memory — private (per-agent), shared (per-workflow), long-term (cross-workflow). Domain-enforced writes, 3-tier conflict escalation, memory decay, TTL, relevance-ranked prompt injection.

**Added:** MA-2 (2026-03-28)

**Usage:**
```bash
python3 scripts/agent_memory.py --workspace my_workflow --test
python3 scripts/agent_memory.py --workspace my_workflow --summary
python3 scripts/agent_memory.py --workspace my_workflow --dump-shared
python3 scripts/agent_memory.py --workspace my_workflow --inject strategy_lead
python3 scripts/agent_memory.py --workspace my_workflow --promote
```

---

## scripts/agent_messaging.py

**Purpose:** MA-3 Structured messaging — 11 intents, 5 channel types, voting, withdrawal, chat mode, hybrid blocking, timeout escalation, forced synthesis.

**Added:** MA-3 (2026-03-28)

**Usage:**
```bash
python3 scripts/agent_messaging.py --test
python3 scripts/agent_messaging.py --list-channels
python3 scripts/agent_messaging.py --read-channel pricing-debate
```

---

## scripts/decision_log.py

**Purpose:** MA-4 Decision lifecycle — proposed → debated → decided → executing → evaluated → learned. Dependencies, reversibility, structured outcomes, velocity, auto-lesson extraction.

**Added:** MA-4 (2026-03-28)

**Usage:**
```bash
python3 scripts/decision_log.py --test
python3 scripts/decision_log.py --summary
python3 scripts/decision_log.py --list
python3 scripts/decision_log.py --pending
python3 scripts/decision_log.py --accuracy strategy_lead
python3 scripts/decision_log.py --velocity
```

---

## scripts/orchestrator.py

**Purpose:** Multi-agent workflow orchestrator v2. Shared memory, agent roles, contracts, failure handling (retry/skip/halt/redirect), NL planning via LLM.

**Added:** Phase 40 (2026-03-27)

**Usage:**
```bash
python3 scripts/orchestrator.py --workflow workflows/pipeline-v2.yaml
python3 scripts/orchestrator.py --workflow workflows/pipeline-v2.yaml --dry-run
python3 scripts/orchestrator.py --plan "Research AI agents then write product spec" --dry-run
python3 scripts/orchestrator.py --list-skills
```

---

## scripts/test-all.py

**Purpose:** Regression test runner. Runs each skill with test-input.json, validates completion, 600s timeout, checkpoint backup/restore.

**Added:** Phase 5 (2026-03-27)

**Usage:**
```bash
python3 scripts/test-all.py                               # all skills
python3 scripts/test-all.py --skill e12-tech-trend-scanner # one skill
```

---

## scripts/tier3-batch-build.py

**Purpose:** Automated skill builder. Generates specs + code via meta-skills, applies known fixes, compile checks, tests. ~$0.25/skill.

**Added:** Tier 3 (2026-03-27)

**Usage:**
```bash
python3 scripts/tier3-batch-build.py
```

---

## scripts/new-skill.py

**Purpose:** Interactive skill scaffolder. Creates directory, skill.yaml template, run.py skeleton, outputs/.gitignore, test-input.json.

**Added:** Phase 13 (2026-03-26)

---

## scripts/checkpoint_utils.py

**Purpose:** Utility functions for LangGraph SqliteSaver checkpoint DB — backup, restore, clear, inspect.

**Added:** Phase 10 (2026-03-24)

**Usage:** Imported by other scripts. Not typically run standalone.

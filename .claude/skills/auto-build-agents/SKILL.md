---
name: auto-build-agents
description: Analyze agent/skill system, identify gaps, implement fixes to reach zero unassigned skills. This writes code. Use when building or fixing agent assignments.
context: fork
model: opus
allowed-tools: Bash, Read, Grep, Glob, Edit, Write
---

Analyze the full agent and skill system, identify all gaps, then implement fixes to reach zero unassigned skills and zero orphan tasks. This command writes code.

## 1. Map Current State (read-only phase)
Read all of the following before making any changes:
- `config/agents/agent-schema.yaml` — all current agent definitions
- `config/agents/capability-registry.yaml` — all skill-to-agent mappings
- `scripts/agent_registry.py` (MA-1)
- `scripts/access_control.py` (MA-19)
- `scripts/agent_performance.py` (MA-12)
- `scripts/behavior_guard.py` (MA-8)
- `scripts/orchestrator.py` — how the orchestrator routes tasks to agents
- All `skill.yaml` files under `skills/`

## 2. Gap Analysis
Build a complete picture of:
- **Unassigned skills** (in `skills/` but not in `capability-registry.yaml`)
- **Orphan tasks** (skills with no agent that has domain authority)
- **Capability holes** (task_class values with no agent handler)
- **Orchestrator routing gaps**

## 3. Design New Agent Definitions
For each gap, design new agents following the exact schema. Only create new agents where existing agents cannot be extended.

## 4. Implement Changes
Update in order: agent-schema.yaml, capability-registry.yaml, agent_registry.py, access_control.py, agent_performance.py, behavior_guard.py, orchestrator.py, pinchtab-config.yaml.

## 5. Validate
Run `python3 scripts/integration_test.py --test` and `python3 scripts/validate.py`. Fix any failures.

## 6. Final Report
Print before/after counts: agents, unassigned skills, orphan tasks, validation status.

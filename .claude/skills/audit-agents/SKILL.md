---
name: audit-agents
description: Deep review of the entire agent layer — permissions, roles, skill assignments, gap analysis. Use when auditing agents or checking agent coverage.
context: fork
model: sonnet
allowed-tools: Read, Grep, Glob
---

Perform a deep review of the entire agent layer. Read each file listed before drawing any conclusions.

## 1. Read Core Agent Files
Read all of the following in full:
- `config/agents/agent-schema.yaml` — all agent definitions
- `config/agents/capability-registry.yaml` — skill-to-agent mappings
- `scripts/agent_registry.py` (MA-1)
- `scripts/access_control.py` (MA-19)
- `scripts/agent_performance.py` (MA-12)
- `scripts/behavior_guard.py` (MA-8)

## 2. Permission vs. Role Consistency
For each agent, verify:
- Authority level in `agent-schema.yaml` matches the role (L1 = executive, L2 = strategy/ops, L3 = specialists)
- `owns` domains do not overlap with another agent's `owns`
- `forbidden` domains are enforced in `access_control.py`
- No agent has access to `blocked_domains` (banking, gov, payment portals)

## 3. Skill Assignment Audit
For every skill in `skills/` and every registered skill:
- Confirm it is assigned to an agent in `capability-registry.yaml`
- Confirm the assigned agent has the domain authority for that skill family
- Flag any skill with no agent owner (orphaned skill)
- Flag any agent with zero assigned skills

## 4. $1M ARR Autonomous Company Gap Analysis
Evaluate the current agent roster against the capabilities required to run a $1M ARR autonomous B2B SaaS/services company. Consider: lead gen, cold outreach, sales closing, client onboarding, delivery/PM, billing, paid ads, organic content/SEO, community/social, partnerships, customer success, financial reporting.

## 5. Recommendations
For each identified gap, propose a new agent definition or expanding an existing agent's scope.

## 6. Final Report
Print structured summary with: agents reviewed, permission violations, orphaned skills, functional gaps, critical gaps, new agent recommendations.

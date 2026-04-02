---
name: thread-agents
description: Session bootstrap for agent system work — MA-1 through MA-20, authority hierarchy, capability registry, gamification. Invoke when working on agents or multi-agent systems.
disable-model-invocation: true
allowed-tools: Read, Edit, Write, Bash, Glob, Grep
---

# Thread: Agent System & MA Architecture

You are now in **agents mode**. Work scoped to `config/agents/`, `scripts/agent_*.py`, and MA systems.

## The 11 Agents — Authority Hierarchy
```
L1 (Executive)
└── Tariq — executive_operator

L2 (Strategy + Operations)
├── Nadia — strategy_lead
└── Khalid — operations_lead

L3 (Domain Leads)
├── Layla — product_architect
├── Omar — growth_revenue_lead
├── Yasmin — narrative_content_lead
└── Faisal — engineering_lead

L4 (Execution)
├── Hassan — sales_outreach_lead
├── Rania — marketing_campaigns_lead
├── Amira — client_success_lead
└── Zara — social_media_lead
```

## Key Config Files
```
config/agents/
├── agent-schema.yaml          ← 11 agent definitions (73KB)
│   ├── identity (Jordanian name, cartoon persona, voice)
│   ├── authority_level (L1-L4)
│   ├── owns[] (skill domains this agent owns)
│   ├── forbidden[] (domains this agent cannot touch)
│   ├── behavior_modes (work | personality)
│   └── capabilities[]
└── capability-registry.yaml   ← skill-to-agent mapping (33KB)
    └── Maps each of 124 skills to owning agent + fallbacks
```

## MA Systems (scripts/)
| System | Script | Purpose |
|--------|--------|---------|
| MA-1 | agent_registry.py | Identity, caps, authority (3-tier) |
| MA-2 | agent_memory.py | 3-layer memory: working+episodic+workspace |
| MA-3 | agent_messaging.py | Typed agent-to-agent channels |
| MA-5 | task_decomposer.py | Goal→parallel tasks (5/wave, <$15 auto) |
| MA-6 | cost_governor.py | Circuit breaker (CLOSED/OPEN/HALF_OPEN) |
| MA-8 | behavior_guard.py | 16 rules, graduated enforcement |
| MA-9 | failure_recovery.py | 6 failure categories, escalation |
| MA-10 | conflict_resolution.py | 6 conflict types, 6 strategies |
| MA-11 | peer_review.py | Domain+capability+authority scoring |
| MA-12 | agent_performance.py | 5 dimensions, gamification, leaderboard |
| MA-13 | learning_loop.py | 90-day decay, priority ordering |
| MA-14 | system_health.py | 12 domains, composite scoring |
| MA-16 | human_loop.py | 4 actions, 6 approval categories |
| MA-19 | access_control.py | 7 domains, role-based permissions |
| MA-20 | integration_test.py | 37 checks, 10 phases |

## Architecture Locks (Critical)
- L-100: 7 agents with defined roles (now 11)
- L-101: 3-tier → 4-tier authority (L1-L4)
- L-120: `channel.add_message(Message(...))` not `.send()`
- L-140: `decompose()` returns 3-tuple `(plan, source, error)`
- L-150: Circuit breaker 3-state: CLOSED→OPEN→HALF_OPEN at 150%
- L-182: Blast radius check runs BEFORE escalation threshold
- L-200: Self-review check BEFORE assignment in `submit_review`

## Test Commands
```bash
python3 scripts/integration_test.py --test     # full MA-20 (all 37 checks)
python3 scripts/integration_test.py --summary  # quick pass/fail
python3 scripts/prod-ops.py agents             # agent roster + performance
```

## Out of Scope in This Thread
- Skill YAML content → use /thread-skills
- Frontend agent display → use /thread-frontend
- Budget/routing → use /thread-routing

## Common Tasks
- Add new skill-to-agent assignment in capability-registry.yaml
- Fix unassigned skills (orphaned skills with no agent owner)
- Add new agent or adjust authority level
- Fix MA system integration failures
- Extend behavior rules in MA-8
- Add new performance dimension in MA-12
- Fix MA-20 integration test failures

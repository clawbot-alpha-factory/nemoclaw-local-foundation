---
name: thread-audit-agents
description: Session bootstrap for deep agent layer audit — coverage gaps, orphaned skills, authority violations, MA system health. Invoke for targeted agent review.
disable-model-invocation: true
context: fork
agent: general-purpose
model: sonnet
allowed-tools: Read, Grep, Glob, Bash
---

# Thread: Agent Coverage Audit

You are running a **deep agent layer audit** for NemoClaw's 11-agent system.

## Files to Read First
```
config/agents/agent-schema.yaml         ← All 11 agent definitions
config/agents/capability-registry.yaml  ← 124 skill-to-agent mappings
```

## Audit Checklist

### 1. Skill Coverage — No Orphans
Every skill in `skills/` must be in capability-registry.yaml.
```bash
# Get all skill IDs
ls skills/ | grep -v skill-runner

# Find unregistered skills (in skills/ but not in registry)
# Cross-reference against capability-registry.yaml entries
```
Flag any skill not assigned to an agent.

### 2. Domain Boundary Violations
Each agent has `owns[]` and `forbidden[]` domains.
Verify capability-registry.yaml assignments respect these:
- Hassan (sales_outreach) should NOT own architecture skills
- Layla (product_architect) should NOT own social media skills
- Zara (social_media_lead) should own cnt-* and social skills

### 3. Authority Level Checks
L1 (Tariq) can delegate to L2/L3/L4.
L2 (Nadia, Khalid) can delegate to L3/L4.
L3 cannot assign tasks to L1/L2.
L4 cannot escalate without L3 approval.

Check MA-1 (agent_registry.py) correctly enforces these rules.

### 4. MA System Integration Gaps
```bash
python3 scripts/integration_test.py --test 2>&1 | grep -E "FAIL|ERROR|❌"
```
Report any MA phase failures with the specific check that failed.

### 5. Capability Gap Analysis
Map each business function to an agent:
| Function | Expected Owner | Actual? |
|----------|---------------|---------|
| Revenue closing | Hassan/Omar | ? |
| Lead qualification | Hassan | ? |
| Content strategy | Yasmin | ? |
| Engineering | Faisal | ? |
| Product design | Layla | ? |
| Marketing campaigns | Rania | ? |
| Client success | Amira | ? |
| Social media | Zara | ? |

### 6. Gamification Health
```bash
python3 scripts/prod-ops.py agents
```
Check: badges awarded, leaderboard populated, rivalries active.

## Report Format
```
AGENT AUDIT REPORT — [DATE]
━━━━━━━━━━━━━━━━━━━━━━━━━━━

Agents defined: 11/11
Skills assigned: X/124
Orphaned skills: X (list them)
Domain violations: X
Authority violations: X
MA integration: X/37 checks pass

ORPHANED SKILLS (no agent owner):
  - skill-id: [family]
  ...

DOMAIN VIOLATIONS:
  - Agent X assigned skill Y (forbidden domain)
  ...

MA FAILURES:
  - Phase X: [check name] FAILED
  ...

RECOMMENDED ASSIGNMENTS:
  - skill-id → assign to [agent] (reason)
  ...
```

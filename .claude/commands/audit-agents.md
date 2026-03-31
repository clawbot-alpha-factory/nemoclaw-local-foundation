Perform a deep review of the entire agent layer. Read each file listed before drawing any conclusions.

## 1. Read Core Agent Files
Read all of the following in full:
- `config/agents/agent-schema.yaml` — all 7 agent definitions
- `config/agents/capability-registry.yaml` — skill-to-agent mappings
- `scripts/agent_registry.py` (MA-1)
- `scripts/access_control.py` (MA-19)
- `scripts/agent_performance.py` (MA-12)
- `scripts/behavior_guard.py` (MA-8)
- `docs/skill-catalog-k40-k49.yaml` and `docs/skill-catalog-k50-k54.yaml` — registered skills awaiting agents

## 2. Permission vs. Role Consistency
For each agent, verify:
- Authority level in `agent-schema.yaml` matches the role (L1 = executive, L2 = strategy/ops, L3 = specialists)
- `owns` domains do not overlap with another agent's `owns`
- `forbidden` domains are enforced in `access_control.py`
- Web access permissions in `pinchtab-config.yaml` match what the agent role warrants
- No agent has access to `blocked_domains` (banking, gov, payment portals)

## 3. Skill Assignment Audit
For every skill in `skills/` and every registered skill in `docs/skill-catalog-k40-k54.yaml`:
- Confirm it is assigned to an agent in `capability-registry.yaml`
- Confirm the assigned agent has the domain authority for that skill family
- Flag any skill with no agent owner (orphaned skill)
- Flag any agent with zero assigned skills

## 4. $1M ARR Autonomous Company Gap Analysis
Evaluate the current 7-agent roster against the capabilities required to run a $1M ARR autonomous B2B SaaS/services company. Consider these functional areas and flag gaps:

| Function | Required? | Covered by Agent? | Gap? |
|---|---|---|---|
| Lead generation & prospecting | Yes | ? | ? |
| Cold outreach (email + LinkedIn) | Yes | ? | ? |
| Sales closing & negotiation | Yes | ? | ? |
| Client onboarding | Yes | ? | ? |
| Delivery & project management | Yes | ? | ? |
| Billing & invoicing | Yes | ? | ? |
| Paid advertising (Meta/Google) | Yes | ? | ? |
| Organic content & SEO | Yes | ? | ? |
| Community & social engagement | High | ? | ? |
| Partnerships & affiliate mgmt | Medium | ? | ? |
| Customer success & retention | Yes | ? | ? |
| Financial reporting & forecasting | Yes | ? | ? |

## 5. Recommendations
Based on the gap analysis, for each identified gap:
- Propose a new agent definition (id, name, role, authority_level, domain_owns, forbidden, web_access, recommended_skills)
- Or propose expanding an existing agent's scope with justification
- List which K40-K54 registered skills should be fast-tracked to implementation

## 6. Final Report
```
=== AGENT AUDIT REPORT ===

AGENTS REVIEWED: 7
PERMISSION VIOLATIONS: N
ORPHANED SKILLS: N (list them)
AGENTS WITH NO SKILLS: N (list them)
FUNCTIONAL GAPS FOR $1M ARR: N gaps identified

CRITICAL GAPS:
  - <gap> → Recommended agent: <name>

NEW AGENT RECOMMENDATIONS:
  1. <agent-id>: <role> — covers <capabilities>
  2. ...

QUICK WINS (expand existing agents):
  1. ...
```

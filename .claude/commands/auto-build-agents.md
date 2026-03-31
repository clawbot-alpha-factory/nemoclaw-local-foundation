Analyze the full agent and skill system, identify all gaps, then implement fixes to reach zero unassigned skills and zero orphan tasks. This command writes code.

## 1. Map Current State (read-only phase)
Read all of the following before making any changes:
- `config/agents/agent-schema.yaml` — all current agent definitions
- `config/agents/capability-registry.yaml` — all skill-to-agent mappings
- `scripts/agent_registry.py` (MA-1) — agent registration logic
- `scripts/access_control.py` (MA-19) — permission domain definitions
- `scripts/agent_performance.py` (MA-12) — performance tracking per agent
- `scripts/behavior_guard.py` (MA-8) — behavior rules per agent
- `scripts/orchestrator.py` — how the orchestrator routes tasks to agents
- All `skill.yaml` files under `skills/` — extract skill_id, family, domain, skill_type
- `docs/skill-catalog-k40-k49.yaml` and `docs/skill-catalog-k50-k54.yaml` — registered skills

## 2. Gap Analysis
Build a complete picture:

**Unassigned skills** (in `skills/` but not in `capability-registry.yaml`):
- List each with skill_id and family

**Orphan tasks** (skills with no agent that has the domain authority to run them):
- Cross-reference skill family → agent `owns` domains

**Capability holes** (task_class values referenced in `routing-config.yaml` with no agent handler):
- Check: web_research, social_publishing, outreach, lead_gen, payment, billing, content_creation

**Orchestrator routing gaps** (goals the orchestrator cannot decompose because no agent covers the needed function):
- Check `orchestrator.py` agent_map or equivalent routing table

## 3. Design New Agent Definitions
For each capability hole identified in step 2, design a new agent following the exact schema in `config/agents/agent-schema.yaml`. Each new agent must have:
- `id`: snake_case, descriptive
- `display_name`: human-readable
- `role`: one-line description
- `authority_level`: L1/L2/L3/L4 (L4 for specialist roles below ops)
- `domain_owns`: list of domain letters this agent controls
- `forbidden_domains`: domains this agent cannot touch
- `memory_write_keys`: keys this agent writes to shared memory
- `web_access`: level (full/navigate_and_read/none) with PinchTab profile
- `skills_assigned`: list of skill_ids from existing built or registered skills
- `ma_systems_integrated`: which MA systems this agent participates in

Only create new agents where existing agents cannot be extended with a scope change.

## 4. Implement Changes
Make all changes in this order:

### 4a. Update `config/agents/agent-schema.yaml`
Add new agent definitions to the `agents` list.

### 4b. Update `config/agents/capability-registry.yaml`
Add new capability entries mapping skills to new agents. Reassign any orphaned skills from step 2.

### 4c. Update `scripts/agent_registry.py` (MA-1)
Register all new agents in the registry. Follow the existing pattern exactly — do not change how existing agents are registered, only add new entries.

### 4d. Update `scripts/access_control.py` (MA-19)
Add permission domain entries for each new agent. Follow the existing 7-domain pattern.

### 4e. Update `scripts/agent_performance.py` (MA-12)
Add performance tracking entries for each new agent using the existing 5-dimension profile pattern.

### 4f. Update `scripts/behavior_guard.py` (MA-8)
Add behavior rule bindings for each new agent. New agents at L3/L4 get the standard specialist rule set.

### 4g. Update `scripts/orchestrator.py`
Ensure the orchestrator's agent routing table includes all new agents with their capability domains.

### 4h. Update `config/pinchtab-config.yaml` (if any new agent has web access)
Add browser profile entry for each new web-enabled agent.

## 5. Validate
After all changes:
1. Run `python3 scripts/integration_test.py --test` — must pass
2. Run `python3 scripts/validate.py` — no new failures
3. Verify zero unassigned skills by re-running the gap check from step 2

If validation fails, diagnose the error, fix it, and re-run before reporting done.

## 6. Final Report
```
=== AUTO-BUILD AGENTS REPORT ===

BEFORE:
  Agents: 7
  Unassigned skills: N
  Orphan tasks: N
  Capability holes: N

NEW AGENTS CREATED: N
  - <agent-id>: <role> — covers <N skills>
  - ...

SKILLS REASSIGNED: N
  - <skill-id> → <new-agent-id>

AFTER:
  Agents: N
  Unassigned skills: 0
  Orphan tasks: 0

VALIDATION: PASS / FAIL
  Integration test: PASS/FAIL
  Validate.py: N pass, N warn, N fail
```

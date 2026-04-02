---
name: thread-skills
description: Session bootstrap for skill development — building, fixing, auditing, and testing NemoClaw skills. Invoke at session start when working on skills/.
disable-model-invocation: true
allowed-tools: Read, Edit, Write, Bash, Glob, Grep
---

# Thread: Skills Development

You are now in **skills mode**. All work is scoped to `skills/` and `lib/routing.py`.

## Schema v2 — Required Structure
Every skill at `skills/<id>/`:
```
skill.yaml          ← Schema v2 definition (REQUIRED)
run.py              ← Execution engine (REQUIRED)
test-input.json     ← {"inputs": {...}} (REQUIRED)
outputs/            ← Artifact directory (REQUIRED, empty OK)
```

## Schema v2 Rules (NON-NEGOTIABLE)
- `step_type` MUST be `local` | `llm` | `critic` — never `makes_llm_call`
- All LLM calls via `from lib.routing import call_llm` — never hardcode models (L-003)
- Step names must be semantic (3+ words — no "Step 1", "Processing", "TODO")
- Family IDs zero-padded: F01-F99, domains single letters A-L
- Skill IDs: `<family>-<name>` (e.g. `a01-arch-spec-writer`, `rev-01-autonomous-sales-closer`)
- Critic loops need: generate step → critic step (scores) → if score < threshold, improve step → re-evaluate

## Routing Usage
```python
from lib.routing import call_llm

# Available task classes (from routing-config.yaml):
# cheap_claude, reasoning_claude, premium_claude
# cheap_openai, reasoning_openai, reasoning_o3
# cheap_google, reasoning_google, vision_google

response = call_llm(
    messages=[{"role": "user", "content": "..."}],
    task_class="reasoning_claude",
    max_tokens=4096
)
```

## Skill Families (124 total)
| Prefix | Domain | Count |
|--------|--------|-------|
| a01 | Architecture | 3 |
| b05-b06 | Build/CI | 6 |
| biz | Business | 8 |
| c07 | Content/Docs | 4 |
| cnt | Content Factory | 16 |
| e08/e12 | Research/Market | 5 |
| int | Intelligence | 6 |
| k40-k61 | Commercial | 15 |
| out | Outreach | 8 |
| rev | Revenue | 25 |
| scl | Scale | 10 |
| (other) | Various | ~18 |

## Dev Commands
```bash
# Generate new skill from template
python3 scripts/new-skill.py --id <id> --name "<name>" --family N --domain D \
  --tag <tag> --skill-type <type> --step-names "<steps>" --llm-steps "N"

# Test single skill
python3 skills/skill-runner.py --skill SKILL_ID --input key value
python3 scripts/test-all.py --skill SKILL_ID

# Test all skills
python3 scripts/test-all.py

# Validate L-003 compliance
grep -rn "ChatAnthropic\|ChatOpenAI\|gpt-4\|claude-3" skills/*/run.py

# Delete checkpoint between runs
rm -f ~/.nemoclaw/checkpoints/langgraph.db
```

## Quality Gate
Skills must score ≥ 9/10 on critic evaluation before production use.
Critic loop: Generate → Score (1-10 per dimension) → min() across dimensions → if < 9.0, Improve → re-score.

## Out of Scope in This Thread
- Frontend/backend → use /thread-frontend or /thread-backend
- Agent YAML config → use /thread-agents
- Routing config changes → use /thread-routing

## Common Tasks
- Build new skill from template
- Fix L-003 violations (hardcoded models)
- Add critic loop to existing skill
- Fix step_type schema violations
- Improve skill prompt quality
- Add better test inputs
- Chain skills via envelope output

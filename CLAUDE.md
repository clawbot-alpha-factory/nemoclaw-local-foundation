# CLAUDE.md

NemoClaw Local Foundation — LangGraph-based AI skill execution and multi-agent orchestration. 124 skills, 11 agents, 4-tier authority hierarchy, 20 MA subsystems.

## Common Commands

```bash
# Validation
python3 scripts/validate.py                          # 31-check validation
python3 scripts/integration_test.py --summary        # MA-20 integration (quick)
python3 scripts/integration_test.py --test           # MA-20 integration (full)
bash scripts/full_regression.sh                      # enterprise regression

# Skills
python3 skills/skill-runner.py --skill SKILL_ID --input key value
python3 skills/skill-runner.py --skill SKILL_ID --input-from envelope.json
python3 scripts/test-all.py                          # all skills
python3 scripts/test-all.py --skill SKILL_ID         # single skill

# Operations
python3 scripts/prod-ops.py status|health|costs|agents|validate|integration
python3 scripts/orchestrator.py --workflow workflows/pipeline-v2.yaml

# New skill
python3 scripts/new-skill.py --id <id> --name "<name>" --family N --domain D \
  --tag <tag> --skill-type <type> --step-names "<steps>" --llm-steps "N"

# Command Center
uvicorn app.main:app --reload --port 8100            # backend (from command-center/backend)
npm run dev                                          # frontend port 3000 (from command-center/frontend)
```

## Architecture

**Runtime:** Python 3.12 (.venv313) · LangGraph StateGraph + SqliteSaver · FastAPI port 8100 · Next.js port 3000

**Routing:** All LLM calls via `lib/routing.py` `call_llm(messages, task_class, max_tokens)` — 9 aliases across Anthropic/OpenAI/Google. Never hardcode models (L-003).

**Execution flow:** skill-runner.py v4.0 → reads skill.yaml → builds StateGraph → dispatches steps by step_type → writes artifact + JSON envelope to `skills/<id>/outputs/`

**Critic loop:** Generate → Critic (score) → if score < 10.0, Improve → re-evaluate

## Key Config Files
- `config/routing/routing-config.yaml` — 9 LLM aliases + routing rules
- `config/routing/budget-config.yaml` — $30/provider with 150% circuit breaker
- `config/agents/agent-schema.yaml` — agent definitions (@see for details)
- `config/agents/capability-registry.yaml` — skill-to-agent mapping
- `config/.env` — API keys (Anthropic, OpenAI, Google, Asana)

## Architecture Locks
See @docs/architecture-lock.md for all 413 locked decisions. Critical:
- **L-001**: Python 3.12.13 via .venv313
- **L-002**: LangGraph StateGraph + SqliteSaver only
- **L-003**: 9-alias routing — never hardcode provider/model
- **L-004**: Per-provider budget with circuit breaker
- **L-005**: skill-runner.py v4.0 sole execution entry point

## Conventions
- Skill IDs: `<family>-<name>` (e.g. `a01-arch-spec-writer`)
- Schema v2: `step_type` = `local` | `llm` | `critic` only
- Family numbers zero-padded (F01-F99), domains single letters A-L
- Step names semantic (3+ words), quality minimum 10/10
- Delete checkpoint DB between test runs
- Logs: `~/.nemoclaw/logs/provider-usage.jsonl`, `validation-runs.jsonl`

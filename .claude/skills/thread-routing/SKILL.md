---
name: thread-routing
description: Session bootstrap for LLM routing system, budget governance, and cost optimization. Invoke when working on lib/routing.py, routing-config.yaml, or budget-config.yaml.
disable-model-invocation: true
allowed-tools: Read, Edit, Write, Bash, Glob, Grep
---

# Thread: LLM Routing & Budget Governance

You are now in **routing mode**. Work scoped to `lib/routing.py`, `config/routing/`, and `scripts/cost_governor.py`.

## The 9 LLM Aliases
```yaml
# From config/routing/routing-config.yaml
cheap_claude:       claude-haiku-4-5     (Anthropic)  ← fast, cheap
reasoning_claude:   claude-sonnet-4-6    (Anthropic)  ← balanced default
premium_claude:     claude-opus-4-6      (Anthropic)  ← highest quality

cheap_openai:       gpt-4o-mini          (OpenAI)     ← fast, cheap
reasoning_openai:   gpt-4.1              (OpenAI)     ← balanced
reasoning_o3:       o3                   (OpenAI)     ← deep reasoning

cheap_google:       gemini-2.0-flash     (Google)     ← fast, cheap
reasoning_google:   gemini-2.5-pro       (Google)     ← balanced
vision_google:      gemini-2.5-pro       (Google)     ← multimodal
```

## Budget System
```yaml
# From config/routing/budget-config.yaml
Per-provider limit: $30/provider
Circuit breaker:    Trips at 150% ($45/provider)
States:             CLOSED → OPEN → HALF_OPEN
Recovery:           HALF_OPEN allows test requests to check if provider recovered
```

## lib/routing.py Interface (v1.1.0)
```python
from lib.routing import call_llm, resolve_alias

# Primary function — used by ALL 124 skills
response = call_llm(
    messages: list[dict],
    task_class: str,        # one of the 9 aliases above
    max_tokens: int = 4096
) -> str

# Secondary — resolve alias to provider/model/cost
provider, model, cost = resolve_alias(task_class)
```

## Architecture Locks
- **L-003**: NEVER hardcode provider/model anywhere. Always use task_class alias.
- **L-004**: Per-provider budget with circuit breaker mandatory.
- Changing routing-config.yaml affects ALL 124 skills simultaneously.
- Adding a new alias requires updating routing-config.yaml + optionally skill YAML.

## Key Violation Pattern (L-003 breach)
```python
# ❌ WRONG — hardcoded model
from langchain_anthropic import ChatAnthropic
llm = ChatAnthropic(model="claude-3-5-sonnet-20241022")

# ✅ CORRECT — alias routing
from lib.routing import call_llm
response = call_llm(messages, "reasoning_claude", max_tokens=4096)
```

## Cost Tracking
- Logs: `~/.nemoclaw/logs/provider-usage.jsonl`
- Per-agent ledger: `scripts/agent_performance.py` (AgentLedger)
- Budget check: `python3 scripts/prod-ops.py costs`
- Enforce: `scripts/budget-enforcer.py`, `scripts/cost_governor.py`

## Commands
```bash
# Check budget status
python3 scripts/prod-ops.py costs
python3 scripts/budget-status.py

# Validate routing
python3 scripts/validate.py   # checks 24+25 routing aliases

# Find L-003 violations
grep -rn "ChatAnthropic\|ChatOpenAI\|gpt-4\|claude-3\|gemini" skills/*/run.py
python3 scripts/fix-l003.py skills/ --dry-run
```

## Out of Scope in This Thread
- Skill content/prompts → use /thread-skills
- Frontend cost display → use /thread-frontend
- Agent behavior → use /thread-agents

## Common Tasks
- Add new LLM alias to routing-config.yaml
- Change default model for a task class
- Fix circuit breaker tripping prematurely
- Audit all skills for L-003 violations
- Adjust per-provider budget limits
- Add new provider integration to lib/routing.py
- Debug routing config loading errors

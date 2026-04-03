# NemoClaw Prompt Engineering Guide

How agent system prompts are constructed, provider-specific best practices, and guidelines for maintaining prompt quality.

## System Prompt Architecture

Every agent response is governed by a 6-block system prompt built dynamically by `AgentPersona.build_system_prompt()` in `command-center/backend/app/services/agent_chat_service.py`.

### Block Structure

| Block | Source | Purpose | Token Budget |
|-------|--------|---------|--------------|
| 1. IDENTITY | agent-schema.yaml identity section | Name, title, authority level, persona, voice rules, philosophy, operating principles | ~200 |
| 2. AUTHORITY | agent-schema.yaml domain_boundaries + authority_hierarchy | Domains owned/forbidden, reporting chain, override rules | ~100 |
| 3. CAPABILITIES | capability-registry.yaml | Skills, tools, invocation format | ~120 |
| 4. TEAM DIRECTORY | All agents (cached at init) | All 11 agents with roles + domain overlap rules | ~200 |
| 5. QUALITY | agent-schema.yaml autonomous_capability | Quality target, KPIs, output structure rules | ~80 |
| 6. CONTEXT | Runtime (budget, work logs) | Budget remaining per provider, last 3 work items | ~60 |
| + QUALITY GUIDE | docs/agents/{id}.md | Checklist + few-shot examples from quality guide | ~300 |
| + BEHAVIOR | Hardcoded | Communication rules, character, conciseness | ~80 |
| **Total** | | | **~1140** |

### Method Mapping

Each block maps to a private method on `AgentPersona`:

```
_build_identity_block()      → Block 1
_build_authority_block()      → Block 2
_build_capabilities_block()   → Block 3
(team_block param)            → Block 4
_build_quality_block()        → Block 5
_build_context_block()        → Block 6
(quality_doc param)           → Quality Guide
_build_behavior_rules()       → Behavior
```

To modify a block, change the corresponding method. Never edit the prompt assembly in `build_system_prompt()` directly — it just joins blocks.

### Data Flow

```
AgentChatService.__init__()
  ├── _load_agents()              → self._agents + self._schema_top
  ├── _load_capability_registry() → self._agent_capabilities + self._agent_tools
  ├── _build_team_block()         → self._team_block (cached, same for all)
  └── _cache_quality_docs()       → self._quality_docs

generate_response(agent_id, message)
  ├── _get_context_data(agent_id) → budget + work history (fresh per call)
  └── agent.build_system_prompt(
        capability_data, team_block, quality_doc, context_data, schema_top
      ) → full system prompt string
```

---

## Provider-Specific Best Practices

NemoClaw routes LLM calls through `lib/routing.py call_llm()` which selects providers via 9-alias routing (L-003/L-004). Agent chat uses OpenAI SDK directly. Skills use call_llm() which can route to any provider.

### OpenAI (gpt-5.4, gpt-5.4-mini)

**Used for:** Agent chat responses, agentic tasks, general skills.

Best practices:
- System prompt is strongly followed — put the most important instructions first
- Use structured output format when expecting JSON (set `response_format`)
- Temperature 0.7 for conversational (agent chat), 0.3 for analytical (skills)
- Function calling for tool invocations when building agentic workflows
- Keep system prompt under 2000 tokens — context quality drops with bloated prompts
- Use `max_completion_tokens` (not `max_tokens`) for newer models

### Anthropic Claude (claude-sonnet-4-6, claude-opus-4-6)

**Used for:** Premium skills, strategic reasoning, complex analysis (via call_llm).

Best practices:
- Use XML tags for structured sections: `<identity>`, `<instructions>`, `<context>`
- Explicit role assignment: "You are X. Your task is Y. Here is the context: Z."
- Chain-of-thought with `<thinking>` tags for complex reasoning tasks
- Claude follows long system prompts well — can handle 3000+ tokens effectively
- Use `\n\nHuman:` / `\n\nAssistant:` format in message construction
- Prefer bulleted instructions over paragraph-form instructions

### Google Gemini (gemini-2.5-pro, gemini-2.5-flash)

**Used for:** Fallback chain, long-context tasks, multimodal skills.

Best practices:
- Separate system instructions from user prompt (use `system_instruction` param)
- Excellent at long-context tasks (1M+ tokens) — useful for research skills
- Grounding with Google Search available for fact-checking tasks
- Temperature 0.4 for factual, 0.8 for creative
- Multimodal inputs supported — useful for image analysis skills (cnt-12, cnt-13)
- Less strict about system prompt following — repeat critical instructions

---

## Token Budget Guidelines

### Per-Tier Allocation

| Tier | Total Budget | System Prompt | Context | Completion | Use Case |
|------|-------------|---------------|---------|------------|----------|
| T1 (general_short) | 4K | ~1200 | ~1800 | ~1000 | Agent chat, quick tasks |
| T2 (moderate) | 8K | ~1200 | ~4800 | ~2000 | Standard skills |
| T3 (premium) | 16K | ~1500 | ~10500 | ~4000 | Complex skills, research |
| T4 (premium_long) | 32K+ | ~2000 | ~24000 | ~6000 | Chain routing, deep analysis |

### System Prompt Budget Breakdown

For agent chat (T1):
- Identity block: 200 tokens — name, title, persona, voice rules, principles
- Authority block: 100 tokens — owns, forbidden, reporting chain
- Capabilities block: 120 tokens — skill IDs (not descriptions), tools, invocation
- Team block: 200 tokens — 11 one-liners + overlap rules
- Quality block: 80 tokens — target, remediation, output rules
- Context block: 60 tokens — budget lines, 3 work items
- Quality guide: 300 tokens — checklist + 1-2 examples (truncated from docs/agents/)
- Behavior: 80 tokens — 7 rules

**Total: ~1140 tokens.** Leaves ~660 tokens headroom for 15-message context window and 800-token completion.

---

## Anti-Patterns to Avoid

### 1. Prompt Bloat
**Bad:** Dumping entire agent schema (200+ lines) into system prompt.
**Fix:** Extract only what the model needs to know. Skill IDs, not descriptions. Domain names, not full governance rules.

### 2. Vague Quality Instructions
**Bad:** "Produce high-quality output."
**Fix:** "Target 9/10. Structure with headers and bullets. Include reasoning for every recommendation. Never fabricate data."

### 3. Static Context
**Bad:** Hardcoding budget numbers or team composition in prompts.
**Fix:** Load budget from provider-usage.jsonl and work history from work-logs/ dynamically per call.

### 4. Generic Delegation
**Bad:** "Delegate to the right person if needed."
**Fix:** Include full team directory with each agent's domains so the model knows exactly who handles what.

### 5. Repeating Instructions Across Blocks
**Bad:** Mentioning "be concise" in identity, quality, AND behavior blocks.
**Fix:** Each instruction appears in exactly one block. Identity = who you are. Quality = output standards. Behavior = communication style.

### 6. Over-Prompting for Character
**Bad:** 500 tokens of character backstory, quotes, and persona details.
**Fix:** One persona line + voice style + work example. The model infers the rest. Character details belong in docs/agents/ quality guides, not every prompt.

### 7. Hallucination Triggers
**Bad:** "You have access to real-time data about..." (when you don't).
**Fix:** "Reference the budget data provided in CONTEXT. If data is not available, state that explicitly."

---

## Adding a New Agent

Checklist when adding agent #12+:

1. Add agent definition to `config/agents/agent-schema.yaml` — follow existing schema
2. Add domain_boundaries entry with owns/forbidden/memory_write_keys
3. Add capabilities to `config/agents/capability-registry.yaml`
4. Add tool_bridges entries if agent uses external tools
5. Create `docs/agents/{agent_id}.md` quality guide (follow template from existing guides)
6. Run `python3 scripts/validate.py` — 0 failures
7. Verify: `build_system_prompt()` produces 500+ words for new agent
8. Team block auto-updates at service init — no manual change needed

## Modifying Prompt Blocks

Each block is isolated in its own `_build_*` method. To change what goes into a prompt:

| Want to change... | Edit this method |
|-------------------|-----------------|
| Agent personality/voice | `_build_identity_block()` |
| Domain permissions | `_build_authority_block()` |
| Available skills/tools | `_build_capabilities_block()` |
| Output quality rules | `_build_quality_block()` |
| Runtime budget/history | `_build_context_block()` |
| Communication style | `_build_behavior_rules()` |
| Few-shot examples | `docs/agents/{id}.md` |
| Team directory | `_build_team_block()` on AgentChatService |

Never edit `build_system_prompt()` to add content — add a new block method and include it in the assembly.

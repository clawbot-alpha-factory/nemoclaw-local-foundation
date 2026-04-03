# OpenAI Multi-Agent Setup Guide for NemoClaw

**Date:** 2026-04-03
**Status:** Research — no code changes applied
**Scope:** Maps OpenAI's agent ecosystem to NemoClaw's 11 agents / 128 skills

---

## 1. OpenAI Agents SDK (Production Framework)

**Repo:** https://github.com/openai/openai-agents-python
**Docs:** https://openai.github.io/openai-agents-python/
**Status:** v0.10.2, Python + TypeScript

The Agents SDK (March 2025) replaced Swarm as OpenAI's production agent framework. Three primitives:

| Primitive | Purpose | NemoClaw Equivalent |
|-----------|---------|-------------------|
| **Agent** | LLM + instructions + tools | Agent definition in `agent-schema.yaml` |
| **Handoff** | Delegate to another agent | MA-3 message protocol + authority tiers |
| **Guardrail** | Input/output validation | MA-15 output quality gate |

### Creating NemoClaw Agents as OpenAI Agents

```python
from agents import Agent, Runner, function_tool, handoff, ToolSearchTool, tool_namespace

# Define a NemoClaw skill as a function tool
@function_tool
def execute_skill(skill_id: str, inputs: dict = {}) -> str:
    """Execute a NemoClaw skill by ID with optional inputs."""
    import subprocess, json
    result = subprocess.run(
        ["python3", "skills/skill-runner.py", "--skill", skill_id,
         "--input-from", "/dev/stdin"],
        input=json.dumps(inputs), capture_output=True, text=True
    )
    return result.stdout

# Agent definitions matching NemoClaw's 11 agents
research_lead = Agent(
    name="research-lead",
    handoff_description="Market research, competitive analysis, trend scanning",
    instructions="""You are Nadia (Strategy Lead). Authority Level 2.
    Domains: market_intelligence, competitive_analysis, go_no_go decisions.
    Max routing tier: 4.""",
    tools=[execute_skill],
)

content_engine = Agent(
    name="content-engine",
    handoff_description="Copywriting, scripts, documentation, brand narrative",
    instructions="""You are Yasmin (Narrative & Content Lead). Authority Level 3.
    Domains: creative_writing, content, research.
    Max routing tier: 3.""",
    tools=[execute_skill],
)

# Ops commander as triage agent (root of hierarchy)
ops_commander = Agent(
    name="ops-commander",
    instructions="""You are Tariq (Executive Operator). Authority Level 1.
    Route tasks to the right specialist agent.
    Override any agent blocking critical path.""",
    handoffs=[research_lead, content_engine],  # + all other agents
)

result = await Runner.run(ops_commander, "Research competitor pricing strategies")
```

### ToolSearchTool for 124 Skills

With 124 skills, loading all tool definitions into context is expensive. OpenAI's `ToolSearchTool` defers loading:

```python
# Group NemoClaw skills into namespaces by domain
@function_tool(defer_loading=True)
def a01_arch_spec_writer(project_name: str, requirements: str) -> str:
    """Write an architecture specification document."""
    return execute_skill("a01-arch-spec-writer", {"project_name": project_name})

architecture_tools = tool_namespace(
    name="architecture",
    description="Architecture and system design tools",
    tools=[a01_arch_spec_writer],  # + other arch skills
)

content_tools = tool_namespace(
    name="content",
    description="Content creation and copywriting tools",
    tools=[...],  # 19 content skills
)

# Agent with deferred tool loading
architect = Agent(
    name="product-architect",
    tools=[*architecture_tools, *content_tools, ToolSearchTool()],
)
```

**Constraint:** Keep namespaces under 10 functions each. For 128 skills across 12 domains, you'd need ~13 namespaces.

### Agent-as-Tool Pattern (Orchestrator)

```python
orchestrator = Agent(
    name="ops-commander",
    tools=[
        research_lead.as_tool(
            tool_name="delegate_research",
            tool_description="Deep market research and competitive analysis",
        ),
        content_engine.as_tool(
            tool_name="delegate_content",
            tool_description="Generate marketing content and documentation",
        ),
        # ... all 10 specialist agents as tools
    ],
)
```

### Guardrails (Maps to MA-15 Quality Gate)

```python
from agents import Agent, InputGuardrail, OutputGuardrail, GuardrailFunctionOutput

async def quality_check(ctx, agent, output) -> GuardrailFunctionOutput:
    """Enforce NemoClaw's min quality score."""
    # Parse quality score from output
    if quality_score < 7:
        return GuardrailFunctionOutput(
            output_info={"score": quality_score},
            tripwire_triggered=True  # Blocks output
        )
    return GuardrailFunctionOutput(output_info={"score": quality_score})

quality_sentinel = Agent(
    name="quality-sentinel",
    output_guardrails=[OutputGuardrail(guardrail_function=quality_check)],
)
```

---

## 2. Responses API (Replacing Assistants API)

**Migration guide:** https://developers.openai.com/api/docs/assistants/migration

| Timeline | Event |
|----------|-------|
| Aug 2025 | Assistants API deprecated |
| Aug 2026 | Assistants API sunset |
| Now | Responses API is the successor |

**NemoClaw impact: NONE.** NemoClaw uses LangChain wrappers (L-016), not raw OpenAI API. The Responses API's stateless model aligns with how NemoClaw already works (state in LangGraph StateGraph, not in OpenAI).

---

## 3. Function Calling Best Practices for 128 Skills

**Docs:** https://developers.openai.com/api/docs/guides/function-calling

### Capacity
- Under ~100 tools is "in-distribution" and reliable
- NemoClaw's 128 skills are slightly over the comfort zone
- **Solution:** Per-agent tool filtering via `capability-registry.yaml` keeps each agent under 31 tools (growth_revenue_lead has the most at 31)

### Best Practices
1. **Clear descriptions** — not "Search web" but "Search for current competitive intelligence on specified market"
2. **System prompt routing** — explicitly state when to use Tool A vs Tool B
3. **`strict: true`** — always enable for schema adherence
4. **`parallel_tool_calls: false`** — when skill ordering matters (critic loops)
5. **Filter tools per agent** — NemoClaw already does this via `capability-registry.yaml`

### o3/o4-mini Guidance
- Improved function calling over GPT-4o
- Put tool selection logic in system prompt for reasoning models
- Use `tool_choice: "required"` when a tool must be called

**Source:** https://developers.openai.com/cookbook/examples/o-series/o3o4-mini_prompting_guide

---

## 4. Model Selection & Pricing

**Source:** https://openai.com/api/pricing/

### Current Pricing (per 1M tokens)

| Model | Input | Output | Context | Best For |
|-------|-------|--------|---------|----------|
| **gpt-4.1** | $2.00 | $8.00 | 1M | Instruction following, long context, coding |
| **gpt-4.1-mini** | $0.40 | $1.60 | 1M | Fast tasks, cost-sensitive |
| **o3** | $0.40 | $1.60 | 200K | Complex reasoning, multi-step logic |
| **o4-mini** | $1.10 | $4.40 | 200K | Reasoning at moderate cost |
| **gpt-4o** | $2.50 | $10.00 | 128K | Legacy (being superseded) |

**Key insight:** o3 at $0.40/$1.60 has reasoning capabilities at the same price as gpt-4.1-mini. Reasoning is now cheap.

### Recommended Routing Updates

Map to NemoClaw's `config/routing/routing-config.yaml`:

| NemoClaw Alias | Current Model | Recommended | Rationale |
|----------------|--------------|-------------|-----------|
| `structured_short` | gpt-5.4-mini | gpt-4.1-mini | Classification, JSON — cheapest |
| `agentic` | gpt-5.4 | gpt-4.1 | Best instruction following, 1M context |
| `deep_reasoning` | o3 | o3 | Already optimal — reasoning at mini prices |
| Critic scoring | — | o3 | Reasoning for quality eval, same cost as mini |
| Fallback | gpt-5.4-mini | gpt-4.1-mini | Cheapest reliable fallback |

### Cost Projection per Full Skill Run

| Scenario | Est. Cost |
|----------|-----------|
| All 128 skills, gpt-4.1 only | ~$8.50 |
| Mixed (mini for simple, 4.1 for standard, o3 for reasoning) | ~$3.20 |
| With prompt caching | ~$1.60 |

---

## 5. Framework Comparison for NemoClaw

| Feature | LangGraph (current) | OpenAI Agents SDK | CrewAI | AutoGen |
|---------|-------------------|-------------------|--------|---------|
| State persistence | SqliteSaver | None | Limited | Event-driven |
| Graph cycles/loops | Native StateGraph | No (linear handoffs) | No | Yes |
| Checkpointing | Built-in | No | No | Yes |
| Multi-provider | Via LangChain | 100+ models | Yes | Yes |
| Tool search/deferred | No | ToolSearchTool | No | No |
| Guardrails | Custom | Built-in | No | No |
| Production maturity | GA v1.0+ | v0.10.2 | v1.10.1 | Preview |
| Cost tracking | Custom (MA-6) | No | No | No |

**Verdict:** LangGraph remains the best foundation for NemoClaw's complexity (state machines, checkpointing, critic loops, graph cycles). The Agents SDK is lighter but lacks persistence and graph-based execution.

### What to Adopt from OpenAI's Ecosystem

| Pattern | Source | NemoClaw Target |
|---------|--------|----------------|
| ToolSearchTool deferred loading | Agents SDK | `lib/routing.py` — tool filtering layer |
| Guardrails (parallel validation + fail-fast) | Agents SDK | MA-15 quality gate |
| o3 for critic/quality scoring | Model pricing | `routing-config.yaml` aliases |
| gpt-4.1 as workhorse | Model pricing | `routing-config.yaml` aliases |
| Namespace grouping for tools | Function calling docs | `capability-registry.yaml` evolution |

### What NOT to Adopt

- **Don't switch to Agents SDK** — LangGraph is strictly more powerful for NemoClaw
- **Don't adopt AgentKit/Agent Builder** — OpenAI-locked, NemoClaw is multi-provider
- **Don't migrate to CrewAI** — Would require rewrite with no material benefit
- **Don't adopt AutoGen** — Maintenance mode, merging into MS Agent Framework

---

## 6. Key URLs Reference

| Resource | URL |
|----------|-----|
| OpenAI Agents SDK (Python) | https://github.com/openai/openai-agents-python |
| Agents SDK Docs | https://openai.github.io/openai-agents-python/ |
| Agents SDK Tools | https://openai.github.io/openai-agents-python/tools/ |
| Agents SDK Multi-Agent | https://openai.github.io/openai-agents-python/multi_agent/ |
| Responses API Migration | https://platform.openai.com/docs/guides/migrate-to-responses |
| Function Calling Guide | https://developers.openai.com/api/docs/guides/function-calling |
| o3/o4-mini Guide | https://developers.openai.com/cookbook/examples/o-series/o3o4-mini_prompting_guide |
| OpenAI Pricing | https://openai.com/api/pricing/ |
| AgentKit | https://openai.com/index/introducing-agentkit/ |
| Agent Builder Guide | https://developers.openai.com/api/docs/guides/agent-builder |
| Practical Guide to Agents (PDF) | https://cdn.openai.com/business-guides-and-resources/a-practical-guide-to-building-agents.pdf |
| Swarm (deprecated) | https://github.com/openai/swarm |
| LangGraph | https://github.com/langchain-ai/langgraph |
| CrewAI | https://github.com/crewAIInc/crewAI |
| AutoGen | https://github.com/microsoft/autogen |

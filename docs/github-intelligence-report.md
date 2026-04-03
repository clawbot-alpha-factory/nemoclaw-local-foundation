# GitHub Intelligence Report: Multi-Agent Open-Source Landscape

**Date:** 2026-04-03
**Status:** Research — no code changes applied
**Scope:** Top repos with agent configurations, quality gates, cost tracking, and patterns NemoClaw can adopt

---

## Executive Summary

Analyzed 13+ repos totaling 250K+ stars. NemoClaw's architecture is ahead of most frameworks in state management (LangGraph), cost governance (MA-6), and quality gates (MA-15). However, 6 gaps were identified: no observability layer, monolithic agent config, no per-model budgets, no standard eval metrics, memory lacks scoring, no agent portability.

**Top 3 immediate adoptions:** DeepEval agentic metrics, AgentOps monitoring, Anthropic cookbook patterns.

---

## 1. Agent Orchestration Frameworks

### 1.1 CrewAI — 44,300 stars

**URL:** https://github.com/crewAIInc/crewAI
**Downloads:** 5.2M/month

Role-playing agents with YAML-first configuration. Closest analog to NemoClaw's `agent-schema.yaml`.

**Agent YAML Pattern:**
```yaml
# config/agents.yaml
researcher:
  role: "{topic} Senior Data Researcher"
  goal: "Uncover cutting-edge developments in {topic}"
  backstory: "You're a seasoned researcher with a knack for uncovering trends..."
  verbose: true
  tools: [SerperDevTool, ScrapeWebsiteTool]
  llm: grok-3
  allow_delegation: true

content_writer:
  role: "{topic} Content Strategist"
  goal: "Create compelling content about {topic}"
  backstory: "You're a skilled content creator..."
  tools: [WritingTool]
  llm: claude-sonnet-4-6
```

**Tasks YAML:**
```yaml
# config/tasks.yaml
research_task:
  description: "Research {topic} and identify key trends"
  expected_output: "Comprehensive research report with sources"
  agent: researcher

writing_task:
  description: "Write a blog post about {topic} based on research"
  expected_output: "Polished 1500-word blog post"
  agent: content_writer
  context: [research_task]  # depends on research completing first
```

**What NemoClaw can adopt:**
- Variable substitution pattern (`{topic}`) for skill parameterization
- `allow_delegation` flag maps to authority tiers
- Separate agents.yaml + tasks.yaml (vs NemoClaw's combined agent-schema.yaml)

---

### 1.2 LangGraph Supervisor — NemoClaw's Foundation

**URL:** https://github.com/langchain-ai/langgraph-supervisor-py

LangChain now recommends tool-calling delegation over the dedicated supervisor library. The pattern:

```python
# Supervisor as tool-caller (recommended approach)
supervisor = create_react_agent(
    model,
    tools=[research_agent_tool, content_agent_tool, quality_agent_tool],
    prompt="Route tasks to the right specialist agent."
)
```

**Key tutorials:**
- `langgraph/docs/docs/tutorials/multi_agent/agent_supervisor.md`
- `langgraph/docs/docs/tutorials/multi_agent/hierarchical_agent_teams/`

Hierarchical agent teams tutorial maps directly to NemoClaw's 4-tier authority model.

---

### 1.3 Microsoft AutoGen — 50,400 stars

**URL:** https://github.com/microsoft/autogen
**Status:** Merging into Microsoft Agent Framework with Semantic Kernel

Event-driven v0.4 architecture. In transition — not recommended for adoption but useful as reference for:
- `microsoft/spec-to-agents` — spec-driven agent workflows
- Event-driven architecture could inform MA-3 message protocol evolution

---

### 1.4 OpenAI Agents SDK — 20,500 stars

**URL:** https://github.com/openai/openai-agents-python
**Status:** v0.10.2, production-ready

**Key patterns to adopt:**

1. **Guardrails** (parallel validation + fail-fast):
```python
from agents import Agent, OutputGuardrail, GuardrailFunctionOutput

async def quality_check(ctx, agent, output) -> GuardrailFunctionOutput:
    score = evaluate_quality(output)
    return GuardrailFunctionOutput(
        output_info={"score": score},
        tripwire_triggered=(score < 7)  # fail-fast
    )

agent = Agent(
    name="content-engine",
    output_guardrails=[OutputGuardrail(guardrail_function=quality_check)]
)
```

2. **Tool guardrails** (pre/post validation on function calls):
```python
from agents import Agent, ToolGuardrail

async def cost_check(ctx, agent, tool_call) -> GuardrailFunctionOutput:
    estimated_cost = estimate_cost(tool_call)
    return GuardrailFunctionOutput(
        tripwire_triggered=(estimated_cost > 15.0)  # MA-5 L-142: approval >$15
    )
```

3. **ToolSearchTool** for deferred loading of 128 skills

**NemoClaw target:** MA-15 quality gate should adopt parallel validation + fail-fast pattern.

---

### 1.5 Google ADK — 17,800 stars

**URL:** https://github.com/google/adk-python
**Downloads:** 3.3M/month

**YAML sub-agent config:**
```yaml
# root_agent.yaml
agent_class: LlmAgent
model: gemini-2.5-flash
name: root_agent
description: Learning assistant
instruction: |
  Delegate coding questions to code_tutor_agent
  and math questions to math_tutor_agent.
sub_agents:
  - config_path: code_tutor_agent.yaml
  - config_path: math_tutor_agent.yaml
```

**What NemoClaw can adopt:**
- `config_path` sub-agent pattern is cleaner than flat `agent-schema.yaml`
- `agent_class` field to differentiate agent types
- Source: https://github.com/google/adk-python/blob/main/contributing/samples/multi_agent_basic_config/root_agent.yaml

---

### 1.6 Swarms — 6,200 stars

**URL:** https://github.com/kyegomez/swarms

8 orchestration patterns. Key feature: `create_agents_from_yaml()`:

```yaml
agents:
  - agent_name: "Researcher"
    system_prompt: "Research the provided topic"
    model_name: "gpt-5.4"
    max_loops: 3
    temperature: 0.7
    max_tokens: 4000
    task: "Research quantum computing"
```

```python
from swarms import create_agents_from_yaml
agents = create_agents_from_yaml("agents.yaml")
```

Validates NemoClaw's YAML-driven agent approach.

---

### 1.7 Pydantic AI — 16,000 stars

**URL:** https://github.com/pydantic/pydantic-ai

Type-safe agents with structured outputs via tool-calling + immediate Pydantic validation. Model-agnostic.

**What NemoClaw can adopt:** Structured output validation pattern could strengthen quality gates. More robust than current step_type system.

---

## 2. Agent Configuration Patterns

### 2.1 GitAgent — 2,500 stars (HIGHEST RELEVANCE)

**URL:** https://github.com/open-gitagent/gitagent
**License:** MIT

Framework-agnostic, git-native agent standard. The "Docker for AI agents."

**Directory structure:**
```
my-agent/
├── agent.yaml          # Manifest: name, version, model, compliance
├── SOUL.md             # Identity, personality, communication style
├── RULES.md            # Hard constraints and safety boundaries
├── DUTIES.md           # Segregation of duties (maker/checker/executor/auditor)
├── skills/             # Reusable capability modules
├── tools/              # MCP-compatible tool definitions
├── workflows/          # Multi-step procedures (YAML)
├── knowledge/          # Reference documents
├── memory/runtime/     # Live agent state
├── hooks/              # Lifecycle handlers
├── config/             # Environment overrides
├── compliance/         # Regulatory compliance artifacts
└── agents/             # Sub-agent definitions (recursive)
```

**agent.yaml with compliance:**
```yaml
spec_version: "0.1.0"
name: compliance-agent
version: 1.0.0
model:
  preferred: claude-opus-4-6
compliance:
  segregation_of_duties:
    roles:
      - id: maker
        permissions: [create, submit]
      - id: checker
        permissions: [review, approve, reject]
    conflicts: [[maker, checker]]
    enforcement: strict
```

**Export to multiple frameworks:**
```bash
gitagent export --format claude-code    # Claude Code format
gitagent export --format openai         # OpenAI Agents SDK
gitagent export --format crewai         # CrewAI
gitagent export --format langgraph      # LangGraph
```

**Validation:**
```bash
gitagent validate --compliance  # Catches role violations before deployment
```

**NemoClaw mapping:**

| GitAgent Concept | NemoClaw Equivalent | Improvement |
|-----------------|-------------------|-------------|
| agent.yaml | `agent-schema.yaml` | Per-agent file vs monolithic |
| SOUL.md | Agent persona in schema | Separate file for identity |
| RULES.md | MA-8 behavior rules | Separate file for constraints |
| DUTIES.md | Authority tiers (L-101) | Formal segregation of duties |
| compliance/ | MA-19 access control | Explicit compliance artifacts |
| Export format | None | Cross-framework portability |

**Recommendation:** Decompose `agent-schema.yaml` into GitAgent's file-per-concern pattern. Each of 11 agents gets its own directory.

---

## 3. Quality & Cost Control

### 3.1 LiteLLM — 22,000+ stars (GOLD STANDARD FOR ROUTING)

**URL:** https://github.com/BerriAI/litellm
**Key file:** https://github.com/BerriAI/litellm/blob/main/proxy_server_config.yaml

Unified proxy for 100+ LLM providers with cost tracking and budget enforcement.

**Budget config pattern:**
```yaml
model_list:
  - model_name: gpt-4o
    litellm_params:
      model: openai/gpt-4o
      api_key: os.environ/OPENAI_API_KEY
      max_budget: 10.00       # USD per model
      budget_duration: 1d     # 1s, 1m, 1h, 1d, 1mo
      rpm: 480                # rate limit
      timeout: 300
      num_retries: 3

router_settings:
  routing_strategy: usage-based-routing-v2
  redis_host: os.environ/REDIS_HOST
  enable_pre_call_checks: true
  allowed_fails: 3
  cooldown_time: 60          # seconds after failure

  provider_budget_config:
    openai:
      budget_limit: 100.00
      time_period: 1d
    anthropic:
      budget_limit: 100.00
      time_period: 1d
```

**Key files to study:**
- `proxy_server_config.yaml` — main routing + budget config
- `litellm/router.py` — routing logic with load balancing
- `litellm/budget_manager.py` — budget enforcement

**Patterns NemoClaw should adopt:**

| LiteLLM Pattern | NemoClaw Current | Improvement |
|----------------|-----------------|-------------|
| Per-model budget + duration | Per-provider only | Track Sonnet vs Opus separately |
| `usage-based-routing-v2` | Static alias mapping | Dynamic load-based routing |
| `cooldown_time` after failures | Circuit breaker (MA-6) | Already similar, validate alignment |
| `rpm` rate limiting | None | Add per-model rate limits |
| `os.environ/KEY` references | `config/.env` | Already similar |
| `allowed_fails: 3` | L-150: trips at 150% | LiteLLM's simpler fail counting |

---

### 3.2 DeepEval — 14,400 stars (STANDARD FOR QUALITY)

**URL:** https://github.com/confident-ai/deepeval

LLM evaluation with agentic metrics. Pytest-like interface.

**Agentic metrics:**

| Metric | Range | What It Measures |
|--------|-------|-----------------|
| Task Completion | 0-1 | Did the agent complete the assigned task? |
| Tool Correctness | 0-1 | Were the right tools called with right args? |
| Goal Accuracy | 0-1 | Does output align with stated goal? |
| Step Efficiency | 0-1 | Minimal steps to achieve result? |
| Plan Adherence | 0-1 | Did agent follow its plan? |
| Plan Quality | 0-1 | Was the plan well-structured? |

**Usage pattern:**
```python
from deepeval import evaluate
from deepeval.metrics import AgentGoalAccuracyMetric
from deepeval.test_case import LLMTestCase

metric = AgentGoalAccuracyMetric(threshold=0.7)
test_case = LLMTestCase(
    input="Analyze competitor pricing",
    actual_output=agent_output,
    expected_output="Comprehensive pricing comparison with recommendations"
)

evaluate([test_case], [metric])
# Returns: score=0.85, passed=True
```

**NemoClaw integration:**
- Replace custom 1-10 scoring in critic loops with DeepEval's 0-1 agentic metrics
- Native LangGraph integration exists
- Target: MA-15 quality gate, all critic steps

---

### 3.3 AgentOps — 3,500+ stars

**URL:** https://github.com/AgentOps-AI/agentops
**License:** MIT

2-line SDK integration for agent monitoring:

```python
import agentops
agentops.init(api_key="...")

# That's it. All LLM calls, tool uses, and agent runs are tracked.
# Dashboard at app.agentops.ai shows:
# - Cost per run
# - Token usage
# - Session replay
# - Error tracking
```

Integrates with: CrewAI, OpenAI Agents SDK, LangChain, Google ADK.

**NemoClaw impact:** Could replace manual `~/.nemoclaw/logs/provider-usage.jsonl` logging with visual dashboards and session replay.

---

### 3.4 Langfuse — 10,000+ stars

**URL:** https://github.com/langfuse/langfuse

Self-hostable LLM engineering platform:
- Tracing with OpenTelemetry
- LLM-as-judge evaluation
- Prompt versioning and management
- Cost tracking per trace
- Dataset management for evals

**NemoClaw note:** Already has Langfuse integration via `lib/routing.py` (v4 OpenTelemetry). Could extend to use prompt versioning for skill prompts.

---

### 3.5 Mem0 — 51,800 stars (LARGEST REPO REVIEWED)

**URL:** https://github.com/mem0ai/mem0

Hybrid memory layer with scoring:

```python
from mem0 import Memory

memory = Memory()

# Add memory with context
memory.add(
    messages=[{"role": "user", "content": "Client prefers conservative pricing"}],
    user_id="client_liaison",
    agent_id="amira"
)

# Search with relevance scoring
results = memory.search(
    query="What are the client's pricing preferences?",
    user_id="client_liaison",
    limit=3
)
# Returns: scored results with relevance, importance, recency
```

**Architecture:**
- **Vector DB** — semantic search
- **Key-Value Store** — fast lookups
- **Graph DB** — relationship tracking
- **Scoring layer** — relevance + importance + recency

**Performance:** 26% accuracy improvement over OpenAI Memory, 91% faster, 90% lower tokens.

**NemoClaw mapping:**

| Mem0 Layer | NemoClaw MA-2 Layer | Enhancement |
|-----------|-------------------|-------------|
| User memory | Episodic memory | Scoring layer adds relevance ranking |
| Session memory | Working memory | Automatic expiry |
| Agent memory | Shared workspace | Cross-agent knowledge |
| Graph DB | None | Relationship tracking between entities |

**Recommendation:** Integrate Mem0's scoring layer into MA-2 and MA-17 context window management. The relevance + importance + recency scoring would significantly improve context pruning decisions.

---

### 3.6 Anthropic Cookbooks

**URL:** https://github.com/anthropics/claude-cookbooks/tree/main/patterns/agents

Official patterns from Anthropic:

| File | Pattern | NemoClaw Mapping |
|------|---------|-----------------|
| `evaluator_optimizer.ipynb` | Evaluator-Optimizer (critic loop) | Critic step in skill-runner.py |
| `orchestrator_workers.ipynb` | Orchestrator-Subagents | ops-commander -> specialist delegation |
| `basic_workflows.ipynb` | Prompt Chaining, Routing, Parallelization | Step chains, routing-config.yaml |
| `prompts/research_lead_agent.md` | Research agent prompt template | research-lead system prompt |

These are the canonical reference for the models NemoClaw uses most.

---

## 4. Adoption Tiers

### Tier 1 — Adopt Immediately (High Impact, Low Effort)

| What | From | Target in NemoClaw | Effort |
|------|------|--------------------|--------|
| Agentic eval metrics (0-1 scoring) | DeepEval | MA-15 quality gate, critic loops | 1-2 days |
| 2-line monitoring SDK | AgentOps | Replace provider-usage.jsonl | 1 hour |
| evaluator_optimizer pattern | Anthropic Cookbooks | Validate/refine critic loop | 1 day |

### Tier 2 — Adopt with Planning (High Impact, Medium Effort)

| What | From | Target in NemoClaw | Effort |
|------|------|--------------------|--------|
| Per-model budget + cooldown | LiteLLM | routing-config.yaml + budget-config.yaml | 2-3 days |
| File-per-concern agents | GitAgent | Decompose agent-schema.yaml | 3-5 days |
| Memory scoring layer | Mem0 | MA-2 memory + MA-17 context window | 3-5 days |
| Parallel validation guardrails | OpenAI Agents SDK | MA-15 quality gate | 2-3 days |

### Tier 3 — Study for Patterns (Strategic Reference)

| What | From | Application |
|------|------|-------------|
| agents.yaml + tasks.yaml | CrewAI | Config format evolution |
| sub_agents with config_path | Google ADK | Agent composition |
| Tool-calling delegation | LangGraph Supervisor | Orchestration simplification |
| Prompt versioning | Langfuse | Skill prompt management |
| create_agents_from_yaml | Swarms | Dynamic agent instantiation |

---

## 5. Gaps Revealed

### Gap 1: No Observability Layer

**Current:** Manual `~/.nemoclaw/logs/provider-usage.jsonl` logging. Langfuse tracing exists but no visual dashboard.

**Solution:** AgentOps (2-line SDK) or extend Langfuse integration with self-hosted dashboard.

**Impact:** Cannot visually debug agent runs, replay sessions, or see cost breakdown per agent.

---

### Gap 2: Monolithic Agent Config

**Current:** Single `config/agents/agent-schema.yaml` with all 11 agents.

**Solution:** GitAgent's file-per-concern pattern:
```
config/agents/
├── ops-commander/
│   ├── agent.yaml      # Manifest
│   ├── SOUL.md         # Identity (Tariq, Homer Simpson)
│   ├── RULES.md        # Authority L1, override permissions
│   └── DUTIES.md       # Orchestrator, quality audit
├── research-lead/
│   ├── agent.yaml
│   ├── SOUL.md         # Nadia, Velma Dinkley
│   ├── RULES.md        # Authority L2, market domains
│   └── DUTIES.md       # Research, trend scanning
└── ... (9 more agents)
```

**Impact:** Easier to version-control individual agent changes, clearer ownership, compliance artifacts.

---

### Gap 3: No Per-Model Budgets

**Current:** `budget-config.yaml` tracks per-provider ($100 Anthropic, $100 OpenAI, $100 Google).

**Solution:** LiteLLM pattern — per-model budget with duration:
```yaml
models:
  claude-sonnet-4-6:
    max_budget: 60.00
    budget_duration: 1mo
  claude-opus-4-6:
    max_budget: 30.00
    budget_duration: 1mo
  # Opus capped lower to prevent cost spikes
```

**Impact:** Prevents one expensive model (Opus) from consuming entire provider budget.

---

### Gap 4: No Standard Evaluation Metrics

**Current:** Custom 1-10 scoring in critic loops. Non-standard.

**Solution:** DeepEval's agentic metrics (0-1 range):
- Task Completion, Tool Correctness, Goal Accuracy, Step Efficiency, Plan Adherence

**Impact:** Industry-standard scoring enables benchmarking against other systems.

---

### Gap 5: Memory Lacks Scoring

**Current:** MA-2 3-layer memory (working, episodic, shared workspace) without relevance scoring.

**Solution:** Mem0's scoring layer — relevance + importance + recency. Items below threshold auto-pruned.

**Impact:** Better context window utilization (MA-17). More relevant memories surfaced.

---

### Gap 6: No Agent Portability

**Current:** Agents locked to NemoClaw's LangGraph implementation.

**Solution:** GitAgent export format:
```bash
gitagent export --format claude-code    # For Claude Code
gitagent export --format openai         # For OpenAI Agents SDK
gitagent export --format langgraph      # For LangGraph (current)
```

**Impact:** Agents become portable across frameworks. Reduces vendor lock-in risk.

---

## 6. Specific Files to Study

| File | URL | Why |
|------|-----|-----|
| LiteLLM proxy config | https://github.com/BerriAI/litellm/blob/main/proxy_server_config.yaml | Gold standard budget/routing YAML |
| LiteLLM router | https://github.com/BerriAI/litellm/blob/main/litellm/router.py | Load balancing logic |
| LiteLLM budget manager | https://github.com/BerriAI/litellm/blob/main/litellm/budget_manager.py | Per-model budget enforcement |
| Google ADK multi-agent YAML | https://github.com/google/adk-python/blob/main/contributing/samples/multi_agent_basic_config/root_agent.yaml | Sub-agent config pattern |
| Anthropic evaluator-optimizer | https://github.com/anthropics/claude-cookbooks/tree/main/patterns/agents/evaluator_optimizer.ipynb | Critic loop reference |
| Anthropic orchestrator-workers | https://github.com/anthropics/claude-cookbooks/tree/main/patterns/agents/orchestrator_workers.ipynb | Agent delegation reference |
| GitAgent spec | https://github.com/open-gitagent/gitagent | File-per-concern agent standard |
| DeepEval agentic metrics | https://github.com/confident-ai/deepeval | 0-1 scoring for agents |
| Mem0 LangGraph integration | https://github.com/mem0ai/mem0 | Memory scoring layer |
| Swarms YAML agents | https://docs.swarms.world/en/latest/swarms/agents/create_agents_yaml/ | Dynamic YAML agent creation |
| CrewAI agents config | https://github.com/crewAIInc/crewAI | agents.yaml + tasks.yaml pattern |
| AgentOps SDK | https://github.com/AgentOps-AI/agentops | 2-line agent monitoring |
| Langfuse self-hosted | https://github.com/langfuse/langfuse | LLM engineering platform |

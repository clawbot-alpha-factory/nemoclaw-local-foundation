# Anthropic Claude Multi-Agent Setup Guide for NemoClaw

**Date:** 2026-04-03
**Status:** Research — no code changes applied
**Scope:** Maps Anthropic's agent ecosystem to NemoClaw's 11 agents / 128 skills

---

## 1. Claude Agent SDK

**Python SDK:** https://github.com/anthropics/claude-agent-sdk-python
**TypeScript SDK:** https://www.npmjs.com/package/@anthropic-ai/claude-agent-sdk
**Docs:** https://platform.claude.com/docs/en/agent-sdk/overview
**Demos:** https://github.com/anthropics/claude-agent-sdk-demos

### Subagent Spawning (Maps to NemoClaw's 11-Agent Hierarchy)

```python
from claude_agent_sdk import query, ClaudeAgentOptions, AgentDefinition

options = ClaudeAgentOptions(
    allowed_tools=["Read", "Glob", "Grep", "Bash", "Agent"],
    agents={
        "research-lead": AgentDefinition(
            description="Market research, competitive analysis, trend scanning",
            prompt="""<agent_identity>
  <name>research-lead</name>
  <persona>Nadia (Strategy Lead)</persona>
  <authority_level>2</authority_level>
</agent_identity>
<capabilities>
  <skills>k07-market-analyst, k08-trend-scanner, k09-competitive-intel-agent</skills>
  <max_tier>4</max_tier>
</capabilities>
<instructions>
  Conduct thorough market research using available tools.
  Always cite sources. Score confidence 1-10.
</instructions>"""
        ),
        "quality-sentinel": AgentDefinition(
            description="Quality assurance, validation, critic loops",
            prompt="""<agent_identity>
  <name>quality-sentinel</name>
  <authority_level>2</authority_level>
</agent_identity>
<behavior_rules>
  <rule priority="critical">Never approve output with score below 7/10</rule>
  <rule priority="high">Run critic loop: evaluate -> score -> improve -> re-evaluate</rule>
</behavior_rules>"""
        ),
        # ... 9 more agent definitions
    }
)

# Parent agent (ops-commander) spawns subagents
async for message in query(
    prompt="Analyze competitor pricing and produce a strategy report",
    options=options
):
    print(message)
```

**Critical rules:**
- `Agent` must be in `allowedTools` or subagents never spawn
- Subagents cannot spawn their own subagents (no recursion)
- Parent-to-subagent channel is the prompt string only
- Subagent context starts fresh each time

### Session Resume (Persistent Agents)

```python
from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage

async def run_agent():
    session_id = None
    async for message in query(
        prompt="Analyze the auth module",
        options=ClaudeAgentOptions(allowed_tools=["Read", "Glob", "Grep"]),
    ):
        if isinstance(message, ResultMessage):
            session_id = message.session_id
    return session_id  # Store for later resume

# Resume later with session_id
async for message in query(
    prompt="Now fix the issues you found",
    options=ClaudeAgentOptions(session_id=saved_session_id),
):
    print(message)
```

Sessions stored as `.jsonl` under `~/.claude/projects/`.

### Hosting Patterns

| Pattern | Best For | NemoClaw Agent |
|---------|----------|---------------|
| Long-running container | Proactive monitoring | ops-commander, quality-sentinel |
| Ephemeral with state recovery | On-demand tasks | content-engine, research-lead |
| Subagent pool (parallel) | Fan-out execution | All skill runners |

---

## 2. Model Selection & Pricing (April 2026)

**Source:** https://platform.claude.com/docs/en/about-claude/pricing

### Current Pricing (per 1M tokens)

| Model | Input | Output | Batch (50% off) | Best For |
|-------|-------|--------|-----------------|----------|
| **Haiku 4.5** | $1.00 | $5.00 | $0.50/$2.50 | Classification, routing, simple scoring |
| **Sonnet 4.6** | $3.00 | $15.00 | $1.50/$7.50 | Default workhorse, coding, analysis |
| **Opus 4.6** | $5.00 | $25.00 | $2.50/$12.50 | Deep reasoning, architecture, review |

**Key insight:** Opus is now only 1.67x Sonnet (was 5x in older generations). Long-context surcharge: 2x for requests >200K input tokens.

### NemoClaw Routing Recommendations

Map to `config/routing/routing-config.yaml`:

| NemoClaw Alias | Current | Recommended | Rationale |
|----------------|---------|-------------|-----------|
| `general_short` | claude-sonnet-4-6 | claude-sonnet-4-6 | Already optimal |
| `moderate` | claude-sonnet-4-6 | claude-sonnet-4-6 | Primary workhorse — keep |
| `complex_reasoning` | claude-sonnet-4-6 | claude-sonnet-4-6 | Best price/performance |
| `code` | claude-sonnet-4-6 | claude-sonnet-4-6 | #1 coding model |
| `premium` | claude-opus-4-6 | claude-opus-4-6 | Deep reasoning |
| `strategic` | claude-opus-4-6 | claude-opus-4-6 | High-stakes decisions |
| Critic scoring | — | **haiku-4.5** | Simple numeric scoring, 5x cheaper |
| Routing/classification | — | **haiku-4.5** | Fast, cheap, sufficient |

### Cost Projection

| Scenario | Est. Cost per Full Run |
|----------|----------------------|
| All 128 skills on Sonnet | ~$5.58 |
| Mixed (Haiku for routing/critics) | ~$2.80 |
| With prompt caching (90% savings) | ~$1.40 |
| With batch API (50% off) | ~$0.70 |

---

## 3. Adaptive Thinking (Replaces budget_tokens)

**Docs:** https://platform.claude.com/docs/en/build-with-claude/adaptive-thinking

On Opus 4.6 / Sonnet 4.6, `budget_tokens` is deprecated. Use adaptive thinking:

```python
import anthropic

client = anthropic.Anthropic()

# NEW: Adaptive thinking with effort parameter
response = client.messages.create(
    model="claude-sonnet-4-6-20260401",
    max_tokens=16000,
    thinking={"type": "adaptive"},
    effort="high",  # low, medium, high, max
    messages=[{"role": "user", "content": "Design the API surface for a payment gateway"}]
)
```

### Per-Agent Effort Mapping

| NemoClaw Agent | Effort | Rationale |
|----------------|--------|-----------|
| Product Architect (Layla) | `max` | Deep architectural reasoning |
| Quality Sentinel | `high` | Thorough quality evaluation |
| Research Lead (Nadia) | `high` | Multi-source synthesis |
| Compliance Officer | `high` | Regulatory analysis |
| Data Analyst | `high` | Complex analysis |
| Content Engine (Yasmin) | `medium` | Standard generation |
| Market Intel | `medium` | Research + synthesis |
| Creative Director | `medium` | Creative generation |
| Ops Commander (Tariq) | `medium` | Monitoring decisions |
| Engineering Lead (Faisal) | `low` | Scripting, straightforward |
| Client Liaison (Amira) | `low` | Conversational, fast |

**Key finding from Anthropic docs:** Extended thinking can HURT performance by up to 36% on simple tasks. Don't use it everywhere.

**Source:** https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/extended-thinking-tips

---

## 4. Prompt Caching (Critical for Cost Control)

**Docs:** https://platform.claude.com/docs/en/build-with-claude/prompt-caching

Cache reads cost **10% of standard input price**. For NemoClaw:

| What to Cache | Size Estimate | Savings |
|--------------|---------------|---------|
| 11 agent system prompts | ~5K tokens each = 55K total | 90% on every call |
| 128 skill tool definitions | ~200 tokens each = 25K total | 90% on every call |
| Routing config context | ~3K tokens | 90% on every call |
| Behavior rules (MA-8) | ~2K tokens | 90% on every call |

**Estimated savings: $21+/day for heavy usage (1000 skill runs/day)**

Cache write costs:
- 5-minute TTL: 1.25x standard input
- 1-hour TTL: 2x standard input
- Pays for itself after 1-2 cache reads

### Implementation Pattern

```python
import anthropic

client = anthropic.Anthropic()

# Cache the system prompt + tool definitions
response = client.messages.create(
    model="claude-sonnet-4-6-20260401",
    max_tokens=4096,
    system=[
        {
            "type": "text",
            "text": "<agent_identity>...</agent_identity><capabilities>...</capabilities>",
            "cache_control": {"type": "ephemeral"}  # 5-min TTL
        }
    ],
    tools=[
        {
            "name": "execute_skill",
            "description": "Execute a NemoClaw skill",
            "input_schema": {"type": "object", "properties": {"skill_id": {"type": "string"}}},
            "cache_control": {"type": "ephemeral"}
        }
    ],
    messages=[{"role": "user", "content": "Run market analysis"}]
)
```

---

## 5. XML Tag System Prompt Templates

**Docs:** https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/use-xml-tags

Claude is specifically trained on XML delimiters. This is a core differentiator from OpenAI.

### Agent System Prompt Template

```xml
<agent_identity>
  <name>quality-sentinel</name>
  <persona>Quality assurance specialist</persona>
  <authority_level>2</authority_level>
  <domains>quality, testing, validation</domains>
</agent_identity>

<capabilities>
  <skills>k01-quality-audit, k02-test-runner, k03-regression-check</skills>
  <tools>Read, Grep, Glob, Bash, Agent</tools>
  <memory_access>working, episodic, shared_workspace</memory_access>
  <max_routing_tier>3</max_routing_tier>
</capabilities>

<behavior_rules>
  <rule priority="critical">Never approve output with quality score below 7/10</rule>
  <rule priority="high">Always run critic loop before approval</rule>
  <rule priority="standard">Log all decisions with rationale</rule>
  <rule priority="standard">Escalate after 3 warnings (MA-8 graduated enforcement)</rule>
</behavior_rules>

<output_format>
  <type>structured_json</type>
  <schema>
    {"quality_score": "number 1-10", "pass": "boolean", "issues": ["string"], "recommendation": "string"}
  </schema>
</output_format>

<context>
  {{dynamic_context_from_langgraph_state}}
</context>

<instructions>
  You are the quality-sentinel agent in the NemoClaw system.
  Evaluate outputs against quality standards using the critic loop:
  1. Evaluate output → 2. Score (1-10) → 3. If score < 10, improve → 4. Re-evaluate
  Maximum 3 revision cycles (L-242), then escalate.
</instructions>
```

### XML Best Practices
1. Be consistent — use same tag names, reference them in instructions
2. Nest hierarchically — `<outer><inner></inner></outer>`
3. Separate concerns — `<instructions>`, `<context>`, `<output_format>`, `<examples>`
4. Reduces hallucination in 100K+ context when sections are XML-tagged

---

## 6. Tool Use Configuration

**Docs:** https://platform.claude.com/docs/en/agents-and-tools/tool-use/implement-tool-use

### Claude Tool Definition Format

```python
tools = [
    {
        "name": "execute_skill",
        "description": "Execute a NemoClaw skill by ID. Returns JSON envelope with output.",
        "input_schema": {
            "type": "object",
            "properties": {
                "skill_id": {
                    "type": "string",
                    "description": "Skill identifier (e.g., 'a01-arch-spec-writer')"
                },
                "input_data": {
                    "type": "object",
                    "description": "Key-value input parameters"
                }
            },
            "required": ["skill_id"]
        }
    },
    {
        "name": "get_agent_status",
        "description": "Check current status and metrics for a NemoClaw agent.",
        "input_schema": {
            "type": "object",
            "properties": {
                "agent_id": {"type": "string", "description": "Agent identifier"}
            },
            "required": ["agent_id"]
        }
    }
]
```

### Key Differences from OpenAI

| Feature | Claude | OpenAI |
|---------|--------|--------|
| Schema field | `input_schema` | `parameters` (inside `function`) |
| Wrapper | Flat `tools[]` array | `tools[].function` wrapper |
| Strict mode | `strict: true` on tool def | `strict: true` on function |
| Tool result | `tool_result` with `tool_use_id` | `tool` role with `tool_call_id` |
| Tool search | Tool Search Tool (1000s of tools) | Not available |

### Strict Tool Use (for Compliance/Quality Agents)

```python
tools = [{
    "name": "quality_report",
    "description": "Submit a quality evaluation report",
    "strict": True,  # Grammar-constrained sampling guarantees schema compliance
    "input_schema": {
        "type": "object",
        "properties": {
            "score": {"type": "number", "minimum": 1, "maximum": 10},
            "pass": {"type": "boolean"},
            "issues": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["score", "pass", "issues"]
    }
}]
```

**Source:** https://platform.claude.com/docs/en/agents-and-tools/tool-use/strict-tool-use

### Tool Search Tool (for 128 Skills)

With 128 skills, don't load all tool definitions into context. Let Claude search:

```python
# Claude's Tool Search Tool searches through thousands of tools
# without consuming context window — critical for NemoClaw's scale
tools = [
    {"type": "tool_search", "max_results": 5},
    # ... only the most common tools loaded directly
]
```

**Source:** https://www.anthropic.com/engineering/advanced-tool-use

---

## 7. MCP Servers for NemoClaw

**MCP Spec:** https://modelcontextprotocol.io/
**FastMCP:** https://github.com/jlowin/fastmcp

Expose NemoClaw capabilities as MCP servers. Any MCP client (Claude Desktop, Claude Code, VS Code) can connect.

### Server Definitions

```python
from fastmcp import FastMCP

# Server 1: Skill Execution
skills_server = FastMCP(name="NemoClaw Skills")

@skills_server.tool
def execute_skill(skill_id: str, inputs: dict = {}) -> dict:
    """Execute a NemoClaw skill and return its output envelope."""
    return run_skill(skill_id, inputs)

@skills_server.tool
def list_skills(domain: str = None) -> list:
    """List available skills, optionally filtered by domain."""
    return get_skills(domain)

@skills_server.resource("nemoclaw://skills/{skill_id}")
def get_skill_config(skill_id: str) -> str:
    """Read the skill.yaml configuration."""
    return open(f"skills/{skill_id}/skill.yaml").read()


# Server 2: Agent Management
agents_server = FastMCP(name="NemoClaw Agents")

@agents_server.tool
def get_agent_status(agent_id: str) -> dict:
    """Get current status and metrics for an agent."""
    return {"agent_id": agent_id, "status": "active", "tasks_completed": 42}

@agents_server.tool
def assign_task(agent_id: str, task: str, priority: str = "medium") -> dict:
    """Assign a task to a specific agent."""
    return {"assigned": True, "agent_id": agent_id, "task_id": "..."}


# Server 3: Budget/Cost Governance
budget_server = FastMCP(name="NemoClaw Budget")

@budget_server.tool
def check_budget(provider: str) -> dict:
    """Check remaining budget for a provider."""
    return {"provider": provider, "remaining": 85.50, "limit": 100.0}

@budget_server.tool
def circuit_breaker_status() -> dict:
    """Get circuit breaker state for all providers."""
    return {"anthropic": "CLOSED", "openai": "CLOSED", "google": "CLOSED"}
```

| MCP Server | Purpose | Exposed Tools |
|-----------|---------|---------------|
| `nemoclaw-skills` | Skill execution | execute_skill, list_skills, get_skill_output |
| `nemoclaw-agents` | Agent management | get_agent_status, assign_task, get_metrics |
| `nemoclaw-memory` | Shared workspace | read_workspace, write_workspace, search_memory |
| `nemoclaw-budget` | Cost governance | check_budget, get_costs, circuit_breaker_status |
| `nemoclaw-browser` | PinchTab bridge | navigate, click, extract_text, screenshot |

---

## 8. Cost Optimization Stack

Cumulative savings when combined:

| Strategy | Savings | NemoClaw Application |
|----------|---------|---------------------|
| Model tiering (Haiku/Sonnet/Opus) | 40-60% | Already via 9-alias routing |
| Prompt caching (system + tools) | 90% on cached | Cache 11 prompts + 128 schemas |
| Batch API (non-urgent) | 50% | Batch skill runs, report generation |
| Adaptive thinking (effort param) | Variable | Low for routing, high for arch |
| Tool Search (don't load all 128) | Context savings | Dynamic tool discovery |
| Subagent isolation (fresh context) | Quality gain | Prevents context pollution |

### Monthly Cost Estimate

| Usage Level | Without Optimization | With Full Optimization |
|------------|---------------------|----------------------|
| Light (100 runs/day) | ~$15-30/day | ~$3-6/day |
| Heavy (1000 runs/day) | ~$150-300/day | ~$30-60/day |
| Monthly (heavy) | ~$4,500-9,000 | ~$900-1,800 |

---

## 9. Recommendations for NemoClaw

### Immediate (No Architecture Changes)

1. **Implement prompt caching** — Cache 11 agent system prompts + 128 skill tool schemas. 90% savings on every call. Target: `lib/routing.py`
2. **Switch to adaptive thinking** — Replace any `budget_tokens` with `thinking.type: "adaptive"` + `effort`. Target: `lib/routing.py`
3. **Add Tool Search** — Don't load all 128 tool definitions. Let Claude search dynamically. Target: `lib/routing.py`
4. **Use strict tool use** — For compliance-officer and quality-sentinel. Target: tool definitions in skill configs
5. **Add Haiku for critics** — Simple scoring at 5x cheaper than Sonnet. Target: `routing-config.yaml`

### Medium-Term (Architecture Enhancements)

6. **Build MCP servers** — Expose skills, agents, memory as MCP. Makes NemoClaw accessible from Claude Desktop/VS Code
7. **Adopt Agent SDK for orchestration** — Replace custom orchestration with subagent pattern where appropriate. Keep LangGraph for skill execution (L-002)
8. **Implement Batch API** — 50% cheaper for bulk runs (regression testing all 128 skills)

### Long-Term (Strategic)

9. **Agent Teams integration** — Evaluate Claude's built-in Agent Teams when stable
10. **MCP ecosystem play** — Publish NemoClaw MCP servers to community registry

---

## 10. Key URLs Reference

### Official Anthropic
| Resource | URL |
|----------|-----|
| Agent SDK Overview | https://platform.claude.com/docs/en/agent-sdk/overview |
| Agent SDK Python | https://github.com/anthropics/claude-agent-sdk-python |
| Subagents | https://platform.claude.com/docs/en/agent-sdk/subagents |
| Sessions | https://platform.claude.com/docs/en/agent-sdk/sessions |
| Hosting | https://platform.claude.com/docs/en/agent-sdk/hosting |
| Tool Use | https://platform.claude.com/docs/en/agents-and-tools/tool-use/overview |
| Implement Tool Use | https://platform.claude.com/docs/en/agents-and-tools/tool-use/implement-tool-use |
| Strict Tool Use | https://platform.claude.com/docs/en/agents-and-tools/tool-use/strict-tool-use |
| Bash Tool | https://platform.claude.com/docs/en/agents-and-tools/tool-use/bash-tool |
| Computer Use | https://platform.claude.com/docs/en/agents-and-tools/tool-use/computer-use-tool |
| Memory Tool | https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool |
| Adaptive Thinking | https://platform.claude.com/docs/en/build-with-claude/adaptive-thinking |
| Extended Thinking | https://platform.claude.com/docs/en/build-with-claude/extended-thinking |
| Effort | https://platform.claude.com/docs/en/build-with-claude/effort |
| XML Tags | https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/use-xml-tags |
| Prompt Caching | https://platform.claude.com/docs/en/build-with-claude/prompt-caching |
| Pricing | https://platform.claude.com/docs/en/about-claude/pricing |
| Structured Outputs | https://platform.claude.com/docs/en/build-with-claude/structured-outputs |

### MCP
| Resource | URL |
|----------|-----|
| MCP Spec | https://modelcontextprotocol.io/ |
| MCP Python SDK | https://github.com/modelcontextprotocol/python-sdk |
| FastMCP | https://github.com/jlowin/fastmcp |
| MCP Introduction | https://www.anthropic.com/news/model-context-protocol |

### Multi-Agent Repos
| Resource | URL |
|----------|-----|
| Agent SDK Demos | https://github.com/anthropics/claude-agent-sdk-demos |
| Anthropic Cookbooks | https://github.com/anthropics/claude-cookbooks/tree/main/patterns/agents |
| Advanced Tool Use | https://www.anthropic.com/engineering/advanced-tool-use |
| Building Agents Blog | https://www.anthropic.com/engineering/building-agents-with-the-claude-agent-sdk |
| When to Use Multi-Agent | https://claude.com/blog/building-multi-agent-systems-when-and-how-to-use-them |

# Google Gemini Multi-Agent Setup Guide for NemoClaw

**Date:** 2026-04-03
**Status:** Research — no code changes applied
**Scope:** Maps Google's Gemini/Vertex AI agent ecosystem to NemoClaw's 11 agents / 128 skills

---

## 1. Google ADK (Agent Development Kit)

**Docs:** https://google.github.io/adk-docs/
**Python SDK:** https://github.com/google/adk-python (17.8K stars)
**PyPI:** https://pypi.org/project/google-adk/
**Multi-agent patterns:** https://developers.googleblog.com/developers-guide-to-multi-agent-patterns-in-adk/

### Agent Types (Map to NemoClaw)

| ADK Agent Type | Purpose | NemoClaw Equivalent |
|----------------|---------|-------------------|
| **LlmAgent** | Core reasoning with tools + sub_agents | All 11 agents |
| **SequentialAgent** | Fixed-order pipeline | Skill step chains (generate->critic->improve) |
| **ParallelAgent** | Concurrent independent tasks | MA-5 parallel wave execution (5 concurrent cap) |
| **LoopAgent** | Iterative with exit condition | Critic loop (score < 10.0 -> improve -> re-eval) |
| **Custom Agent** (BaseAgent) | Full control | Custom StateGraph nodes |

### Multi-Agent Coordinator Pattern

```python
from google.adk.agents import LlmAgent
from google.adk.agents.sequential_agent import SequentialAgent
from google.adk.agents.parallel_agent import ParallelAgent
from google.adk.agents.loop_agent import LoopAgent

# Specialist agents (NemoClaw's 11 agents)
research_lead = LlmAgent(
    name="research_lead",
    model="gemini-2.5-pro",
    instruction="You are Nadia (Strategy Lead). Authority Level 2. "
                "Domains: market_intelligence, competitive_analysis.",
    tools=[web_search_tool, document_tool],
    output_key="research_output"
)

content_engine = LlmAgent(
    name="content_engine",
    model="gemini-2.5-flash",  # Flash for high-volume content
    instruction="You are Yasmin (Narrative & Content Lead). Authority Level 3. "
                "Domains: creative_writing, content, research.",
    tools=[writing_tool],
    output_key="content_output"
)

# Critic loop (NemoClaw's generate->critic->improve pattern)
quality_loop = LoopAgent(
    name="quality_loop",
    max_iterations=3,  # L-242: max 3 revisions then escalate
    sub_agents=[
        LlmAgent(name="evaluator", model="gemini-2.5-pro",
                 instruction="Score the output 1-10. Output JSON: {score, issues}"),
        LlmAgent(name="improver", model="gemini-2.5-flash",
                 instruction="Fix the issues identified. Produce improved output."),
    ]
)

# Parallel research + content generation
parallel_work = ParallelAgent(
    name="parallel_work",
    sub_agents=[research_lead, content_engine]
)

# Coordinator (NemoClaw's ops-commander)
coordinator = LlmAgent(
    name="ops_commander",
    model="gemini-2.5-pro",
    description="Routes tasks to specialist agents",
    sub_agents=[research_lead, content_engine, quality_loop, parallel_work]
)
```

### YAML Agent Configuration

ADK supports YAML config (like NemoClaw's `agent-schema.yaml`):

```yaml
# root_agent.yaml
agent_class: LlmAgent
model: gemini-2.5-pro
name: ops_commander
description: Executive Operator - routes tasks to specialist agents
instruction: |
  You are Tariq (Executive Operator). Authority Level 1.
  Route tasks to the right specialist. Override any agent blocking critical path.
sub_agents:
  - config_path: agents/research_lead.yaml
  - config_path: agents/content_engine.yaml
  - config_path: agents/quality_sentinel.yaml
  - config_path: agents/engineering_lead.yaml
  # ... all 10 specialist agents
```

**Source:** https://github.com/google/adk-python/blob/main/contributing/samples/multi_agent_basic_config/root_agent.yaml

### ADK vs LangGraph

| Dimension | LangGraph (NemoClaw current) | Google ADK |
|-----------|---------------------------|------------|
| Orchestration | Explicit state machine graphs | Event-driven workflows |
| Multi-agent | Manual via StateGraph nodes | Built-in LlmAgent hierarchy |
| State | SqliteSaver checkpointing | Session state + Memory Bank |
| Deployment | Self-hosted | Vertex AI Agent Engine or Cloud Run |
| Dev tools | Custom scripts | Built-in Dev UI, API server, CLI |
| Testing | Custom harness | Built-in evaluation framework |
| Model-agnostic | Via LangChain | Via LiteLLM (100+ providers) |

**Verdict:** Keep LangGraph core (L-002 lock). ADK is complementary — its SequentialAgent/ParallelAgent/LoopAgent patterns are useful reference, and its model-agnostic design via LiteLLM means it could coexist with NemoClaw's 9-alias routing.

---

## 2. Gemini Model Selection & Pricing

**Source:** https://ai.google.dev/gemini-api/docs/pricing

### Pricing Comparison

| Model | Input/1M | Output/1M | Speed | Context |
|-------|----------|-----------|-------|---------|
| **Gemini 2.5 Flash** | $0.30 | $2.50 | ~201 tok/s | 1M tokens |
| **Gemini 2.5 Pro** | $1.25 | $10.00 | ~148 tok/s | 1M tokens |
| **Flash vs Pro** | 4.2x cheaper | 4x cheaper | 1.4x faster | Same |

### When to Use Each

| Use Case | Model | Rationale |
|----------|-------|-----------|
| Content generation, summarization | **Flash** | 4x cheaper, similar quality |
| Chat, RAG, classification | **Flash** | Volume-sensitive workloads |
| Complex reasoning, debugging | **Pro** | Higher accuracy matters |
| Agentic orchestration (coordinator) | **Pro** | Best reasoning for routing |
| Bulk skill execution (128 skills) | **Flash** | Cost adds up at scale |
| Vision/multimodal | **Flash** | Cheapest multimodal option |

### NemoClaw Routing Recommendations

Map to `config/routing/routing-config.yaml`:

| NemoClaw Alias | Current Google Model | Recommended | Rationale |
|----------------|---------------------|-------------|-----------|
| `vision` | gemini-2.5-flash | gemini-2.5-flash | Already optimal |
| `long_document` | gemini-2.5-pro | gemini-2.5-pro | 1M context needed |
| Bulk skills | — | **gemini-2.5-flash** | 4x cheaper than Pro |
| Critic/review | — | **gemini-2.5-pro** | Reasoning quality needed |

### Cost Projection: Adding Gemini to NemoClaw

| Component | Monthly Estimate |
|-----------|-----------------|
| Flash for bulk skills (80% of 128) | ~$5-15/mo |
| Pro for coordinator + critic | ~$10-20/mo |
| Google Search grounding (1K queries/day) | ~$1.50/mo |
| Context caching savings | -30% on above |
| **Total Gemini addition** | **~$12-25/mo** |

Fits within NemoClaw's $100/provider budget (L-005).

---

## 3. Context Caching (Major Cost Saver)

**Docs:** https://ai.google.dev/gemini-api/docs/caching

### Two Mechanisms

| Type | How It Works | Savings | Code Changes |
|------|-------------|---------|--------------|
| **Implicit** | Auto-enabled on Gemini 2.5+ | Up to 75% on cache hits | None |
| **Explicit** | Manual cache creation | Up to 90% | Must create cache |

### Explicit Caching for NemoClaw

```python
import google.generativeai as genai

# Cache NemoClaw's 128 skill definitions + agent configs
cache = genai.caching.CachedContent.create(
    model="gemini-2.5-flash",
    display_name="nemoclaw-skills-config",
    contents=[
        # All 128 skill.yaml files concatenated
        {"role": "user", "parts": [skill_definitions_text]},
        # Agent schema
        {"role": "user", "parts": [agent_schema_text]},
        # Routing config
        {"role": "user", "parts": [routing_config_text]},
    ],
    ttl="3600s"  # 1 hour
)

# Use cached content in subsequent calls
model = genai.GenerativeModel.from_cached_content(cache)
response = model.generate_content("Execute skill k07-market-analyst with input...")
```

**Pricing:** Cached tokens at $0.125-$0.25/1M vs $1.25-$2.50/1M standard. 90% savings.

**Source:** https://dev.to/rawheel/lowering-your-gemini-api-bill-a-guide-to-context-caching-aag

---

## 4. A2A Protocol (Agent-to-Agent)

**Spec:** https://a2a-protocol.org/latest/specification/
**GitHub:** https://github.com/a2aproject/A2A (17K+ stars)
**Announcement:** https://developers.googleblog.com/en/a2a-a-new-era-of-agent-interoperability/

### What It Is
Emerging industry standard for agent interop. 50+ partners (Atlassian, Salesforce, SAP, ServiceNow, LangChain, MongoDB, PayPal). Now under Linux Foundation governance.

### Protocol Architecture

| Layer | Purpose | Format |
|-------|---------|--------|
| Layer 1 | Canonical data model | Protocol Buffers |
| Layer 2 | Abstract operations | Framework-agnostic behaviors |
| Layer 3 | Protocol bindings | JSON-RPC 2.0 over HTTPS, gRPC |

### Agent Card (Published at `/.well-known/agent-card.json`)

```json
{
  "name": "research-lead",
  "description": "Conducts market research and competitive analysis",
  "capabilities": ["web_search", "document_analysis", "report_generation"],
  "endpoint": "https://agents.nemoclaw.com/research-lead",
  "authentication": {
    "schemes": ["oauth2", "apiKey"]
  },
  "skills": [
    {"name": "k07-market-analyst", "description": "Deep market analysis"},
    {"name": "k08-trend-scanner", "description": "Emerging trend detection"},
    {"name": "k09-competitive-intel-agent", "description": "Competitor tracking"}
  ]
}
```

### NemoClaw Mapping

| A2A Concept | NemoClaw Equivalent | File |
|------------|-------------------|------|
| Agent Card | Agent definition | `agent-schema.yaml` |
| Task lifecycle | Skill execution | `skill-runner.py` |
| Task status streaming | Step progress | StateGraph state |
| Authentication | Access control | MA-19 (L-280 through L-283) |
| Agent discovery | Capability registry | `capability-registry.yaml` |

**Why adopt:** External agents (Salesforce, ServiceNow) could call NemoClaw agents. NemoClaw agents could call external agents. Replaces MA-3's internal protocol with a standard one.

**Codelab:** https://codelabs.developers.google.com/intro-a2a-purchasing-concierge

---

## 5. 1M Token Context Window

**Docs:** https://ai.google.dev/gemini-api/docs/long-context

### Capabilities
- **Gemini 2.5 Pro/Flash:** 1M token context
- **Capacity:** ~1,500 pages of text, 50,000 lines of code

### Impact on NemoClaw

| NemoClaw Subsystem | Current Constraint | With 1M Context |
|-------------------|-------------------|-----------------|
| MA-17 Context Window Management | Pool budgets: 80K-200K tokens | Overflow handling eliminated |
| MA-2 3-Layer Memory | External state management | Working memory fits in context |
| Skill definitions | Loaded per-agent | All 128 skills in context |
| Agent configs | Loaded per-call | Full agent-schema.yaml in context |

### Thought Signatures (Critical for Agents)

For Gemini 3+ models, multi-turn function calling requires "thought signatures" — encrypted representations of internal reasoning. **You MUST return these in subsequent requests** to maintain reasoning continuity.

```python
# Gemini 3+ function calling with thought signatures
response = model.generate_content(messages)

# Extract thought signature from response
thought_sig = response.candidates[0].thought_signature

# Include in next turn
next_messages = messages + [response_message]
# thought_sig automatically included when using SDK
next_response = model.generate_content(next_messages)
```

Without thought signatures, context degrades in extended conversations.

---

## 6. Google Search Grounding

**Docs:** https://docs.cloud.google.com/vertex-ai/generative-ai/docs/grounding/grounding-with-google-search
**ADK integration:** https://google.github.io/adk-docs/grounding/vertex_ai_search_grounding/

### How It Works
- Agent calls trigger Google Search automatically when current information needed
- Returns cited, grounded responses with source attribution
- Configurable threshold: set prediction score for when grounding kicks in (saves costs)
- Limit: 1M queries/day

### NemoClaw Agent Mapping

| Agent | Grounding Use Case |
|-------|--------------------|
| **Market Intel** | Real-time competitive pricing, market data |
| **Research Lead** | Current industry trends, news |
| **Compliance Officer** | Current regulations, legal updates |
| **Sales Outreach** | Prospect company information |

### Enterprise Search (Vertex AI Search)
- Index your own documents (company policies, technical docs)
- $1.50-$4.00 per 1,000 queries
- Could index NemoClaw's skill outputs for cross-referencing

---

## 7. Multimodal Capabilities

**Gemini multimodal:** https://www.datastudios.org/post/google-gemini-multimodal-input-in-2025-vision-audio-and-video-capabilities-explained
**Live API:** https://docs.cloud.google.com/vertex-ai/generative-ai/docs/live-api

### Capabilities

| Modality | Capability | NemoClaw Agent |
|----------|-----------|---------------|
| **Vision** | Image analysis, document understanding, screenshots | Creative Director, Quality Sentinel |
| **Audio** | Real-time speech processing, call analysis | Client Liaison |
| **Video** | Video understanding, multi-hour analysis | Content Engine |
| **Live API** | Low-latency real-time voice+video | Client Liaison (real-time interactions) |

### Live API Pattern

```python
from google.genai import Client

client = Client()

# Real-time voice interaction for client-liaison agent
async with client.aio.live.connect(
    model="gemini-3.1-flash-live",
    config={"tools": [{"google_search": {}}]}
) as session:
    # Stream audio/video in real-time
    async for response in session.receive():
        print(response.text)
```

Both Gemini 2.5 Pro and Flash support native audio output.

---

## 8. Vertex AI Agent Engine

**Overview:** https://docs.cloud.google.com/agent-builder/agent-engine/overview
**Deploy:** https://google.github.io/adk-docs/deploy/agent-engine/
**Quickstart:** https://docs.cloud.google.com/agent-builder/agent-engine/quickstart-adk

### What It Provides
- Fully-managed runtime with auto-scaling
- Persistent sessions + Memory Bank
- Sandboxed code execution
- Built-in evaluation framework
- Native A2A support
- Monitoring and tracing

### Pricing

| Service | Cost |
|---------|------|
| Runtime (vCPU) | $0.00994/vCPU-hour |
| Runtime (Memory) | $0.0090/GB-hour |
| Code Execution | $0.0864/vCPU-hour |
| Sessions/Memories | $0.25 per 1,000 events |
| Search (Standard) | $1.50 per 1,000 queries |

### Deployment

```bash
adk deploy  # Single command to Vertex AI Agent Engine
```

**NemoClaw assessment:** Agent Engine could host all 11 agents with managed scaling. But at NemoClaw's current $200/mo budget, self-hosted FastAPI + SqliteSaver remains more cost-effective. Consider when scaling beyond local.

---

## 9. Google vs OpenAI vs Anthropic Agent Ecosystems

| Dimension | Google | OpenAI | Anthropic |
|-----------|--------|--------|-----------|
| Agent framework | ADK (open-source, multi-lang) | Agents SDK | Claude Agent SDK |
| Protocol | A2A (50+ partners, Linux Foundation) | None (proprietary) | MCP (tool integration) |
| Deployment | Vertex AI Agent Engine (managed) | OpenAI platform | Self-hosted / API |
| Grounding | Google Search + Vertex AI Search | Web browsing | Web search tool |
| Multimodal | Vision+audio+video+Live API | Vision+audio | Vision only |
| Context window | 1M-2M tokens | 200K tokens | 200K-1M (Opus 4.6) |
| Model range | Flash (cheap) to Pro (smart) | Mini to GPT-4.1 | Haiku to Opus |
| Strength | Cost + data platform depth | Ecosystem maturity | Code quality + safety |

### Strategic Positioning
- **Google:** Platform depth + data access. Search grounding is unique.
- **OpenAI:** Vertical integration + largest developer ecosystem.
- **Anthropic:** Safety-first + enterprise coding (Claude Code grew to 29% market share in 2025).

---

## 10. Recommendations for NemoClaw

### Immediate (No Architecture Changes)

1. **Add Gemini 2.5 Flash as routing alias** — At $0.30/$2.50, cheapest high-quality option for bulk skill execution. Target: `routing-config.yaml`
2. **Enable implicit context caching** — Auto-enabled on Gemini 2.5+, no code changes needed
3. **Google Search grounding for market-intel** — Add as tool for market-intel and research-lead agents. Replaces custom web scraping

### Medium-Term

4. **A2A protocol for agent interop** — Expose 11 agents as A2A-compliant services. Maps to MA-3 + MA-19. Industry standard with 50+ partners
5. **Gemini multimodal for creative-director** — Vision for asset analysis, Live API for real-time client interactions
6. **Explicit context caching** — Cache 128 skill definitions + agent configs for 90% cost reduction

### Architecture Considerations

7. **ADK as complementary, not replacement** — Keep LangGraph core (L-002). Use ADK patterns as reference
8. **1M context for MA-17** — Eliminates overflow handling. Load all configs in one call
9. **Don't abandon multi-provider strategy** — Add Gemini as additional aliases, don't replace existing

---

## 11. Key URLs Reference

### Official Documentation
| Resource | URL |
|----------|-----|
| ADK Docs | https://google.github.io/adk-docs/ |
| ADK Agents | https://google.github.io/adk-docs/agents/ |
| ADK Multi-agent | https://google.github.io/adk-docs/agents/multi-agents/ |
| ADK Deploy | https://google.github.io/adk-docs/deploy/agent-engine/ |
| Gemini Function Calling | https://ai.google.dev/gemini-api/docs/function-calling |
| Gemini Long Context | https://ai.google.dev/gemini-api/docs/long-context |
| Gemini Caching | https://ai.google.dev/gemini-api/docs/caching |
| Gemini Pricing | https://ai.google.dev/gemini-api/docs/pricing |
| Vertex AI Grounding | https://docs.cloud.google.com/vertex-ai/generative-ai/docs/grounding/grounding-with-google-search |
| Agent Engine | https://docs.cloud.google.com/agent-builder/agent-engine/overview |
| Live API | https://docs.cloud.google.com/vertex-ai/generative-ai/docs/live-api |

### Protocols & Standards
| Resource | URL |
|----------|-----|
| A2A Spec | https://a2a-protocol.org/latest/specification/ |
| A2A GitHub | https://github.com/a2aproject/A2A |
| A2A JS SDK | https://github.com/a2aproject/a2a-js |
| A2A Codelab | https://codelabs.developers.google.com/intro-a2a-purchasing-concierge |

### GitHub Repos
| Resource | URL |
|----------|-----|
| ADK Python | https://github.com/google/adk-python |
| Gemini Cookbook | https://github.com/google-gemini/cookbook |
| Gemini Live Examples | https://github.com/google-gemini/gemini-live-api-examples |
| GCP Generative AI | https://github.com/GoogleCloudPlatform/generative-ai |
| Gemini Skills | https://github.com/google-gemini/gemini-skills |

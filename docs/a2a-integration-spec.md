# A2A Protocol Integration Spec for NemoClaw

**Date:** 2026-04-03
**Status:** Research Complete — Ready for Implementation
**Protocol Version:** A2A v0.3 (Linux Foundation, Apache 2.0)

---

## Executive Summary

The Agent2Agent (A2A) protocol is the emerging industry standard for agent interoperability, backed by 150+ organizations including Google, Microsoft, IBM, Salesforce, and Adobe. NemoClaw's 11 agents and 124 skills can be exposed as A2A-compliant services, enabling external agents to discover and invoke NemoClaw capabilities — transforming it from a closed system into a skill provider in a multi-agent ecosystem.

**Key insight:** A2A is the inter-agent layer (peer collaboration), while MCP is the intra-agent layer (tool invocation). NemoClaw already uses MCP-style tool patterns internally. A2A adds the external-facing protocol.

---

## 1. Agent Card Generation

### What A2A Requires
Every A2A agent publishes an Agent Card at `/.well-known/a2a` containing:
- Identity (name, description, version, provider)
- Endpoints (jsonRpc, grpc, http)
- Capabilities (streaming, pushNotifications, multiTurn)
- Skills (name, description, inputSchema, outputSchema, mediaTypes)
- Security schemes (apiKey, bearer, oauth2, etc.)

### NemoClaw Mapping

**Source:** `config/agents/agent-schema.yaml` (11 agents with name, role, authority_level, domains, capabilities)

**Source:** `config/agents/capability-registry.yaml` (124 skills mapped to domains with I/O contracts)

**Transformation:**

```
NemoClaw agent-schema.yaml         →  A2A Agent Card
─────────────────────────────────────────────────────
agent.name                         →  AgentCard.name
agent.role                         →  AgentCard.description
agent.domains[]                    →  AgentCard.skills[].tags
capability-registry.skills[]       →  AgentCard.skills[]
skill.yaml inputs                  →  AgentSkill.inputSchema
skill.yaml outputs/artifact        →  AgentSkill.outputSchema
agent.authority_level              →  (internal only, not exposed)
```

**Example Agent Card for strategy_lead (Nadia):**

```json
{
  "id": "nemoclaw-strategy-lead",
  "name": "Nadia — Strategy Lead",
  "version": "1.0.0",
  "description": "Market intelligence, competitive analysis, pricing strategy, and business planning agent",
  "provider": {
    "organization": "NemoClaw",
    "url": "http://localhost:8100"
  },
  "endpoints": {
    "http": "http://localhost:8100/api/a2a"
  },
  "capabilities": {
    "streaming": true,
    "pushNotifications": true,
    "multiTurn": true,
    "extendedAgentCard": false
  },
  "skills": [
    {
      "name": "market-research",
      "description": "Deep market analysis with competitive landscape, trends, and opportunities",
      "inputSchema": {
        "type": "object",
        "properties": {
          "research_topic": {"type": "string"},
          "market_region": {"type": "string", "default": "global"},
          "depth": {"type": "string", "enum": ["overview", "detailed", "exhaustive"]}
        },
        "required": ["research_topic"]
      },
      "outputSchema": {
        "type": "object",
        "properties": {
          "report": {"type": "string"},
          "key_insights": {"type": "array", "items": {"type": "string"}},
          "market_size": {"type": "string"}
        }
      },
      "mediaTypes": ["text/markdown", "application/json"]
    }
  ],
  "securitySchemes": {
    "bearerAuth": {
      "type": "http",
      "scheme": "bearer"
    }
  },
  "security": [{"bearerAuth": []}]
}
```

### Implementation

**File to create:** `command-center/backend/app/api/routers/a2a.py`

**File to modify:** `command-center/backend/app/main.py` — mount A2A router

**Generator function:** Read `agent-schema.yaml` + `capability-registry.yaml` + individual `skill.yaml` files → produce Agent Cards dynamically.

**Discovery endpoint:** `GET /.well-known/a2a` returns array of all 11 Agent Cards, or `GET /.well-known/a2a?agent=strategy_lead` for single agent.

**Effort:** 1-2 days

**Priority:** P1 (highest — this is the interoperability gateway)

---

## 2. Task Lifecycle Mapping

### A2A Task States

```
IDLE → WORKING → COMPLETED
                → FAILED
                → INPUT_REQUIRED → (client responds) → WORKING
                → AUTH_REQUIRED → (client authenticates) → WORKING
                → CANCELED
     → REJECTED
```

### NemoClaw Mapping

```
A2A State          NemoClaw Equivalent                    Source
──────────────────────────────────────────────────────────────────
IDLE               TaskExecution.status = QUEUED           execution_service.py
WORKING            TaskExecution.status = RUNNING          execution_service.py
                   WorkflowPhase = BRAINSTORM/PLAN/        task_workflow_service.py
                   EXECUTE/VALIDATE/DOCUMENT
COMPLETED          TaskExecution.status = COMPLETED        execution_service.py
                   WorkflowPhase = COMPLETED               task_workflow_service.py
FAILED             TaskExecution.status = DEAD_LETTER      execution_service.py
                   WorkflowPhase = FAILED                  task_workflow_service.py
INPUT_REQUIRED     requires_human_approval=true            skill-runner.py:575
                   MA-16 Human-in-the-Loop pending         approval_chain_service.py
CANCELED           TaskExecution.cancel(id)                execution_service.py
REJECTED           (not implemented — add rejection        NEW
                   for unauthorized/over-budget requests)
AUTH_REQUIRED      (not implemented — add for              NEW
                   external callers needing auth)
```

### Implementation

**A2A task wrapper** around `TaskWorkflowService`:

```python
# Pseudocode for a2a_task_adapter.py
class A2ATaskAdapter:
    """Maps A2A SendMessage → NemoClaw workflow → A2A Task response"""

    async def handle_send_message(self, message: A2AMessage) -> A2ATask:
        # 1. Parse A2A message parts → NemoClaw skill inputs
        skill_id, inputs = self._resolve_skill(message)

        # 2. Create NemoClaw workflow
        wf_id = task_workflow_service.create_workflow(
            goal=message.parts[0].text,
            agent_id=self._best_agent(skill_id)
        )

        # 3. Start execution
        result = await task_workflow_service.run_workflow(wf_id)

        # 4. Map to A2A Task
        return A2ATask(
            id=wf_id,
            status=self._map_status(result),
            artifacts=self._map_artifacts(result),
            messages=[message, self._agent_response(result)]
        )
```

**Files to modify:**
- `command-center/backend/app/services/task_workflow_service.py` — add status mapping methods
- `command-center/backend/app/services/execution_service.py` — add REJECTED status to `ExecutionStatus` enum
- `command-center/backend/app/models/engine_models.py` — add AUTH_REQUIRED, REJECTED to status enum

**Effort:** 3-5 days

**Priority:** P1

---

## 3. Streaming via SSE

### A2A Streaming Protocol
- Client calls `SendStreamingMessage` or `SubscribeToTask`
- Server returns SSE stream with `TaskStatusUpdateEvent` and `TaskArtifactUpdateEvent`
- Stream closes on terminal state

### NemoClaw Mapping

**Existing streaming:** `lib/routing.py:call_llm_stream()` yields `(chunk_text, error)` tuples — this is LLM-level streaming.

**Existing WebSockets:** `command-center/backend/app/adapters/websocket_manager.py` broadcasts state/chat/alerts on 3 channels.

**Gap:** No SSE endpoint. No per-task streaming. WebSockets broadcast to all connected clients, not per-task subscribers.

### Implementation

**New SSE endpoint:** `GET /api/a2a/tasks/{task_id}/stream`

```python
# In a2a.py router
@router.get("/tasks/{task_id}/stream")
async def stream_task(task_id: str):
    async def event_generator():
        workflow = task_workflow_service.get_workflow(task_id)
        last_phase = None
        while workflow and workflow["phase"] not in ("completed", "failed"):
            if workflow["phase"] != last_phase:
                yield {
                    "event": "TaskStatusUpdateEvent",
                    "data": json.dumps({
                        "taskId": task_id,
                        "status": {"state": _map_phase(workflow["phase"])},
                        "timestamp": datetime.utcnow().isoformat()
                    })
                }
                last_phase = workflow["phase"]
            await asyncio.sleep(2)
            workflow = task_workflow_service.get_workflow(task_id)
        # Final state
        yield {"event": "TaskStatusUpdateEvent", "data": json.dumps({...terminal...})}
    return EventSourceResponse(event_generator())
```

**Dependency:** `pip install sse-starlette` (SSE for FastAPI)

**Files to modify:**
- `command-center/backend/app/api/routers/a2a.py` — add SSE endpoint
- `command-center/backend/app/services/task_workflow_service.py` — add phase change events

**Effort:** 1-2 days

**Priority:** P1

---

## 4. Push Notifications (Webhooks)

### A2A Push Protocol
- Client registers webhook URL per task via `CreateTaskPushNotificationConfig`
- Server POSTs `TaskStatusUpdateEvent` / `TaskArtifactUpdateEvent` to webhook
- Supports 4 auth types: api_key, bearer_token, basic, oauth2

### NemoClaw Mapping

**Existing:** `AgentNotificationService` in `agent_notification_service.py` handles internal notifications via `MessageStore` lanes. No external webhook support.

**Existing:** `EventBusService` in `command-center/backend/app/services/event_bus_service.py` fires events for skill_completed, skill_failed, task_started, task_completed, task_failed.

### Implementation

**New service:** `WebhookDeliveryService`

```python
class WebhookDeliveryService:
    """Delivers A2A push notifications to registered webhooks."""

    def __init__(self):
        self.configs: dict[str, list[PushNotificationConfig]] = {}  # task_id → configs

    async def register(self, task_id: str, config: PushNotificationConfig):
        self.configs.setdefault(task_id, []).append(config)

    async def deliver(self, task_id: str, event: dict):
        for config in self.configs.get(task_id, []):
            headers = self._build_auth_headers(config.authentication_info)
            async with httpx.AsyncClient() as client:
                await client.post(config.webhook_url, json=event, headers=headers)

    def _build_auth_headers(self, auth: AuthenticationInfo) -> dict:
        if auth.type == "bearer_token":
            return {"Authorization": f"Bearer {auth.value}"}
        elif auth.type == "api_key":
            return {auth.header or "X-API-Key": auth.value}
        return {}
```

**Wire into EventBus:** Subscribe to task_completed, task_failed events → call `webhook_service.deliver()`.

**Files to create:**
- `command-center/backend/app/services/webhook_delivery_service.py`

**Files to modify:**
- `command-center/backend/app/main.py` — init + wire to event bus
- `command-center/backend/app/api/routers/a2a.py` — CRUD endpoints for webhook configs

**Effort:** 2-3 days

**Priority:** P2

---

## 5. Multi-Turn Conversations

### A2A Multi-Turn Pattern
- `contextId` groups related tasks into a conversation
- `INPUT_REQUIRED` state pauses execution for client input
- Client sends follow-up message with same `taskId` to resume

### NemoClaw Mapping

**Existing:** `scripts/agent_messaging.py` has channels with `max_turns`, typed messages, vote system.

**Existing:** `skill-runner.py:575-579` has `requires_human_approval` gate that pauses execution.

**Existing:** `TaskWorkflowService` workflows persist to `~/.nemoclaw/workflows/{workflow_id}/`.

**Gap:** No external-facing multi-turn API. Internal agent channels are not exposed.

### Implementation

**Context management:** Map A2A `contextId` → NemoClaw project_id + workflow chain.

```python
# Context tracking
class A2AContextManager:
    """Maps A2A contextIds to NemoClaw workflow chains."""

    def __init__(self):
        self.contexts: dict[str, A2AContext] = {}

    def get_or_create(self, context_id: str = None) -> A2AContext:
        if context_id and context_id in self.contexts:
            return self.contexts[context_id]
        ctx = A2AContext(
            context_id=context_id or str(uuid4()),
            workflow_ids=[],
            messages=[]
        )
        self.contexts[ctx.context_id] = ctx
        return ctx

    def resume_task(self, task_id: str, message: A2AMessage):
        """Handle INPUT_REQUIRED resume."""
        # Find workflow, inject client response, continue execution
        workflow = task_workflow_service.get_workflow(task_id)
        if workflow and workflow["phase"] == "paused_approval":
            # Inject response and resume
            pass
```

**Files to modify:**
- `command-center/backend/app/services/task_workflow_service.py` — add pause/resume methods
- `command-center/backend/app/api/routers/a2a.py` — handle follow-up messages
- `skills/skill-runner.py` — expose approval gate status externally (currently stdin-only)

**Effort:** 3-5 days

**Priority:** P2

---

## 6. Parts System (Content Types)

### A2A Parts → NemoClaw Artifacts

```
A2A Part Type          NemoClaw Equivalent                    Source
──────────────────────────────────────────────────────────────────────
TextPart               Artifact markdown content               skill outputs/*.md
(text/markdown)        Envelope.outputs.primary                skill-runner.py:789

TextPart               Structured JSON output                  skill outputs/*.json
(application/json)     Envelope.outputs.sections               skill-runner.py:789

FilePart               Artifact file reference                 skill outputs/*
                       Envelope.outputs.artifact_path          skill-runner.py:789

DataPart               Envelope.metrics                        skill-runner.py:789
(structured)           Envelope.contracts                      skill-runner.py:789
```

### Implementation

**Artifact → A2A Artifact mapper:**

```python
def skill_output_to_a2a_artifact(envelope: dict) -> A2AArtifact:
    parts = []

    # Primary output as TextPart
    if envelope.get("outputs", {}).get("primary"):
        parts.append({
            "text": envelope["outputs"]["primary"],
            "mediaType": "text/markdown"
        })

    # Artifact file as FilePart
    if envelope.get("outputs", {}).get("artifact_path"):
        parts.append({
            "fileReference": {
                "uri": f"/api/artifacts/{envelope['skill_id']}/{Path(envelope['outputs']['artifact_path']).name}",
                "mediaType": _guess_media_type(envelope["outputs"]["artifact_path"])
            }
        })

    # Metrics as DataPart
    if envelope.get("metrics"):
        parts.append({
            "structuredData": envelope["metrics"],
            "mediaType": "application/json"
        })

    return {
        "id": f"artifact-{envelope.get('thread_id', 'unknown')}",
        "name": f"{envelope['skill_id']} output",
        "parts": parts,
        "createdTime": envelope.get("timestamp", datetime.utcnow().isoformat())
    }
```

**Files to modify:**
- `command-center/backend/app/api/routers/a2a.py` — artifact mapping
- `command-center/backend/app/main.py` — static file serving for artifacts

**Effort:** 1 day

**Priority:** P1

---

## 7. Authentication & Security

### A2A Auth Schemes → NemoClaw MA-19

**Current:** `command-center/backend/app/auth.py` uses local bearer token from `CC_AUTH_TOKEN` env var.

**A2A requires** declaring supported schemes in Agent Card.

### Recommended Implementation

**Phase 1 (immediate):** Bearer token auth (already exists). Declare in Agent Card:

```json
"securitySchemes": {
  "bearerAuth": {"type": "http", "scheme": "bearer"}
},
"security": [{"bearerAuth": []}]
```

**Phase 2 (later):** Add API key auth for programmatic access:

```json
"securitySchemes": {
  "apiKeyAuth": {"type": "apiKey", "in": "header", "name": "X-NemoClaw-Key"}
}
```

**Phase 3 (enterprise):** OAuth 2.0 client credentials flow for B2B.

**Files to modify:**
- `command-center/backend/app/auth.py` — add API key validation
- `config/.env` — add `NEMOCLAW_API_KEYS` for external access
- Agent Card generation — declare supported schemes

**Effort:** Phase 1: 0.5 days, Phase 2: 1 day, Phase 3: 3-5 days

**Priority:** Phase 1 is P1, Phase 2 is P2, Phase 3 is P3

---

## 8. Priority-Ranked Feature Adoption

| # | Feature | Files to Modify | Effort | Priority | Revenue Impact |
|---|---------|----------------|--------|----------|---------------|
| 1 | Agent Card generation + `/.well-known/a2a` | NEW `a2a.py`, `main.py`, read `agent-schema.yaml` | 1-2d | P1 | Ecosystem discovery |
| 2 | Task lifecycle mapping (A2A → Workflow) | `a2a.py`, `task_workflow_service.py`, `engine_models.py` | 3-5d | P1 | External task submission |
| 3 | Parts/Artifact mapping | `a2a.py` | 1d | P1 | Output delivery |
| 4 | SSE streaming endpoint | `a2a.py`, add `sse-starlette` | 1-2d | P1 | Real-time progress |
| 5 | Bearer auth declaration | `auth.py`, Agent Card | 0.5d | P1 | Security baseline |
| 6 | Push notification webhooks | NEW `webhook_delivery_service.py`, `main.py`, `a2a.py` | 2-3d | P2 | Async delivery |
| 7 | Multi-turn context management | `task_workflow_service.py`, `a2a.py`, `skill-runner.py` | 3-5d | P2 | Complex tasks |
| 8 | API key auth | `auth.py`, `.env` | 1d | P2 | Programmatic access |
| 9 | A2A Python SDK integration (`a2a-sdk`) | NEW service, `requirements.txt` | 2-3d | P2 | Standards compliance |
| 10 | OAuth 2.0 client credentials | `auth.py`, token management | 3-5d | P3 | Enterprise B2B |
| 11 | gRPC binding | NEW proto files, gRPC server | 5-7d | P3 | High-performance |
| 12 | Agent Card signing | Crypto key management | 2-3d | P3 | Trust verification |

### Total Estimated Effort

- **P1 (minimum viable A2A):** 7-11 days
- **P2 (production A2A):** +8-12 days
- **P3 (enterprise A2A):** +10-15 days

### Recommended Approach

**Sprint 1 (1 week):** Items 1-5 — Agent Cards + task mapping + streaming + auth = external agents can discover NemoClaw, submit tasks, and track progress.

**Sprint 2 (1 week):** Items 6-9 — Webhooks + multi-turn + API keys + SDK = production-quality A2A endpoint.

**Sprint 3 (2 weeks):** Items 10-12 — Enterprise features on demand.

---

## 9. A2A vs MCP: NemoClaw's Dual-Protocol Strategy

### Current State
NemoClaw uses MCP-style patterns internally (skills as structured tools with defined I/O). No external protocol.

### Target State

```
External Agents ──── A2A Protocol ────→ NemoClaw A2A Router
                                            │
                                            ▼
                                     Task Workflow Service
                                            │
                                            ▼
                                     Execution Service
                                            │
                                            ▼
                                     skill-runner.py ──── MCP-style ────→ LLM Providers
                                                          tool calls      (Anthropic, OpenAI,
                                                                           Google, NVIDIA)
```

**A2A is the external API.** MCP remains the internal execution pattern. They're complementary layers.

### Key Benefit
NemoClaw's 124 skills become discoverable services in a 150+ organization ecosystem. Any A2A-compliant agent (Google ADK, Microsoft Agent Framework, CrewAI, AutoGen) can discover and invoke NemoClaw capabilities.

---

## Sources

- [A2A Protocol Specification v0.3](https://a2a-protocol.org/latest/specification/)
- [A2A and MCP Relationship](https://a2a-protocol.org/latest/topics/a2a-and-mcp/)
- [GitHub google/A2A](https://github.com/google/A2A)
- [A2A Python SDK](https://pypi.org/project/a2a-sdk/)
- [Linux Foundation A2A Announcement](https://www.linuxfoundation.org/press/linux-foundation-launches-the-agent2agent-protocol-project)
- [Google Cloud Blog: A2A Upgrade](https://cloud.google.com/blog/products/ai-machine-learning/agent2agent-protocol-is-getting-an-upgrade)

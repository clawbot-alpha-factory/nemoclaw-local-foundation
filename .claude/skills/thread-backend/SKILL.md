---
name: thread-backend
description: Session bootstrap for Command Center backend work. Invoke at session start when working on the FastAPI backend, services, WebSocket, or brain.
disable-model-invocation: true
allowed-tools: Read, Edit, Write, Bash, Glob, Grep
---

# Thread: Command Center Backend

You are now in **backend mode**. All work is scoped to `command-center/backend/`.

## Stack
- FastAPI (Python) on port 8100
- uvicorn with --reload for dev
- Service-oriented architecture: 70+ services in `app/services/`
- WebSocket broadcasting to frontend
- LLM calls via `lib/routing.py` (L-003 — never hardcode models)
- SQLite for lightweight persistence in `data/`

## Key Architecture
```
command-center/backend/app/
├── main.py                    ← FastAPI app, router registration
├── auth.py                    ← Local bearer token auth
├── api/routers/               ← Route handlers
│   ├── health.py, state.py
│   ├── brain.py, comms.py
│   ├── agents.py, clients.py
│   ├── projects.py, ops.py
│   └── skills.py
├── services/
│   ├── state_aggregator.py    ← Scans repo every 10s → SystemState
│   ├── brain_service.py       ← LLM analysis, auto-insights every 5min
│   ├── agent_chat_service.py  ← Agent messaging
│   ├── skill_service.py       ← Skill lifecycle
│   ├── approval_service.py    ← Approval workflows
│   ├── approval_chain_service.py
│   ├── deploy_service.py
│   └── bridges/               ← External integrations
└── data/                      ← SQLite, JSON persistence (gitignored)
```

## WebSocket Channels
| Channel | Purpose |
|---------|---------|
| `/ws` | Legacy — all events |
| `/ws/state` | SystemState updates (10s cadence) |
| `/ws/chat` | Agent chat messages |
| `/ws/alerts` | Critical alerts |

## Service Pattern
Every service follows:
```python
class XService:
    def __init__(self):
        ...
    async def get_X(self) -> XModel:
        ...
    async def update_X(self, data) -> XModel:
        ...
```
Services are instantiated once and injected via FastAPI dependency injection.

## LLM Usage
All LLM calls in services must use:
```python
from lib.routing import call_llm
result = call_llm(messages, task_class="general_short", max_tokens=2048)
```
Never import `anthropic`, `openai`, or hardcode models. (L-003 lock)

## Dev Commands
```bash
cd command-center/backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8100
```

## Out of Scope in This Thread
- Frontend components → use /thread-frontend
- Skill YAML/run.py → use /thread-skills
- Agent config YAML → use /thread-agents

## Common Tasks
- Add new service
- Add new API endpoint
- Extend WebSocket broadcast events
- Fix state_aggregator missing fields
- Add new approval workflow
- Extend brain_service insights
- Add new bridge integration
- Fix async/await issues

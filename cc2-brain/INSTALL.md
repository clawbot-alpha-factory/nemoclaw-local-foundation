# CC-2: AI Brain — Installation Guide

## What This Adds

The AI Brain is a persistent right sidebar in the Command Center that provides:

- **LLM-powered system analysis** — reads full SystemState and generates strategic insights
- **Conversational interface** — ask questions about your system, get context-aware answers
- **Auto-insights** — every 5 minutes, the Brain analyzes system state and broadcasts insights via WebSocket
- **Zustand state store** — replaces prop-drilling with centralized client-side state management

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Frontend (Next.js)                                     │
│  ┌──────────┐  ┌──────────┐  ┌────────────────────────┐│
│  │ Sidebar   │  │ HomeTab  │  │ BrainSidebar (new)     ││
│  │           │  │          │  │  - Chat messages       ││
│  │           │  │          │  │  - Insights display    ││
│  │           │  │          │  │  - Analyze button      ││
│  │           │  │          │  │  - Token auth          ││
│  └──────────┘  └──────────┘  └────────────────────────┘│
│                     │              │                     │
│              Zustand Store (new)   │                     │
│                     │              │                     │
│           ┌─────────┴──────────────┘                    │
│           │   useWebSocket (patched: brain_insight)      │
└───────────┼─────────────────────────────────────────────┘
            │
    REST /api/brain/*  +  WS /ws (brain_insight type)
            │
┌───────────┼─────────────────────────────────────────────┐
│  Backend (FastAPI)                                       │
│           │                                              │
│  ┌────────┴─────┐  ┌────────────────┐  ┌──────────────┐│
│  │ brain router  │  │ brain_service  │  │ state_agg    ││
│  │ (new)         │→ │ (new)          │← │ (existing)   ││
│  │ /ask          │  │ - routing.yaml │  │              ││
│  │ /analyze      │  │ - LLM calls    │  │              ││
│  │ /status       │  │ - history mgmt │  │              ││
│  └──────────────┘  └────────┬───────┘  └──────────────┘│
│                              │                           │
│                    ┌─────────┴──────────┐                │
│                    │ routing-config.yaml │                │
│                    │ config/.env (key)   │                │
│                    └────────────────────┘                │
└─────────────────────────────────────────────────────────┘
```

## New Files

| File | Location | Purpose |
|------|----------|---------|
| brain_service.py | backend/app/ | LLM integration service |
| brain.py | backend/app/routers/ | Brain API endpoints (5 endpoints) |
| store.ts | frontend/src/lib/ | Zustand state store |
| BrainSidebar.tsx | frontend/src/components/ | Brain sidebar component |

## Patched Files

| File | Changes |
|------|---------|
| backend/app/main.py | Brain imports, router, service init, auto-insight task |
| backend/app/websocket_manager.py | broadcast_brain_message() method |
| frontend/src/app/page.tsx | BrainSidebar import + component in layout |
| frontend/src/hooks/useWebSocket.ts | brain_insight WS message handling |
| backend/requirements.txt | anthropic, openai packages |
| frontend/package.json | zustand package |

## New API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /api/brain/ask | Yes | Ask a question with system context |
| POST | /api/brain/analyze | Yes | Trigger immediate system analysis |
| GET | /api/brain/status | No | Brain availability and provider info |
| GET | /api/brain/history | Yes | Get conversation history |
| POST | /api/brain/clear | Yes | Clear conversation history |

## Quick Install

```bash
# 1. Extract archive to project root
cd ~/nemoclaw-local-foundation
tar xzf cc2-brain.tar.gz

# 2. Run setup script
python3 cc2-brain/apply_cc2.py

# 3. Install backend deps
cd command-center/backend
source ~/.venv313/bin/activate
pip install -r requirements.txt --break-system-packages

# 4. Install frontend deps
cd ../frontend
npm install

# 5. Set API key
echo 'ANTHROPIC_API_KEY=sk-ant-your-key-here' >> ../../config/.env

# 6. Start backend
cd ../backend
python run.py --reload

# 7. Start frontend (new terminal)
cd ~/nemoclaw-local-foundation/command-center/frontend
npm run dev

# 8. Verify
curl -s http://127.0.0.1:8100/api/brain/status | python3 -m json.tool
```

## Manual Install (if setup script needs adjustment)

If `apply_cc2.py` can't find the right anchor points in your files, apply patches manually:

### main.py

Add imports:
```python
from .brain_service import BrainService
from .routers.brain import router as brain_router, set_dependencies as brain_set_deps
```

In lifespan, before `yield`:
```python
brain_service = BrainService(
    project_root=str(Path(__file__).parent.parent.parent.parent),
    routing_alias=os.environ.get("CC_BRAIN_ROUTING_ALIAS", "balanced"),
)
brain_set_deps(brain_service, state_agg)  # use your state aggregator var name
app.include_router(brain_router)
```

### websocket_manager.py

Add method to WebSocketManager class:
```python
async def broadcast_brain_message(self, message: dict):
    import json
    data = json.dumps(message)
    dead = set()
    for ws in self._connections:
        try:
            await ws.send_text(data)
        except Exception:
            dead.add(ws)
    self._connections -= dead
```

### page.tsx

Add import and component:
```tsx
import BrainSidebar from '../components/BrainSidebar';

// In your layout, after </main>:
<BrainSidebar />
```

### useWebSocket.ts

Add to the onmessage handler, before state processing:
```tsx
import { useStore } from '../lib/store';

// After JSON.parse:
if (data?.type === 'brain_insight' && data?.data) {
  const store = useStore.getState();
  store.addBrainMessage({
    role: 'assistant',
    content: data.data.content,
    timestamp: data.data.timestamp,
    type: 'insight',
  });
  return;
}
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| CC_BRAIN_ROUTING_ALIAS | balanced | Which routing alias to use for LLM calls |
| CC_BRAIN_INSIGHT_INTERVAL_SECONDS | 300 | Auto-insight interval (seconds) |
| CC_PROJECT_ROOT | auto-detected | Path to nemoclaw-local-foundation root |
| ANTHROPIC_API_KEY | — | Required if routing alias uses Anthropic |
| OPENAI_API_KEY | — | Required if routing alias uses OpenAI |
| GOOGLE_API_KEY | — | Required if routing alias uses Google |

## Troubleshooting

**Brain shows "offline"**
- Check that your API key is set in config/.env
- Verify the key is valid: `curl https://api.anthropic.com/v1/messages -H "x-api-key: YOUR_KEY" -H "anthropic-version: 2023-06-01" -d '{"model":"claude-sonnet-4-20250514","max_tokens":10,"messages":[{"role":"user","content":"hi"}]}' -H "content-type: application/json"`
- Check backend logs for "Brain API key loaded" or error messages

**401 on brain endpoints**
- Enter your auth token in the Brain sidebar (from backend startup log)
- Or add `?token=YOUR_TOKEN` to the URL

**Auto-insights not appearing**
- Default interval is 5 minutes (300s). Wait or set CC_BRAIN_INSIGHT_INTERVAL_SECONDS=30 for testing
- Check backend logs for "Auto-insight generated"

**Zustand errors**
- Run `npm install` in frontend directory
- Verify zustand is in package.json dependencies

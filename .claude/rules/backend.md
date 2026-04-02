---
paths:
  - "command-center/backend/**"
---

## Command Center Backend
- Stack: FastAPI (Python)
- Service pattern: app/services/ (70+ services)
- State aggregator: scans repo filesystem every 10s, builds SystemState
- Brain service: LLM-powered analysis, auto-insights every 5min
- Auth: local bearer token (app/auth.py)
- WebSocket broadcasting via /ws, /ws/state, /ws/chat, /ws/alerts
- Dev server: uvicorn on port 8100 with --reload
- Entry point: command-center/backend/run.py

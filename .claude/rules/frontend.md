---
paths:
  - "command-center/frontend/**"
---

## Command Center Frontend
- Stack: Next.js + React + Zustand + Tailwind CSS
- State store: src/lib/store.ts (Zustand)
- WebSocket: src/hooks/useWebSocket.ts (auto-reconnect, exponential backoff 3s-30s)
- WebSocket channels: /ws (legacy), /ws/state, /ws/chat, /ws/alerts
- 12 tabs: Home, Comms, Agents, Skills, Ops, Execution, Approvals, Clients, Projects, Settings, etc.
- Dev server: npm run dev on port 3000
- Build: npm run build (production)
- Lint: npm run lint

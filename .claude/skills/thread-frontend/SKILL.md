---
name: thread-frontend
description: Session bootstrap for Command Center frontend work. Invoke at session start when working on the Next.js dashboard UI.
disable-model-invocation: true
allowed-tools: Read, Edit, Write, Bash, Glob, Grep
---

# Thread: Command Center Frontend

You are now in **frontend mode**. All work is scoped to `command-center/frontend/`.

## Stack
- Next.js + TypeScript + React
- Tailwind CSS for styling
- Zustand for state (`src/lib/store.ts`)
- Custom WebSocket hook (`src/hooks/useWebSocket.ts`) — auto-reconnect, exponential backoff 3s→30s
- API clients in `src/lib/` (agents-api.ts, skills-api.ts, clients-api.ts, approvals-api.ts, ops-api.ts, comms-api.ts)

## Key Files
```
command-center/frontend/src/
├── components/         ← All tab components (18 tabs)
│   ├── AgentsTab.tsx
│   ├── SkillsTab.tsx
│   ├── ProjectsTab.tsx
│   ├── ClientsTab.tsx
│   ├── ApprovalTab.tsx
│   ├── ExecutionTab.tsx
│   ├── OpsTab.tsx
│   ├── CommsTab.tsx
│   ├── BrainSidebar.tsx
│   └── HomeTab.tsx
├── hooks/              ← useWebSocket.ts and others
├── lib/
│   ├── store.ts        ← Zustand state store
│   ├── types.ts        ← Shared TypeScript types
│   └── *-api.ts        ← Per-domain API clients
└── app/                ← Next.js app router
```

## Backend Contracts
- REST base: `http://localhost:8100/api/`
- WebSocket channels: `/ws` (legacy), `/ws/state`, `/ws/chat`, `/ws/alerts`
- Auth: Bearer token (local dev — check app/auth.py for token)
- State refresh: state_aggregator scans filesystem every 10s

## Conventions
- Functional components only, no class components
- Tailwind for ALL styling — no custom CSS files
- Zustand store for shared state, React state for component-local state
- All API calls go through `src/lib/*-api.ts` clients — never fetch() inline in components
- TypeScript strict mode — no `any` types
- WebSocket data flows: backend pushes → useWebSocket hook → Zustand store → component renders

## Dev Commands
```bash
cd command-center/frontend
npm run dev        # port 3000
npm run build      # production build
npm run lint       # ESLint check
npm run type-check # TypeScript check
```

## Out of Scope in This Thread
- Backend FastAPI code → use /thread-backend
- Skill YAML or run.py → use /thread-skills
- Agent config → use /thread-agents

## Common Tasks
- Add new tab or panel
- Connect new WebSocket event to UI
- Add new API client method
- Fix TypeScript type errors
- Improve real-time data display
- Add approval flow UI
- Style improvements with Tailwind

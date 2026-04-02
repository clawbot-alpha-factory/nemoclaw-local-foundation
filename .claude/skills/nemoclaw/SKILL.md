---
name: nemoclaw
description: NemoClaw master session — loads full project context and routes you to the right thread. Invoke at the start of any NemoClaw session to get oriented.
disable-model-invocation: true
allowed-tools: Read, Bash, Glob, Grep
---

# NemoClaw — Master Thread Router

You are working on **NemoClaw Local Foundation** — an autonomous AI company platform.

## Quick Stats
- 124 skills · 11 agents · 4-tier authority · 20 MA systems
- Command Center: FastAPI :8100 + Next.js :3000
- 9-alias LLM routing (Anthropic/OpenAI/Google)
- 413 architecture lock decisions

## Available Threads — Pick One

| Thread | Invoke | Use When |
|--------|--------|----------|
| **Frontend** | `/thread-frontend` | Working on Command Center UI (Next.js, 18 tabs, Zustand) |
| **Backend** | `/thread-backend` | Working on FastAPI, services, WebSocket, brain |
| **Skills** | `/thread-skills` | Building/fixing skills, schema v2, routing compliance |
| **Agents** | `/thread-agents` | Agent system, MA-1 through MA-20, authority hierarchy |
| **Content Factory** | `/thread-content-factory` | Video pipeline, CapCut, HeyGen, Fish Speech, Zara |
| **Routing** | `/thread-routing` | LLM aliases, budget governance, L-003 fixes |
| **Deployment** | `/thread-deployment` | Deploy P1-P12, prod-ops, health monitoring |
| **Integrations** | `/thread-integrations` | Bridges (n8n, HubSpot, Meta Ads, Supabase, etc.) |
| **Audit: Full** | `/thread-audit-full` | Complete system health before release |
| **Audit: Skills** | `/thread-audit-skills` | Deep skill quality + L-003 compliance |
| **Audit: Agents** | `/thread-audit-agents` | Agent coverage + MA system health |
| **Audit: Infra** | `/thread-audit-infra` | Infrastructure readiness + security |
| **Research** | `/thread-research <question>` | Understand something deeply before changing it |
| **Debug** | `/thread-debug <problem>` | Something is broken, fix it systematically |

## Quick Actions (no thread needed)
```
/validate          → 31-check validation
/health            → system status + costs
/audit-system      → full audit in isolated context
/run-skill <id>    → execute a skill
/new-skill         → create a skill
```

## Start the Right Thread
Tell me what you want to work on today, or invoke a thread directly.

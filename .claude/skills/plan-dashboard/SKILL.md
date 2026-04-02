---
name: plan-dashboard
description: Planning session for the Command Center dashboard — wireframes, data sources, tech stack, components, phases. Output is docs/dashboard-spec.md only. Use when planning dashboard features.
disable-model-invocation: true
context: fork
model: sonnet
allowed-tools: Read, Grep, Glob, Write
---

Planning session only. Do NOT write any code, create any files outside of `docs/`, or modify any existing files. The sole output is `docs/dashboard-spec.md`.

## 1. Read Existing System (required before planning)
Read the following to understand what data already exists:
- `command-center/backend/app/domain/models.py` — SystemState and all sub-models
- `command-center/backend/app/api/routers/` — all existing REST endpoints
- `command-center/backend/app/adapters/websocket_manager.py` — WebSocket channel structure
- `command-center/frontend/src/lib/types.ts` — TypeScript types
- `command-center/frontend/src/lib/store.ts` — Zustand state shape
- `command-center/frontend/src/app/page.tsx` — current tab structure
- `command-center/frontend/package.json` — current frontend deps
- `scripts/system_health.py` (MA-14)
- `scripts/decision_log.py` (MA-4)
- `scripts/human_loop.py` (MA-16)
- `scripts/cost_governor.py` (MA-6)
- `config/routing/budget-config.yaml`

## 2. Define 13 Dashboard Views
For each view, write detailed wireframe descriptions (layout, sections, data points, interactions):
Command Overview, Agent Activity, Skill Execution, Revenue Pipeline, Cost Burn, Task Queue, Client View, Content Calendar, Alerts, System Health, Decision Log, Approval Queue, Kill Switch.

## 3. Data Sources Mapping
For each view: existing endpoints, WebSocket channels, new endpoints needed, polling vs push.

## 4. Tech Stack Recommendation
Evaluate current stack suitability. Assess Zustand vs alternatives, chart library, table components, component library.

## 5. Component List
All React components grouped by view with name, purpose, props interface, store slices.

## 6. State Management Approach
New Zustand slices, derived selectors, WebSocket subscription model, optimistic updates.

## 7. Implementation Phases
P0 Foundation (must-have), P1 Revenue visibility, P2 Autonomous operations.

## 8. Write the Spec
Create `docs/dashboard-spec.md` with all of the above.

Planning session only. Do NOT write any code, create any files outside of `docs/`, or modify any existing files. The sole output is `docs/dashboard-spec.md`.

## 1. Read Existing System (required before planning)
Read the following to understand what data already exists:
- `command-center/backend/app/domain/models.py` — SystemState and all sub-models
- `command-center/backend/app/api/routers/` — all existing REST endpoints (list all route paths)
- `command-center/backend/app/adapters/websocket_manager.py` — WebSocket channel structure
- `command-center/frontend/src/lib/types.ts` — TypeScript types
- `command-center/frontend/src/lib/store.ts` — Zustand state shape
- `command-center/frontend/src/app/page.tsx` — current tab structure
- `command-center/frontend/package.json` — current frontend deps
- `scripts/system_health.py` (MA-14) — 12 health domain structure
- `scripts/decision_log.py` (MA-4) — decision log schema
- `scripts/human_loop.py` (MA-16) — approval queue structure
- `scripts/cost_governor.py` (MA-6) — cost tracking structure
- `config/routing/budget-config.yaml` — provider budget structure

## 2. Define Dashboard Views
For each of the following views, write a detailed wireframe description (not code — describe layout, sections, key data points, interactions):

### View 1: Command Overview (Home)
Real-time snapshot: agent activity feed, system health ring, active skill executions, today's costs, pending approvals count, latest brain insight.

### View 2: Agent Activity Monitor
Per-agent status cards showing: current task, last active, tasks completed today, cost today, performance score (MA-12), authority level badge, web browser active indicator.

### View 3: Skill Execution Console
Live execution log table: skill_id, triggering agent, start time, duration, status (running/complete/failed), cost, output preview. Filter by agent, family, status. Click row to expand full envelope JSON.

### View 4: Revenue Pipeline
MRR/ARR tracker, deal pipeline kanban (prospect → qualified → proposal → closed), invoices sent/paid/overdue, Lemon Squeezy subscription counts, revenue by source.

### View 5: Cost Burn Dashboard
Provider cost gauges (Anthropic/OpenAI/Google) with budget % bars, daily burn rate chart (7-day), cost per agent breakdown, cost per skill family breakdown, projected month-end spend, circuit breaker status.

### View 6: Task Queue & Throughput
Active queue depth, tasks per hour chart (24h), avg execution time by skill family, failure rate by skill, MA-5 task decomposition viewer (goal → tasks tree).

### View 7: Client & Customer View
Client list (from CRM/Asana), per-client delivery status, SLA compliance indicators, upcoming deliverable due dates, client health score, churn risk alerts (MA-E11).

### View 8: Content Calendar
Social media post schedule (7-day forward view), platform icons (LinkedIn/Twitter/YouTube), post status (draft/approved/published), content skill that generated each post, engagement metrics if available.

### View 9: Alerts & Notifications
Unified alert feed from MA-14 (system health), MA-6 (budget), MA-8 (behavior violations), MA-16 (pending approvals), WebSocket alerts channel. Severity badges (critical/warn/info). Dismiss and snooze controls.

### View 10: System Health (MA-14)
12-domain health grid with RAG (red/amber/green) status per domain, composite score, trend indicators, last-checked timestamp, drill-down to domain details.

### View 11: Decision Log Viewer (MA-4)
Searchable log of all agent decisions: timestamp, agent_id, decision_type, rationale, outcome, cost. Filter by agent, date range, decision_type. Export to CSV.

### View 12: Approval Queue (MA-16)
Pending approvals list with: category, requesting agent, risk score, expiry countdown, approve/reject buttons. History of past approvals with outcomes.

### View 13: Global Kill Switch
Prominent emergency stop panel: individual agent pause/resume toggles, full system halt button (requires confirmation), circuit breaker manual override, "safe mode" toggle (disables all web + external actions).

## 3. Data Sources Mapping
For each view, specify:
- Which existing REST endpoint(s) feed it
- Which WebSocket channel(s) update it in real-time
- Which new endpoints need to be created (if any)
- Polling vs. push recommendation

## 4. Tech Stack Recommendation
Evaluate whether to keep the current stack (Next.js + React + Zustand + Tailwind) or switch. Assess:
- Does current stack support all 13 views?
- Is Zustand adequate or is Redux/Jotai better for this complexity?
- Should charts use Recharts, Chart.js, or Tremor?
- Should the table/grid components use TanStack Table?
- Is there a benefit to a component library (shadcn/ui, Radix, Mantine)?
- Recommendation with clear rationale

## 5. Component List
List all React components that would need to be built or heavily modified, grouped by view. For each component:
- Name
- Purpose (1 sentence)
- Props interface (TypeScript types, not code — just describe the shape)
- Which store slice(s) it reads from

## 6. State Management Approach
Design the Zustand store expansion:
- New slices needed (revenue, clients, approvals, content calendar, alerts, health)
- Derived selectors (computed values, not raw state)
- WebSocket subscription model (which channels update which slices)
- Optimistic update patterns for approve/reject actions

## 7. Implementation Phases
Break the full dashboard into phases:

**P0 — Foundation (must-have for go-live)**
List views, components, and endpoints. Goal: owner can monitor system in real-time.

**P1 — Revenue visibility**
List views, components, and endpoints. Goal: owner can track money in/out.

**P2 — Autonomous operations**
List views, components, and endpoints. Goal: owner only needs to check in weekly.

## 8. Write the Spec Document
Create `docs/dashboard-spec.md` containing all of the above, structured with clear H2/H3 headings. The document should be detailed enough that a frontend engineer could build any view without asking clarifying questions.

Do not write any implementation code. The spec document is the only output.

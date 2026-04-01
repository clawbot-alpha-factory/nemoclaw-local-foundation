# NemoClaw Command Center — Dashboard Specification v1.0

**Date:** 2026-04-01
**Status:** Planning
**Author:** Claude Opus 4.6 (automated architecture session)

---

## Table of Contents
1. [Existing System Summary](#1-existing-system-summary)
2. [Dashboard Views (13)](#2-dashboard-views)
3. [Data Sources Mapping](#3-data-sources-mapping)
4. [Tech Stack Recommendation](#4-tech-stack-recommendation)
5. [Component List](#5-component-list)
6. [State Management Approach](#6-state-management-approach)
7. [Implementation Phases](#7-implementation-phases)

---

## 1. Existing System Summary

### Backend (FastAPI)
- **155+ REST endpoints** across 28 router files
- **4 WebSocket channels:** `/ws` (legacy), `/ws/state` (10s push), `/ws/chat`, `/ws/alerts`
- **Pydantic models:** SystemState, EngineState, ExecutionRequest, ChainExecution, Message, Lane, etc.
- **Key services:** StateAggregator (10s scan), BrainService (5min insights), ExecutionService, ApprovalService, RevenueService

### Frontend (Next.js 14 + React 18)
- **9 tabs implemented** (home, comms, agents, skills, ops, execution, approvals, clients, projects)
- **4 tabs unimplemented** (finance, intelligence, settings, playground)
- **Zustand store** with systemState, brain sidebar, navigation
- **WebSocket hook** with dual connections + exponential backoff
- **37 source files**, all custom components (no UI library, no charts, no tables)
- **Deps:** next, react, zustand, tailwindcss, lucide-react, clsx

### MA Systems Feeding Dashboard
- **MA-4** Decision Log: 12-field schema, status workflow, JSON storage
- **MA-6** Cost Governor: circuit breaker (CLOSED/OPEN/HALF_OPEN), per-agent ledger, 4 alert thresholds
- **MA-8** Behavior Guard: 16 rules, graduated enforcement, violation tracking
- **MA-12** Agent Performance: 6 dimensions (quality/speed/cost/reliability/compliance/revenue_impact), gamification
- **MA-14** System Health: 12 weighted domains, composite scoring, RAG indicators
- **MA-16** Human Loop: 6 approval categories, pending queue, 4h-72h expiry

### Budget Structure
- 3 providers (Anthropic/OpenAI/Google) at $30 each
- Cumulative tracking, 90% warn, 100% hard stop
- Logged to `~/.nemoclaw/logs/provider-usage.jsonl`

---

## 2. Dashboard Views

### View 1: Command Overview (Home)

**Purpose:** Single-glance system status for the owner. Answer: "Is everything working? What happened today?"

**Layout:**
- **Top row (4 cards):** Active Agents (count + green/yellow dots), Skills Running (count + queue depth), Today's Revenue ($X), Pending Approvals (count with red badge if >0)
- **Middle left (60%):** Activity Feed — chronological stream of agent actions (agent avatar + name + action + timestamp). Real-time via WebSocket. Last 50 entries. Color-coded by type: green=revenue, blue=task, yellow=approval, red=error
- **Middle right (40%):** System Health Ring — donut chart showing 12 health domains as colored segments (green/amber/red). Center shows composite score (0-100). Click segment to drill into domain.
- **Bottom left (50%):** Active Executions — compact table showing currently running skills (skill_id, agent, elapsed time, cost so far). Max 10 rows. Sparkline for queue depth over last hour.
- **Bottom right (50%):** Brain Insight — latest auto-insight from BrainService. Shows summary text + confidence score. "Ask Brain" button opens right sidebar.
- **Footer bar:** Cost burn today ($X of $Y), WebSocket status dot, git branch, last scan timestamp

### View 2: Agent Activity Monitor

**Purpose:** See what each agent is doing right now and how they're performing.

**Layout:**
- **Grid of 11 agent cards** (3 columns on desktop, 1 on mobile)
- **Each card contains:**
  - Agent avatar (from assets/avatars/*.png) + name + character persona
  - Authority level badge (L1 gold, L2 silver, L3 bronze, L4 blue)
  - Current status: idle / executing [skill_name] / waiting for approval
  - Performance score ring (0-10, color-coded)
  - Today's stats row: tasks completed, cost spent, revenue attributed
  - Last active timestamp
  - PinchTab indicator (green dot if browser session active)
  - Quick actions: View Details, Pause Agent, View History
- **Top bar:** Sort by: performance score, revenue, activity, cost. Filter by authority level.
- **Right panel (click agent to expand):** Full performance breakdown (6 dimensions radar chart), recent task history (last 20), skill inventory, learning loop lessons applied

### View 3: Skill Execution Console

**Purpose:** Live execution monitoring. See every skill running, completed, or failed.

**Layout:**
- **Top bar:** Filters — Agent (dropdown all 11), Family (dropdown), Status (running/completed/failed/all), Date range. Search box for skill_id.
- **Main table:** Sortable columns — Skill ID, Agent (avatar+name), Started, Duration, Status (badge), Cost, Quality Score, Output Preview (first 100 chars truncated)
- **Click row to expand:** Full execution details — input JSON, output JSON, envelope path, retry count, error message (if failed), LLM routing decision (provider/model/cost), thread_id
- **Right sidebar (live):** Queue depth gauge, executions per hour sparkline, failure rate last 24h, most-executed skill today, most expensive skill today
- **Bottom:** Dead letter queue summary — count of dead-lettered executions with "retry" and "dismiss" buttons

### View 4: Revenue Pipeline

**Purpose:** Track money — from lead to closed deal to invoice paid.

**Layout:**
- **Top metrics row (5 cards):** MRR ($X), ARR ($X projected), Pipeline Value ($X), Deals This Month (N), Revenue Growth (% MoM)
- **Kanban board (center):** 6 columns — Prospect, Qualified, Proposal Sent, Negotiation, Closed Won, Closed Lost. Each card shows: company name, deal value, assigned agent (Hassan/Omar), days in stage, next action. Drag-drop to advance stage.
- **Bottom left:** Invoice tracker — table of invoices (client, amount, status: draft/sent/paid/overdue, due date). Red highlight for overdue.
- **Bottom right:** Revenue attribution chart — stacked bar chart showing revenue by source (outbound, inbound, paid ads, organic, referral) over last 6 months. Uses data from `GET /api/revenue/attribution`.
- **Corner:** Subscription tracker — Lemon Squeezy active subscriptions count, MRR from subscriptions, churn rate

### View 5: Cost Burn Dashboard

**Purpose:** Track and control LLM spend across all providers.

**Layout:**
- **Top row (3 gauges):** One per provider (Anthropic/OpenAI/Google). Circular gauge showing spent/limit. Color: green <50%, yellow 50-90%, red >90%. Shows exact $X/$Y below.
- **Circuit breaker status:** Traffic light indicator — CLOSED (green), HALF_OPEN (yellow), OPEN (red) with trip reason if not closed.
- **Center chart:** Daily burn rate — line chart showing $/day over last 30 days. Three lines (one per provider). Horizontal dashed line at daily average.
- **Bottom left table:** Cost by agent — ranked list of agents by cost today. Columns: agent (avatar+name), calls today, cost today, avg cost per call, % of total.
- **Bottom right table:** Cost by skill family — ranked by total cost. Columns: family, executions, total cost, avg cost, most expensive skill in family.
- **Footer:** Projected month-end spend (linear extrapolation), days until budget exhausted per provider, budget reset controls (admin only)

### View 6: Task Queue & Throughput

**Purpose:** Operational health of the execution engine.

**Layout:**
- **Top metrics (4 cards):** Queue Depth (current), Throughput (tasks/hr last hour), Avg Execution Time (today), Failure Rate (% last 24h)
- **Center chart:** Tasks per hour — bar chart over last 24 hours. Stacked by status (completed green, failed red, running blue). Hover shows exact counts.
- **Left table:** Execution time by skill family — sorted slowest first. Columns: family, avg time, p95 time, executions count, trend arrow (up/down vs yesterday).
- **Right panel:** MA-5 Task Decomposition Viewer — tree/hierarchy view of a selected workflow goal broken into subtasks. Each node shows: task_id, assigned agent, status, cost. Expand/collapse nodes.
- **Bottom:** Failure analysis — top 5 failing skills with error message pattern, failure count, last failure timestamp, "investigate" link

### View 7: Client & Customer View

**Purpose:** Track delivery status and client health for retention.

**Layout:**
- **Client list (left panel, 30%):** Scrollable list of clients with health score badge (green/yellow/red), name, MRR, last contact date. Click to select.
- **Client detail (right panel, 70%):** Selected client expanded view:
  - Header: client name, industry, contact email, onboarding date, total revenue
  - Health score breakdown: engagement (%), delivery (%), satisfaction (%), payment history
  - Active deliverables table: deliverable name, due date, status (on-track/at-risk/overdue), assigned agent
  - SLA compliance: response time vs target, delivery time vs target, uptime vs target
  - Churn risk indicator: low/medium/high with contributing factors
  - Communication log: last 10 interactions (date, channel, summary)
  - Upsell opportunities: detected by Amira, with revenue estimate
- **Bottom bar:** Portfolio summary — total clients, avg health score, total MRR, overdue deliverables count, upcoming renewals (next 30 days)

### View 8: Content Calendar

**Purpose:** See what content is scheduled, published, and performing across platforms.

**Layout:**
- **Calendar view (center):** 7-day forward view, each day as a column. Content items as cards within each day's column. Each card shows: time, platform icon (LinkedIn/TikTok/Instagram/Twitter/YouTube), title preview (20 chars), status badge (draft/scheduled/published), generating agent (Zara/Yasmin)
- **Content detail (click card):** Full content preview, platform, scheduled time, generating skill (e.g., cnt-01-viral-hook-generator), approval status, engagement metrics (if published: views, likes, comments, shares)
- **Right sidebar:** Platform summary — per-platform post count this week, top performing post, engagement rate trend
- **Top actions:** "Schedule Post" button (triggers Zara's content calendar skill), "View All Published" toggle, platform filter checkboxes
- **Bottom:** Content pipeline — draft queue showing content generated but not yet scheduled (from cnt-* skill outputs)

### View 9: Alerts & Notifications

**Purpose:** Unified alert feed from all MA systems. Don't miss critical issues.

**Layout:**
- **Full-width alert feed:** Reverse-chronological list. Each alert shows:
  - Severity badge (critical=red, warn=yellow, info=blue)
  - Source system (MA-6 Cost, MA-8 Behavior, MA-14 Health, MA-16 Approval, etc.)
  - Alert message (1-2 sentences)
  - Timestamp
  - Agent involved (if applicable, with avatar)
  - Actions: Dismiss, Snooze (1h/4h/24h), View Details
- **Top filter bar:** Filter by severity, source system, agent, date range. "Show dismissed" toggle.
- **Right summary panel:**
  - Alert counts by severity (critical/warn/info)
  - Most-alerting system today
  - Most-alerting agent today
  - Alert trend (more/fewer than yesterday)
- **Auto-scroll:** New alerts animate in at top. Audio chime for critical alerts (configurable).
- **WebSocket powered:** Receives from `/ws/alerts` channel in real-time.

### View 10: System Health (MA-14)

**Purpose:** Deep dive into the 12 health domains.

**Layout:**
- **Top:** Composite health score — large number (0-100) with color ring. Trend arrow (improving/declining/stable).
- **Grid (3x4):** 12 domain cards, one per health domain. Each card shows:
  - Domain name (infrastructure, agents, memory, messaging, decisions, tasks, interactions, recovery, conflicts, reviews, learning, browser)
  - RAG status dot (red <30%, amber 30-60%, green >60%)
  - Score as percentage
  - Weight badge (how much this domain affects composite)
  - Last checked timestamp
  - Trend arrow vs 24h ago
- **Click domain to expand:** Drill-down panel showing:
  - Score history chart (24h line)
  - Contributing metrics (what's pulling score up/down)
  - Active alerts for this domain
  - Recommended actions
- **Bottom:** Health snapshot timeline — sparkline showing composite score over last 7 days with notable events marked

### View 11: Decision Log Viewer (MA-4)

**Purpose:** Audit trail of every decision every agent has made.

**Layout:**
- **Top bar:** Search (full-text across title, context, rationale), Filter by agent (dropdown), Filter by status (proposed/debated/decided/executing/evaluated/learned), Date range picker
- **Main table:** Columns — Timestamp, Agent (avatar+name), Title, Status (badge), Confidence (0-1 bar), Reversibility (icon), Cost Impact, Outcome Score (if evaluated)
- **Click row to expand:** Full decision record:
  - Context: what triggered this decision
  - Options considered: bullet list with pros/cons
  - Final decision + rationale
  - Dependencies: linked decision IDs (clickable)
  - Expected vs actual outcome (if evaluated)
  - Lessons extracted (if learned)
- **Right panel:** Decision stats — total decisions today, avg confidence, most-deciding agent, decisions by status (pie chart)
- **Export:** CSV download button for filtered results

### View 12: Approval Queue (MA-16)

**Purpose:** Approve, reject, or modify pending human-in-the-loop requests.

**Layout:**
- **Top metrics (3 cards):** Pending (count, red if >3), Approved Today (count), Avg Response Time (minutes)
- **Pending queue (main):** List of pending approvals, sorted by expiry (soonest first). Each item shows:
  - Category badge (cost_override, circuit_breaker, behavior_escalation, lesson_approval, quality_escalation, decision_review)
  - Requesting agent (avatar + name)
  - Description (2-3 sentences of what needs approval)
  - Risk score (low/medium/high/critical color-coded)
  - Expiry countdown timer (e.g., "Expires in 3h 21m")
  - **Action buttons:** Approve (green), Reject (red), Modify (yellow, opens edit dialog), Defer (gray)
- **Below pending:** History tab — past approvals with outcome (approved/rejected/expired), response time, who approved, impact assessment
- **Auto-expire warning:** Items within 1h of expiry get pulsing red border + notification sound

### View 13: Global Kill Switch

**Purpose:** Emergency controls. Stop the system safely.

**Layout:**
- **Center panel (prominent):**
  - **SYSTEM HALT** button — large red button with confirmation dialog ("Are you sure? This will stop ALL agent activity."). Requires double-click or type "HALT" confirmation.
  - Current system mode: NORMAL / SAFE MODE / HALTED (large status indicator)
  - **Safe Mode toggle** — disables all external actions (web browsing, email sending, social posting, API calls to third parties) but keeps internal processing running.
- **Agent controls (grid below):**
  - 11 toggle switches, one per agent. Each shows: agent avatar, name, current status, pause/resume toggle.
  - "Pause All" and "Resume All" buttons
  - Paused agents show grayed-out card with "PAUSED" overlay
- **Circuit breaker panel:**
  - Per-provider circuit breaker status (Anthropic/OpenAI/Google)
  - Manual override buttons: Force OPEN (stop all calls), Force CLOSED (resume), Reset
- **Audit log:** Last 10 kill switch / safe mode / agent pause actions with timestamp and who triggered

---

## 3. Data Sources Mapping

| View | REST Endpoints | WebSocket | New Endpoints Needed | Update Strategy |
|------|---------------|-----------|---------------------|-----------------|
| **1. Command Overview** | `GET /api/state`, `GET /api/brain/status`, `GET /api/execution/queue` | `/ws/state` (10s), `/ws/alerts` | None | Push (WS) + poll health every 30s |
| **2. Agent Monitor** | `GET /api/state/agents`, `GET /api/agents/{id}/activity`, `GET /api/agents/workload` | `/ws/state` | `GET /api/agents/{id}/performance` (MA-12 data) | Push (WS) for status, poll performance every 60s |
| **3. Execution Console** | `GET /api/execution/queue`, `GET /api/execution/history`, `GET /api/execution/dead-letter`, `GET /api/execution/{id}` | `/ws/state` | None — existing endpoints sufficient | Push for running, poll history every 15s |
| **4. Revenue Pipeline** | `GET /api/revenue/pipeline`, `GET /api/revenue/forecast`, `GET /api/revenue/attribution`, `GET /api/revenue/catalog` | None (poll) | `GET /api/revenue/mrr-history` (MRR over time), `GET /api/revenue/invoices` | Poll every 60s |
| **5. Cost Burn** | `GET /api/state/budget`, `GET /api/ops/budget` | `/ws/state` | `GET /api/budget/daily-history` (30-day cost series), `GET /api/budget/by-agent`, `GET /api/budget/by-family` | Push budget via WS, poll history every 5min |
| **6. Task Queue** | `GET /api/execution/queue`, `GET /api/execution/history`, `GET /api/infrastructure/queue/status` | `/ws/state` | `GET /api/execution/throughput` (tasks/hr series), `GET /api/execution/failure-analysis` | Push queue depth via WS, poll charts every 30s |
| **7. Client View** | `GET /api/clients`, `GET /api/clients/{id}`, `GET /api/clients/{id}/deliverables`, `GET /api/lifecycle/health` | None | `GET /api/clients/{id}/health-score`, `GET /api/clients/{id}/churn-risk` | Poll every 60s |
| **8. Content Calendar** | None directly | None | `GET /api/content/calendar` (7-day), `GET /api/content/drafts`, `GET /api/content/{id}/metrics`, `POST /api/content/schedule` | Poll every 60s |
| **9. Alerts** | `GET /api/engine/alerts` | `/ws/alerts` | None — existing alert channel sufficient | Push via WS (real-time) |
| **10. System Health** | `GET /api/state/health` | `/ws/state` | `GET /api/health/history` (7-day snapshots), `GET /api/health/{domain}/details` | Push composite via WS, poll details on drill-down |
| **11. Decision Log** | `GET /api/autonomous/decision-log` | None | `GET /api/decisions/search` (full-text), `GET /api/decisions/stats`, `GET /api/decisions/export` | Poll on view load + manual refresh |
| **12. Approval Queue** | `GET /api/approvals/queue`, `POST /api/approvals/{id}/approve`, `POST /api/approvals/{id}/reject` | `/ws/alerts` (approval notifications) | None — existing endpoints sufficient | Push new approvals via WS, poll queue every 30s |
| **13. Kill Switch** | `POST /api/agents/{id}/stop`, `POST /api/agents/stop-all`, `GET /api/engine/status` | `/ws/state` | `POST /api/system/halt`, `POST /api/system/safe-mode`, `GET /api/system/kill-switch-log` | Push status via WS, actions are immediate POST |

**New endpoints needed: 14** (across revenue, budget, content, health, decisions, system)

---

## 4. Tech Stack Recommendation

### Keep Current Stack: Next.js 14 + React 18 + Zustand + Tailwind CSS

**Rationale:**
- All 13 views are achievable with current stack
- Zustand handles this complexity well (13 slices is manageable, not excessive)
- No need for Redux/Jotai overhead — Zustand's simplicity is an advantage
- Tailwind provides all layout/styling primitives needed
- Next.js SSR not critical (this is a real-time dashboard, CSR is fine)

### Add These Libraries

| Library | Purpose | Size | Why |
|---------|---------|------|-----|
| **@tanstack/react-table v8** | Data tables (execution log, decision log, invoices) | 14KB | Headless, works with Tailwind, sorting/filtering/pagination built-in |
| **recharts** | Charts (cost burn, throughput, health history, revenue attribution) | 130KB | React-native, composable, works with Tailwind colors |
| **@radix-ui/react-dialog + @radix-ui/react-dropdown-menu + @radix-ui/react-toggle** | Accessible primitives for modals, dropdowns, toggles | ~20KB total | Unstyled, Tailwind-friendly, handles keyboard/focus |
| **date-fns** | Date formatting and relative time | 12KB (tree-shaken) | Lightweight alternative to moment/dayjs |
| **react-hot-toast** | Toast notifications for alerts, approvals | 5KB | Minimal, configurable, works with Tailwind |

**Total addition: ~181KB** (gzipped ~60KB). Minimal impact.

### NOT Recommended
- **shadcn/ui**: Good library but would require restructuring all existing components. Not worth the migration cost.
- **Chart.js**: Less React-native than Recharts. More configuration overhead.
- **AG-Grid**: Overkill for our table sizes (max ~500 rows). TanStack Table is sufficient and much lighter.
- **Redux/Jotai**: Zustand is working fine. Migration cost isn't justified.

---

## 5. Component List

### View 1: Command Overview
| Component | Purpose | Props | Store Slice |
|-----------|---------|-------|-------------|
| `OverviewMetricsRow` | 4 top metric cards (agents, skills, revenue, approvals) | None (reads store) | systemState, revenue, approvals |
| `ActivityFeed` | Chronological agent activity stream | maxItems: number | activityFeed (new slice) |
| `HealthRing` | Donut chart of 12 health domains | size: number | systemState.health |
| `ActiveExecutions` | Compact running skills table | maxRows: number | execution |
| `BrainInsightCard` | Latest brain auto-insight | None | brainMessages |
| `CostBurnFooter` | Cost summary bar at bottom | None | systemState.budget |

### View 2: Agent Monitor
| Component | Purpose | Props | Store Slice |
|-----------|---------|-------|-------------|
| `AgentGrid` | Grid layout of 11 agent cards | sortBy, filterLevel | agents |
| `AgentCard` | Individual agent status card | agent: AgentInfo | agents, performance |
| `AgentDetailPanel` | Expanded agent view with radar chart | agentId: string | agents, performance |
| `PerformanceRadar` | 6-dimension radar chart | dimensions: Record<string, number> | performance |

### View 3: Execution Console
| Component | Purpose | Props | Store Slice |
|-----------|---------|-------|-------------|
| `ExecutionTable` | Main sortable/filterable execution log | filters: ExecutionFilters | execution |
| `ExecutionDetail` | Expanded row with full envelope JSON | executionId: string | execution |
| `ExecutionFilters` | Filter bar (agent, family, status, date) | onChange: callback | execution |
| `QueueDepthGauge` | Real-time queue depth indicator | None | execution |
| `DeadLetterQueue` | Dead letter summary with retry buttons | None | execution |

### View 4: Revenue Pipeline
| Component | Purpose | Props | Store Slice |
|-----------|---------|-------|-------------|
| `RevenueMetrics` | Top 5 revenue KPI cards | None | revenue |
| `PipelineKanban` | Drag-drop deal pipeline board | None | revenue.pipeline |
| `InvoiceTable` | Invoice list with status badges | None | revenue.invoices |
| `RevenueChart` | Stacked bar chart by source | period: '6m' | '12m' | revenue.attribution |
| `SubscriptionTracker` | Lemon Squeezy sub count + MRR | None | revenue.subscriptions |

### View 5: Cost Burn
| Component | Purpose | Props | Store Slice |
|-----------|---------|-------|-------------|
| `ProviderGauge` | Circular gauge per provider | provider: ProviderBudget | systemState.budget |
| `CircuitBreakerStatus` | Traffic light for circuit breaker | None | costGovernor |
| `DailyBurnChart` | 30-day line chart per provider | None | budget.history |
| `CostByAgentTable` | Agent cost ranking table | None | budget.byAgent |
| `CostByFamilyTable` | Skill family cost ranking | None | budget.byFamily |
| `BudgetProjection` | Month-end spend projection | None | budget |

### View 6: Task Queue
| Component | Purpose | Props | Store Slice |
|-----------|---------|-------|-------------|
| `ThroughputMetrics` | 4 top KPI cards | None | execution |
| `TasksPerHourChart` | Stacked bar chart over 24h | None | execution.throughput |
| `ExecutionTimeTable` | Skill family avg/p95 times | None | execution |
| `TaskTreeViewer` | MA-5 goal decomposition tree | workflowId: string | execution |
| `FailureAnalysis` | Top 5 failing skills panel | None | execution |

### View 7: Client View
| Component | Purpose | Props | Store Slice |
|-----------|---------|-------|-------------|
| `ClientList` | Scrollable client list with health badges | None | clients |
| `ClientDetail` | Full client expanded view | clientId: string | clients |
| `HealthBreakdown` | Client health score breakdown | scores: HealthScores | clients |
| `DeliverableTable` | Client deliverables with status | clientId: string | clients |
| `ChurnRiskIndicator` | Churn risk level + factors | risk: ChurnRisk | clients |
| `PortfolioSummary` | Bottom bar portfolio stats | None | clients |

### View 8: Content Calendar
| Component | Purpose | Props | Store Slice |
|-----------|---------|-------|-------------|
| `CalendarWeekView` | 7-day column layout | startDate: Date | content |
| `ContentCard` | Individual content item card | content: ContentItem | content |
| `ContentDetail` | Full content preview modal | contentId: string | content |
| `PlatformSummary` | Per-platform stats sidebar | None | content |
| `DraftQueue` | Unpublished content pipeline | None | content |

### View 9: Alerts
| Component | Purpose | Props | Store Slice |
|-----------|---------|-------|-------------|
| `AlertFeed` | Full-width alert stream | filters: AlertFilters | alerts |
| `AlertItem` | Individual alert with actions | alert: Alert | alerts |
| `AlertFilters` | Filter bar for alerts | onChange: callback | alerts |
| `AlertSummary` | Right panel counts + trends | None | alerts |

### View 10: System Health
| Component | Purpose | Props | Store Slice |
|-----------|---------|-------|-------------|
| `CompositeScore` | Large composite health number + ring | None | systemState.health |
| `HealthDomainGrid` | 3x4 grid of domain cards | None | systemState.health |
| `HealthDomainCard` | Individual domain card | domain: HealthDomain | systemState.health |
| `HealthDrilldown` | Expanded domain detail panel | domainId: string | health |
| `HealthTimeline` | 7-day composite sparkline | None | health.history |

### View 11: Decision Log
| Component | Purpose | Props | Store Slice |
|-----------|---------|-------|-------------|
| `DecisionTable` | Searchable/filterable decision log | None | decisions |
| `DecisionDetail` | Expanded decision record | decisionId: string | decisions |
| `DecisionFilters` | Search + agent + status + date filters | onChange: callback | decisions |
| `DecisionStats` | Right panel decision statistics | None | decisions |

### View 12: Approval Queue
| Component | Purpose | Props | Store Slice |
|-----------|---------|-------|-------------|
| `ApprovalMetrics` | Top 3 KPI cards | None | approvals |
| `PendingQueue` | Pending approvals list with actions | None | approvals |
| `ApprovalItem` | Individual approval with approve/reject | approval: Approval | approvals |
| `ApprovalHistory` | Past approvals with outcomes | None | approvals |

### View 13: Kill Switch
| Component | Purpose | Props | Store Slice |
|-----------|---------|-------|-------------|
| `SystemHaltButton` | Large red emergency stop | None | system |
| `SystemModeIndicator` | NORMAL/SAFE/HALTED status | None | system |
| `SafeModeToggle` | Toggle external actions | None | system |
| `AgentToggleGrid` | 11 agent pause/resume switches | None | agents |
| `CircuitBreakerControls` | Per-provider manual override | None | costGovernor |
| `KillSwitchLog` | Last 10 control actions | None | system |

**Total: 72 components** (many are small, focused components)

---

## 6. State Management Approach

### New Zustand Slices

```
AppStore (expanded):
  // Existing
  systemState         — full SystemState from backend
  wsStatus            — WebSocket connection status
  brainMessages       — AI chat history
  activeTab           — current navigation tab

  // New slices
  execution: {
    queue             — ExecutionRequest[]
    history           — TaskExecution[]
    deadLetter        — DeadLetterEntry[]
    throughput        — { hour: string, completed: number, failed: number }[]
    isLoading         — boolean
  }

  revenue: {
    pipeline          — { stage: string, deals: Deal[] }[]
    mrr               — number
    mrrHistory        — { date: string, mrr: number }[]
    invoices          — Invoice[]
    attribution       — { source: string, amount: number }[]
    subscriptions     — { active: number, mrr: number, churn: number }
  }

  clients: {
    list              — Client[]
    selectedId        — string | null
    deliverables      — Record<string, Deliverable[]>
    healthScores      — Record<string, HealthScores>
  }

  approvals: {
    pending           — Approval[]
    history           — ApprovalHistory[]
    stats             — { pending: number, approvedToday: number, avgResponseMin: number }
  }

  alerts: {
    feed              — Alert[]
    unreadCount       — number
    filters           — AlertFilters
  }

  content: {
    calendar          — ContentItem[]
    drafts            — ContentItem[]
    platforms         — Record<string, PlatformStats>
  }

  health: {
    history           — { timestamp: string, composite: number }[]
    domainDetails     — Record<string, DomainDetail>
  }

  decisions: {
    log               — Decision[]
    stats             — DecisionStats
    filters           — DecisionFilters
  }

  budget: {
    dailyHistory      — { date: string, anthropic: number, openai: number, google: number }[]
    byAgent           — { agent: string, cost: number, calls: number }[]
    byFamily          — { family: string, cost: number, executions: number }[]
  }

  performance: {
    agents            — Record<string, AgentPerformance>
    leaderboard       — LeaderboardEntry[]
    employeeOfMonth   — { agentId: string, score: number, month: string } | null
  }

  system: {
    mode              — 'normal' | 'safe' | 'halted'
    agentStates       — Record<string, 'running' | 'paused'>
    circuitBreakers   — Record<string, 'closed' | 'open' | 'half_open'>
    killSwitchLog     — KillSwitchEntry[]
  }

  activityFeed: {
    items             — ActivityItem[]
    isLoading         — boolean
  }
```

### Derived Selectors (Computed)
- `totalPendingApprovals` — approvals.pending.length
- `criticalAlertCount` — alerts.feed.filter(a => a.severity === 'critical' && !a.dismissed).length
- `systemHealthColor` — derived from systemState.health.overall (green/yellow/red)
- `todayCostTotal` — sum of budget providers' spent today
- `topPerformingAgent` — highest composite score from performance.leaderboard
- `overdueDeliverables` — clients.deliverables filtered by dueDate < now && status !== 'completed'

### WebSocket Subscription Model
- `/ws/state` updates → systemState, execution.queue, budget (every 10s)
- `/ws/alerts` updates → alerts.feed, approvals.pending (real-time push)
- `/ws/chat` updates → brainMessages (on message)

### Optimistic Updates
- **Approve/Reject:** Remove from pending immediately, add to history. Revert on API error.
- **Agent Pause/Resume:** Toggle UI state immediately. Revert on API error.
- **Deal Stage Advance:** Move kanban card immediately. Revert on API error.
- **Alert Dismiss/Snooze:** Remove from feed immediately. Revert on API error.

---

## 7. Implementation Phases

### P0 — Foundation (must-have for go-live)

**Goal:** Owner can monitor system in real-time and intervene if needed.

**Views:** 1 (Command Overview), 2 (Agent Monitor), 5 (Cost Burn), 9 (Alerts), 10 (System Health), 12 (Approval Queue), 13 (Kill Switch)

**Components:** 32 (from views above)

**New endpoints:** 3 (`GET /api/budget/daily-history`, `GET /api/agents/{id}/performance`, `POST /api/system/halt`)

**New store slices:** alerts, performance, system, budget.dailyHistory

**Libraries to add:** recharts, @radix-ui/react-dialog, react-hot-toast

**Estimated effort:** 3-5 days

### P1 — Revenue Visibility

**Goal:** Owner can track money in and money out.

**Views:** 3 (Execution Console), 4 (Revenue Pipeline), 6 (Task Queue)

**Components:** 22 (from views above)

**New endpoints:** 5 (`GET /api/revenue/mrr-history`, `GET /api/revenue/invoices`, `GET /api/budget/by-agent`, `GET /api/budget/by-family`, `GET /api/execution/throughput`)

**New store slices:** revenue, execution (expanded)

**Libraries to add:** @tanstack/react-table, date-fns

**Estimated effort:** 3-5 days

### P2 — Autonomous Operations

**Goal:** Owner only needs to check in weekly. System runs itself.

**Views:** 7 (Client View), 8 (Content Calendar), 11 (Decision Log)

**Components:** 18 (from views above)

**New endpoints:** 6 (`GET /api/clients/{id}/health-score`, `GET /api/clients/{id}/churn-risk`, `GET /api/content/calendar`, `GET /api/content/drafts`, `GET /api/decisions/search`, `GET /api/decisions/export`)

**New store slices:** clients (expanded), content, decisions

**Libraries to add:** None additional

**Estimated effort:** 3-5 days

### Phase Summary

| Phase | Views | Components | New Endpoints | Libraries | Days |
|-------|-------|------------|---------------|-----------|------|
| P0 Foundation | 7 | 32 | 3 | recharts, radix, toast | 3-5 |
| P1 Revenue | 3 | 22 | 5 | tanstack-table, date-fns | 3-5 |
| P2 Autonomous | 3 | 18 | 6 | None | 3-5 |
| **Total** | **13** | **72** | **14** | **5 packages** | **9-15** |

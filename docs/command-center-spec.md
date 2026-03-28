# NemoClaw Command Center — Architecture Spec v2

The complete web interface for operating the NemoClaw AI company.
Not a dashboard — a full operating system UI with autonomous intelligence.

**Status**: Spec v2 — incorporates external review (9.2/10 score, 8 improvements accepted)
**Estimated build**: 10 phases across multiple sessions
**Stack**: Next.js + React + Tailwind + shadcn/ui + FastAPI + WebSocket

---

## Critical Architecture Additions (from review)

### Addition 1: AI Company Brain (Always-Visible Intelligence Layer)

Not a tab — a persistent sidebar/overlay that sits above all tabs.

**What it does**:
- Continuously interprets system state across all 20 MA systems
- Generates natural language situation reports
- Detects risks before they become failures
- Recommends specific actions with one-click execution
- Explains causality ("X failed because Y was degraded")

**Example auto-generated output**:
```
SITUATION: 2 agents degraded due to PinchTab latency.
IMPACT: Browser-dependent skills (k50-k54) at risk.
CAUSE: 3 Chrome instances consuming 900MB (limit: 1024MB).
ACTION: Reduce to 2 instances. [Execute] [Dismiss]

SITUATION: Budget burn rate increased 40% today.
CAUSE: 12 premium skill runs by growth_revenue_lead.
FORECAST: Anthropic budget exhausted in 8 days at this rate.
ACTION: Switch 4 non-critical skills to moderate routing. [Execute] [Dismiss]

PENDING: 3 approvals blocking task execution (oldest: 4h).
ACTION: Review approvals. [Go to Approvals]
```

**Data sources**: MA-14 (health), MA-6 (cost), MA-8 (behavior), MA-12 (performance), MA-16 (approvals), MA-9 (failures), MA-13 (learning)

**Implementation**: LLM call (via existing routing) that reads aggregated system state and produces structured recommendations. Runs every 5 minutes or on-demand.

### Addition 2: State Aggregation Layer

FastAPI does NOT read raw files per request. Instead:

```
~/.nemoclaw/ files → State Aggregator (background process)
                          ↓
                    Normalized Cache (in-memory)
                          ↓
                    FastAPI REST + WebSocket
                          ↓
                    Next.js Frontend
```

**State Aggregator responsibilities**:
- Read all MA system state files every 10 seconds
- Normalize timestamps, agent IDs, status values
- Resolve conflicts (latest-write-wins)
- Compute derived metrics (burn rate, capacity, trends)
- Cache computed views (health summary, agent status, cost breakdown)
- Emit WebSocket events on state changes

**Why this matters**: Without it, 12 tabs hitting raw files creates race conditions, partial reads, and UI inconsistency.

### Addition 3: Replay & Time Travel

**Replay System**:
- State snapshots saved every 5 minutes (MA-14 already does this)
- Event timeline: every MA system action logged with timestamp
- Timeline scrubber: drag to any point in time, see system state at that moment
- "What happened?" query: select time range, get narrative summary (via Brain)
- Diff view: compare two snapshots to see what changed

**Where it lives**: Available from Intelligence tab + accessible via Brain ("what happened yesterday?")

---

## Updated Interface Architecture

```
NemoClaw Command Center
│
├── 🧠 AI Brain (persistent sidebar — always visible)
│   ├── Situation Summary
│   ├── Risk Alerts
│   ├── Recommended Actions (one-click)
│   ├── Causal Explanations
│   └── "Ask the Brain" natural language query
│
├── 🏠 Home (System Overview)
├── 💬 Communications (classified message lanes)
│   ├── Chat Lane (agent conversations)
│   ├── Decision Lane (proposals + votes)
│   ├── Alert Lane (sticky top, auto-pinned)
│   ├── Task Lane (execution updates)
│   ├── Approval Lane (interactive approve/reject)
│   ├── Group Channels
│   ├── Direct Messages
│   └── Conversation → Outcome Linking
├── 👥 Agents (HR)
│   ├── Agent Roster + Org Chart
│   ├── Performance Reviews
│   ├── Capacity & Load Modeling
│   ├── Hire / Fire / Reassign
│   └── Compliance Dashboard
├── ⚡ Skills
│   ├── Built Skills (30) with dependency maps
│   ├── Registered Skills (15)
│   ├── Execution Console
│   ├── Skill Factory
│   └── Skill → Tool → MCP dependency graph
├── 🔧 Tools & Integrations
│   ├── Connected Tools (health grid)
│   ├── API Key Vault
│   ├── Bridge Health + Error Rates
│   ├── MCP Servers
│   └── PinchTab Control Panel
├── 📊 Operations
│   ├── Task Plans (active/completed/failed)
│   ├── Cost Governance (active governor, not passive)
│   ├── Budget Management
│   ├── Circuit Breaker Controls
│   └── Auto-Throttle Rules
├── 🏗️ Project Builder
│   ├── Build Timeline (visual)
│   ├── Live Execution Graph (DAG)
│   ├── Phase Tracker
│   ├── GitHub Commit History
│   ├── Architecture Diagram (interactive)
│   └── Decision Records
├── 📋 Client Projects
│   ├── Project Tracking
│   ├── Timeline & Milestones
│   ├── Deliverables
│   ├── Billing & Invoicing
│   └── Client Communication Log
├── ✅ Approvals
│   ├── Pending (approve/reject/defer)
│   ├── History + Impact Tracking
│   ├── Rules & Delegation
│   └── Bulk Actions
├── 🧠 Intelligence
│   ├── System Health (12 domains)
│   ├── Learning Loop
│   ├── Conflict & Recovery
│   ├── Security Audit
│   ├── Anomaly Detection
│   └── Replay & Time Travel
├── 💰 Finance
│   ├── LLM Provider Spend
│   ├── External Tool Costs
│   ├── Revenue Dashboard
│   ├── Credit Top-Up
│   ├── Budget Forecasting
│   └── Autonomous Cost Control (suggestions + auto-actions)
└── ⚙️ Settings
    ├── System Configuration
    ├── Notifications
    ├── Theme & Display
    ├── Backup & Recovery
    └── API & Access Tokens
```

---

## Updated Communications (Message Classification)

### Message Types (system-level classification)

| Type | Rendering | Behavior |
|---|---|---|
| **chat** | WhatsApp-style bubble | Normal conversation, reactions, threads |
| **decision** | Structured card with vote buttons | Votable, tracks outcome, links to MA-4 |
| **alert** | Red/yellow banner, sticky top | Auto-pinned, dismissable, links to source |
| **task** | Progress card with status bar | Links to task plan, shows completion |
| **approval** | Interactive card with approve/reject | Countdown timer, links to MA-16 |
| **system** | Collapsed by default, gray | Expandable, non-human logs |

### Message Lanes (filterable views)

Default view shows all lanes interleaved (WhatsApp-style). User can:
- Filter to single lane (e.g., "show only decisions")
- Pin lanes to always-visible
- Set default lane per channel (e.g., #alerts = alert lane only)

### Conversation → Outcome Linking

Every message can link to:
- Decision it triggered → MA-4 decision record
- Task it spawned → MA-5 task plan
- Skill it executed → skill run result
- Approval it requested → MA-16 approval record
- Cost it incurred → MA-6 cost entry

Click any message → see its full impact chain.

---

## Updated HR: Capacity & Load Modeling

### Capacity Model

Each agent has:
- **Capacity units**: tasks/hour they can handle (derived from MA-12 historical data)
- **Current load**: active tasks / capacity = utilization %
- **Queue depth**: tasks waiting for this agent

### Load Dashboard

```
Agent                 Utilization    Queue    Status
strategy_lead         ████░░░░░░ 40%   2      🟢 Normal
growth_revenue_lead   ████████░░ 80%   5      🟡 Heavy
product_delivery_lead ██░░░░░░░░ 20%   0      🟢 Light
narrative_content_lead████████████ 120%  8      🔴 Overloaded
engineering_lead      ██████░░░░ 60%   3      🟢 Normal
operations_systems_lead███░░░░░░░ 30%   1      🟢 Light
quality_validation_lead█████░░░░░ 50%   2      🟢 Normal
```

### Overload Actions (auto-suggested by Brain)
- Reassign tasks to underloaded agents
- Queue non-urgent tasks
- Trigger internal competition (MA-18) for overloaded agent's tasks
- Escalate to human if critical tasks are blocked

---

## Updated Skills: Dependency Mapping

### Skill Dependency Graph

Click any skill → see:

```
k40-deal-qualifier
├── Uses Provider: Anthropic (premium alias → Claude Opus)
├── Uses Framework: FW-001 (MEDDPICC)
├── Feeds Into: k43-pipeline-analyzer, k47-account-expansion-planner, h30-cold-email-writer
├── Accepts From: c09-market-analyst, j36-biz-idea-validator
├── Estimated Cost: $0.12-0.15 per run
├── Avg Quality: 8.2/10 (last 20 runs)
├── Failure Rate: 3% (last 30 days)
└── Risk: None currently
```

For web-aware skills, additionally:

```
k51-competitor-scraper
├── Uses Provider: Anthropic (premium)
├── Uses PinchTab: navigate, snapshot, text, click
├── Uses Bridge: web_browser.py
├── External Dependency: Target website availability
├── Rate Limits: 100 nav/hr, 50 clicks/task
├── Risk: 🟡 Target site may block automated access
└── MA-8 Rules: web_never_submit_payment, web_screenshot_before_submit
```

### Dependency Health View

Visual graph (D3 force-directed):
- Nodes = skills, tools, providers, bridges
- Edges = dependencies
- Color = health (green/yellow/red)
- Click node → detail panel
- Hover edge → see data flow

---

## Updated Finance: Autonomous Cost Control

### Active Governor (not passive reporting)

The finance tab doesn't just show spend — it actively controls it:

| Control | Trigger | Action |
|---|---|---|
| Auto-throttle | Agent exceeds 80% of daily budget | Switch to moderate routing |
| Provider fallback | Primary provider at 90% budget | Route to cheaper alternative |
| Task deferral | Non-critical tasks when budget tight | Queue for next budget period |
| Alert escalation | Burn rate → budget exhaustion in <3 days | Notify via Brain + approval request |
| Skill cost cap | Individual skill run > $0.20 | Require approval |

### Cost Control Rules (configurable)
```yaml
cost_controls:
  auto_throttle:
    enabled: true
    trigger: agent_daily_spend > 80%
    action: switch_to_moderate_routing
  
  provider_fallback:
    enabled: true
    trigger: provider_budget > 90%
    action: route_to_cheapest_available
  
  task_deferral:
    enabled: true
    trigger: total_budget > 85%
    action: queue_non_critical_tasks
    
  skill_cost_cap:
    enabled: true
    max_per_run: 0.20
    action: require_approval
```

---

## Updated Project Builder: Execution Graph

### Live DAG (Directed Acyclic Graph)

Not just a timeline — a live graph of work being executed:

```
[Market Research] ──→ [Biz Validation] ──→ [MVP Scope]
       │                     │                  │
       ↓                     ↓                  ↓
[Comp Intel] ──→ [Pricing Strategy] ──→ [Product Req]
                                              │
                                              ↓
                                    [Arch Spec] ──→ [Implementation]
```

**Node states**:
- ⚪ Pending (not started)
- 🔵 Running (in progress)
- 🟢 Complete
- 🔴 Failed
- 🟡 Blocked (waiting on dependency)

**Node details on click**:
- Assigned agent
- Skill being used
- Current step (step 1/2/3/4/5)
- Quality score (if complete)
- Cost
- Duration
- Errors (if failed)

**Real-time updates**: Nodes change color as tasks execute. WebSocket pushes status changes.

---

## Updated Build Phases

### Phase CC-1: Foundation + State Aggregator
- FastAPI server with state aggregation layer
- Background state reader (10-second cycle)
- Normalized cache with computed views
- WebSocket server for real-time pushes
- Next.js scaffold with navigation shell
- Home tab (system overview from cached state)
- Basic local auth (token)
- Health endpoint for self-monitoring

### Phase CC-2: AI Company Brain
- LLM-powered situation analysis (runs every 5 min)
- Persistent sidebar component
- Risk detection rules
- Action recommendations with one-click execution
- "Ask the Brain" natural language query
- Causal explanation generation

### Phase CC-3: Communications
- WhatsApp-style chat interface
- Message type classification (6 types)
- Message lanes with filtering
- Group channels + direct messages
- Conversation → Outcome linking
- Real-time via WebSocket
- Search across all conversations

### Phase CC-4: Agents (HR)
- Agent roster with cards + org chart
- Agent detail page with performance radar
- Capacity & load modeling
- Hire/fire/reassign workflows
- Compliance dashboard
- Overload detection + auto-suggestions

### Phase CC-5: Skills & Tools
- Skills table with execution console
- Skill → Tool → MCP dependency graph (D3)
- Skill factory wizard
- Tools health grid
- API key vault (masked)
- PinchTab control panel

### Phase CC-6: Operations + Finance
- Task plan monitor with DAG view
- Cost governance (active governor)
- Autonomous cost control rules
- Budget management
- Circuit breaker controls
- Provider spend charts
- Revenue dashboard (when Lemon Squeezy connected)
- Budget forecasting

### Phase CC-7: Project Builder
- Build timeline visualization
- Live execution graph (DAG)
- Phase tracker with completion %
- GitHub commit integration
- Interactive architecture diagram
- Decision records browser

### Phase CC-8: Client Projects
- Project CRUD + timeline
- Deliverables tracking
- Client communication log
- Billing & invoicing
- Client satisfaction metrics

### Phase CC-9: Approvals + Intelligence
- Approval queue with inline actions
- Bulk approve/reject
- System health gauges (12 domains)
- Learning loop dashboard
- Security audit trail
- Replay & time travel system
- Anomaly detection alerts

### Phase CC-10: Settings + Polish
- Configuration editors (YAML)
- Notification preferences
- Theme (light/dark)
- Backup/recovery
- Mobile responsiveness
- Performance optimization
- Contextual search (cmd+K)

---

## Summary of Changes from v1

| Area | v1 | v2 (after review) |
|---|---|---|
| Intelligence | Passive observation | Active Brain (interprets, recommends, acts) |
| State management | Raw file reads | State Aggregation Layer (normalized cache) |
| Chat | Single stream | 6 message types, lanes, outcome linking |
| HR | Status display | Capacity modeling, overload detection |
| Skills/Tools | List view | Dependency graph (skill → tool → MCP → cost) |
| Finance | Passive reporting | Active governor (auto-throttle, fallback, deferral) |
| Project Builder | Timeline only | Timeline + live execution DAG |
| Time | Current state only | Replay + time travel + snapshot diffing |
| Navigation | Static tabs | Static tabs + contextual search (CC-10) |

---

## Repo Location

```
nemoclaw-local-foundation/
├── command-center/          # New — the web UI
│   ├── frontend/            # Next.js app
│   │   ├── app/             # App router pages
│   │   ├── components/      # Reusable UI components
│   │   ├── lib/             # API client, WebSocket, state
│   │   └── public/          # Static assets
│   ├── backend/             # FastAPI server
│   │   ├── api/             # REST endpoints
│   │   ├── aggregator/      # State aggregation layer
│   │   ├── brain/           # AI Company Brain
│   │   ├── websocket/       # Real-time events
│   │   └── main.py          # Server entry point
│   └── README.md            # Command Center docs
├── scripts/                 # Existing — MA systems + bridges
├── skills/                  # Existing — 30 skills
├── config/                  # Existing — configs
└── docs/                    # Existing — specs + catalogs
```

# NemoClaw Command Center — Phase CC-1

## What This Is

The Command Center foundation: FastAPI backend with a real-time state aggregation layer, WebSocket server, and a Next.js frontend with navigation shell and Home tab.

## Architecture

```
command-center/
├── start.sh                 # Launch both services
├── backend/
│   ├── run.py               # Entry point
│   ├── requirements.txt
│   └── app/
│       ├── main.py          # FastAPI app + WebSocket endpoint + lifecycle
│       ├── config.py        # Settings (env-driven, safe defaults)
│       ├── models.py        # Pydantic models (SystemState + all sub-models)
│       ├── auth.py          # Local token auth (auto-generated)
│       ├── state_aggregator.py  # Core: scans filesystem every 10s
│       ├── websocket_manager.py # Broadcasts state to all WS clients
│       └── routers/
│           ├── state.py     # GET /api/state/* + POST /api/state/refresh
│           └── health.py    # GET /api/health (unauthenticated probes)
└── frontend/
    ├── package.json
    ├── next.config.js       # Proxies /api/* to backend
    ├── tailwind.config.js   # NemoClaw dark theme
    └── src/
        ├── app/
        │   ├── layout.tsx
        │   ├── page.tsx     # Main shell: sidebar + active tab
        │   └── globals.css
        ├── components/
        │   ├── Sidebar.tsx      # 12-tab navigation (Home active, rest disabled)
        │   ├── HomeTab.tsx      # Full system overview dashboard
        │   └── StatusCard.tsx   # Reusable cards, bars, health dots
        ├── hooks/
        │   └── useWebSocket.ts  # Auto-reconnecting WS with state
        └── lib/
            ├── types.ts     # TypeScript types (mirrors backend)
            └── api.ts       # REST API client
```

## State Aggregator

The heart of CC-1. Runs as a background task inside FastAPI:

1. Every 10 seconds, scans `~/nemoclaw-local-foundation/` and `~/.nemoclaw/`
2. Reads skill.yaml files, agent configs, bridge scripts, budget config, test files
3. Normalizes everything into a single `SystemState` object
4. Caches in memory
5. WebSocket manager broadcasts to all connected clients every 10 seconds

### What It Scans

| Domain | Source | What It Reads |
|---|---|---|
| Skills | `skills/*/skill.yaml` | skill_id, family, provider, status |
| Registered Skills | `docs/skill-catalog-*.yaml` | Catalog entries |
| Agents | `config/agents/*.yaml` | agent_id, name, capabilities |
| MA Systems | `tests/test_ma_*.py` | Test function counts |
| Bridges | `scripts/*_bridge.py` | Bridge files + test counts |
| Budget | `config/budget-config.yaml` | Provider spend/limits |
| Validation | `~/.nemoclaw/last-validation.yaml` | Pass/warn/fail counts |
| Git | `.git/` | Branch + commit hash |
| PinchTab | `localhost:9867` | Socket reachability |

### Graceful Degradation

Every scanner catches exceptions individually. If a file is missing, malformed, or the directory doesn't exist, that domain returns empty/default data. The aggregator never crashes the server.

## API Endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/state` | Yes | Full SystemState |
| GET | `/api/state/skills` | Yes | Skills summary |
| GET | `/api/state/agents` | Yes | Agents summary |
| GET | `/api/state/ma-systems` | Yes | MA systems summary |
| GET | `/api/state/bridges` | Yes | Bridges summary |
| GET | `/api/state/budget` | Yes | Budget summary |
| GET | `/api/state/health` | Yes | Health domains |
| GET | `/api/state/validation` | Yes | Validation results |
| POST | `/api/state/refresh` | Yes | Force immediate rescan |
| GET | `/api/health` | No | Liveness probe |
| GET | `/api/health/ready` | No | Readiness probe |
| WS | `/ws?token=...` | Yes | Real-time state stream |

## Authentication

Local token auth, suitable for development:

1. On first run, a token is auto-generated at `~/.nemoclaw/cc-token`
2. The token is printed in the server startup log
3. Set `CC_AUTH_TOKEN` env var to override
4. Frontend stores token in localStorage

For local dev, unauthenticated WebSocket connections are allowed by default.

## Quick Start

### Option 1: Launch Script

```bash
chmod +x command-center/start.sh
./command-center/start.sh
```

### Option 2: Manual

**Backend:**
```bash
cd command-center/backend
source ~/.venv313/bin/activate
pip install -r requirements.txt --break-system-packages
python run.py --reload
```

**Frontend (separate terminal):**
```bash
cd command-center/frontend
npm install
npm run dev
```

### Access

- Dashboard: http://localhost:3000
- API docs: http://127.0.0.1:8100/docs
- Health: http://127.0.0.1:8100/api/health

## Home Tab

The Home tab displays:

- Overall health banner (pass/warn/fail from validation)
- 4-card metric grid: Skills (30 built + 15 registered), Agents (7), MA Systems (20/20), Frameworks (15)
- Bridges panel: all 10 bridges with status dots and test counts
- Budget panel: per-provider spend bars with color-coded thresholds
- Health domains: 9 domains with status and messages
- Skill families breakdown
- Git branch/commit + PinchTab status footer

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `CC_HOST` | `127.0.0.1` | Backend bind host |
| `CC_PORT` | `8100` | Backend bind port |
| `CC_AUTH_TOKEN` | (auto) | Override auth token |
| `CC_SCAN_INTERVAL_SECONDS` | `10` | Filesystem scan interval |
| `CC_REPO_ROOT` | `~/nemoclaw-local-foundation` | Path to repo |

## Next Phases

- **CC-2**: AI Brain (persistent sidebar, LLM calls against aggregated state)
- **CC-3**: Communications (WhatsApp-style with 6 message types)
- **CC-4**: Agents/HR (capacity & load modeling)
- **CC-5 → CC-10**: Skills, Ops, Projects, Clients, Approvals, Settings

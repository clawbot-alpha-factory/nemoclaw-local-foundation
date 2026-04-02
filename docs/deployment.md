# NemoClaw Deployment Guide

## Local Development

```bash
# Start backend (port 8100)
make backend

# Start frontend (port 3000)
make frontend

# Start both
make both

# Run validation
make validate

# Run integration tests
make test

# Run CI policy checks
make ci-check
```

## Docker Deployment

```bash
# Build images
docker compose build

# Start services
docker compose up -d

# Check health
curl http://localhost:8100/api/health
curl http://localhost:3000

# Stop
docker compose down
```

### Services
| Service | Port | Image |
|---------|------|-------|
| Backend (FastAPI) | 8100 | command-center/backend/Dockerfile |
| Frontend (Next.js) | 3000 | command-center/frontend/Dockerfile |

### Volumes
- `nemoclaw-data` → `/root/.nemoclaw` (checkpoints, logs, state)
- `./config` → `/app/config` (read-only, API keys + routing config)

## Monitoring

### Prometheus Metrics
```bash
curl http://localhost:8100/api/health/metrics
```

Exposed metrics (frozen names, stable contract):
- `nemoclaw_skills_built_total` — gauge
- `nemoclaw_agents_total` — gauge
- `nemoclaw_llm_cost_usd{provider="..."}` — gauge per provider
- `nemoclaw_provider_budget_remaining_usd{provider="..."}` — gauge per provider
- `nemoclaw_system_health_score` — gauge (1.0=healthy, 0.5=warning, 0.0=error)
- `nemoclaw_validation_passed` — gauge
- `nemoclaw_validation_failed` — gauge
- `nemoclaw_ws_clients` — gauge

### Structured JSON Logging (opt-in)
```bash
LOG_FORMAT=json make backend
```
When enabled, all log output is JSON. Default: plain text.

## Future Integration Points

### Error Tracking (Sentry)
Not yet implemented. Integration point:
- Add `sentry-sdk[fastapi]` to backend requirements
- Initialize in `command-center/backend/app/main.py` lifespan
- Set `SENTRY_DSN` in `config/.env`

### Task Queue Scaling (Redis)
Current task queue is in-memory (sufficient for local). To scale:
- Replace `task_queue_service.py` with Redis-backed queue
- Add Redis to docker-compose.yaml
- Set `REDIS_URL` in `config/.env`

### Rate Limiter Persistence (opt-in)
```bash
RATE_LIMITER_PERSIST=true make backend
```
When enabled:
- State saved to `~/.nemoclaw/rate-limiter/state.json`
- TTL: entries expire after configured window (default 1 hour)
- Max keys: 1000 (capped to prevent disk growth)
- Compaction: every 5 minutes, expired entries removed
- When disabled (default): pure in-memory, no file I/O

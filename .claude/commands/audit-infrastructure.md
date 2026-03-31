Perform a full infrastructure audit for a production autonomous AI company. Audit existing infrastructure, identify gaps, rate each gap, then implement the top 5 most critical missing pieces.

## 1. Read Existing Infrastructure
Before auditing gaps, read the current state:
- `command-center/backend/requirements.txt`
- `command-center/frontend/package.json`
- `config/routing/routing-config.yaml` and `budget-config.yaml`
- Check for: `Dockerfile`, `docker-compose.yaml`, `Makefile`, `.github/workflows/`, `pyproject.toml`, `scripts/__init__.py`, `command-center/backend/app/__init__.py`
- Check `config/.env` structure (without printing secrets)
- Check `~/.nemoclaw/` directory structure

## 2. Infrastructure Gap Audit Table
For each infrastructure category, determine current state and gap severity:

| Category | Current Solution | Gap | Impact | Effort |
|---|---|---|---|---|
| State/persistence | SqliteSaver + JSON files | Need Redis or PostgreSQL for concurrent agents? | ? | ? |
| Vector database | None detected | RAG for agent memory? Pinecone/Chroma/Weaviate | ? | ? |
| Embedding pipeline | None detected | Needed for semantic search across skills/docs | ? | ? |
| Document store | File system | Structured storage for skill outputs, proposals, reports | ? | ? |
| Message queue | None detected | Async task queue for skill execution? RabbitMQ/Redis Streams | ? | ? |
| Caching layer | None detected | LLM response caching, state caching | ? | ? |
| Secrets management | `config/.env` file | HashiCorp Vault / AWS Secrets Manager / env injection | ? | ? |
| Structured logging | JSONL files | Centralized log aggregation (ELK / Loki / CloudWatch) | ? | ? |
| Error tracking | None detected | Sentry or equivalent for exception monitoring | ? | ? |
| Metrics/observability | Custom scripts | Prometheus + Grafana / Datadog | ? | ? |
| CI/CD pipeline | None detected | GitHub Actions for test + deploy | ? | ? |
| Containerization | None detected | Docker + docker-compose for local dev parity | ? | ? |
| Auto-scaling | N/A (local) | When moving to cloud: K8s / ECS / Fly.io | ? | ? |
| Webhook infrastructure | P-3 implemented | Persistent webhook receiver with retry queue? | ? | ? |
| Payment processing | Lemon Squeezy (P-10) | Stripe for flexibility? Webhook handling complete? | ? | ? |
| Email service | Resend (config/.env) | Transactional + marketing separation, bounce handling | ? | ? |
| Scheduler/cron | AutonomousSchedulerService | External cron reliability (Temporal / Celery Beat)? | ? | ? |
| File storage | Local `outputs/` dirs | S3-compatible storage for artifacts at scale | ? | ? |
| Database (relational) | SQLite | PostgreSQL for production multi-agent concurrency | ? | ? |
| API rate limiting | None detected | Rate limiting middleware on FastAPI | ? | ? |

Impact ratings: **critical** (system fails without it), **high** (significant capability loss), **medium** (nice to have), **low** (future scaling)

## 3. Project Skeleton Audit
Check for missing standard files:
- `__init__.py` in `scripts/`, `command-center/backend/app/`, all subdirectories
- `requirements.txt` or `pyproject.toml` at repo root (not just inside `command-center/backend/`)
- `Dockerfile` for backend, `Dockerfile` for frontend
- `docker-compose.yaml` at repo root
- `Makefile` with common targets (install, dev, test, build, deploy)
- `.github/workflows/ci.yml` for automated testing
- `.github/workflows/deploy.yml` for deployment
- `CHANGELOG.md`
- `pyproject.toml` with tool configs (black, isort, mypy, pytest)

## 4. Implement Top 5 Critical Missing Pieces
After completing the audit table above, rank all gaps by (impact × urgency). Select the top 5 and implement them:

For each implementation:
1. State what you're implementing and why it's top 5
2. Create the necessary files
3. Update any config or requirements files
4. Test that it works

Do NOT implement anything ranked medium or low. Focus only on critical/high impact items that can be implemented locally right now (no cloud accounts required for implementation).

## 5. Final Infrastructure Report
```
=== INFRASTRUCTURE AUDIT REPORT ===

CRITICAL GAPS (implement immediately):
  1. <gap> — <reason> — Recommended: <tool>
  2. ...

HIGH GAPS (implement this sprint):
  1. <gap> — <reason> — Recommended: <tool>
  2. ...

MEDIUM GAPS (backlog):
  1. ...

SKELETON FILES MISSING: N
  - <list each>

IMPLEMENTED IN THIS AUDIT:
  ✅ <item 1>: <files created>
  ✅ <item 2>: <files created>
  ...
```

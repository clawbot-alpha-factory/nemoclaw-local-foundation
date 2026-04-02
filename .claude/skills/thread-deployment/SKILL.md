---
name: thread-deployment
description: Session bootstrap for production deployment, P1-P12 phases, prod-ops, and infrastructure. Invoke when deploying, monitoring production, or managing deployment phases.
disable-model-invocation: true
allowed-tools: Read, Edit, Write, Bash, Glob, Grep
---

# Thread: Deployment & Production Operations

You are now in **deployment mode**. Work scoped to `scripts/deploy-p*.py`, `scripts/prod-ops.py`, and production readiness.

## Deployment Phases (P1-P12)
```
scripts/
├── deploy-p1.py    ← Environment validation
├── deploy-p2.py    ← Dependency installation
├── deploy-p3.py    ← Configuration verification
├── deploy-p4.py    ← Database/checkpoint setup
├── deploy-p5.py    ← Skill system initialization
├── deploy-p6.py    ← Agent system startup
├── deploy-p7.py    ← Backend API launch
├── deploy-p8.py    ← Frontend build
├── deploy-p9.py    ← Integration verification
├── deploy-p10.py   ← Health check & validation
├── deploy-p12.py   ← Post-deployment monitoring
└── validate-p1-p10.sh ← Run all phase validations
```

## Production Operations
```bash
python3 scripts/prod-ops.py status       # full system status
python3 scripts/prod-ops.py health       # health dashboard (12 domains)
python3 scripts/prod-ops.py agents       # agent roster + performance
python3 scripts/prod-ops.py costs        # budget by provider
python3 scripts/prod-ops.py validate     # 31-check validation
python3 scripts/prod-ops.py integration  # MA-20 integration test
python3 scripts/prod-ops.py run GOAL     # execute multi-agent workflow
```

## Validation Gates (before any deployment)
```bash
# Must all pass before deploying
python3 scripts/validate.py              # 31 checks: 0 failures required
python3 scripts/integration_test.py --summary  # MA-20: all phases pass
bash scripts/full_regression.sh          # full enterprise regression
bash scripts/validate-p1-p10.sh         # P1-P10 feature validation
```

## Health Monitoring (12 Domains — MA-14)
| Domain | What it checks |
|--------|----------------|
| 1. Skill execution | skill-runner latency, error rate |
| 2. Routing system | alias resolution, provider availability |
| 3. Budget governance | per-provider spend vs limits |
| 4. Agent communication | message delivery, channel health |
| 5. Memory system | working/episodic/workspace access |
| 6. Task decomposition | decompose() success rate |
| 7. Cost governance | circuit breaker state |
| 8. Learning loop | lesson application rate |
| 9. Human-in-the-loop | approval queue depth |
| 10. Access control | permission enforcement |
| 11. Peer review | review completion rate |
| 12. Browser automation | PinchTab instance count, memory |

Alert triggers when 3+ domains degraded simultaneously (L-231).

## Log Locations
```
~/.nemoclaw/logs/
├── provider-usage.jsonl     ← LLM cost per call
├── validation-runs.jsonl    ← Validation history
└── health-reports/          ← Daily health check reports
                                (from scripts/daily-health.sh, runs 9am)
```

## Out of Scope in This Thread
- Skill content → use /thread-skills
- Frontend/backend code → use /thread-frontend or /thread-backend
- Agent config → use /thread-agents

## Common Tasks
- Run deployment phase sequence
- Debug failing validation check
- Investigate health domain degradation
- Check budget circuit breaker state
- Review deployment phase error
- Run post-deployment smoke test
- Monitor production costs
- Check regression results

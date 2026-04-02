---
name: thread-audit-infra
description: Session bootstrap for infrastructure audit — dependencies, deployment readiness, containerization, CI/CD, secrets management, monitoring gaps. Invoke before production releases.
disable-model-invocation: true
context: fork
agent: general-purpose
model: sonnet
allowed-tools: Read, Grep, Glob, Bash
---

# Thread: Infrastructure Audit

You are running a **production infrastructure audit** for NemoClaw.

## Audit Checklist

### 1. Python Environment
```bash
python3 --version                    # Should be 3.12.x (L-001 lock)
.venv313/bin/python3 --version       # Confirm venv
pip list | grep -E "langgraph|fastapi|anthropic|openai"
```
Check requirements.txt is complete and pinned.

### 2. Backend Dependencies
```bash
cd command-center/backend
pip check    # Check for conflicts
cat requirements.txt | wc -l
```

### 3. Frontend Dependencies
```bash
cd command-center/frontend
npm audit    # Security vulnerabilities
cat package.json | grep '"dependencies"' -A 50
```
Flag any HIGH/CRITICAL npm vulnerabilities.

### 4. Configuration Files
Verify these all exist and are valid YAML/JSON:
```bash
python3 -c "import yaml; yaml.safe_load(open('config/routing/routing-config.yaml'))" && echo "OK"
python3 -c "import yaml; yaml.safe_load(open('config/routing/budget-config.yaml'))" && echo "OK"
python3 -c "import yaml; yaml.safe_load(open('config/agents/agent-schema.yaml'))" && echo "OK"
python3 -c "import yaml; yaml.safe_load(open('config/agents/capability-registry.yaml'))" && echo "OK"
```

### 5. Secrets & .gitignore
```bash
git check-ignore config/.env         # Must be gitignored
git check-ignore .claude/settings.local.json  # Must be gitignored
grep -r "sk-ant\|sk-\|AIza" --include="*.py" --include="*.yaml" --include="*.json" . \
  --exclude-dir=".git" --exclude-dir=".venv313"   # No hardcoded keys
```

### 6. Deployment Validation
```bash
bash scripts/validate-p1-p10.sh 2>&1 | tail -20
```

### 7. Data Persistence
```bash
ls ~/.nemoclaw/checkpoints/          # LangGraph SQLite DB
ls ~/.nemoclaw/logs/                 # Provider usage, validation runs
ls ~/.nemoclaw/gamification/         # Agent performance data
```

### 8. Port Conflicts
```bash
lsof -i :8100 | head -5    # Backend
lsof -i :3000 | head -5    # Frontend
lsof -i :9867 | head -5    # PinchTab
```

### 9. Missing Infrastructure
Evaluate readiness for production:
| Item | Present? | Priority |
|------|---------|---------|
| Dockerfile | ? | HIGH |
| docker-compose.yaml | ? | HIGH |
| CI/CD pipeline | ? | HIGH |
| Health endpoint (/health) | ? | MED |
| Error monitoring | ? | MED |
| Log aggregation | ? | MED |
| Backup strategy | ? | LOW |

## Report Format
```
INFRASTRUCTURE AUDIT — [DATE]
━━━━━━━━━━━━━━━━━━━━━━━━━━━

Python: [version] | Expected: 3.12.x
Backend deps: [OK/CONFLICTS]
Frontend deps: [X HIGH vulns / OK]
Config files: [X/4 valid]
Secrets exposed: [YES ❌/NO ✅]
Deployment phases: [X/10 pass]
Data persistence: [OK/MISSING]
Port conflicts: [YES ❌/NO ✅]

CRITICAL GAPS:
  1. [issue]
  ...

PRODUCTION BLOCKERS:
  1. [issue]
  ...
```

---
name: thread-debug
description: Session bootstrap for systematic debugging — import errors, runtime failures, L-003 violations, routing failures, integration test failures, skill execution errors. Invoke when something is broken.
disable-model-invocation: true
context: fork
agent: general-purpose
model: sonnet
allowed-tools: Read, Grep, Glob, Bash
---

# Thread: System Debug

You are running a **systematic debug session** on NemoClaw.

Problem to debug: $ARGUMENTS

## Debug Runbook

### Step 1 — Isolate the Failure
```bash
# Run validation to get baseline
python3 scripts/validate.py 2>&1 | grep -E "❌|FAIL|ERROR"

# Run integration test to find broken MA system
python3 scripts/integration_test.py --summary 2>&1 | grep -E "FAIL|ERROR"

# Check system health
python3 scripts/prod-ops.py health 2>&1 | grep -E "DEGRADED|CRITICAL|ERROR"
```

### Step 2 — Check Python Imports
```bash
# Check all scripts for import errors
for f in scripts/*.py; do
  python3 -c "import ast; ast.parse(open('$f').read())" 2>/dev/null || echo "SYNTAX ERROR: $f"
done

# Check routing import
python3 -c "from lib.routing import call_llm; print('routing OK')"

# Check skill runner
python3 -c "import importlib.util; spec = importlib.util.spec_from_file_location('runner', 'skills/skill-runner.py'); print('runner OK')"
```

### Step 3 — Check Routing
```bash
# Validate routing config
python3 -c "
from lib.routing import resolve_alias
for alias in ['cheap_claude','reasoning_claude','premium_claude','cheap_openai','reasoning_openai']:
    try:
        p,m,c = resolve_alias(alias)
        print(f'  ✅ {alias}: {p}/{m}')
    except Exception as e:
        print(f'  ❌ {alias}: {e}')
"
```

### Step 4 — Skill-Specific Debug
```bash
# Run skill with verbose output
python3 skills/skill-runner.py --skill SKILL_ID --input key value

# Delete stale checkpoint first
rm -f ~/.nemoclaw/checkpoints/langgraph.db

# Check skill YAML syntax
python3 -c "import yaml; yaml.safe_load(open('skills/SKILL_ID/skill.yaml'))" && echo "YAML OK"
```

### Step 5 — Backend Debug
```bash
# Check for syntax errors in backend
for f in command-center/backend/app/**/*.py; do
  python3 -m py_compile "$f" 2>/dev/null || echo "SYNTAX: $f"
done

# Test backend startup (dry run)
cd command-center/backend
python3 -c "from app.main import app; print('backend imports OK')"
```

### Step 6 — Check L-003 Violations
```bash
grep -rn "ChatAnthropic\|ChatOpenAI\|model=\"gpt\|model=\"claude" skills/*/run.py | head -10
```

## Debug Output Format
```
DEBUG SESSION — [DATE]
━━━━━━━━━━━━━━━━━━━━━━

PROBLEM: [What was reported]

ROOT CAUSE:
  File: path/to/file.py:L42
  Error: [exact error message]
  Why:   [root cause explanation]

FIX:
  [Exact change needed]

VERIFICATION:
  [Command to confirm fix works]

RELATED ISSUES:
  [Other things found while debugging]
```

---
name: system-validator
description: Run 31-check validation suite, integration tests, budget status, and health dashboard. Use after code changes or before commits.
tools: Read, Grep, Glob, Bash
model: sonnet
---

Run the full NemoClaw validation suite and report results.

## Steps

1. `python3 scripts/validate.py` — 31-check validation
2. `python3 scripts/integration_test.py --summary` — MA-20 integration
3. `python3 scripts/prod-ops.py health` — Health dashboard
4. `python3 scripts/prod-ops.py costs` — Budget report

## Output

- Pass/fail counts per suite
- Any CRITICAL failures highlighted first
- Budget status (spend vs limits per provider)
- One-line summary: HEALTHY / DEGRADED / CRITICAL

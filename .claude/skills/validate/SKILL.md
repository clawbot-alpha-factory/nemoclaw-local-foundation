---
name: validate
description: Run 31-check system validation and integration tests. Use when asked to validate, check system, verify health, or confirm everything works.
allowed-tools: Bash, Read
---

Run the NemoClaw validation suite:

1. `python3 scripts/validate.py`
2. `python3 scripts/integration_test.py --summary`

Report: pass/fail counts, critical failures, one-line verdict.

# ops-01-failure-recovery-engine

**ID:** `ops-01-failure-recovery-engine`
**Version:** 1.0.0
**Type:** executor
**Family:** ? | **Domain:** ? | **Tag:** operations

## Description

Handles skill/bridge failures. Retry (2x) → fallback skill → escalate to different agent → log pattern. Prevents silent failures.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `failure_context` | string | Yes | What failed: skill_id, error, agent, inputs |
| `severity` | string | No | Severity: low, medium, high, critical |

## Outputs

- `result`
- `result_file`
- `envelope_file`

## Usage

```bash
.venv313/bin/python3 skills/ops-01-failure-recovery-engine/run.py --force --input failure_context "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)

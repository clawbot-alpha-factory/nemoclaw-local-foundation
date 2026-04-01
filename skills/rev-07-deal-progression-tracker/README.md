# rev-07-deal-progression-tracker

**ID:** `rev-07-deal-progression-tracker`
**Version:** 1.0.0
**Type:** executor
**Family:** ? | **Domain:** ? | **Tag:** revenue

## Description

Maintains state per deal: last touch, next action, days in stage, risk score. Triggers agent actions on stale deals automatically.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `deals_data` | string | Yes | Active deals with stage, last activity, value |
| `stale_threshold_days` | string | No | Days before a deal is flagged stale |

## Outputs

- `result`
- `result_file`
- `envelope_file`

## Usage

```bash
.venv313/bin/python3 skills/rev-07-deal-progression-tracker/run.py --force --input deals_data "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)

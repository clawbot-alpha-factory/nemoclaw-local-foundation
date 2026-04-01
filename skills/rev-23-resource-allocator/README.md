# rev-23-resource-allocator

**ID:** `rev-23-resource-allocator`
**Version:** 1.0.0
**Type:** executor
**Family:** ? | **Domain:** ? | **Tag:** revenue

## Description

Hard enforcement of daily outreach caps, per-channel budget, risk thresholds. Prevents spam, domain burn, budget waste.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `current_usage` | string | Yes | Current usage: emails sent, budget spent, outreach volume per channel |
| `limits` | string | No | Hard limits |

## Outputs

- `result`
- `envelope_file`

## Usage

```bash
.venv313/bin/python3 skills/rev-23-resource-allocator/run.py --force --input current_usage "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)

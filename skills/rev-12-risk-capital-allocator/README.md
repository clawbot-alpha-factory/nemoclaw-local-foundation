# rev-12-risk-capital-allocator

**ID:** `rev-12-risk-capital-allocator`
**Version:** 1.0.0
**Type:** executor
**Family:** ? | **Domain:** ? | **Tag:** revenue

## Description

Allocates time, budget, API spend, outreach volume based on confidence, past success rates, current revenue. Prevents spam and budget waste. Sits above rev-06.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `portfolio_state` | string | Yes | Current campaigns, budgets, performance, available resources |
| `risk_tolerance` | string | No | Risk tolerance: conservative, moderate, aggressive |

## Outputs

- `result`
- `result_file`
- `envelope_file`

## Usage

```bash
.venv313/bin/python3 skills/rev-12-risk-capital-allocator/run.py --force --input portfolio_state "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)

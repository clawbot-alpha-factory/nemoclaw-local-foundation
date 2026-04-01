# rev-22-auto-business-launcher

**ID:** `rev-22-auto-business-launcher`
**Version:** 1.0.0
**Type:** executor
**Family:** ? | **Domain:** ? | **Tag:** revenue

## Description

Full autonomous loop: detect demand → generate offer → create landing page → payment link → content → outreach → sales. Zero human intervention from signal to revenue.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `demand_signal` | string | Yes | Validated demand signal with confidence score and ICP |
| `budget_limit` | string | No | Maximum budget in USD for launch |

## Outputs

- `result`
- `result_file`
- `envelope_file`

## Usage

```bash
.venv313/bin/python3 skills/rev-22-auto-business-launcher/run.py --force --input demand_signal "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)

# rev-18-instant-offer-launcher

**ID:** `rev-18-instant-offer-launcher`
**Version:** 1.0.0
**Type:** executor
**Family:** ? | **Domain:** ? | **Tag:** revenue

## Description

Full loop: demand signal → generate offer → create landing page → deploy payment link → start outreach → activate content loop → engage sales closer. Zero human intervention from detection to revenue.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `demand_signal` | string | Yes | Validated demand signal with urgency score and target ICP |
| `speed_mode` | string | No | Launch speed: fast (24h), standard (72h), thorough (1wk) |

## Outputs

- `result`
- `result_file`
- `envelope_file`

## Usage

```bash
.venv313/bin/python3 skills/rev-18-instant-offer-launcher/run.py --force --input demand_signal "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)

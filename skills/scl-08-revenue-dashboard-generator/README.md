# scl-08-revenue-dashboard-generator

**ID:** `scl-08-revenue-dashboard-generator`
**Version:** 1.0.0
**Type:** executor
**Family:** ? | **Domain:** ? | **Tag:** scale

## Description

Auto-generates weekly revenue report: pipeline value, conversion rates, channel ROI, forecast, action items.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `revenue_data` | string | Yes | Revenue metrics: pipeline, conversions, spend, revenue |
| `report_type` | string | No | Report frequency |

## Outputs

- `result`
- `result_file`
- `envelope_file`

## Usage

```bash
.venv313/bin/python3 skills/scl-08-revenue-dashboard-generator/run.py --force --input revenue_data "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)

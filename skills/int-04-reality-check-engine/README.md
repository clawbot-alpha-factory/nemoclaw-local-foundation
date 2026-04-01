# int-04-reality-check-engine

**ID:** `int-04-reality-check-engine`
**Version:** 1.0.0
**Type:** executor
**Family:** ? | **Domain:** ? | **Tag:** intelligence

## Description

Challenges assumptions. Cross-checks demand vs actual conversions. Prevents false positives and vanity metric traps. Can output trigger_skill: null to STOP revenue cycle.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `opportunity_data` | string | Yes | Opportunity details with demand signals, engagement data, conversion data |
| `historical_results` | string | No | Past similar opportunities and their outcomes |

## Outputs

- `result`
- `result_file`
- `envelope_file`
- `insight`
- `recommended_action`
- `trigger_skill`
- `confidence`

## Usage

```bash
.venv313/bin/python3 skills/int-04-reality-check-engine/run.py --force --input opportunity_data "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)

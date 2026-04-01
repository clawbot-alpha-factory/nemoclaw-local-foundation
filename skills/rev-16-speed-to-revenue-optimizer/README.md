# rev-16-speed-to-revenue-optimizer

**ID:** `rev-16-speed-to-revenue-optimizer`
**Version:** 1.0.0
**Type:** executor
**Family:** ? | **Domain:** ? | **Tag:** revenue

## Description

Prioritizes actions that generate fastest cash. Deprioritizes long-term branding when cash is needed. Aligns system with real business constraint: cash flow.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `current_state` | string | Yes | Cash position, pipeline, active campaigns, conversion rates |
| `urgency` | string | No | Cash urgency: low, moderate, critical |

## Outputs

- `result`
- `result_file`
- `envelope_file`

## Usage

```bash
.venv313/bin/python3 skills/rev-16-speed-to-revenue-optimizer/run.py --force --input current_state "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)

# rev-02-lead-qualification-engine

**ID:** `rev-02-lead-qualification-engine`
**Version:** 1.0.0
**Type:** executor
**Family:** ? | **Domain:** ? | **Tag:** revenue

## Description

Scores leads on ICP fit, intent signals, engagement, timing. Outputs priority tier (hot/warm/cold/disqualify). Feeds into sales closer.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `lead_data` | string | Yes | Lead details to qualify |
| `icp_criteria` | string | No | ICP definition |

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
.venv313/bin/python3 skills/rev-02-lead-qualification-engine/run.py --force --input lead_data "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)

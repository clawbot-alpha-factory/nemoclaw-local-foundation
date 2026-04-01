# rev-03-revenue-attribution-analyzer

**ID:** `rev-03-revenue-attribution-analyzer`
**Version:** 1.0.0
**Type:** executor
**Family:** ? | **Domain:** ? | **Tag:** revenue

## Description

Maps every dollar to source: channel, message, agent action. Outputs ROI per channel. Enforced output: insight + recommended_action + trigger_skill.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `revenue_data` | string | Yes | Revenue events with source tracking data |
| `period` | string | No | Analysis period |

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
.venv313/bin/python3 skills/rev-03-revenue-attribution-analyzer/run.py --force --input revenue_data "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)

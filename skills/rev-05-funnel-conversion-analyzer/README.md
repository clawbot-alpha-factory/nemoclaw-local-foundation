# rev-05-funnel-conversion-analyzer

**ID:** `rev-05-funnel-conversion-analyzer`
**Version:** 1.0.0
**Type:** executor
**Family:** ? | **Domain:** ? | **Tag:** revenue

## Description

Identifies where leads drop off. Outputs bottleneck report + fix recommendations per stage. Enforced action output.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `funnel_data` | string | Yes | Stage-by-stage conversion data |
| `funnel_type` | string | No | Funnel type: sales, content, onboarding |

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
.venv313/bin/python3 skills/rev-05-funnel-conversion-analyzer/run.py --force --input funnel_data "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)

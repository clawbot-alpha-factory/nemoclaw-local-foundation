# rev-25-experiment-decision-engine

**ID:** `rev-25-experiment-decision-engine`
**Version:** 1.0.0
**Type:** executor
**Family:** ? | **Domain:** ? | **Tag:** revenue

## Description

Kill/scale decisions based on conversion thresholds. If conversion < threshold → kill. If ROI > threshold → scale. Completes autonomous loop.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `experiment_data` | string | Yes | Experiment results: variants, impressions, conversions, costs, revenue |

## Outputs

- `result`
- `envelope_file`
- `insight`
- `recommended_action`
- `trigger_skill`
- `confidence`

## Usage

```bash
.venv313/bin/python3 skills/rev-25-experiment-decision-engine/run.py --force --input experiment_data "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)

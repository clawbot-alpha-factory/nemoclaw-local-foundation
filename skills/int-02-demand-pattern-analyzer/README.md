# int-02-demand-pattern-analyzer

**ID:** `int-02-demand-pattern-analyzer`
**Version:** 1.0.0
**Type:** executor
**Family:** ? | **Domain:** ? | **Tag:** intelligence

## Description

Clusters comments into pain points, desires, objections, confusion. Detects repeated problems, urgency signals, buying intent. Enforced output: insight + recommended_action + trigger_skill + confidence + demand_volume.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `raw_signals` | string | Yes | Raw comments and signals from scraper |
| `niche` | string | No | Market niche for context |

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
.venv313/bin/python3 skills/int-02-demand-pattern-analyzer/run.py --force --input raw_signals "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)

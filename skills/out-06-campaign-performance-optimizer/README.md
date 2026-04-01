# out-06-campaign-performance-optimizer

**ID:** `out-06-campaign-performance-optimizer`
**Version:** 1.0.0
**Type:** executor
**Family:** ? | **Domain:** ? | **Tag:** outreach

## Description

Analyzes open rates, reply rates, conversion per variant. Kills losers, scales winners. Enforced action output with trigger_skill.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `campaign_data` | string | Yes | Campaign metrics: sends, opens, replies, conversions per variant |
| `min_sample_size` | string | No | Minimum sample before declaring winner |

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
.venv313/bin/python3 skills/out-06-campaign-performance-optimizer/run.py --force --input campaign_data "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)

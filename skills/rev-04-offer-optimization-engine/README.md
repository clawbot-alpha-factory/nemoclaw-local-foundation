# rev-04-offer-optimization-engine

**ID:** `rev-04-offer-optimization-engine`
**Version:** 1.0.0
**Type:** executor
**Family:** ? | **Domain:** ? | **Tag:** revenue

## Description

Tests which offer converts best. Tracks win rates per pricing/packaging variant. Outputs insight + recommended_action + trigger_skill.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `offer_performance_data` | string | Yes | Offer variants with conversion rates and revenue |
| `market_context` | string | No | Market context |

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
.venv313/bin/python3 skills/rev-04-offer-optimization-engine/run.py --force --input offer_performance_data "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)

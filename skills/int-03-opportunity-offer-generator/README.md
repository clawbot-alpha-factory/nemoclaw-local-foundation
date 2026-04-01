# int-03-opportunity-offer-generator

**ID:** `int-03-opportunity-offer-generator`
**Version:** 1.0.0
**Type:** executor
**Family:** ? | **Domain:** ? | **Tag:** intelligence

## Description

Takes demand signals → generates offer, pricing, target ICP, funnel. Triggers content creation (cnt-*), outreach (out-*), proposal (biz-01).


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `demand_insights` | string | Yes | Analyzed demand patterns with confidence scores |
| `capabilities` | string | No | Available capabilities to package |

## Outputs

- `result`
- `result_file`
- `envelope_file`

## Usage

```bash
.venv313/bin/python3 skills/int-03-opportunity-offer-generator/run.py --force --input demand_insights "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)

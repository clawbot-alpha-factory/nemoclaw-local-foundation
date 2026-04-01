# scl-01-affiliate-program-engine

**ID:** `scl-01-affiliate-program-engine`
**Version:** 1.0.0
**Type:** executor
**Family:** ? | **Domain:** ? | **Tag:** scale

## Description

Designs affiliate program: commission structure, tracking, partner recruitment outreach, performance dashboard spec.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `product_context` | string | Yes | Product/service details and target partners |
| `commission_model` | string | No | Commission model preference |

## Outputs

- `result`
- `result_file`
- `envelope_file`

## Usage

```bash
.venv313/bin/python3 skills/scl-01-affiliate-program-engine/run.py --force --input product_context "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)

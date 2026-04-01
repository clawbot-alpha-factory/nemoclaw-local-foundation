# biz-06-upsell-opportunity-detector

**ID:** `biz-06-upsell-opportunity-detector`
**Version:** 1.0.0
**Type:** executor
**Family:** ? | **Domain:** ? | **Tag:** business

## Description

Analyzes client usage + needs → identifies expansion revenue. Outputs specific upsell proposal. Enforced action output.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `client_usage_data` | string | Yes | Client usage patterns, current services, satisfaction |
| `service_catalog` | string | No | Available services for upsell |

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
.venv313/bin/python3 skills/biz-06-upsell-opportunity-detector/run.py --force --input client_usage_data "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)

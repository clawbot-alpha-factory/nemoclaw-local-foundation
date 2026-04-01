# biz-08-social-proof-engine

**ID:** `biz-08-social-proof-engine`
**Version:** 1.0.0
**Type:** executor
**Family:** ? | **Domain:** ? | **Tag:** business

## Description

Auto-generates case studies, testimonials from real outputs, before/after results. Injects into landing pages, outreach, proposals. Conversion multiplier across entire system.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `client_results` | string | Yes | Raw client outcomes: metrics, feedback, deliverables completed |
| `output_formats` | string | No | Proof formats to generate |

## Outputs

- `result`
- `result_file`
- `envelope_file`

## Usage

```bash
.venv313/bin/python3 skills/biz-08-social-proof-engine/run.py --force --input client_results "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)

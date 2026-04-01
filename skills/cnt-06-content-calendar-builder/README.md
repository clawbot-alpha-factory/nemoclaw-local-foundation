# cnt-06-content-calendar-builder

**ID:** `cnt-06-content-calendar-builder`
**Version:** 1.0.0
**Type:** executor
**Family:** ? | **Domain:** ? | **Tag:** content

## Description

30-day content plan across all channels. Maps content to funnel stages. Balances education/entertainment/conversion.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `business_context` | string | Yes | Business, audience, goals for the month |
| `channels` | string | No | Active channels |

## Outputs

- `result`
- `result_file`
- `envelope_file`

## Usage

```bash
.venv313/bin/python3 skills/cnt-06-content-calendar-builder/run.py --force --input business_context "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)

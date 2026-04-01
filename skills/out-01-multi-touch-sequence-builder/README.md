# out-01-multi-touch-sequence-builder

**ID:** `out-01-multi-touch-sequence-builder`
**Version:** 1.0.0
**Type:** executor
**Family:** ? | **Domain:** ? | **Tag:** outreach

## Description

Full 7-day sequence: Day 1 email → Day 2 LinkedIn view → Day 3 connect → Day 5 follow-up → Day 7 objection handler → Day 10 break-up email.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `prospect_profile` | string | Yes | Target prospect details and pain points |
| `value_prop` | string | Yes | Core value proposition |

## Outputs

- `result`
- `result_file`
- `envelope_file`

## Usage

```bash
.venv313/bin/python3 skills/out-01-multi-touch-sequence-builder/run.py --force --input prospect_profile "value" --input value_prop "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)

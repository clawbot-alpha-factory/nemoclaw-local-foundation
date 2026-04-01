# rev-11-follow-up-enforcer

**ID:** `rev-11-follow-up-enforcer`
**Version:** 1.0.0
**Type:** executor
**Family:** ? | **Domain:** ? | **Tag:** revenue

## Description

Auto follow-up on stale deals. If no reply in X days → auto follow-up. If deal idle → escalate. If near close → push urgency sequence.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `deal_context` | string | Yes | Deal details: stage, last contact, conversation history |
| `days_since_contact` | string | No | Days since last contact |

## Outputs

- `result`
- `result_file`
- `envelope_file`

## Usage

```bash
.venv313/bin/python3 skills/rev-11-follow-up-enforcer/run.py --force --input deal_context "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)

# out-04-follow-up-intelligence

**ID:** `out-04-follow-up-intelligence`
**Version:** 1.0.0
**Type:** executor
**Family:** ? | **Domain:** ? | **Tag:** outreach

## Description

Analyzes reply sentiment, determines next best action (schedule call, send case study, handle objection, disengage). Enforced action output.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `conversation_history` | string | Yes | Full email/message thread with prospect |
| `deal_stage` | string | No | Current deal stage |

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
.venv313/bin/python3 skills/out-04-follow-up-intelligence/run.py --force --input conversation_history "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)

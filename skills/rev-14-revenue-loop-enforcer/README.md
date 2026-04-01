# rev-14-revenue-loop-enforcer

**ID:** `rev-14-revenue-loop-enforcer`
**Version:** 1.0.0
**Type:** executor
**Family:** ? | **Domain:** ? | **Tag:** revenue

## Description

Ensures every opportunity completes full cycle: Demand → Offer → Content → Outreach → Close → Payment → Feedback. Auto-fixes broken loops, re-triggers missing steps.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `active_opportunities` | string | Yes | List of active opportunities with their current stage and status |
| `loop_stages` | string | No | Expected stages |

## Outputs

- `result`
- `result_file`
- `envelope_file`

## Usage

```bash
.venv313/bin/python3 skills/rev-14-revenue-loop-enforcer/run.py --force --input active_opportunities "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)

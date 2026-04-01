# out-03-linkedin-action-planner

**ID:** `out-03-linkedin-action-planner`
**Version:** 1.0.0
**Type:** executor
**Family:** ? | **Domain:** ? | **Tag:** outreach

## Description

Generates connection requests, InMail messages, comment strategies. Ready for LinkedIn bridge.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `prospect_linkedin` | string | Yes | Prospect LinkedIn info: name, headline, recent activity |
| `approach` | string | No | Approach: warm_connection, inmail, comment_first |

## Outputs

- `result`
- `result_file`
- `envelope_file`

## Usage

```bash
.venv313/bin/python3 skills/out-03-linkedin-action-planner/run.py --force --input prospect_linkedin "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)

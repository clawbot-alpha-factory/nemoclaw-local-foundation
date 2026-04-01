# out-08-comment-conversion-engine

**ID:** `out-08-comment-conversion-engine`
**Version:** 1.0.0
**Type:** executor
**Family:** ? | **Domain:** ? | **Tag:** outreach

## Description

Monitors comments via Apify. Detects questions, pain, interest signals. Auto-replies publicly (value-first), DMs when appropriate, routes hot leads to Sales Closer. Free inbound lead capture at scale.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `monitored_accounts` | string | Yes | Accounts/posts to monitor for comments |
| `response_tone` | string | No | Response tone: helpful_expert, casual, authoritative |

## Outputs

- `result`
- `result_file`
- `envelope_file`

## Usage

```bash
.venv313/bin/python3 skills/out-08-comment-conversion-engine/run.py --force --input monitored_accounts "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)

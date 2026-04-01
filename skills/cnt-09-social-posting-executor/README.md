# cnt-09-social-posting-executor

**ID:** `cnt-09-social-posting-executor`
**Version:** 1.0.0
**Type:** executor
**Family:** ? | **Domain:** ? | **Tag:** content

## Description

Posts to IG/TikTok/LinkedIn via bridges. Tracks performance per post. Feeds analytics back into cnt-07. Bridge-ready for Buffer/Meta APIs.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `post_content` | string | Yes | Content to post with platform-specific formatting |
| `platform` | string | Yes | Target platform: linkedin, instagram, tiktok, twitter |

## Outputs

- `result`
- `result_file`
- `envelope_file`

## Usage

```bash
.venv313/bin/python3 skills/cnt-09-social-posting-executor/run.py --force --input post_content "value" --input platform "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)

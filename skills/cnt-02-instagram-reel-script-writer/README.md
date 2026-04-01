# cnt-02-instagram-reel-script-writer

**ID:** `cnt-02-instagram-reel-script-writer`
**Version:** 1.0.0
**Type:** executor
**Family:** ? | **Domain:** ? | **Tag:** content

## Description

Full reel: hook (3s) → context (10s) → value (20s) → CTA (5s). Caption + hashtags + posting time.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `topic` | string | Yes | Reel topic |
| `cta_goal` | string | No | Call to action goal |

## Outputs

- `result`
- `result_file`
- `envelope_file`

## Usage

```bash
.venv313/bin/python3 skills/cnt-02-instagram-reel-script-writer/run.py --force --input topic "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)

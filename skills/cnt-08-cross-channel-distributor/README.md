# cnt-08-cross-channel-distributor

**ID:** `cnt-08-cross-channel-distributor`
**Version:** 1.0.0
**Type:** executor
**Family:** ? | **Domain:** ? | **Tag:** content

## Description

Takes content → distributes across all channels via bridges. Tracks per-channel performance. Bridge-connected executor.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `content_piece` | string | Yes | Content to distribute |
| `channels` | string | No | Distribution channels |

## Outputs

- `result`
- `result_file`
- `envelope_file`

## Usage

```bash
.venv313/bin/python3 skills/cnt-08-cross-channel-distributor/run.py --force --input content_piece "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)

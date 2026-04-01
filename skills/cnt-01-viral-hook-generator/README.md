# cnt-01-viral-hook-generator

**ID:** `cnt-01-viral-hook-generator`
**Version:** 1.0.0
**Type:** executor
**Family:** ? | **Domain:** ? | **Tag:** content

## Description

Pattern-based hooks for reels/TikTok/shorts. 10 hooks per topic. Uses proven viral frameworks: curiosity gap, contrarian, story open.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `topic` | string | Yes | Content topic or key message |
| `platform` | string | No | Target platform |

## Outputs

- `result`
- `result_file`
- `envelope_file`

## Usage

```bash
.venv313/bin/python3 skills/cnt-01-viral-hook-generator/run.py --force --input topic "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)

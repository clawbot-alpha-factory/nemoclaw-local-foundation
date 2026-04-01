# cnt-05-youtube-script-writer

**ID:** `cnt-05-youtube-script-writer`
**Version:** 1.0.0
**Type:** executor
**Family:** ? | **Domain:** ? | **Tag:** content

## Description

Full script: hook → intro → 3-5 sections → CTA → end screen. SEO-optimized title + description + tags.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `video_topic` | string | Yes | Video topic and target keyword |
| `video_length` | string | No | Target video length |

## Outputs

- `result`
- `result_file`
- `envelope_file`

## Usage

```bash
.venv313/bin/python3 skills/cnt-05-youtube-script-writer/run.py --force --input video_topic "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)

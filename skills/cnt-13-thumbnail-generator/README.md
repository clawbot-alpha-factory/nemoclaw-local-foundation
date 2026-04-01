# cnt-13-thumbnail-generator

**ID:** `cnt-13-thumbnail-generator`
**Version:** 1.0.0
**Type:** executor
**Family:** ? | **Domain:** ? | **Tag:** content-factory

## Description

Generates scroll-stopping thumbnails for video content. Uses LLM for design concept, calls image generation bridge, and validates quality via critic loop.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `title` | string | Yes | Video or post title for the thumbnail |
| `agent_id` | string | Yes | Agent character to feature |
| `platform` | string | Yes | Target platform |
| `subtitle` | string | No | Optional subtitle or tagline |

## Outputs

- `result`
- `result_file`
- `envelope_file`

## Usage

```bash
.venv313/bin/python3 skills/cnt-13-thumbnail-generator/run.py --force --input title "value" --input agent_id "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)

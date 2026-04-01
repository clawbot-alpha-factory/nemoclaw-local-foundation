# cnt-04-content-repurposer

**ID:** `cnt-04-content-repurposer`
**Version:** 1.0.0
**Type:** executor
**Family:** ? | **Domain:** ? | **Tag:** content

## Description

1 piece → 10 formats: blog → LinkedIn post → tweet thread → reel script → email excerpt → podcast talking points → infographic brief → carousel → quote card → newsletter section.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `source_content` | string | Yes | Original content to repurpose |
| `target_formats` | string | No | Which formats to generate |

## Outputs

- `result`
- `result_file`
- `envelope_file`

## Usage

```bash
.venv313/bin/python3 skills/cnt-04-content-repurposer/run.py --force --input source_content "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)

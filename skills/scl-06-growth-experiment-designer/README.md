# scl-06-growth-experiment-designer

**ID:** `scl-06-growth-experiment-designer`
**Version:** 1.0.0
**Type:** executor
**Family:** ? | **Domain:** ? | **Tag:** scale

## Description

Hypothesis → test design → success metrics → timeline → analysis template. 10 experiments per run.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `growth_goal` | string | Yes | What growth metric to improve |
| `constraints` | string | No | Resource constraints |

## Outputs

- `result`
- `result_file`
- `envelope_file`

## Usage

```bash
.venv313/bin/python3 skills/scl-06-growth-experiment-designer/run.py --force --input growth_goal "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)

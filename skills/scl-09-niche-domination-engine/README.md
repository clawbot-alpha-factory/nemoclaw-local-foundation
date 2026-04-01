# scl-09-niche-domination-engine

**ID:** `scl-09-niche-domination-engine`
**Version:** 1.0.0
**Type:** executor
**Family:** ? | **Domain:** ? | **Tag:** scale

## Description

Picks niche from demand signals. Floods content, outreach, comments, partnerships simultaneously. Builds authority fast. Strategy: compress 6 months of presence into 2 weeks.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `niche_definition` | string | Yes | Target niche with demand data and competitive landscape |
| `timeline` | string | No | Domination timeline |

## Outputs

- `result`
- `result_file`
- `envelope_file`

## Usage

```bash
.venv313/bin/python3 skills/scl-09-niche-domination-engine/run.py --force --input niche_definition "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)

# cnt-07-content-performance-analyzer

**ID:** `cnt-07-content-performance-analyzer`
**Version:** 1.0.0
**Type:** executor
**Family:** ? | **Domain:** ? | **Tag:** content

## Description

Tracks which content drives leads, engagement, revenue. Enforced output: insight + recommended_action + trigger_skill.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `content_metrics` | string | Yes | Per-content metrics: views, engagement, leads, revenue |
| `period` | string | No | Analysis period |

## Outputs

- `result`
- `result_file`
- `envelope_file`
- `insight`
- `recommended_action`
- `trigger_skill`
- `confidence`

## Usage

```bash
.venv313/bin/python3 skills/cnt-07-content-performance-analyzer/run.py --force --input content_metrics "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)

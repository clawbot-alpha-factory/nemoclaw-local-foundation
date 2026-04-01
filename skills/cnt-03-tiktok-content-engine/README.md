# cnt-03-tiktok-content-engine

**ID:** `cnt-03-tiktok-content-engine`
**Version:** 1.0.0
**Type:** executor
**Family:** ? | **Domain:** ? | **Tag:** content

## Description

Full script + text overlay + sound suggestion + CTA. Batch mode: 30 pieces per run. Executor, not planner.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `niche` | string | Yes | Content niche |
| `batch_size` | string | No | Number of scripts to generate |

## Outputs

- `result`
- `result_file`
- `envelope_file`

## Usage

```bash
.venv313/bin/python3 skills/cnt-03-tiktok-content-engine/run.py --force --input niche "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)

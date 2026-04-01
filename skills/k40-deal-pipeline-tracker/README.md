# k40-deal-pipeline-tracker

**ID:** `k40-deal-pipeline-tracker`
**Version:** 1.0.0
**Type:** executor
**Family:** K40 | **Domain:** K | **Tag:** sales

## Description

Analyzes the current deal pipeline, identifies bottlenecks, stalled deals, and recommends next actions for each stage.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `pipeline_data` | string | Yes | Description of current pipeline deals and stages |
| `time_period` | string | No | Analysis time period |

## Execution Steps

1. **Parse input and prepare analysis context** (local) — Validate inputs, extract key parameters, prepare context for generation.
2. **Generate primary output** (llm) — Core generation step using execution_role persona.
3. **Evaluate output quality** (critic) — Score output on relevance, completeness, and actionability.
4. **Validate and write artifact** (local) — Write markdown artifact and JSON envelope.

## Outputs

- `result`
- `result_file`
- `envelope_file`

## Usage

```bash
.venv313/bin/python3 skills/k40-deal-pipeline-tracker/run.py --force --input pipeline_data "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)

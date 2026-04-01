# k43-sales-forecast-modeler

**ID:** `k43-sales-forecast-modeler`
**Version:** 1.0.0
**Type:** executor
**Family:** K43 | **Domain:** K | **Tag:** sales

## Description

Produces revenue forecasts based on pipeline data, historical conversion rates, and market signals.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `pipeline_summary` | string | Yes | Summary of current pipeline and historical data |
| `forecast_horizon` | string | No | Forecast period |

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
.venv313/bin/python3 skills/k43-sales-forecast-modeler/run.py --force --input pipeline_summary "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)

# k45-budget-allocator

**ID:** `k45-budget-allocator`
**Version:** 1.0.0
**Type:** executor
**Family:** K45 | **Domain:** K | **Tag:** marketing

## Description

Recommends optimal budget allocation across channels based on performance data, goals, and constraints.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `channel_performance` | string | Yes | Performance data per channel (spend, leads, conversions) |
| `total_budget` | string | Yes | Total available budget |

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
.venv313/bin/python3 skills/k45-budget-allocator/run.py --force --input channel_performance "value" --input total_budget "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)

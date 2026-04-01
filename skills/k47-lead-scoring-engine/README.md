# k47-lead-scoring-engine

**ID:** `k47-lead-scoring-engine`
**Version:** 1.0.0
**Type:** executor
**Family:** K47 | **Domain:** K | **Tag:** sales

## Description

Scores leads based on fit (ICP match), intent signals, engagement data, and assigns priority tiers.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `lead_data` | string | Yes | Lead information including company, role, engagement |
| `icp_criteria` | string | No | Ideal customer profile criteria |

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
.venv313/bin/python3 skills/k47-lead-scoring-engine/run.py --force --input lead_data "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)

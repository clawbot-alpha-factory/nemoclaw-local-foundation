# k51-competitor-scraper

**ID:** `k51-competitor-scraper`
**Version:** 1.0.0
**Type:** executor
**Family:** K51 | **Domain:** K | **Tag:** research

## Description

Analyzes competitor presence: pricing, positioning, features, messaging, and produces comparison matrix.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `competitors` | string | Yes | List of competitors to analyze |
| `focus_areas` | string | No | Analysis dimensions |

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
.venv313/bin/python3 skills/k51-competitor-scraper/run.py --force --input competitors "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)

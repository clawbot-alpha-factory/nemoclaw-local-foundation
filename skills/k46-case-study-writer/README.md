# k46-case-study-writer

**ID:** `k46-case-study-writer`
**Version:** 1.0.0
**Type:** executor
**Family:** K46 | **Domain:** K | **Tag:** content

## Description

Produces professional case studies with challenge-solution-results structure and quantified outcomes.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `client_context` | string | Yes | Client name, industry, challenge, solution applied, results achieved |
| `tone` | string | No | Writing tone |

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
.venv313/bin/python3 skills/k46-case-study-writer/run.py --force --input client_context "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)

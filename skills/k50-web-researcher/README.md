# k50-web-researcher

**ID:** `k50-web-researcher`
**Version:** 1.0.0
**Type:** executor
**Family:** K50 | **Domain:** K | **Tag:** research

## Description

Conducts structured web research on a given topic, synthesizes findings into a comprehensive brief with sources.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `research_query` | string | Yes | Research question or topic to investigate |
| `depth` | string | No | Research depth: quick, standard, deep |

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
.venv313/bin/python3 skills/k50-web-researcher/run.py --force --input research_query "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)

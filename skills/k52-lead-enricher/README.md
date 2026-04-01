# k52-lead-enricher

**ID:** `k52-lead-enricher`
**Version:** 1.0.0
**Type:** executor
**Family:** K52 | **Domain:** K | **Tag:** sales

## Description

Takes raw lead data and enriches with company info, decision-maker identification, and outreach recommendations.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `lead_list` | string | Yes | Raw lead data (names, companies, titles) |
| `enrichment_depth` | string | No | Enrichment level: basic, standard, deep |

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
.venv313/bin/python3 skills/k52-lead-enricher/run.py --force --input lead_list "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)

# k42-landing-page-optimizer

**ID:** `k42-landing-page-optimizer`
**Version:** 1.0.0
**Type:** executor
**Family:** K42 | **Domain:** K | **Tag:** marketing

## Description

Analyzes landing page copy and structure, produces optimized versions with improved headlines, CTAs, and social proof.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `page_content` | string | Yes | Current landing page content and structure |
| `target_action` | string | No | Desired conversion action |

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
.venv313/bin/python3 skills/k42-landing-page-optimizer/run.py --force --input page_content "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)

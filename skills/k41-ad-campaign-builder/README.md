# k41-ad-campaign-builder

**ID:** `k41-ad-campaign-builder`
**Version:** 1.0.0
**Type:** executor
**Family:** K41 | **Domain:** K | **Tag:** marketing

## Description

Generates complete ad campaign plans with targeting, creative briefs, budget allocation, and A/B test variants.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `campaign_goal` | string | Yes | Campaign objective and target outcome |
| `budget` | string | Yes | Campaign budget and timeline |
| `platform` | string | No | Advertising platform |

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
.venv313/bin/python3 skills/k41-ad-campaign-builder/run.py --force --input campaign_goal "value" --input budget "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)

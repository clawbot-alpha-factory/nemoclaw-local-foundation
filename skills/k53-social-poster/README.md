# k53-social-poster

**ID:** `k53-social-poster`
**Version:** 1.0.0
**Type:** executor
**Family:** K53 | **Domain:** K | **Tag:** marketing

## Description

Generates platform-specific social media posts with hashtags, CTAs, and optimal posting recommendations.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `topic` | string | Yes | Post topic or key message |
| `platform` | string | Yes | Target platform: linkedin, twitter, instagram |

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
.venv313/bin/python3 skills/k53-social-poster/run.py --force --input topic "value" --input platform "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)

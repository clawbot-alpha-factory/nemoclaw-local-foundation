# k49-newsletter-composer

**ID:** `k49-newsletter-composer`
**Version:** 1.0.0
**Type:** executor
**Family:** K49 | **Domain:** K | **Tag:** content

## Description

Composes engaging newsletters with curated sections, headlines, summaries, and CTAs.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `newsletter_brief` | string | Yes | Key topics, updates, and announcements to include |
| `audience` | string | No | Newsletter audience |

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
.venv313/bin/python3 skills/k49-newsletter-composer/run.py --force --input newsletter_brief "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)

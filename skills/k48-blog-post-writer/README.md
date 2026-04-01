# k48-blog-post-writer

**ID:** `k48-blog-post-writer`
**Version:** 1.0.0
**Type:** executor
**Family:** K48 | **Domain:** K | **Tag:** content

## Description

Writes SEO-optimized blog posts with structured headings, internal linking suggestions, and meta descriptions.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `topic` | string | Yes | Blog post topic and target keyword |
| `target_audience` | string | Yes | Intended reader persona |

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
.venv313/bin/python3 skills/k48-blog-post-writer/run.py --force --input topic "value" --input target_audience "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)

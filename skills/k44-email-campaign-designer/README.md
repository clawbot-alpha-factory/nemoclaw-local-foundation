# k44-email-campaign-designer

**ID:** `k44-email-campaign-designer`
**Version:** 1.0.0
**Type:** executor
**Family:** K44 | **Domain:** K | **Tag:** marketing

## Description

Creates multi-email campaign sequences with subject lines, body copy, send timing, and segmentation strategy.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `campaign_brief` | string | Yes | Campaign goal, audience, and key messages |
| `num_emails` | string | No | Number of emails in sequence |

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
.venv313/bin/python3 skills/k44-email-campaign-designer/run.py --force --input campaign_brief "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)

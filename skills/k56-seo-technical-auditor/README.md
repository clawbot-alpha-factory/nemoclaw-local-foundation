# k56-seo-technical-auditor

**ID:** `k56-seo-technical-auditor`
**Version:** 1.0.0
**Type:** executor
**Family:** K56 | **Domain:** K | **Tag:** marketing

## Description

Technical SEO audit — site structure, page speed, meta tags, schema markup recommendations. Produces actionable audit reports with prioritized fixes.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `website_url` | string | Yes | Website URL to audit |
| `focus_areas` | string | No | Comma-separated focus areas (meta tags, page speed, mobile, schema markup, etc.) |
| `depth` | string | No | Audit depth: quick, standard, deep |

## Execution Steps

1. **Parse Request** (local) — Validate inputs, extract URL and focus areas, prepare audit context.
2. **Audit Structure** (llm) — Audit site structure, URL hierarchy, internal linking, crawlability, and indexation issues.
3. **Audit Performance** (llm) — Audit page speed, Core Web Vitals, mobile optimization, meta tags, and schema markup.
4. **Generate Recommendations** (llm) — Generate prioritized technical SEO recommendations with implementation guides.
5. **Quality Review** (critic) — Score audit on thoroughness, accuracy, actionability, and prioritization.
6. **Write Artifact** (local) — Write markdown artifact and JSON envelope.

## Outputs

- `result`
- `result_file`
- `envelope_file`

## Usage

```bash
.venv313/bin/python3 skills/k56-seo-technical-auditor/run.py --force --input website_url "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)

# k55-seo-keyword-researcher

**ID:** `k55-seo-keyword-researcher`
**Version:** 1.0.0
**Type:** executor
**Family:** K55 | **Domain:** K | **Tag:** marketing

## Description

SEO keyword research, SERP analysis, and content gap identification. Produces prioritized keyword clusters with search volume estimates, difficulty scores, and content strategy recommendations.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `niche` | string | Yes | Target niche or industry for keyword research |
| `competitor_urls` | string | No | Comma-separated competitor URLs for competitive analysis |
| `target_audience` | string | No | Target audience persona for intent matching |
| `content_goals` | string | No | Content marketing goals (traffic, leads, authority, etc.) |

## Execution Steps

1. **Parse Niche** (local) — Validate inputs, extract niche parameters, prepare context for keyword research.
2. **Research Keywords** (llm) — Research primary keywords, long-tail keywords, search volume estimates, keyword difficulty, and search intent.
3. **Analyze Competition** (llm) — Analyze top 10 SERP results for target keywords, identify content gaps, find low-competition opportunities.
4. **Generate Strategy** (llm) — Generate SEO content strategy with prioritized keyword clusters, content calendar recommendations, on-page optimization checklist.
5. **Quality Review** (critic) — Score output on keyword relevance, research depth, actionability, and strategic value.
6. **Write Artifact** (local) — Write markdown artifact and JSON envelope.

## Outputs

- `result`
- `result_file`
- `envelope_file`

## Usage

```bash
.venv313/bin/python3 skills/k55-seo-keyword-researcher/run.py --force --input niche "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)

# e08-kb-article-writer

**ID:** `e08-kb-article-writer`
**Version:** 1.0.0
**Type:** executor
**Family:** F08 | **Domain:** E | **Tag:** dual-use

## Description

Produces structured knowledge base articles from a topic, target audience, and source material. Generates clear titles, problem statements, step-by-step solutions, troubleshooting tips, related article suggestions, and metadata tags. Supports how-to, troubleshooting, reference, and conceptual article types. All solutions are grounded in provided source material to prevent fabrication.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `topic` | string | Yes | The subject or question the KB article should address. |
| `article_type` | string | Yes | The type of KB article to produce. |
| `target_audience` | string | Yes | The intended reader — e.g., end users, IT admins, developers, support agents. |
| `source_material` | string | Yes | Raw source content — documentation excerpts, support tickets, product specs, or  |
| `related_article_hints` | string | No | Optional comma-separated list of related article titles or IDs to suggest. |
| `tone` | string | No | Desired tone for the article. |

## Execution Steps

1. **Parse Inputs Validate Source Build Article Plan** (local) — Validates all inputs, checks that source_material meets minimum substance requirements, determines article structure based on article_type, and builds a generation plan including required sections, tone directives, and audience framing.

2. **Generate Structured KB Article Draft** (llm) — Using the validated inputs and generation plan from step_1, produces a fully structured KB article. The article must include: a clear title, problem statement or overview, step-by-step solution or explanation, troubleshooting tips, related article suggestions, and metadata tags. All content must be grounded strictly in the provided source_material. No steps, solutions, or facts may be fabricated beyond what the source supports.

3. **Evaluate Article Quality Anti-Fabrication Compliance** (critic) — Two-layer validation of the generated KB article. Deterministic checks: verifies presence of required sections (title, problem statement, solution steps, troubleshooting, metadata tags), minimum word count, and that article_type structure matches the requested type. LLM evaluation: scores accuracy grounding in source_material, clarity for target_audience, structural completeness, actionability of steps, and anti-fabrication compliance. Produces a combined quality_score 0-10.

4. **Improve Article Based On Critic Feedback** (llm) — Revises the KB article using specific feedback from the critic evaluation in step_3. Addresses identified gaps in structure, improves grounding to source_material, enhances clarity for the target_audience, and corrects any fabricated or unsupported claims. Preserves all content that scored well in the critic evaluation.

5. **Write Final Article Artifact** (local) — Final deterministic gate. Confirms the selected output is non-empty and structurally valid, then writes the KB article to the artifact store and returns the artifact path. Returns {"output": "artifact_written"} on success.


## Outputs

- `result`
- `result_file`
- `envelope_file`

## Usage

```bash
.venv313/bin/python3 skills/e08-kb-article-writer/run.py --force --input topic "value" --input article_type "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)

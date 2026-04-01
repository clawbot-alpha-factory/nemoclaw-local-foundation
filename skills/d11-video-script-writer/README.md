# d11-video-script-writer

**ID:** `d11-video-script-writer`
**Version:** 1.0.0
**Type:** executor
**Family:** F11 | **Domain:** D | **Tag:** customer-facing

## Description

Transforms script briefs into structured video scripts for marketing and educational content. Produces platform-optimized scripts with hooks, scene breakdowns with timing, on-screen text callouts, B-roll/visual direction cues, CTA placement, and brand voice consistency across YouTube long-form, TikTok/Reels short-form, LinkedIn, and general video formats.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `script_brief` | string | Yes | The core brief describing the video's topic, key messages, goals, and any specif |
| `target_audience` | string | Yes | Description of the intended viewer demographic, psychographics, knowledge level, |
| `video_format` | string | Yes | The target platform and format determining length constraints, hook timing, and  |
| `brand_voice` | string | Yes | Brand voice guidelines including tone descriptors, vocabulary preferences, phras |
| `reference_material` | string | No | Supporting facts, data points, quotes, product details, or source material that  |
| `video_duration_target` | string | No | Optional target duration for the video. If not provided, platform defaults apply |

## Execution Steps

1. **Parse brief and build generation plan** (local) — Validates all inputs, resolves platform-specific constraints (hook window, duration limits, structural requirements), extracts key messages from the brief, catalogs reference material for anti-fabrication traceability, and assembles a structured generation plan including segment count, timing budget, and CTA placement strategy.
2. **Generate structured video script draft** (llm) — Generates the complete structured video script following the generation plan. Produces: (1) a platform-appropriate hook within the timing window (5s for short-form, 15s for long-form), (2) scene/segment breakdowns with precise timing allocations, (3) on-screen text callouts marked with [ON-SCREEN] tags, (4) B-roll and visual direction cues marked with [VISUAL] tags, (5) a single CTA placement at the strategically optimal position, (6) speaker dialogue/narration with tone markers. All factual claims are grounded in the reference material or brief. Output maintains brand voice throughout.
3. **Evaluate script quality and compliance** (critic) — Two-layer validation of the generated script. Deterministic layer: verifies hook exists within timing window, checks scene/segment count and timing sum against duration target, confirms exactly one CTA is present, validates [ON-SCREEN] and [VISUAL] tag presence and formatting, checks for fabricated claims not traceable to reference material, verifies platform-specific length constraints. LLM layer: scores hook engagement quality, narrative flow and pacing, brand voice consistency, audience appropriateness, visual direction clarity, and CTA effectiveness. Final quality_score is min(deterministic_score, llm_score) on 0-10 scale. Returns structured feedback with specific improvement directives.
4. **Improve script based on critic feedback** (llm) — Revises the video script based on specific critic feedback. Addresses identified issues including: weak or slow hooks, timing imbalances across segments, missing or poorly formatted on-screen text callouts, insufficient visual direction cues, CTA placement or effectiveness problems, brand voice drift, fabricated claims, pacing issues, and platform constraint violations. Preserves strong elements while surgically improving flagged areas.
5. **Write final script artifact to disk** (local) — Final deterministic gate that selects the highest-quality script version, performs a last structural integrity check, and writes the artifact to the configured storage location. Returns the standard artifact_written confirmation.

## Outputs

- `result`
- `result_file`
- `envelope_file`

## Usage

```bash
.venv313/bin/python3 skills/d11-video-script-writer/run.py --force --input script_brief "value" --input target_audience "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)

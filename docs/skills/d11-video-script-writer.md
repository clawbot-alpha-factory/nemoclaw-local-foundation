# Video Script Writer

**ID:** `d11-video-script-writer` | **Version:** 1.0.0 | **Family:** F11 | **Domain:** D | **Type:** transformer | **Tag:** customer-facing

## Description

Transforms script briefs into structured video scripts for marketing and educational content. Produces platform-optimized scripts with hooks, scene breakdowns with timing, on-screen text callouts, B-roll/visual direction cues, CTA placement, and brand voice consistency across YouTube long-form, TikTok/Reels short-form, LinkedIn, and general video formats.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `script_brief` | string | Yes | The core brief describing the video's topic, key messages, goals, and any specific requirements or constraints. |
| `target_audience` | string | Yes | Description of the intended viewer demographic, psychographics, knowledge level, and pain points. |
| `video_format` | string | Yes | The target platform and format determining length constraints, hook timing, and structural conventions. |
| `brand_voice` | string | Yes | Brand voice guidelines including tone descriptors, vocabulary preferences, phrases to use or avoid, and personality traits. |
| `reference_material` | string | No | Supporting facts, data points, quotes, product details, or source material that the script may reference. All claims in the script must be traceable to this material or the brief. |
| `video_duration_target` | string | No | Optional target duration for the video. If not provided, platform defaults apply (60s for short-form, 8-12min for YouTube long-form, 90-120s for LinkedIn, 3-5min for general). |

## Outputs

| Name | Type | Description |
|------|------|-------------|
| `result` | string | The complete structured video script in markdown format including hook, scene breakdowns with timing, on-screen text callouts, B-roll/visual direction cues, CTA placement, and platform-specific formatting. |
| `result_file` | file_path | Path to the written video script artifact file. |
| `envelope_file` | file_path | Path to the execution envelope JSON file with provenance and quality metadata. |

## Steps

- **step_1** — Parse brief and build generation plan (`local`, `general_short`)
- **step_2** — Generate structured video script draft (`llm`, `premium`)
- **step_3** — Evaluate script quality and compliance (`critic`, `moderate`)
- **step_4** — Improve script based on critic feedback (`llm`, `premium`)
- **step_5** — Write final script artifact to disk (`local`, `general_short`)

## Quality Gate

- **Min Quality Score:** 7
- **Min Quality Score:** 10.0
- **Max Retries:** 5
- **Escalate Below:** 5.0
- **Critic Loop:** enabled, acceptance=10, max_improvements=5
- **Max Execution:** 300s
- **Max Cost:** $2.5

## Declarative Guarantees

- Every factual claim in the script is traceable to the provided reference material or script brief; no statistics, quotes, or data points are fabricated.
- The hook appears within the first 5 seconds for short-form formats and within the first 15 seconds for long-form formats.
- Exactly one call-to-action is placed in the script at a strategically appropriate position.
- All scenes/segments include timing allocations that sum to the target duration within a 10% tolerance.
- On-screen text callouts are marked with [ON-SCREEN] tags and B-roll/visual direction cues are marked with [VISUAL] tags throughout.
- Brand voice tone and vocabulary are maintained consistently across all script segments.
- Platform-specific length and format constraints are respected for the selected video format.

## Composability

- **Output Type:** structured_video_script

## Example Usage

```json
{
  "skill_id": "d11-video-script-writer",
  "inputs": {
    "script_brief": "Create a 60-second product launch video for ClawBot AI showing the key pain point of manual data entry and driving viewers to sign up for a free trial.",
    "target_audience": "VP of Operations at B2B SaaS companies frustrated with manual processes",
    "video_format": "tiktok_reels_shortform",
    "brand_voice": "Confident but approachable, active verbs, short sentences, no jargon"
  }
}
```

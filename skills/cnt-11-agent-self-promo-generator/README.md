# Agent Self-Promotion Generator

**ID:** `cnt-11-agent-self-promo-generator`
**Version:** 1.0.0
**Type:** generator
**Family:** 11 | **Domain:** C | **Tag:** social-media

## Description

Generates weekly self-promotion briefs for each agent. Collects performance data, recent wins, milestone progress, and formats into social media content briefs for the social_media_lead (Zara) to turn into viral content.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `agent_id` | string | Yes | The agent ID to generate a promotion brief for |
| `performance_data` | string | Yes | JSON string of agent performance metrics, recent wins, milestones |

## Execution Steps

1. **Parse Agent Data** (local) — Parse performance data and extract key metrics, wins, milestones
2. **Generate Promotion Brief** (llm) — Create a compelling self-promotion brief with hooks, talking points, and visual ideas in FRIENDS-show narrative style
3. **Quality Review** (critic) — Evaluate brief quality, engagement potential, and brand consistency
4. **Write Artifact** (local) — Write final brief to output file

## Outputs

- `result`
- `result_file`
- `envelope_file`

## Usage

```bash
.venv313/bin/python3 skills/cnt-11-agent-self-promo-generator/run.py --force --input agent_id "value" --input performance_data "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)

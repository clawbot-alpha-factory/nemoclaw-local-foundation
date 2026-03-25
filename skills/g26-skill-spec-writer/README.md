# g26-skill-spec-writer — Skill Spec Writer

> **Family:** F26 (Skill System Meta-Skills)
> **Domain:** G (Governance, Coordination, and Meta-Skills)
> **Tag:** internal
> **Type:** executor
> **Schema:** v2
> **Runner:** >=4.0.0

## Purpose

Takes a skill concept and metadata, produces a complete schema-v2-compliant
`skill.yaml` specification. This is the meta-skill that accelerates all other
skill building by encoding the full v2 schema law into its generation and
validation prompts.

## Inputs

| Name | Type | Required | Description |
|---|---|---|---|
| `skill_concept` | string | yes | Natural language description of the skill |
| `skill_id` | string | yes | Target skill ID (e.g., `b05-feature-impl-writer`) |
| `skill_name` | string | yes | Human-readable display name |
| `family` | string | yes | Family code (e.g., `F05`) |
| `domain` | string | yes | Domain letter (A–L) |
| `tag` | string | yes | `internal` / `customer-facing` / `dual-use` |
| `skill_type` | string | no | Default: `executor` |
| `step_hints` | string | no | Comma-separated hints for step names |
| `has_critic_loop` | boolean | no | Default: false |

## Steps

| Step | Name | Type | Description |
|---|---|---|---|
| step_1 | Parse skill concept and validate naming convention | local | Validates skill_id format, domain/family consistency, tag validity |
| step_2 | Generate complete skill.yaml specification | llm | Produces full YAML following v2 schema rules |
| step_3 | Validate schema compliance and structural correctness | critic | Deterministic + LLM two-layer validation |
| step_4 | Fix schema violations based on critic feedback | llm | Fixes violations, loops back to step_3 |
| step_5 | Write validated skill.yaml artifact | local | Final YAML parse, hard-fail on invalid, write artifact |

## Critic Loop

Acceptance: 8/10 · Max improvements: 2

## Key Design Decisions

- **Step 2** system prompt includes the complete v2 schema reference, explicitly
  forbids invented/renamed fields, and requires raw YAML only (no fences).
- **Step 3** uses two-layer validation: deterministic structural checks (YAML parse,
  required keys, forbidden fields, condition formats) before LLM quality scoring.
  Deterministic failures heavily penalize the final score.
- **Step 5** hard-fails on YAML parse failure — same pattern as F35's numeric
  integrity hard-fail.

## Usage

```bash
~/nemoclaw-local-foundation/.venv312/bin/python \
  ~/nemoclaw-local-foundation/skills/skill-runner.py \
  --skill g26-skill-spec-writer \
  --input skill_concept 'Takes raw competitor data and produces structured competitive intelligence reports with SWOT analysis, positioning maps, and strategic recommendations' \
  --input skill_id 'e08-comp-intel-synth' \
  --input skill_name 'Competitive Intelligence Synthesizer' \
  --input family F08 \
  --input domain E \
  --input tag dual-use \
  --input skill_type executor \
  --input has_critic_loop true
```

## Routing

| Tag | Default Alias |
|---|---|
| internal | production |

## Composable

- **Output type:** `skill_yaml_spec`
- **Can feed into:** `g26-skill-template-generator`

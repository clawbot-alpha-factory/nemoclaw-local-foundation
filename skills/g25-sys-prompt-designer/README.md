# g25-sys-prompt-designer — System Prompt Designer

> **Family:** F25 (Prompt Engineering and Model Optimization)
> **Domain:** G (Governance, Coordination, and Meta-Skills)
> **Tag:** internal
> **Type:** executor
> **Schema:** v2
> **Runner:** >=4.0.0

## Purpose

Generates structured system prompts for skill LLM steps following the F35
reference pattern: role definition, explicit constraints, output format rules,
and forbidden behaviors. Accepts either a full skill.yaml (auto-extracts
LLM steps) or an explicit llm_steps JSON array.

## Inputs

| Name | Type | Required | Description |
|---|---|---|---|
| `skill_purpose` | string | yes | What the skill does |
| `skill_id` | string | yes | Skill ID for context |
| `tag` | string | yes | internal / customer-facing / dual-use |
| `skill_yaml` | string | no | Full skill.yaml — step 1 extracts LLM steps |
| `llm_steps` | string | no | JSON array of LLM step objects |
| `execution_role` | string | no | Foundation persona |
| `domain_constraints` | string | no | Domain-specific rules |
| `output_format_preference` | string | no | prose / structured_json / yaml / markdown_sections |

Must provide either `skill_yaml` or `llm_steps`.

## Steps

| Step | Name | Type | Description |
|---|---|---|---|
| step_1 | Parse inputs and build prompt generation plan | local | Accepts skill_yaml or llm_steps, classifies prompt needs |
| step_2 | Generate structured system prompts for all LLM steps | llm | Full prompt generation with F35 reference embedded |
| step_3 | Evaluate prompt quality and structural completeness | critic | Deterministic + LLM two-layer validation |
| step_4 | Improve prompts based on critic feedback | llm | Fix banned phrases, add constraints |
| step_5 | Validate and write prompt artifact | local | Full deterministic gate — hard-fail on violations |

## Deterministic Checks

- JSON parse validation
- Step coverage (every expected step_id has a prompt)
- Minimum prompt length (100 chars)
- Banned vague phrases (15 patterns)
- Banned capability hallucinations (14 patterns)
- Required structure (role, task, constraint, output format)
- Output format positive checks (JSON/YAML/markdown mentioned when required)
- Critic prompt enforcement (quality_score, feedback, JSON format)

## Usage

```bash
# From skill.yaml (auto-extract LLM steps)
~/nemoclaw-local-foundation/.venv312/bin/python \
  ~/nemoclaw-local-foundation/skills/skill-runner.py \
  --skill g25-sys-prompt-designer \
  --input skill_purpose 'Competitive intelligence reports with SWOT analysis' \
  --input skill_id 'e08-comp-intel-synth' \
  --input tag dual-use \
  --input skill_yaml "$(cat path/to/skill.yaml)" \
  --input output_format_preference structured_json
```

## Composable

- **Output type:** `system_prompts`
- **Accepts input from:** `g26-skill-spec-writer`
- **Can feed into:** `g26-skill-template-gen`

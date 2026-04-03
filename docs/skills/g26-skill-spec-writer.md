# Skill Spec Writer

**ID:** `g26-skill-spec-writer` | **Version:** 1.0.0 | **Family:** F26 | **Domain:** G | **Type:** executor | **Tag:** internal

## Description

Takes a skill concept and metadata, produces a complete schema-v2-compliant skill.yaml specification. Encodes all v2 schema rules into generation prompts and validates output with deterministic structural checks plus LLM quality review.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `skill_concept` | string | Yes | Natural language description of the skill: what it does, who it's for, what it produces |
| `skill_id` | string | Yes | Target skill ID following naming convention (e.g., b05-feature-impl-writer) |
| `skill_name` | string | Yes | Human-readable display name |
| `family` | string | Yes | Family code (e.g., F05) |
| `domain` | string | Yes | Domain letter (A-L) |
| `tag` | string | Yes | internal, customer-facing, or dual-use |
| `skill_type` | string | No | One of: executor, planner, evaluator, transformer, router |
| `step_hints` | string | No | Optional comma-separated hints for step names and purposes |
| `has_critic_loop` | boolean | No | Whether to include critic loop structure in the generated spec |

## Outputs

| Name | Type | Description |
|------|------|-------------|
| `result` | string | The complete skill.yaml content as a string |
| `result_file` | file_path | Path to the markdown artifact containing the YAML |
| `envelope_file` | file_path | Path to the JSON envelope for skill chaining |

## Steps

- **step_1** — Parse skill concept and validate naming convention (`local`, `general_short`)
- **step_2** — Generate complete skill.yaml specification (`llm`, `premium`)
- **step_3** — Validate schema compliance and structural correctness (`critic`, `moderate`)
- **step_4** — Fix schema violations based on critic feedback (`llm`, `premium`)
- **step_5** — Write validated skill.yaml artifact (`local`, `general_short`)

## Quality Gate

- **Min Quality Score:** 7
- **Min Quality Score:** 10.0
- **Max Retries:** 5
- **Escalate Below:** 5.0
- **Critic Loop:** enabled, acceptance=10, max_improvements=5
- **Max Execution:** 90s
- **Max Cost:** $0.1

## Declarative Guarantees

- Output is valid parseable YAML
- Output follows skill-yaml-schema-v2 structure completely
- All step names are semantic — minimum 3 words, no banned terms
- success_conditions use structured left/op/right format
- Transitions use structured left/op/right/go_to format
- No makes_llm_call field — step_type determines LLM usage
- No decision step type — only local, llm, critic
- No best_available in input_source
- Contracts split into machine_validated and declarative_guarantees
- critic_loop block is first-class when has_critic_loop is true
- No invented fields outside schema v2
- No renamed required schema fields

## Composability

- **Output Type:** skill_yaml_spec
- **Can Feed Into:** g26-skill-template-generator

## Example Usage

```json
{
  "skill_id": "g26-skill-spec-writer",
  "inputs": {
    "skill_concept": "A content calendar planner that takes brand guidelines, content pillars, and a time period to produce a structured editorial calendar with topic ideas, content types, publishing schedule, and platform assignments.",
    "skill_name": "Content Calendar Planner",
    "skill_id": "d11-content-calendar-planner",
    "family": "F11",
    "domain": "D",
    "tag": "dual-use"
  }
}
```

# g26-skill-template-gen — Skill Template Generator

> **Family:** F26 (Skill System Meta-Skills)
> **Domain:** G (Governance, Coordination, and Meta-Skills)
> **Tag:** internal
> **Type:** executor
> **Schema:** v2
> **Runner:** >=4.0.0

## Purpose

Takes a skill.yaml and generates an architecture-aligned first-draft run.py
with step handlers, provider dispatch, and validation structure. Produces
strong prompt scaffolding and correct runtime wiring — not finished production
code. Human review of generated run.py is still required before deployment.

## Hard Rules

The generated run.py must conform to the existing NemoClaw runner contract
and may not invent new runtime conventions, helper abstractions, state fields,
or orchestration semantics beyond what the skill.yaml and reference architecture
define.

## Inputs

| Name | Type | Required | Description |
|---|---|---|---|
| `skill_yaml` | string | yes | Complete skill.yaml content |
| `reference_pattern` | string | no | Advisory: `executor`, `transformer`, `evaluator`. Default: `executor` |
| `deterministic_check_type` | string | no | `none`, `numeric`, `structural`, `schema`, `custom`. Default: `none` |

## Steps

| Step | Name | Type | Description |
|---|---|---|---|
| step_1 | Parse skill.yaml and classify step implementation requirements | local | Deep per-step classification: handler type, output format, LLM usage, deterministic needs |
| step_2 | Generate architecture-aligned run.py implementation | llm | Full code generation with reference architecture embedded in prompt |
| step_3 | Validate code correctness and architectural compliance | critic | Deterministic (compile, handlers, call patterns, imports) + LLM (prompt quality, completeness) |
| step_4 | Fix code issues based on critic feedback | llm | Fix violations, loop back to step_3 |
| step_5 | Validate final code and write artifact | local | Full deterministic gate — hard-fail on any structural violation |

## Critic Loop

Acceptance: 8/10 · Max improvements: 2

## Usage

```bash
# Using skill.yaml content directly
~/nemoclaw-local-foundation/.venv312/bin/python \
  ~/nemoclaw-local-foundation/skills/skill-runner.py \
  --skill g26-skill-template-gen \
  --input skill_yaml "$(cat ~/nemoclaw-local-foundation/skills/i35-tone-calibrator/skill.yaml)" \
  --input reference_pattern transformer \
  --input deterministic_check_type numeric
```

## Composable

- **Output type:** `skill_run_py`
- **Accepts input from:** `g26-skill-spec-writer`

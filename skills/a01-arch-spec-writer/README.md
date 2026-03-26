# Skill: a01-arch-spec-writer

**Name:** Architecture Specification Writer
**Version:** 1.0.0
**Family:** F01 | **Domain:** A | **Tag:** internal
**Type:** executor | **Schema:** v2 | **Runner:** v4.0+
**Status:** Production — tested

## What It Does

Takes a subsystem concept, boundaries, integration context, and constraints. Produces a complete architecture specification with:

- Purpose and scope (in-scope / out-of-scope)
- Architecture overview with layer breakdown (2+ layers enforced)
- Component descriptions with responsibility AND interface/contract per component
- Data/control flow — directional (arrows, numbered steps, or directional verbs) referencing 2+ components
- Dependency map with direction (depends on / provides to) and interaction type (API, DB, file, etc.)
- Risk analysis (3+ specific risks enforced)
- Extension points and open questions
- Assumptions section (explicit when input is incomplete)
- Constraint propagation from input

## Usage

```bash
~/nemoclaw-local-foundation/.venv312/bin/python \
  ~/nemoclaw-local-foundation/skills/skill-runner.py \
  --skill a01-arch-spec-writer \
  --input subsystem_name 'Budget Enforcement System' \
  --input subsystem_concept 'Per-provider budget tracking and enforcement layer that intercepts every inference call, checks cumulative spend against configurable limits, logs usage, and routes to fallback when budgets are exhausted. Supports 3 providers with independent limits.' \
  --input boundaries 'In scope: spend tracking, threshold warnings, hard stops, fallback routing, usage logging. Out of scope: model selection logic (handled by routing config), actual API calls (handled by skill run.py), billing reconciliation.' \
  --input integration_context 'Called by skill-runner.py before every LLM step. Reads routing-config.yaml and budget-config.yaml. Writes to provider-spend.json and provider-usage.jsonl.' \
  --input constraints 'Must complete in under 50ms per call. Must not block if log files are temporarily unavailable. Must support atomic spend file updates.'
```

## Steps

| Step | Name | Type | Task Class |
|---|---|---|---|
| step_1 | Parse subsystem concept and identify architectural concerns | local | general_short |
| step_2 | Generate complete architecture specification | llm | moderate |
| step_3 | Evaluate specification completeness and structural rigor | critic | moderate |
| step_4 | Strengthen specification based on critic feedback | llm | moderate |
| step_5 | Validate final spec and write artifact | local | general_short |

## Critic Loop

Generate → evaluate → improve loop. Threshold: 8/10. Max improvements: 2.

## Deterministic Validation

- Required sections: Purpose, Scope, Architecture Overview, Components, Data/Control Flow, Dependencies, Risks, Extension Points
- Layer breakdown: 2+ distinct layers
- Components: each must have responsibility AND interface description
- Data/control flow: directional (numbered steps, arrows, or directional verbs) referencing 2+ components
- Dependencies: direction markers (depends on, provides to, calls) AND interaction type (API, DB, file, etc.)
- Risks: 3+ specific risks
- Banned vague language: "handles everything", "manages stuff", "general purpose layer", "flexible component"
- Constraint propagation: input constraints must appear in spec
- No invented systems or technologies not implied by input

## Resume

```bash
~/nemoclaw-local-foundation/.venv312/bin/python \
  ~/nemoclaw-local-foundation/skills/skill-runner.py \
  --skill a01-arch-spec-writer --thread-id THREAD_ID --resume
```

## Docs

See `docs/architecture/skill-yaml-schema-v2.md` and `docs/architecture/skill-build-plan.md`.

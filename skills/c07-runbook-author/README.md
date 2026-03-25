# Skill: c07-runbook-author

**Name:** Runbook Author
**Version:** 1.0.0
**Family:** F07 | **Domain:** C | **Tag:** dual-use
**Type:** executor | **Schema:** v2 | **Runner:** v4.0+
**Status:** Production — tested

## What It Does

Takes a system description, list of operational procedures, and failure scenarios. Produces a structured operational runbook with:

- Dedicated section per procedure with actionable steps and verification checkpoints
- Decision trees with real branching for recovery and incident procedures
- Rollback instructions for recovery and modification procedures (or explicit no-rollback statement)
- Quick reference card with estimated completion time per procedure
- Troubleshooting section (minimum 3 scenarios)
- Escalation paths for on-call audience

Procedures are classified in step_1 (startup, verification, recovery, maintenance, incident, modification) and the classification drives which validation rules apply.

## Usage

```bash
~/nemoclaw-local-foundation/.venv312/bin/python \
  ~/nemoclaw-local-foundation/skills/skill-runner.py \
  --skill c07-runbook-author \
  --input system_description 'NemoClaw local foundation: LangGraph + Direct API, 9-alias routing, budget enforcement, SqliteSaver checkpointing, Docker Desktop sandbox' \
  --input procedures 'cold start after reboot, health check, budget reset, incident response for API failure, config change rollback' \
  --input failure_scenarios 'Docker not running, API key expired, budget exhausted, checkpoint DB corrupt' \
  --input audience operator
```

## Steps

| Step | Name | Type | Task Class |
|---|---|---|---|
| step_1 | Parse system context and classify procedures | local | general_short |
| step_2 | Generate operational runbook with decision trees and checkpoints | llm | complex_reasoning |
| step_3 | Evaluate runbook completeness and decision tree quality | critic | moderate |
| step_4 | Strengthen runbook based on critic feedback | llm | complex_reasoning |
| step_5 | Validate final runbook and write artifact | local | general_short |

## Critic Loop

Generate → evaluate → improve loop. Threshold: 8/10. Max improvements: 2.

## Deterministic Validation

- Every input procedure has a section with actionable steps AND verification checkpoints
- Recovery/incident procedures: real decision tree branching (If + Else/Otherwise, or 2+ conditionals)
- Recovery/modification procedures: rollback instructions or explicit "no rollback applicable"
- Quick reference card with time estimates
- Troubleshooting: 3+ scenarios
- On-call audience: escalation instructions required
- Extended banned phrases: fluff + vague ops language ("investigate further", "check logs" without specifying which)

## Audience Modes

| Audience | Style | Decision Trees | Escalation |
|---|---|---|---|
| operator | Step-by-step, no assumed knowledge, heavy verification | Full if/then format | Optional |
| developer | Concise, assumes stack familiarity | Compact for recovery/incident | Optional |
| on-call | Triage-first, fastest path to resolution | Prominent and prioritized | Required |

## Resume

```bash
~/nemoclaw-local-foundation/.venv312/bin/python \
  ~/nemoclaw-local-foundation/skills/skill-runner.py \
  --skill c07-runbook-author --thread-id THREAD_ID --resume
```

## Docs

See `docs/architecture/skill-yaml-schema-v2.md` and `docs/architecture/skill-build-plan.md`.

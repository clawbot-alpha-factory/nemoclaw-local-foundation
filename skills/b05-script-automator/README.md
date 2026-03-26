# Skill: b05-script-automator

**Name:** Script Automator
**Version:** 1.0.0
**Family:** F05 | **Domain:** B | **Tag:** dual-use
**Type:** executor | **Schema:** v2 | **Runner:** v4.0+
**Status:** Production — tested

## What It Does

Takes a task description, target shell, and operational context. Produces a complete automation script with:

- Argument parsing for all configurable values
- Usage/help documentation (--help or header comment)
- Conditional error handling (file I/O, subprocess, network — not trivial ops)
- No embedded secrets (tokens, keys, passwords) — use env vars or arguments
- Dry-run mode with behavioral enforcement for destructive/deployment scripts
- Confirmation prompt for destructive scripts (unless --force)
- Exit 0 on success, non-zero on failure
- Logging for data pipeline, deployment, and monitoring scripts
- Shebang line for bash scripts
- Idempotency where applicable

Scripts are classified in step_1 (data_pipeline, deployment, maintenance, monitoring, integration, destructive) and the classification drives which validation rules apply.

**Critical boundary:** Produces scripts as text only. Does NOT execute the script.

## Usage

```bash
~/nemoclaw-local-foundation/.venv312/bin/python \
  ~/nemoclaw-local-foundation/skills/skill-runner.py \
  --skill b05-script-automator \
  --input task_description 'Clean up old skill output artifacts older than 30 days from all skill output directories. Delete .md and .json files only. Log what was deleted. Must support dry-run to preview without deleting.' \
  --input target_shell bash \
  --input operational_context 'Skill outputs are in ~/nemoclaw-local-foundation/skills/*/outputs/. Files are markdown artifacts and JSON envelopes. Do not delete .gitignore files.' \
  --input safety_requirements 'Must not delete .gitignore. Must confirm before deletion. Must support --dry-run.'
```

## Steps

| Step | Name | Type | Task Class |
|---|---|---|---|
| step_1 | Parse task and classify script type | local | general_short |
| step_2 | Generate complete automation script with safety controls | llm | complex_reasoning |
| step_3 | Evaluate script completeness and safety compliance | critic | moderate |
| step_4 | Strengthen script based on critic feedback | llm | complex_reasoning |
| step_5 | Validate final script and write artifact | local | general_short |

## Critic Loop

Generate → evaluate → improve loop. Threshold: 8/10. Max improvements: 2.

## Script Type Classification

| Type | Triggers | Dry-Run Required | Logging Required | Confirmation Required |
|---|---|---|---|---|
| data_pipeline | etl, transform, parse, convert | No | Yes | No |
| deployment | deploy, release, publish, push | Yes | Yes | No |
| maintenance | cleanup, backup, rotate, prune | No | No | No |
| monitoring | check, watch, alert, health | No | Yes | No |
| integration | sync, connect, webhook, bridge | No | No | No |
| destructive | delete, remove, purge, wipe | Yes | No | Yes |

## Deterministic Validation

- Argument parsing present (language-aware: argparse, getopts, process.argv)
- Usage/help documentation accessible
- Error handling on risk paths only (file ops, subprocess, network)
- No embedded secrets (regex for API keys, tokens, passwords, Bearer tokens)
- No hardcoded user-specific paths not in operational_context
- Dry-run: flag exists AND destructive commands wrapped in conditionals
- Confirmation prompt for destructive scripts (or --force flag)
- Explicit exit codes (0 success, non-zero failure)
- Logging for observable script types
- Shebang for bash scripts
- No fake completeness patterns

## Resume

```bash
~/nemoclaw-local-foundation/.venv312/bin/python \
  ~/nemoclaw-local-foundation/skills/skill-runner.py \
  --skill b05-script-automator --thread-id THREAD_ID --resume
```

## Docs

See `docs/architecture/skill-yaml-schema-v2.md` and `docs/architecture/skill-build-plan.md`.

# Skill: c07-setup-guide-writer

**Name:** Setup Guide Writer
**Version:** 1.0.0
**Family:** F07 | **Domain:** C | **Tag:** dual-use
**Type:** executor | **Schema:** v2 | **Runner:** v4.0+
**Status:** Production — tested

## What It Does

Takes a system description, target environment, and prerequisite context. Produces a complete step-by-step setup guide with:

- Prerequisites table (tool, version, check command, install source)
- Numbered installation steps — each with either a CLI command or UI action instruction
- Verification per step (Expected:, Verify:, Confirm:)
- Environment notes
- Troubleshooting section (minimum 3 failure scenarios)
- Post-setup checklist

Audience level (developer, devops, non-technical) controls vocabulary complexity, command explanation depth, and whether GUI alternatives are mentioned.

## Usage

```bash
~/nemoclaw-local-foundation/.venv313/bin/python \
  ~/nemoclaw-local-foundation/skills/skill-runner.py \
  --skill c07-setup-guide-writer \
  --input system_description "NemoClaw local foundation: LangGraph + Direct API on MacBook M1 with Docker Desktop, Python 3.12 venv, 3-provider routing, budget enforcement" \
  --input target_environment "MacBook Apple Silicon M1, macOS 15+ Sequoia, 16GB RAM" \
  --input prerequisites "Docker Desktop 29+, Homebrew, Python 3.12, Node.js 20+" \
  --input audience developer
```

## Steps

| Step | Name | Type | Task Class |
|---|---|---|---|
| step_1 | Parse system context and plan guide structure | local | general_short |
| step_2 | Generate complete setup guide with verification commands | llm | complex_reasoning |
| step_3 | Evaluate guide completeness and verification coverage | critic | moderate |
| step_4 | Strengthen guide based on critic feedback | llm | complex_reasoning |
| step_5 | Validate final guide and write artifact | local | general_short |

## Critic Loop

Generate → evaluate → improve loop. Threshold: 8/10. Max improvements: 2.

## Deterministic Validation

- Required sections: Prerequisites, numbered steps, Troubleshooting, Post-Setup/Checklist
- Per-step mapping: each numbered step checked for CLI code block OR UI action instruction
- Per-step mapping: each numbered step checked for verification instruction
- Prerequisites table: minimum 2 data rows
- Troubleshooting: minimum 3 scenarios (counted by bullets/numbers)
- Banned fluff phrases rejected

## Resume

```bash
~/nemoclaw-local-foundation/.venv313/bin/python \
  ~/nemoclaw-local-foundation/skills/skill-runner.py \
  --skill c07-setup-guide-writer --thread-id THREAD_ID --resume
```

## Docs

See `docs/architecture/skill-yaml-schema-v2.md` and `docs/architecture/skill-build-plan.md`.

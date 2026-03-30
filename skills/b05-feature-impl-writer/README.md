# Skill: b05-feature-impl-writer

**Name:** Feature Implementation Writer
**Version:** 1.0.0
**Family:** F05 | **Domain:** B | **Tag:** dual-use
**Type:** executor | **Schema:** v2 | **Runner:** v4.0+
**Status:** Production — tested

## What It Does

Takes a feature specification, target language, and integration context. Produces complete first-draft implementation code intended to be runnable after human review, integration, and testing. Includes:

- Structured implementation plan extracted from spec (functions, classes, modules, test targets)
- Module structure appropriate to complexity (single file, multi-module, component+helper+test)
- Real function/class implementations (not stubs or placeholders)
- Conditional error handling for I/O, external input, and integration paths
- Inline documentation per requested code style (minimal, documented, defensive)
- Separate test stub section with meaningful assertions

**Critical boundary:** This skill produces code as text. It does NOT execute, compile, or test the code. It does NOT claim the code is verified or production-ready.

## Usage

```bash
~/nemoclaw-local-foundation/.venv313/bin/python \
  ~/nemoclaw-local-foundation/skills/skill-runner.py \
  --skill b05-feature-impl-writer \
  --input feature_spec 'Build a budget-status CLI tool that reads provider-spend.json, displays per-provider spend with visual bar charts, supports --provider flag to filter, and exits with code 1 if any provider exceeds 90 percent' \
  --input language python \
  --input integration_context 'Reads ~/.nemoclaw/logs/provider-spend.json (JSON with provider keys and cumulative_spend_usd). Reads ~/nemoclaw-local-foundation/config/routing/budget-config.yaml for limits.' \
  --input constraints 'Must work on Python 3.12. No external dependencies beyond pyyaml and standard library.' \
  --input code_style documented
```

## Steps

| Step | Name | Type | Task Class |
|---|---|---|---|
| step_1 | Parse feature spec and build structured implementation plan | local | general_short |
| step_2 | Generate complete implementation with error handling and documentation | llm | complex_reasoning |
| step_3 | Evaluate code quality and specification compliance | critic | moderate |
| step_4 | Strengthen implementation based on critic feedback | llm | complex_reasoning |
| step_5 | Validate final implementation and write artifact | local | general_short |

## Critic Loop

Generate → evaluate → improve loop. Threshold: 8/10. Max improvements: 2.

## Deterministic Validation

- Code blocks present with implementation and separate test sections
- Implementation plan coverage: each planned unit has a corresponding definition (50%+ match)
- Implementation block minimum length (100 chars)
- Error handling present on risk paths (I/O, external input, integration) — not on trivial paths
- No fake completeness: `// implementation here`, `pass` in critical path, empty catch blocks, `return null` placeholder
- No unspecified dependencies (generalized — not just banned imports)
- No "tested and verified" or "production-ready" claims
- React: component structure, props/state separation
- Language-aware structural detection (Python, JS/TS, Bash, React, Go)

## Supported Languages

| Language | Aliases | Key Detection Patterns |
|---|---|---|
| Python | py | def, class, try/except, import |
| JavaScript | js | function, const/let, try/catch, require/import |
| TypeScript | ts | Same as JS |
| React | jsx, tsx | Component return, useState, props, JSX |
| Bash | sh, shell | function(), if [, set -e, trap |
| Go | — | func, type struct, if err != nil |

Other languages use Python-like fallback detection.

## Resume

```bash
~/nemoclaw-local-foundation/.venv313/bin/python \
  ~/nemoclaw-local-foundation/skills/skill-runner.py \
  --skill b05-feature-impl-writer --thread-id THREAD_ID --resume
```

## Docs

See `docs/architecture/skill-yaml-schema-v2.md` and `docs/architecture/skill-build-plan.md`.

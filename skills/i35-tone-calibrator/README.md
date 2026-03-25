# Skill: i35-tone-calibrator

**Name:** Tone Calibrator
**Version:** 1.0.0
**Family:** F35 | **Domain:** I | **Tag:** customer-facing
**Type:** transformer | **Schema:** v2 | **Runner:** v4.0+
**Status:** Boilerplate — implement prompts and test

## What It Does

TODO: Describe what Tone Calibrator does.

## Usage

```bash
~/nemoclaw-local-foundation/.venv312/bin/python \
  ~/nemoclaw-local-foundation/skills/skill-runner.py \
  --skill i35-tone-calibrator \
  --input input_text "your input here"
```

## Steps

| Step | Name | Type | Task Class |
|---|---|---|---|
| step_1 | Parse input and detect current tone characteristics | local | general_short |
| step_2 | Rewrite text to match target tone profile | llm | premium |
| step_3 | Evaluate tone match and preservation quality | critic | premium |
| step_4 | Improve rewrite based on critic feedback | llm | premium |
| step_5 | Validate contracts and write artifact | local | general_short |

## Critic Loop

Generate → evaluate → improve loop. Threshold: 8/10. Max improvements: 2.

## Resume

```bash
~/nemoclaw-local-foundation/.venv312/bin/python \
  ~/nemoclaw-local-foundation/skills/skill-runner.py \
  --skill i35-tone-calibrator --thread-id THREAD_ID --resume
```

## Docs

See `docs/architecture/skill-yaml-schema-v2.md` and `docs/architecture/skill-build-plan.md`.

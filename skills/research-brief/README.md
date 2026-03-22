# Skill: research-brief

**Version:** 1.0.0
**Status:** Phase 4 — v1 pipeline complete, live inference connection pending

## What It Does

Takes a topic as input and produces a structured research brief with:
- Background
- Key Findings
- Open Questions
- Recommendations

## Usage
```bash
python3 skills/skill-runner.py --skill research-brief \
  --input topic "your topic here" \
  --input depth standard
```

## Inputs

| Field | Required | Default | Values |
|---|---|---|---|
| topic | Yes | — | Any string 5-500 chars |
| depth | No | standard | brief, standard, deep |

## Outputs

Markdown file written to `skills/research-brief/outputs/`

## Routing

| Step | Alias | Model |
|---|---|---|
| step_1 validate | cheap_openai | gpt-4o-mini |
| step_2 research | reasoning_claude | claude-sonnet-4-6 |
| step_3 structure | cheaper_claude | claude-haiku-4-5-20251001 |
| step_4 validate | cheap_openai | gpt-4o-mini |
| step_5 write | none | local only |

## Resume
```bash
python3 skills/skill-runner.py --skill research-brief \
  --input topic "your topic" \
  --workflow-id WORKFLOW_ID \
  --resume
```

## Known Limitations

- step_2 currently uses templated output — live gateway inference connection is Phase 4 Item 4
- Outputs directory is gitignored — artifacts are local only

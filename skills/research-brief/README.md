# Skill: research-brief

**Version:** 1.0.0
**Status:** Production — live inference, tested end-to-end
**Author:** Core88
**Created:** 2026-03-23

## What It Does

Takes a topic as input and produces a structured research brief with Background, Key Findings, Open Questions, and Recommendations. Runs as a 5-step LangGraph StateGraph with budget-enforced model routing across OpenAI and Anthropic.

## Usage
```bash
~/nemoclaw-local-foundation/.venv313/bin/python \
  ~/nemoclaw-local-foundation/skills/skill-runner.py \
  --skill research-brief \
  --input topic "your topic here" \
  --input depth standard
```

**Important:** Use `.venv313/bin/python`, not system python3.

## Inputs

| Field | Required | Default | Allowed Values |
|---|---|---|---|
| topic | Yes | — | Any string 5–500 chars |
| depth | No | standard | brief, standard, deep |

## Outputs

Markdown file written to `skills/research-brief/outputs/`. Artifacts are gitignored — local only.

Filename pattern: `research_brief_{workflow_id}_{timestamp}.md`

## Routing

| Step | Name | Task Class | Alias | Model |
|---|---|---|---|---|
| step_1 | Validate input and plan research | general_short | cheap_openai | gpt-5.4-mini |
| step_2 | Research topic | complex_reasoning | reasoning_claude | claude-sonnet-4-6 |
| step_3 | Structure findings into brief | moderate | cheap_claude | claude-haiku-4-5-20251001 |
| step_4 | Validate output | general_short | cheap_openai | gpt-5.4-mini |
| step_5 | Write artifact to output | — | — | No inference — file write only |

Estimated cost per run: ~$0.017

## Resume

If a run is interrupted, resume from the last checkpoint:
```bash
~/nemoclaw-local-foundation/.venv313/bin/python \
  ~/nemoclaw-local-foundation/skills/skill-runner.py \
  --skill research-brief \
  --thread-id THREAD_ID \
  --resume
```

The thread ID is printed when the skill starts and when it completes.

## Output Sections

Every research brief contains these four required sections:

- **Background** — Context and framing of the topic
- **Key Findings** — Core research results
- **Open Questions** — Unresolved areas for further investigation
- **Recommendations** — Actionable next steps

## Validation

Output is validated before the artifact is written:
- Brief must be at least 200 characters
- Brief must contain all four required sections
- If validation fails, the artifact is not written and the skill pauses with status failed

## Known Limitations

- Linear execution only — steps run sequentially, no branching
- Single research pass — no iterative refinement loop
- No external tool integration — research is LLM-only, no web search
- Artifacts are local — not synced or backed up

## Full Documentation

See `docs/architecture/skill-system.md` for the complete skill.yaml specification and execution architecture.

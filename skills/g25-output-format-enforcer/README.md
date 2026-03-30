# g25-output-format-enforcer — Output Format Enforcer

> **Family:** F25 (Prompt Engineering and Model Optimization)
> **Domain:** G (Governance, Coordination, and Meta-Skills)
> **Tag:** internal
> **Type:** transformer
> **Schema:** v2
> **Runner:** >=4.0.0

## Purpose

Takes LLM output with format violations (fences, preamble, postamble, wrong
structure) and transforms it into the exact target format. Deterministic fixes
applied first; LLM reformat only when structural change is needed. Reusable
post-processor for any skill.

## Inputs

| Name | Type | Required | Description |
|---|---|---|---|
| `input_text` | string | yes | Raw LLM output to enforce |
| `target_format` | string | yes | `json`, `yaml`, `markdown`, `prose`, `csv` |
| `format_spec` | string | no | JSON: `{"required_keys": [...], "required_sections": [...], "max_length": N}` |
| `strip_preamble` | boolean | no | Default: true |
| `strip_postamble` | boolean | no | Default: true |
| `strip_fences` | boolean | no | Default: true |
| `preserve_content` | boolean | no | Default: true. Deterministically enforced. |

## format_spec Schema

```json
{
  "required_keys": ["title", "summary"],
  "required_sections": ["## Summary", "## Details"],
  "max_length": 5000,
  "min_length": 100,
  "column_headers": ["name", "value"]
}
```

All fields optional. Unknown keys rejected. Step 1 validates the schema.

## Steps

| Step | Name | Type | Description |
|---|---|---|---|
| step_1 | Detect format violations and classify repair needs | local | Parse, detect violations, validate format_spec, classify repair type |
| step_2 | Apply deterministic fixes and LLM reformat if needed | local | Strip fences/preamble/postamble. LLM called internally only for structural reformat. |
| step_3 | Validate output format and content preservation | local | Format compliance + factual token preservation check |
| step_4 | Write validated output artifact | local | Write artifact, hard-fail if step_3 failed |

## Key Design Decisions

- **Step 2 is `local`** — calls LLM internally only when deterministic fixes
  are insufficient (structural reformat needed). Most common case (fence/preamble
  stripping) costs zero LLM calls.
- **No critic loop** — format compliance is binary (pass/fail), not scored.
- **Content preservation is deterministic** — extracts factual tokens (numbers,
  URLs, emails, dates, versions) and verifies they exist in the output.
- **format_spec is structured JSON** — validated in step_1, rejected on bad schema.

## Usage

```bash
~/nemoclaw-local-foundation/.venv313/bin/python \
  ~/nemoclaw-local-foundation/skills/skill-runner.py \
  --skill g25-output-format-enforcer \
  --input input_text 'Here is the JSON you requested: ```json {"name": "test", "value": 42.5} ``` Hope this helps!' \
  --input target_format json \
  --input format_spec '{"required_keys": ["name", "value"]}'
```

## Composable

- **Output type:** `format_enforced_text`
- **Accepts input from:** any skill (universal post-processor)

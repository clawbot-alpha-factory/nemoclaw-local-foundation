# Output Format Enforcer

**ID:** `g25-output-format-enforcer` | **Version:** 1.0.0 | **Family:** F25 | **Domain:** G | **Type:** transformer | **Tag:** internal

## Description

Takes LLM output with format violations (fences, preamble, postamble, wrong structure) and transforms it into the exact target format. Deterministic fixes applied first; LLM reformat only when structural change is needed. Reusable post-processor for any skill.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `input_text` | string | Yes | The raw LLM output to be format-enforced |
| `target_format` | string | Yes | Expected output format |
| `format_spec` | string | No | JSON object defining specific format requirements. Schema: {"required_keys": [...], "required_sections": [...], "max_length": N,  "min_length": N, "column_headers": [...]}  |
| `strip_preamble` | boolean | No | Remove preamble like 'Here is...' or 'Sure, here is...' |
| `strip_postamble` | boolean | No | Remove trailing explanations after the main content |
| `strip_fences` | boolean | No | Remove markdown code fences wrapping the content |
| `preserve_content` | boolean | No | Preserve all factual tokens (numbers, identifiers, URLs, emails) and all semantic content. Deterministically enforced in step_3.  |

## Outputs

| Name | Type | Description |
|------|------|-------------|
| `result` | string | The format-enforced text |
| `result_file` | file_path | Path to the artifact |
| `envelope_file` | file_path | Path to the JSON envelope |

## Steps

- **step_1** — Detect format violations and classify repair needs (`local`, `general_short`)
- **step_2** — Apply deterministic fixes and LLM reformat if needed (`local`, `general_short`)
- **step_3** — Evaluate Format Compliance and Content Preservation (`critic`, `general_short`)
- **step_3b** — Improve Format Enforcement Based on Validation Issues (`llm`, `moderate`)
- **step_4** — Write validated output artifact (`local`, `general_short`)

## Quality Gate

- **Min Quality Score:** 10.0
- **Max Retries:** 5
- **Escalate Below:** 5.0
- **Critic Loop:** enabled, acceptance=10, max_improvements=5
- **Max Execution:** 30s
- **Max Cost:** $0.03

## Declarative Guarantees

- Output matches the target_format exactly
- All factual tokens (numbers, URLs, emails, identifiers) preserved if preserve_content is true
- No preamble, postamble, or fences remain if strip options are true
- JSON output is valid parseable JSON
- YAML output is valid parseable YAML
- format_spec requirements are met if provided

## Composability

- **Output Type:** format_enforced_text

## Example Usage

```json
{
  "skill_id": "g25-output-format-enforcer",
  "inputs": {
    "input_text": "Here is a summary of the market research:\n\nThe AI meeting assistant market is growing at 25 percent annually. Key players include Otter.ai, Fireflies, and Grain. The total addressable market is estimated at 5 billion dollars by 2027.",
    "target_format": "markdown"
  }
}
```

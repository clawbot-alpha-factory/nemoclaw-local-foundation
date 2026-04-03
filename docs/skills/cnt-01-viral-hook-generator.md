# Viral Hook Generator

**ID:** `cnt-01-viral-hook-generator` | **Version:** 1.0.0 | **Type:** generator | **Tag:** content

## Description

Pattern-based hooks for reels/TikTok/shorts. 10 hooks per topic. Uses proven viral frameworks: curiosity gap, contrarian, story open.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `topic` | string | Yes | Content topic or key message |
| `platform` | string | No | Target platform |

## Outputs

| Name | Type | Description |
|------|------|-------------|
| `result` | string | The generated output |
| `result_file` | file_path | Path to the markdown artifact |
| `envelope_file` | file_path | Path to JSON envelope for skill chaining |

## Quality Gate

- **Min Quality Score:** 7
- **Min Quality Score:** 10.0
- **Max Retries:** 5
- **Escalate Below:** 5.0
- **Critic Loop:** enabled, acceptance=N/A, max_improvements=N/A
- **Max Execution:** 120s
- **Max Cost:** $0.35

## Composability

- **Output Type:** content_generator_output

## Example Usage

```json
{
  "inputs": {
    "topic": "Why 90 percent of small businesses fail at AI adoption and the 3 counterintuitive steps that actually work for teams under 20 people",
    "platform": "instagram_reels"
  }
}
```

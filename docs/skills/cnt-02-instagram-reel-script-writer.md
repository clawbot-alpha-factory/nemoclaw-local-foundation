# Instagram Reel Script Writer

**ID:** `cnt-02-instagram-reel-script-writer` | **Version:** 1.0.0 | **Type:** generator | **Tag:** content

## Description

Full reel: hook (3s) → context (10s) → value (20s) → CTA (5s). Caption + hashtags + posting time.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `topic` | string | Yes | Reel topic |
| `cta_goal` | string | No | Call to action goal |

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
    "topic": "How a solo founder automated 80 percent of their customer support using AI agents and saved 25 hours per week without writing a single line of code",
    "cta_goal": "follow_and_dm"
  }
}
```

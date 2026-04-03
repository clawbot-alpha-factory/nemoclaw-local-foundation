# Cross-Channel Distributor

**ID:** `cnt-08-cross-channel-distributor` | **Version:** 1.0.0 | **Type:** orchestrator | **Tag:** content

## Description

Takes content → distributes across all channels via bridges. Tracks per-channel performance. Bridge-connected executor.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `content_piece` | string | Yes | Content to distribute |
| `channels` | string | No | Distribution channels |

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
- **Max Execution:** 180s
- **Max Cost:** $0.5

## Composability

- **Output Type:** content_orchestrator_output

## Example Usage

```json
{
  "inputs": {
    "content_piece": "We analyzed 500 B2B outreach campaigns and found that personalized AI-generated sequences outperform templated ones by 3.4x in reply rates. The secret is not just using the prospect's name but referencing their company's recent milestones, tech stack decisions, and hiring patterns. Here are the 5 data points that matter most for B2B personalization and how to automate gathering them without manual research.",
    "channels": "linkedin,instagram,twitter,email"
  }
}
```

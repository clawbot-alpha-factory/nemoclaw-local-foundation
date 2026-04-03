# Community Growth Engine

**ID:** `scl-05-community-growth-engine` | **Version:** 1.0.0 | **Type:** orchestrator | **Tag:** scale

## Description

Content strategy + engagement rules + member acquisition sequence + retention triggers. Full community lifecycle.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `community_vision` | string | Yes | Community purpose, target members, platform |
| `platform` | string | No | Community platform |

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

- **Output Type:** scale_orchestrator_output

## Example Usage

```json
{
  "inputs": {
    "community_vision": "Build a community of 500 AI-forward B2B founders who share automation playbooks, exchange leads, and beta-test new AI tools. Focus on practical implementation over theory. Target members: SaaS founders with 5-100 employees who are actively implementing AI in their operations. Value: weekly automation teardowns, member deal flow sharing, early access to new NemoClaw features.",
    "platform": "discord"
  }
}
```

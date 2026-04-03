# Competitive Intelligence Monitor

**ID:** `biz-07-competitive-intelligence-monitor` | **Version:** 1.0.0 | **Type:** analyzer | **Tag:** business

## Description

Daily scan of competitor pricing, features, messaging. Weekly summary. Alerts on major changes. Enforced action output.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `competitors` | string | Yes | Competitors to monitor: names, URLs, focus areas |
| `focus_areas` | string | No | What to monitor |

## Outputs

| Name | Type | Description |
|------|------|-------------|
| `result` | string | The generated output |
| `result_file` | file_path | Path to the markdown artifact |
| `envelope_file` | file_path | Path to JSON envelope for skill chaining |
| `insight` | string | Key insight from analysis |
| `recommended_action` | string | Specific action to take |
| `trigger_skill` | string | Skill ID to trigger (or null to stop) |
| `confidence` | float | Confidence score 0-1 |

## Quality Gate

- **Min Quality Score:** 7
- **Min Quality Score:** 10.0
- **Max Retries:** 5
- **Escalate Below:** 5.0
- **Critic Loop:** enabled, acceptance=N/A, max_improvements=N/A
- **Max Execution:** 120s
- **Max Cost:** $0.3

## Composability

- **Output Type:** business_analyzer_output

## Example Usage

```json
{
  "inputs": {
    "competitors": "Jasper AI (jasper.ai) - content generation focus, Copy.ai (copy.ai) - marketing copy automation, Writesonic (writesonic.com) - multi-format content, HubSpot AI (hubspot.com) - integrated marketing suite",
    "focus_areas": "pricing,features,messaging,hiring"
  }
}
```

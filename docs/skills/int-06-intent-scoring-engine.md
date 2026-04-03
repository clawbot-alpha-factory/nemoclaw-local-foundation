# Intent Scoring Engine

**ID:** `int-06-intent-scoring-engine` | **Version:** 1.0.0 | **Type:** analyzer | **Tag:** intelligence

## Description

Turns raw signals into scored buying intent. Pain level, buying intent, urgency, recommended offer type. Feeds into lead qualification.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `raw_signals` | string | Yes | Raw demand signals with context |

## Outputs

| Name | Type | Description |
|------|------|-------------|
| `result` | string |  |
| `envelope_file` | file_path |  |
| `insight` | string |  |
| `recommended_action` | string |  |
| `trigger_skill` | string |  |
| `confidence` | float |  |

## Quality Gate

- **Min Quality Score:** 7
- **Min Quality Score:** 10.0
- **Max Retries:** 5
- **Escalate Below:** 5.0
- **Critic Loop:** enabled, acceptance=N/A, max_improvements=N/A
- **Max Execution:** 120s
- **Max Cost:** $0.3

## Example Usage

```json
{
  "inputs": {
    "raw_signals": "Signal 1: User asked 'What is the best AI tool for automating sales follow-ups under $200/mo?' on Reddit (r/SaaS, 45 upvotes). Signal 2: LinkedIn comment 'We just lost our only SDR and need to automate outreach ASAP' (high urgency). Signal 3: Twitter reply 'Interesting, do you offer a free trial?' on our product post. Signal 4: Instagram DM 'How much does your automation service cost for a team of 8?' Signal 5: Blog comment 'Great article, but how does this work with HubSpot specifically?'"
  }
}
```

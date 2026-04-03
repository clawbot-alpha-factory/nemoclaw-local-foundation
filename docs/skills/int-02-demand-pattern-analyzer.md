# Demand Pattern Analyzer

**ID:** `int-02-demand-pattern-analyzer` | **Version:** 1.0.0 | **Type:** analyzer | **Tag:** intelligence

## Description

Clusters comments into pain points, desires, objections, confusion. Detects repeated problems, urgency signals, buying intent. Enforced output: insight + recommended_action + trigger_skill + confidence + demand_volume.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `raw_signals` | string | Yes | Raw comments and signals from scraper |
| `niche` | string | No | Market niche for context |

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

- **Output Type:** intelligence_analyzer_output

## Example Usage

```json
{
  "inputs": {
    "raw_signals": "Comment 1: 'Does anyone know a tool that can automate follow-up emails based on CRM activity?' (47 likes). Comment 2: 'We spent $12K on an agency and got nothing, looking for AI alternative' (89 likes). Comment 3: 'How do you handle lead scoring without a dedicated ops person?' (23 likes). Comment 4: 'Need help connecting our Slack notifications to our sales pipeline' (12 likes). Comment 5: 'Is there an AI that can write proposals based on discovery call notes?' (156 likes). Comment 6: 'Struggling to keep up with content creation across 4 platforms' (67 likes).",
    "niche": "B2B SaaS automation"
  }
}
```

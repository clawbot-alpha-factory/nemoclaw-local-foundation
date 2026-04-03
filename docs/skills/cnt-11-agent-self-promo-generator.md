# Agent Self-Promotion Generator

**ID:** `Agent Self-Promotion Generator` | **Version:** 1.0.0 | **Family:** 11 | **Domain:** C | **Tag:** social-media

## Description

Generates weekly self-promotion briefs for each agent. Collects performance data, recent wins, milestone progress, and formats into social media content briefs for the social_media_lead (Zara) to turn into viral content.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `agent_id` | string | Yes | The agent ID to generate a promotion brief for |
| `performance_data` | string | Yes | JSON string of agent performance metrics, recent wins, milestones |

## Outputs

| Name | Type | Description |
|------|------|-------------|
| `result` | string | Self-promotion brief with talking points, suggested hooks, visual ideas |
| `result_file` | string | Path to the output artifact |
| `envelope_file` | string | Path to the chaining envelope |

## Quality Gate

- **Min Quality Score:** 7
- **Min Quality Score:** 10.0
- **Max Retries:** 5
- **Escalate Below:** 5.0
- **Critic Loop:** enabled, acceptance=N/A, max_improvements=N/A
- **Max Execution:** 120s
- **Max Cost:** $0.35

## Composability

- **Output Type:** markdown

## Example Usage

```json
{
  "inputs": {
    "agent_id": "sales_outreach_lead",
    "performance_data": "{\"name\": \"Hassan\", \"wins\": [\"Closed 3 deals worth $4,500\", \"Booked 12 meetings this week\", \"Response rate up 23%\"], \"metrics\": {\"pipeline_value\": 45000, \"deals_closed\": 3, \"meetings_booked\": 12}, \"milestones\": [\"First $10K month\"], \"character\": \"SpongeBob SquarePants\"}"
  }
}
```

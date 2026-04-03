# Upsell Opportunity Detector

**ID:** `biz-06-upsell-opportunity-detector` | **Version:** 1.0.0 | **Type:** analyzer | **Tag:** business

## Description

Analyzes client usage + needs → identifies expansion revenue. Outputs specific upsell proposal. Enforced action output.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `client_usage_data` | string | Yes | Client usage patterns, current services, satisfaction |
| `service_catalog` | string | No | Available services for upsell |

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
    "client_usage_data": "Client: GreenLeaf Ventures. Current service: Content Automation ($2,000/mo). Usage: generating 45 blog posts/month (capacity 50), 120 social posts (capacity 150). Satisfaction score: 9.1/10. Mentioned interest in email marketing during last call. Website traffic up 34 percent since engagement. Team has grown from 8 to 14 people in 3 months.",
    "service_catalog": "Email Campaign Automation ($1,500/mo), Lead Scoring Engine ($2,200/mo), Analytics Dashboard Pro ($800/mo), Full Revenue Operations Suite ($5,500/mo)"
  }
}
```

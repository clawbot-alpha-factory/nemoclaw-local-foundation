# Revenue Attribution Analyzer

**ID:** `rev-03-revenue-attribution-analyzer` | **Version:** 1.0.0 | **Type:** analyzer | **Tag:** revenue

## Description

Maps every dollar to source: channel, message, agent action. Outputs ROI per channel. Enforced output: insight + recommended_action + trigger_skill.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `revenue_data` | string | Yes | Revenue events with source tracking data |
| `period` | string | No | Analysis period |

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

- **Output Type:** revenue_analyzer_output

## Example Usage

```json
{
  "inputs": {
    "revenue_data": "Deal 1: DataBridge Analytics, $12,000, source=LinkedIn outreach, touches: LinkedIn connect -> email sequence -> demo -> proposal -> close (18 days). Deal 2: Meridian SaaS, $8,500, source=inbound blog, touches: blog visit -> ebook download -> email nurture -> webinar -> demo -> close (32 days). Deal 3: SwiftOps, $6,000, source=referral from existing client, touches: intro email -> demo -> close (7 days). Deal 4: NovaTech, $22,000, source=Google Ads, touches: ad click -> landing page -> demo request -> discovery call -> proposal -> negotiation -> close (28 days).",
    "period": "last_30_days"
  }
}
```

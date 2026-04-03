# Content Performance Analyzer

**ID:** `cnt-07-content-performance-analyzer` | **Version:** 1.0.0 | **Type:** analyzer | **Tag:** content

## Description

Tracks which content drives leads, engagement, revenue. Enforced output: insight + recommended_action + trigger_skill.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `content_metrics` | string | Yes | Per-content metrics: views, engagement, leads, revenue |
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

- **Output Type:** content_analyzer_output

## Example Usage

```json
{
  "inputs": {
    "content_metrics": "LinkedIn Post 'AI ROI Calculator': 4,200 views, 89 likes, 23 comments, 12 shares, 4 DM leads. Instagram Reel 'Day in Life of AI Founder': 18,500 views, 342 likes, 67 comments, 2 DM leads. Blog 'Automation Playbook': 1,800 views, avg 4.2min read time, 45 email signups, 3 demo requests. Email Newsletter: 2,100 sent, 42 percent open rate, 8.1 percent click rate, 2 demo bookings. TikTok 'AI Tools Review': 52,000 views, 1,200 likes, 89 comments, 0 direct leads.",
    "period": "last_7_days"
  }
}
```

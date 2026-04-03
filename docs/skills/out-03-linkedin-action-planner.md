# LinkedIn Action Planner

**ID:** `out-03-linkedin-action-planner` | **Version:** 1.0.0 | **Type:** generator | **Tag:** outreach

## Description

Generates connection requests, InMail messages, comment strategies. Ready for LinkedIn bridge.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `prospect_linkedin` | string | Yes | Prospect LinkedIn info: name, headline, recent activity |
| `approach` | string | No | Approach: warm_connection, inmail, comment_first |

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

- **Output Type:** outreach_generator_output

## Example Usage

```json
{
  "inputs": {
    "prospect_linkedin": "Elena Voroshilova, VP of Operations at ScaleOps Platform (120 employees, Dubai). Headline: 'Building scalable ops for high-growth SaaS'. Recent activity: shared article about AI in operations management, commented on a post about reducing manual workflows, liked 3 posts about automation tools this week. Mutual connections: 2 (both in SaaS space).",
    "approach": "warm_connection"
  }
}
```

# Cross-Channel Scheduler

**ID:** `scl-07-cross-channel-scheduler` | **Version:** 1.0.0 | **Type:** orchestrator | **Tag:** scale

## Description

Takes content queue → schedules across all channels at optimal times. Bridge-ready for Buffer/Hootsuite APIs.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `content_queue` | string | Yes | Content pieces ready for scheduling |
| `timezone` | string | No | Target timezone |

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
    "content_queue": "Post 1: Blog article 'AI Onboarding Systems' - ready for LinkedIn summary, Twitter thread, Instagram carousel. Post 2: Case study 'Pinnacle Logistics 97% faster quotes' - ready for all channels. Post 3: Webinar promo 'AI Sales Pipeline in 30 Days' - needs urgency-based scheduling (event in 10 days). Post 4: Client testimonial quote card from Meridian SaaS CEO. Post 5: Behind-the-scenes reel showing AI agent dashboard in action.",
    "timezone": "Asia/Amman"
  }
}
```

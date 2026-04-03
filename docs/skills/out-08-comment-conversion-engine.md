# Comment Conversion Engine

**ID:** `out-08-comment-conversion-engine` | **Version:** 1.0.0 | **Type:** executor | **Tag:** outreach

## Description

Monitors comments via Apify. Detects questions, pain, interest signals. Auto-replies publicly (value-first), DMs when appropriate, routes hot leads to Sales Closer. Free inbound lead capture at scale.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `monitored_accounts` | string | Yes | Accounts/posts to monitor for comments |
| `response_tone` | string | No | Response tone: helpful_expert, casual, authoritative |

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
- **Max Execution:** 90s
- **Max Cost:** $0.25

## Composability

- **Output Type:** outreach_executor_output

## Example Usage

```json
{
  "inputs": {
    "monitored_accounts": "Our LinkedIn company page posts about AI automation, our Instagram @nemoclaw_ai posts about founder productivity, competitor threads on Twitter where users express frustration with manual sales processes, Reddit r/SaaS threads about outreach automation",
    "response_tone": "helpful_expert"
  }
}
```

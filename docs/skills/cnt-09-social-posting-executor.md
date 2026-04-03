# Social Posting Executor

**ID:** `cnt-09-social-posting-executor` | **Version:** 1.0.0 | **Type:** executor | **Tag:** content

## Description

Posts to IG/TikTok/LinkedIn via bridges. Tracks performance per post. Feeds analytics back into cnt-07. Bridge-ready for Buffer/Meta APIs.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `post_content` | string | Yes | Content to post with platform-specific formatting |
| `platform` | string | Yes | Target platform: linkedin, instagram, tiktok, twitter |

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

- **Output Type:** content_executor_output

## Example Usage

```json
{
  "inputs": {
    "post_content": "Most founders think AI automation is about replacing people. Wrong. It is about amplifying what your best people already do well. We helped a 12-person SaaS team handle the workload of a 40-person team. Not by cutting staff but by automating the repetitive 60 percent of every role. The result: faster shipping, happier team, 3x revenue growth in 8 months.",
    "platform": "linkedin"
  }
}
```

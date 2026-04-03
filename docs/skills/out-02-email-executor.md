# Email Executor

**ID:** `out-02-email-executor` | **Version:** 1.0.0 | **Type:** executor | **Tag:** outreach

## Description

Sends emails via Resend bridge. Tracks opens/replies. Triggers next step in sequence. Bridge-connected.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `email_spec` | string | Yes | Email details: to, subject, body, from_email |
| `sequence_context` | string | No | Where in the sequence this email falls |

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
    "email_spec": "To: ahmad.khalil@cloudserve.io. Subject: Quick question about your onboarding workflow. Body: Hi Ahmad, I noticed your LinkedIn post about streamlining customer onboarding. We helped a similar-sized SaaS company reduce their onboarding from 3 weeks to 4 days using AI automation. Would a 15-minute walkthrough of how we did it be useful? From: outreach@nemoclaw.ai",
    "sequence_context": "Touch 1 of 5 in the discovery sequence. Follow-up scheduled for day 3 if no reply."
  }
}
```

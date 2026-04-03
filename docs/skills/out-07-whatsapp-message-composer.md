# WhatsApp Message Composer

**ID:** `out-07-whatsapp-message-composer` | **Version:** 1.0.0 | **Type:** generator | **Tag:** outreach

## Description

MENA-optimized. Relationship-first tone. Arabic + English. Ready for WhatsApp bridge. Warm intro weighting 3x.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `recipient_context` | string | Yes | Recipient details and relationship stage |
| `language` | string | No | Language: en, ar, bilingual |

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
    "recipient_context": "Nadia Hasan, Head of Growth at DataStream Analytics in Riyadh. Met at a SaaS conference last week. She expressed interest in AI-powered content automation for her team of 12 marketers. Prefers informal communication. Has responded positively to previous WhatsApp messages. Relationship stage: warm lead, post-conference follow-up.",
    "language": "en"
  }
}
```

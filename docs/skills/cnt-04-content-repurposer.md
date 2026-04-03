# Content Repurposer

**ID:** `cnt-04-content-repurposer` | **Version:** 1.0.0 | **Type:** transformer | **Tag:** content

## Description

1 piece → 10 formats: blog → LinkedIn post → tweet thread → reel script → email excerpt → podcast talking points → infographic brief → carousel → quote card → newsletter section.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `source_content` | string | Yes | Original content to repurpose |
| `target_formats` | string | No | Which formats to generate |

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
- **Max Cost:** $0.3

## Composability

- **Output Type:** content_transformer_output

## Example Usage

```json
{
  "inputs": {
    "source_content": "The future of B2B sales is not about hiring more SDRs. It is about building intelligent systems that qualify leads, personalize outreach, and follow up relentlessly without human intervention. Our analysis of 200 B2B SaaS companies shows that AI-driven outreach achieves 3.2x higher response rates than manual sequences. The key differentiator is not the AI itself but how it integrates with existing CRM workflows. Companies that deploy AI agents alongside their sales team see 47 percent faster deal cycles and 28 percent higher average contract values. The most successful implementations start with a single high-impact use case like automated follow-ups rather than trying to automate everything at once.",
    "target_formats": "all"
  }
}
```

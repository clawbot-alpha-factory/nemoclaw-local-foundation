# Blog Post Writer

**ID:** `k48-blog-post-writer` | **Version:** 1.0.0 | **Family:** K48 | **Domain:** K | **Type:** generator | **Tag:** content

## Description

Writes SEO-optimized blog posts with structured headings, internal linking suggestions, and meta descriptions.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `topic` | string | Yes | Blog post topic and target keyword |
| `target_audience` | string | Yes | Intended reader persona |

## Outputs

| Name | Type | Description |
|------|------|-------------|
| `result` | string | The generated output |
| `result_file` | file_path | Path to the markdown artifact |
| `envelope_file` | file_path | Path to the JSON envelope for skill chaining |

## Quality Gate

- **Min Quality Score:** 7
- **Min Quality Score:** 10.0
- **Max Retries:** 5
- **Escalate Below:** 5.0
- **Critic Loop:** enabled, acceptance=N/A, max_improvements=N/A
- **Max Execution:** 120s
- **Max Cost:** $0.35

## Composability

- **Output Type:** content_generator_output

## Example Usage

```json
{
  "inputs": {
    "topic": "How to build an AI-powered customer onboarding system that reduces time-to-value by 60 percent: a practical guide for B2B SaaS companies",
    "target_audience": "VP of Customer Success and Head of Operations at B2B SaaS companies with 50-500 employees who are struggling with manual onboarding processes and high churn in the first 90 days"
  }
}
```

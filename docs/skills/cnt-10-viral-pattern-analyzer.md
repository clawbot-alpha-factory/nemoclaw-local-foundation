# Viral Pattern Analyzer

**ID:** `cnt-10-viral-pattern-analyzer` | **Version:** 1.0.0 | **Type:** analyzer | **Tag:** content

## Description

Scrapes top-performing posts. Extracts hook structures, sentence patterns, topic clusters, format types. Removes guesswork from content. Feeds cnt-01 hooks, cnt-02/03 scripts. Enforced action output.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `platform_data` | string | Yes | Top-performing posts with engagement metrics |
| `niche` | string | No | Content niche |

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
    "platform_data": "Post 1: 'Hot take: SDRs are not going away, they are evolving' - 52K views, 890 likes, 234 comments, 67 reposts. Post 2: 'I fired my marketing agency and replaced them with AI' - 128K views, 2,100 likes, 567 comments, 312 reposts. Post 3: 'Step by step: How I built a $10K/mo AI service in 30 days' - 89K views, 1,450 likes, 345 comments, 189 reposts. Post 4: 'Why your CRM is killing your sales (and what to use instead)' - 34K views, 456 likes, 112 comments, 45 reposts. Post 5: 'The $0 marketing stack that generates 50 leads/week' - 95K views, 1,800 likes, 423 comments, 245 reposts.",
    "niche": "B2B SaaS"
  }
}
```

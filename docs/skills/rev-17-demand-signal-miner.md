# Demand Signal Miner

**ID:** `rev-17-demand-signal-miner` | **Version:** 1.0.0 | **Type:** executor | **Tag:** intelligence

## Description

Scrapes Twitter/X, Instagram, TikTok, Reddit, LinkedIn via Apify. Extracts pain points, buying intent signals, repeated complaints, budget signals. Outputs demand clusters with urgency scores. Feeds rev-10, cnt-01, rev-08.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `target_niches` | string | Yes | Niches to mine: keywords, hashtags, accounts, subreddits |
| `platforms` | string | No | Platforms to scrape |

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

- **Output Type:** intelligence_executor_output

## Example Usage

```json
{
  "inputs": {
    "target_niches": "Keywords: 'automate sales outreach', 'AI for small business', 'replace SDR with AI'. Hashtags: #NoCodeAutomation, #SaaSGrowth, #AITools. Accounts: @theaikidboss, @aisolopreneur. Subreddits: r/SaaS, r/Entrepreneur, r/smallbusiness.",
    "platforms": "twitter,instagram,tiktok,reddit,linkedin"
  }
}
```

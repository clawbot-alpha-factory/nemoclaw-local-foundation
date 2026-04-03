# Cross-Platform Scraper

**ID:** `int-05-cross-platform-scraper` | **Version:** 1.0.0 | **Type:** executor | **Tag:** intelligence

## Description

Scrapes Twitter/X, Instagram, TikTok, YouTube, Reddit via Apify. Extracts comments, replies, discussions. Feeds into int-02 Demand Pattern Analyzer. Bridge-ready for Apify API.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `targets` | string | Yes | Scraping targets: URLs, usernames, hashtags, subreddits |
| `platforms` | string | No | Platforms to scrape |

## Outputs

| Name | Type | Description |
|------|------|-------------|
| `result` | string |  |
| `result_file` | file_path |  |
| `envelope_file` | file_path |  |

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
    "targets": "@buildinpublic on Twitter, r/SaaS and r/Entrepreneur on Reddit, #NoCodeTools on Instagram, 'AI business automation' search on YouTube",
    "platforms": "twitter,instagram,youtube,reddit"
  }
}
```

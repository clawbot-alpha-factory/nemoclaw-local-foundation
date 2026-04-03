# Comment & Signal Scraper

**ID:** `int-01-comment-signal-scraper` | **Version:** 1.0.0 | **Type:** executor | **Tag:** intelligence

## Description

Scrapes IG/TikTok/YouTube/Twitter comments from competitors and influencers. Extracts raw demand signals. Apify/Puppeteer bridge-ready.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `targets` | string | Yes | Accounts/posts to scrape: URLs, usernames, hashtags |
| `platforms` | string | No | Platforms to scan |

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
    "targets": "@aiautomation_tips on Instagram, #AIforBusiness on TikTok, 'How to automate your business' YouTube videos by top creators, @SaaS_growth on Twitter",
    "platforms": "instagram,tiktok,youtube,twitter"
  }
}
```

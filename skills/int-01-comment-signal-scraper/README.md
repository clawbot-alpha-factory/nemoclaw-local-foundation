# int-01-comment-signal-scraper

**ID:** `int-01-comment-signal-scraper`
**Version:** 1.0.0
**Type:** executor
**Family:** ? | **Domain:** ? | **Tag:** intelligence

## Description

Scrapes IG/TikTok/YouTube/Twitter comments from competitors and influencers. Extracts raw demand signals. Apify/Puppeteer bridge-ready.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `targets` | string | Yes | Accounts/posts to scrape: URLs, usernames, hashtags |
| `platforms` | string | No | Platforms to scan |

## Outputs

- `result`
- `result_file`
- `envelope_file`

## Usage

```bash
.venv313/bin/python3 skills/int-01-comment-signal-scraper/run.py --force --input targets "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)

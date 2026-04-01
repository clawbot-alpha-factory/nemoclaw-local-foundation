# int-05-cross-platform-scraper

**ID:** `int-05-cross-platform-scraper`
**Version:** 1.0.0
**Type:** executor
**Family:** ? | **Domain:** ? | **Tag:** intelligence

## Description

Scrapes Twitter/X, Instagram, TikTok, YouTube, Reddit via Apify. Extracts comments, replies, discussions. Feeds into int-02 Demand Pattern Analyzer. Bridge-ready for Apify API.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `targets` | string | Yes | Scraping targets: URLs, usernames, hashtags, subreddits |
| `platforms` | string | No | Platforms to scrape |

## Outputs

- `result`
- `result_file`
- `envelope_file`

## Usage

```bash
.venv313/bin/python3 skills/int-05-cross-platform-scraper/run.py --force --input targets "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)

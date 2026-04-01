# rev-17-demand-signal-miner

**ID:** `rev-17-demand-signal-miner`
**Version:** 1.0.0
**Type:** executor
**Family:** ? | **Domain:** ? | **Tag:** intelligence

## Description

Scrapes Twitter/X, Instagram, TikTok, Reddit, LinkedIn via Apify. Extracts pain points, buying intent signals, repeated complaints, budget signals. Outputs demand clusters with urgency scores. Feeds rev-10, cnt-01, rev-08.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `target_niches` | string | Yes | Niches to mine: keywords, hashtags, accounts, subreddits |
| `platforms` | string | No | Platforms to scrape |

## Outputs

- `result`
- `result_file`
- `envelope_file`

## Usage

```bash
.venv313/bin/python3 skills/rev-17-demand-signal-miner/run.py --force --input target_niches "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)

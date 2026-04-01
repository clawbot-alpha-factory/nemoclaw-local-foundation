# cnt-10-viral-pattern-analyzer

**ID:** `cnt-10-viral-pattern-analyzer`
**Version:** 1.0.0
**Type:** executor
**Family:** ? | **Domain:** ? | **Tag:** content

## Description

Scrapes top-performing posts. Extracts hook structures, sentence patterns, topic clusters, format types. Removes guesswork from content. Feeds cnt-01 hooks, cnt-02/03 scripts. Enforced action output.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `platform_data` | string | Yes | Top-performing posts with engagement metrics |
| `niche` | string | No | Content niche |

## Outputs

- `result`
- `result_file`
- `envelope_file`
- `insight`
- `recommended_action`
- `trigger_skill`
- `confidence`

## Usage

```bash
.venv313/bin/python3 skills/cnt-10-viral-pattern-analyzer/run.py --force --input platform_data "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)

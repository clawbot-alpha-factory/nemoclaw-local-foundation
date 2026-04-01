# rev-10-lead-source-engine

**ID:** `rev-10-lead-source-engine`
**Version:** 1.0.0
**Type:** executor
**Family:** ? | **Domain:** ? | **Tag:** revenue

## Description

Pulls leads from Apollo, LinkedIn, website inbound, referrals. Feeds directly into rev-02 Lead Qualification Engine. Closes top-of-funnel gap.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `target_icp` | string | Yes | Target ICP for lead sourcing |
| `sources` | string | No | Lead sources to activate |

## Outputs

- `result`
- `result_file`
- `envelope_file`

## Usage

```bash
.venv313/bin/python3 skills/rev-10-lead-source-engine/run.py --force --input target_icp "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)

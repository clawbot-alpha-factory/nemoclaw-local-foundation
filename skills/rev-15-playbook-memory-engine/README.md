# rev-15-playbook-memory-engine

**ID:** `rev-15-playbook-memory-engine`
**Version:** 1.0.0
**Type:** executor
**Family:** ? | **Domain:** ? | **Tag:** revenue

## Description

Stores winning campaigns, failed experiments, best offers, top channels per niche. System stops starting from zero. Persists to ~/.nemoclaw/playbooks.json.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `campaign_results` | string | Yes | Recent campaign/experiment results with outcomes |
| `existing_playbooks` | string | No | Current playbook entries for context |

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
.venv313/bin/python3 skills/rev-15-playbook-memory-engine/run.py --force --input campaign_results "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)

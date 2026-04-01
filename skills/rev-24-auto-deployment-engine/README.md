# rev-24-auto-deployment-engine

**ID:** `rev-24-auto-deployment-engine`
**Version:** 1.0.0
**Type:** executor
**Family:** ? | **Domain:** ? | **Tag:** revenue

## Description

Generate offer → create landing page → deploy → connect tracking → start traffic. Full deployment loop. Bridge-ready for Webflow/Framer.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `offer_spec` | string | Yes | Offer details: name, price, value prop, target audience |

## Outputs

- `result`
- `envelope_file`

## Usage

```bash
.venv313/bin/python3 skills/rev-24-auto-deployment-engine/run.py --force --input offer_spec "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)

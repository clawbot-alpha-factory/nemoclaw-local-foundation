# j36-mvp-scope-definer

**ID:** `j36-mvp-scope-definer`
**Version:** 1.0.0
**Type:** executor
**Family:** F36 | **Domain:** J | **Tag:** dual-use

## Description

An MVP scope definer that takes a product idea, target audience, resource constraints, and timeline. Produces a structured MVP scope document with prioritized feature list (MoSCoW), user journey map for core flow, technical scope boundaries, launch criteria checklist, risk-adjusted timeline, explicit out-of-scope section, and resource allocation recommendations. Supports scope-driven generation modes and grounds all timeline estimates in stated constraints.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `product_idea` | string | Yes | Description of the product idea including its core value proposition and problem |
| `target_audience` | string | Yes | Description of the target audience including demographics, pain points, and user |
| `resource_constraints` | string | Yes | Available resources including team size, skill sets, budget, and infrastructure. |
| `timeline` | string | Yes | Target timeline for MVP delivery including hard deadlines, milestones, and any e |
| `scope_mode` | string | No | Scope generation mode controlling feature count: lean (3-5 features), balanced ( |
| `domain_context` | string | No | Optional additional context about the industry, regulatory requirements, or comp |
| `existing_assets` | string | No | Optional description of existing code, infrastructure, APIs, or third-party serv |

## Execution Steps

1. **Parse inputs and build scoping plan** (local) — Validates all inputs, extracts structured data from resource constraints and timeline, determines feature count range based on scope_mode (lean=3-5, balanced=5-10, comprehensive=10-15), identifies existing assets that affect build-vs-buy decisions, and constructs a generation plan with grounding anchors for timeline estimates.
2. **Generate comprehensive MVP scope document** (llm) — Generates the full MVP scope document using the generation plan from step_1. Produces: (1) MoSCoW-prioritized feature list within the scope_mode range, (2) user journey map for core flow only, (3) technical scope boundaries (build vs buy vs skip), (4) launch criteria checklist with measurable thresholds, (5) risk-adjusted timeline with milestones grounded in stated constraints, (6) explicit out-of-scope section to prevent scope creep, (7) resource allocation recommendations. All timeline estimates must reference specific resource constraints — no fabricated durations.
3. **Evaluate scope quality and grounding integrity** (critic) — Two-layer validation of the generated MVP scope document. Deterministic layer: verifies presence of all required sections (MoSCoW features, user journey, technical boundaries, launch criteria, timeline, out-of-scope, resource allocation), checks feature count falls within scope_mode range, validates that launch criteria include measurable thresholds, confirms out-of-scope section exists. LLM evaluation layer: scores quality across dimensions — MoSCoW rigor (proper must/should/could/won't categorization), timeline grounding (estimates traceable to stated constraints, no fabricated durations), technical boundary clarity (clear build/buy/skip rationale), launch criteria measurability, user journey coherence, and scope creep prevention strength. Combines scores using min() to produce final quality_score 0-10.
4. **Improve scope document from critic feedback** (llm) — Revises the MVP scope document based on specific critic feedback. Addresses identified weaknesses: strengthens MoSCoW categorization if features were misclassified, re-grounds timeline estimates in stated resource constraints if fabrication was detected, sharpens technical boundary rationale, adds measurable thresholds to launch criteria that lacked them, strengthens out-of-scope section if scope creep risks were identified, and improves user journey coherence. Preserves all sections that scored well while surgically improving flagged areas.
5. **Write final scope artifact to disk** (local) — Final deterministic gate that selects the highest-quality scope document from generation candidates, performs a last structural integrity check ensuring all seven required sections are present, and writes the artifact to the configured storage location. Returns confirmation of artifact write.

## Outputs

- `result`
- `result_file`
- `envelope_file`

## Usage

```bash
.venv313/bin/python3 skills/j36-mvp-scope-definer/run.py --force --input product_idea "value" --input target_audience "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)

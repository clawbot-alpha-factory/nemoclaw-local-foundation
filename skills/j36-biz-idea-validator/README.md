# j36-biz-idea-validator

**ID:** `j36-biz-idea-validator`
**Version:** 1.0.0
**Type:** executor
**Family:** F36 | **Domain:** J | **Tag:** dual-use

## Description

A business idea validator that takes a business idea, target market, and competitive landscape. Produces structured validation output with market viability assessment (TAM/SAM/SOM with three-path sizing), competitive positioning analysis, revenue model feasibility with revenue grounding (numeric tokens or derivation chain or data gap acknowledgment), risk assessment with categorized risks (market, technical, financial, regulatory, operational), go/no-go recommendation linked to specific findings, and actionable next steps. Scope-driven generation with anti-fabrication controls ensuring all market data is grounded in input or explicitly flagged as estimates.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `business_idea` | string | Yes | Description of the business idea including the product or service, value proposi |
| `target_market` | string | Yes | Description of the target market including customer segments, demographics, geog |
| `competitive_landscape` | string | Yes | Description of known competitors, their positioning, strengths, weaknesses, and  |
| `scope` | string | No | Depth of validation analysis. Quick produces 3-5 items per section, standard pro |
| `revenue_model_hints` | string | No | Optional hints about intended revenue model (e.g., SaaS subscription, marketplac |
| `known_constraints` | string | No | Optional known constraints such as budget limits, regulatory requirements, geogr |

## Execution Steps

1. **Parse inputs and build validation plan** (local) — Parses and validates all inputs. Determines scope-driven item counts (quick=3-5, standard=5-10, comprehensive=10-20). Extracts structured data from business_idea, target_market, and competitive_landscape. Identifies any numeric market data provided in inputs for grounding. Builds a generation plan specifying sections, depth targets, and grounding constraints.
2. **Generate comprehensive business validation report** (llm) — Generates the full structured business idea validation report following the generation plan from step_1. Produces all required sections: (1) Market Viability Assessment with TAM/SAM/SOM using three-path sizing (top-down, bottom-up, value-theory) where each figure includes a derivation chain or is explicitly flagged as an estimate with stated assumptions; (2) Competitive Positioning Analysis mapping competitors on key dimensions; (3) Revenue Model Feasibility with revenue grounding — every revenue projection must include numeric tokens, a derivation chain, or an explicit data gap acknowledgment; (4) Risk Assessment with categorized risks across market, technical, financial, regulatory, and operational dimensions; (5) Go/No-Go Recommendation explicitly linked to specific findings from prior sections; (6) Actionable Next Steps prioritized by impact. Item counts per section follow scope setting. Anti-fabrication rule: all market data must trace to input data or be flagged as [ESTIMATE: assumption stated].
3. **Evaluate validation report quality and grounding** (critic) — Two-layer validation of the generated report. Deterministic layer: checks presence of all required sections (market viability, competitive positioning, revenue feasibility, risk assessment, go/no-go, next steps), verifies TAM/SAM/SOM figures are present with sizing paths, counts items per section against scope targets, checks that revenue projections contain numeric tokens or derivation chains or [ESTIMATE] flags, verifies risk categories (market, technical, financial, regulatory, operational) are all represented, confirms go/no-go recommendation references specific findings. LLM layer: evaluates analytical depth and coherence, checks logical consistency between market sizing and revenue projections, assesses whether competitive positioning insights are actionable, evaluates risk completeness relative to the business idea, scores anti-fabrication compliance (no ungrounded market claims). Combines scores with min() to produce quality_score 0-10.
4. **Improve validation report from critic feedback** (llm) — Improves the business validation report based on specific critic feedback. Addresses identified gaps: missing sections, insufficient item counts for scope level, ungrounded market data lacking [ESTIMATE] flags, revenue projections without derivation chains, missing risk categories, go/no-go recommendation not linked to findings, or weak competitive positioning analysis. Preserves all content that passed validation while surgically improving flagged areas. Maintains anti-fabrication discipline — any new data introduced must be grounded or flagged.
5. **Write final validation artifact to disk** (local) — Final deterministic gate step. Selects the highest-quality validation report from generation or improvement candidates. Performs a last structural check to confirm all six required sections are present. Writes the final markdown artifact to the configured storage location and returns the artifact path.

## Outputs

- `result`
- `result_file`
- `envelope_file`

## Usage

```bash
.venv313/bin/python3 skills/j36-biz-idea-validator/run.py --force --input business_idea "value" --input target_market "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)

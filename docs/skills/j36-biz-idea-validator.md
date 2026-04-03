# Business Idea Validator

**ID:** `j36-biz-idea-validator` | **Version:** 1.0.0 | **Family:** F36 | **Domain:** J | **Type:** executor | **Tag:** dual-use

## Description

A business idea validator that takes a business idea, target market, and competitive landscape. Produces structured validation output with market viability assessment (TAM/SAM/SOM with three-path sizing), competitive positioning analysis, revenue model feasibility with revenue grounding (numeric tokens or derivation chain or data gap acknowledgment), risk assessment with categorized risks (market, technical, financial, regulatory, operational), go/no-go recommendation linked to specific findings, and actionable next steps. Scope-driven generation with anti-fabrication controls ensuring all market data is grounded in input or explicitly flagged as estimates.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `business_idea` | string | Yes | Description of the business idea including the product or service, value proposition, and how it solves a problem. |
| `target_market` | string | Yes | Description of the target market including customer segments, demographics, geography, and any known market size data or references. |
| `competitive_landscape` | string | Yes | Description of known competitors, their positioning, strengths, weaknesses, and any market share data available. |
| `scope` | string | No | Depth of validation analysis. Quick produces 3-5 items per section, standard produces 5-10, comprehensive produces 10-20. |
| `revenue_model_hints` | string | No | Optional hints about intended revenue model (e.g., SaaS subscription, marketplace commission, freemium, advertising). Helps ground revenue feasibility analysis. |
| `known_constraints` | string | No | Optional known constraints such as budget limits, regulatory requirements, geographic restrictions, or technical limitations that should factor into risk assessment. |

## Outputs

| Name | Type | Description |
|------|------|-------------|
| `result` | string | Complete structured business idea validation report in markdown format containing market viability assessment, competitive positioning analysis, revenue model feasibility, categorized risk assessment, go/no-go recommendation, and actionable next steps. |
| `result_file` | file_path | Path to the written validation report artifact file. |
| `envelope_file` | file_path | Path to the envelope metadata JSON file for this validation run. |

## Steps

- **step_1** — Parse inputs and build validation plan (`local`, `general_short`)
- **step_2** — Generate comprehensive business validation report (`llm`, `complex_reasoning`)
- **step_3** — Evaluate validation report quality and grounding (`critic`, `moderate`)
- **step_4** — Improve validation report from critic feedback (`llm`, `complex_reasoning`)
- **step_5** — Write final validation artifact to disk (`local`, `general_short`)

## Quality Gate

- **Min Quality Score:** 7
- **Min Quality Score:** 10.0
- **Max Retries:** 5
- **Escalate Below:** 5.0
- **Critic Loop:** enabled, acceptance=10, max_improvements=5
- **Max Execution:** 300s
- **Max Cost:** $2.5

## Declarative Guarantees

- All TAM/SAM/SOM figures include three-path sizing (top-down, bottom-up, value-theory) or explicitly state which paths are infeasible given inputs.
- Every revenue projection includes numeric tokens, a derivation chain, or an explicit [ESTIMATE] flag with stated assumptions.
- No market data is fabricated — all figures trace to provided inputs or are flagged as estimates.
- Risk assessment covers all five categories: market, technical, financial, regulatory, and operational.
- Go/no-go recommendation explicitly references specific findings from the analysis sections.
- Item counts per section respect the scope setting: quick=3-5, standard=5-10, comprehensive=10-20.
- Actionable next steps are prioritized by impact and linked to identified risks or opportunities.

## Composability

- **Output Type:** business_idea_validation_report

## Example Usage

```json
{
  "skill_id": "j36-biz-idea-validator",
  "inputs": {
    "business_idea": "An AI-powered platform that generates personalized onboarding sequences for SaaS products based on user behavior patterns and industry best practices.",
    "target_market": "B2B SaaS companies with 1000 to 50000 users focused on product-led growth where onboarding impacts conversion.",
    "competitive_landscape": "Appcues Series B 200 employees template-based. Pendo public enterprise-focused. Userpilot Series A mid-market. Gap: none offer AI-generated personalized flows.",
    "scope": "quick"
  }
}
```

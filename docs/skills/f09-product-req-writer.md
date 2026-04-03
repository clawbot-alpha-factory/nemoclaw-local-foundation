# Product Requirements Writer

**ID:** `f09-product-req-writer` | **Version:** 1.0.0 | **Family:** F09 | **Domain:** F | **Type:** executor | **Tag:** dual-use

## Description

Takes a product idea, target audience, and business context, produces a structured product requirements document with problem statement, user stories (As a/I want/so that), functional requirements (system behaviors), non-functional requirements (categorized), testable acceptance criteria linked to user stories, MoSCoW prioritization, dependencies with type and direction, success metrics with measurable targets, edge cases, and scope boundaries. Works only from provided input — states assumptions when data is missing.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `product_idea` | string | Yes | What the product/feature does, who it's for, what problem it solves |
| `target_audience` | string | Yes | Who uses this — role, technical level, pain points |
| `business_context` | string | No | Market position, revenue model, competitive landscape, strategic goals |
| `constraints` | string | No | Budget, timeline, tech stack, regulatory, team size limitations |
| `scope_level` | string | No | mvp (minimum viable, Must+Should only, ≤7 stories), full (complete, all MoSCoW), increment (feature addition to existing system) |

## Outputs

| Name | Type | Description |
|------|------|-------------|
| `result` | string | The complete product requirements document in markdown |
| `result_file` | file_path | Path to the markdown artifact |
| `envelope_file` | file_path | Path to the JSON envelope |

## Steps

- **step_1** — Parse product idea and structure requirements plan (`local`, `general_short`)
- **step_2** — Generate complete product requirements document (`llm`, `complex_reasoning`)
- **step_3** — Evaluate requirements completeness and structural rigor (`critic`, `moderate`)
- **step_4** — Strengthen requirements based on critic feedback (`llm`, `complex_reasoning`)
- **step_5** — Validate final PRD and write artifact (`local`, `general_short`)

## Quality Gate

- **Min Quality Score:** 7
- **Min Quality Score:** 10.0
- **Max Retries:** 5
- **Escalate Below:** 5.0
- **Critic Loop:** enabled, acceptance=10, max_improvements=5
- **Max Execution:** 90s
- **Max Cost:** $0.1

## Declarative Guarantees

- User stories follow As a/I want/so that format with unique IDs (US-1, US-2...)
- Acceptance criteria are testable: condition word AND measurable element required
- Acceptance criteria are linked to specific user stories or functional requirements
- Functional requirements describe system behaviors — no As a patterns
- Non-functional requirements are categorized (performance, security, scalability, etc.)
- Priorities use MoSCoW with scope-appropriate levels
- Dependencies specify type (technical, business, external) and direction
- Success metrics contain measurable targets with numbers or timeframes
- Edge cases and failure scenarios included (minimum 2)
- Scope section includes both in-scope and out-of-scope
- No invented market data — assumptions stated explicitly when data is missing

## Composability

- **Output Type:** product_requirements
- **Can Feed Into:** b05-feature-impl-writer, a01-arch-spec-writer, f09-pricing-strategist
- **Accepts Input From:** j36-biz-idea-validator, e12-market-research-analyst

## Example Usage

```json
{
  "skill_id": "f09-product-req-writer",
  "inputs": {
    "product_idea": "An AI-powered meeting assistant that records, transcribes, and summarizes meetings with action item extraction and CRM integration",
    "target_audience": "Engineering managers at SaaS companies with 50 to 200 person teams who spend 15 hours per week in meetings",
    "business_context": "Competing with Otter.ai and Fireflies.ai. Differentiate on action item tracking with automatic CRM updates and team accountability dashboards.",
    "scope_level": "mvp"
  }
}
```

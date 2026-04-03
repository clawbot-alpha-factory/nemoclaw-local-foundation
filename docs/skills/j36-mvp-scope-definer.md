# MVP Scope Definer

**ID:** `j36-mvp-scope-definer` | **Version:** 1.0.0 | **Family:** F36 | **Domain:** J | **Type:** executor | **Tag:** dual-use

## Description

An MVP scope definer that takes a product idea, target audience, resource constraints, and timeline. Produces a structured MVP scope document with prioritized feature list (MoSCoW), user journey map for core flow, technical scope boundaries, launch criteria checklist, risk-adjusted timeline, explicit out-of-scope section, and resource allocation recommendations. Supports scope-driven generation modes and grounds all timeline estimates in stated constraints.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `product_idea` | string | Yes | Description of the product idea including its core value proposition and problem it solves |
| `target_audience` | string | Yes | Description of the target audience including demographics, pain points, and user personas |
| `resource_constraints` | string | Yes | Available resources including team size, skill sets, budget, and infrastructure. All timeline estimates will be grounded in these constraints. |
| `timeline` | string | Yes | Target timeline for MVP delivery including hard deadlines, milestones, and any external dependencies |
| `scope_mode` | string | No | Scope generation mode controlling feature count: lean (3-5 features), balanced (5-10 features), or comprehensive (10-15 features) |
| `domain_context` | string | No | Optional additional context about the industry, regulatory requirements, or competitive landscape |
| `existing_assets` | string | No | Optional description of existing code, infrastructure, APIs, or third-party services that can be leveraged |

## Outputs

| Name | Type | Description |
|------|------|-------------|
| `result` | string | The complete MVP scope document in structured markdown format including MoSCoW feature prioritization, user journey map, technical scope boundaries, launch criteria, risk-adjusted timeline, out-of-scope section, and resource allocation recommendations |
| `result_file` | file_path | Path to the generated MVP scope document markdown file |
| `envelope_file` | file_path | Path to the execution envelope JSON file with metadata and quality scores |

## Steps

- **step_1** — Parse inputs and build scoping plan (`local`, `general_short`)
- **step_2** — Generate comprehensive MVP scope document (`llm`, `complex_reasoning`)
- **step_3** — Evaluate scope quality and grounding integrity (`critic`, `moderate`)
- **step_4** — Improve scope document from critic feedback (`llm`, `complex_reasoning`)
- **step_5** — Write final scope artifact to disk (`local`, `general_short`)

## Quality Gate

- **Min Quality Score:** 7
- **Min Quality Score:** 10.0
- **Max Retries:** 5
- **Escalate Below:** 5.0
- **Critic Loop:** enabled, acceptance=10, max_improvements=5
- **Max Execution:** 300s
- **Max Cost:** $1.5

## Declarative Guarantees

- All timeline estimates are grounded in stated resource constraints and timeline inputs — no fabricated durations
- Feature count respects scope_mode: lean produces 3-5, balanced produces 5-10, comprehensive produces 10-15 features
- MoSCoW prioritization uses proper Must-Have, Should-Have, Could-Have, and Won't-Have categories
- Launch criteria include measurable thresholds, not vague qualitative statements
- Out-of-scope section explicitly lists excluded features and rationale to prevent scope creep
- Technical scope boundaries provide clear build vs buy vs skip rationale for each component
- User journey map covers only the core MVP flow, not aspirational future flows
- Resource allocation recommendations align with stated team size and skill constraints

## Composability

- **Output Type:** mvp_scope_document

## Example Usage

```json
{
  "skill_id": "j36-mvp-scope-definer",
  "inputs": {
    "product_idea": "A browser extension that uses AI to automatically summarize and tag bookmarks.",
    "target_audience": "Knowledge workers who save 20 plus bookmarks per week.",
    "resource_constraints": "Solo developer, 3 months, 5000 dollar budget.",
    "timeline": "3 months to public beta",
    "scope_level": "balanced"
  }
}
```

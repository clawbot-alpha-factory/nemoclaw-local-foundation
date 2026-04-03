# Technology Trend Scanner

**ID:** `e12-tech-trend-scanner` | **Version:** 1.0.0 | **Family:** F12 | **Domain:** E | **Type:** executor | **Tag:** dual-use

## Description

Takes a technology domain, industry context, time horizon, known technologies, and specific focus areas. Produces a structured technology trend intelligence report with maturity-classified trends, adoption timelines, disruption vectors, convergence analysis, strategic implications, and actionable recommendations. Works only from provided input — does not fabricate adoption statistics, market sizes, or research citations. States analysis limitations explicitly.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `technology_domain` | string | Yes | The technology area to scan: AI in healthcare, edge computing for manufacturing, etc. |
| `industry_context` | string | Yes | Industry background: size, players, current tech stack, pain points, regulatory, geography |
| `time_horizon` | string | No | near_term (0-1yr), mid_term (1-3yr), long_term (3-5yr+), comprehensive (all) |
| `known_technologies` | string | No | Technologies the user already tracks — scan should surface trends beyond these |
| `specific_focus` | string | No | Angles to prioritize: cost reduction, security, competitive differentiation, etc. |
| `scan_depth` | string | No | overview (broad, 5+), detailed (deep, 8+), strategic (fewer, deeper implications) |

## Outputs

| Name | Type | Description |
|------|------|-------------|
| `result` | string | The complete technology trend scan report in markdown |
| `result_file` | file_path | Path to the markdown artifact |
| `envelope_file` | file_path | Path to the JSON envelope |

## Steps

- **step_1** — Parse technology context and build scan plan (`local`, `general_short`)
- **step_2** — Generate complete technology trend scan report (`llm`, `complex_reasoning`)
- **step_3** — Evaluate trend scan quality and analytical rigor (`critic`, `moderate`)
- **step_4** — Strengthen scan based on critic feedback (`llm`, `complex_reasoning`)
- **step_5** — Validate final trend scan and write artifact (`local`, `general_short`)

## Quality Gate

- **Min Quality Score:** 7
- **Min Quality Score:** 10.0
- **Max Retries:** 5
- **Escalate Below:** 5.0
- **Critic Loop:** enabled, acceptance=10, max_improvements=5
- **Max Execution:** 300s
- **Max Cost:** $0.25

## Declarative Guarantees

- Every trend has a maturity stage classification (experimental/emerging/growing/established/mature/declining)
- Maturity stages are coherent with stated adoption timelines
- Disruption analysis names specific processes, roles, or business models being disrupted
- Technology convergence identifies compound impact or explicitly states no significant convergence
- Recommendations contain action verbs, reference specific trends, and include time horizons
- Strategic implications are grounded in the stated industry context
- When known technologies provided, scan surfaces trends beyond what was already known
- No fabricated adoption statistics, market sizes, or research citations
- Assumptions section acknowledges analysis limitations
- Trend confidence levels explicitly classified (high/medium/speculative)

## Composability

- **Output Type:** technology_trend_scan
- **Can Feed Into:** e12-market-research-analyst, f09-product-req-writer, f09-pricing-strategist, a01-arch-spec-writer
- **Accepts Input From:** e08-comp-intel-synth

## Example Usage

```json
{
  "skill_id": "e12-tech-trend-scanner",
  "inputs": {
    "technology_domain": "AI agent frameworks and autonomous systems for enterprise automation",
    "industry_context": "B2B SaaS mid-market companies with 50 to 500 employees looking to automate customer operations",
    "scan_depth": "overview"
  }
}
```

# e12-market-research-analyst — Market Research Analyst

**Family:** F12 | **Domain:** E | **Tag:** dual-use | **Type:** executor
**Schema:** v2 | **Runner:** v4.0+ | **Routing:** complex_reasoning

## What It Does

Takes a research topic, industry context, specific questions, and known data, then produces a structured market research report with market overview, segmentation, trends, competitive landscape, opportunities, risk factors, and actionable recommendations.

## Key Design Decisions

- **Three-path market sizing:** Numeric indicators, qualitative scoping (emerging/mature/fragmented), or explicit data gap acknowledgment. No dead overview sections.
- **Data grounding:** Known data must be integrated into analysis context (2+ references), not just token-repeated. Thin data triggers gap acknowledgment.
- **Fabrication flagging:** When known_data is empty, precise percentages and dollar amounts are flagged as potentially fabricated. Penalized in critic, not hard-fail.
- **Competitive archetype fallback:** No competitors → must describe competitive categories (enterprise vendors, open-source, etc.) or state what data is needed. No dead sections.
- **Section-scoped entity detection:** Competitive entity check runs within the Competitive Landscape section only, filtering section heading words.
- **Depth-scaled trends:** Overview requires 3+, detailed requires 5+, competitive_focus requires 3+.
- **Insight linkage:** Opportunities and recommendations must reference trends, segments, or competitive insights.
- **Risk grounding:** Risks must tie to market forces, competition, or constraints.
- **Segment naming quality:** No "Segment A/B" — must use meaningful names (SMB, enterprise, prosumers).
- **Question coverage:** 60% of topic words from specific_questions must appear in output.
- **Anti-hallucination:** No fabricated research citations. General observations must be labeled as assumptions.

## Usage

```bash
.venv313/bin/python skills/skill-runner.py \
  --skill e12-market-research-analyst \
  --input research_topic 'AI-powered legal tech market for mid-market law firms in the US' \
  --input industry_context 'Legal tech is growing. Major players include Kira Systems, Luminance, and ContractPodAi focused on enterprise. Mid-market (50-200 attorney firms) underserved. Regulatory environment requires data security compliance.' \
  --input specific_questions 'What segments exist within mid-market legal tech? What are the key adoption barriers? Who are the main competitors and what do they charge?' \
  --input known_data 'Kira Systems: $50000+/year enterprise. Luminance: $30000+/year. Mid-market budget: $500-$2000/month. Approximately 15000 mid-market firms in US.' \
  --input research_depth 'detailed'
```

## Inputs

| Name | Required | Description |
|---|---|---|
| research_topic | yes | What to research (min 20 chars) |
| industry_context | yes | Industry background, known players, trends (min 20 chars) |
| specific_questions | no | Questions the research should answer |
| known_data | no | Statistics, reports, competitor info the user has |
| research_depth | no | overview (default), detailed, competitive_focus |

## Composability

- **Accepts input from:** e12-tech-trend-scanner, e08-comp-intel-synth
- **Can feed into:** f09-product-req-writer, f09-pricing-strategist, d11-copywriting-specialist

## Deterministic Validation

- Required sections: Market Overview, Segmentation, Trends, Competitive Landscape, Opportunities, Risks, Recommendations
- Market sizing: numeric + context, qualitative scoping terms, or explicit data gap
- Question coverage: 60% topic word presence
- Data grounding: 2+ references from known_data integrated in context
- Competitive entities: section-scoped detection, archetype fallback
- Trend count: depth-scaled (3/5/3)
- Actionable recommendations: action verb required
- Anti-hallucination: citation pattern detection
- Fabrication flagging: precise stats without known_data → penalized
- Segment naming: no generic labels
- Insight linkage: opportunities/recommendations reference analysis
- Risk grounding: tied to market forces

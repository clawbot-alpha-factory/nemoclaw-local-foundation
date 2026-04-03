# NemoClaw Revenue Architecture Blueprint

**Date:** 2026-04-03
**Status:** Research Complete — Ready for Implementation
**Validated Against:** MetaGPT MGX ($2.2M revenue), CrewAI Enterprise ($120K/yr), Microsoft credit-based pricing

---

## Executive Summary

NemoClaw has 124 skills, 11 agents, and 5 mega-project templates — but zero revenue wiring. The infrastructure exists (pipeline service, catalog, attribution, A/B tests) as scaffolding without activation. This document defines 5 revenue streams ranked by feasibility, maps each to existing skills/agents, designs the pricing engine, and specifies the minimum viable revenue pipeline.

**Key insight from competitive research:** MetaGPT's MGX product hit $2.2M revenue with zero advertising by delivering complete digital artifacts (websites, apps) from one-line requirements. NemoClaw's skill chains can produce the same — the gap is the delivery pipeline, not the capability.

---

## 1. Five Revenue Streams (Ranked by Feasibility)

### Stream 1: Content-as-a-Service (CaaS)
**Feasibility: HIGHEST — Start earning in < 1 week**

**What:** Blog posts, social media content, newsletters, video scripts, SEO content delivered on-demand or via subscription.

**Why first:** Lowest risk, highest existing skill coverage, fastest time-to-revenue. Content is consumed immediately — no complex delivery pipelines needed.

**Skills Required (18 existing):**

| Skill ID | Name | Agent | Output |
|----------|------|-------|--------|
| cnt-01-blog-post-writer | Blog Post Writer | narrative_content_lead | Markdown article |
| cnt-02-viral-hook-generator | Viral Hook Generator | narrative_content_lead | Hook copy |
| cnt-03-social-caption-writer | Social Caption Writer | social_media_lead | Platform-specific captions |
| cnt-04-newsletter-composer | Newsletter Composer | narrative_content_lead | HTML newsletter |
| cnt-05-video-script-writer | Video Script Writer | narrative_content_lead | Script + shot list |
| cnt-06-content-calendar-builder | Content Calendar | narrative_content_lead | 30-day calendar |
| cnt-07-content-performance-analyzer | Performance Analyzer | narrative_content_lead | Analytics report |
| cnt-08-script-to-video-planner | Video Planner | narrative_content_lead | Production plan |
| cnt-09-thumbnail-brief-writer | Thumbnail Brief | narrative_content_lead | Design brief |
| cnt-10-content-strategy-analyzer | Strategy Analyzer | narrative_content_lead | Strategy doc |
| cnt-11-agent-self-promo-generator | Self-Promo Generator | social_media_lead | Promotional content |
| k55-seo-keyword-researcher | SEO Keyword Research | strategy_lead | Keyword report |
| g25-output-format-enforcer | Format Enforcer | operations_lead | Formatted output |

**Agent Assignment:**
- **Lead:** Yasmin (narrative_content_lead, L3)
- **Support:** Zara (social_media_lead, L4), Nadia (strategy_lead, L2 — for SEO/strategy)

**Pricing Model:**

| Tier | Deliverable | Skills Used | LLM Cost | Sell Price | Margin |
|------|------------|-------------|----------|------------|--------|
| Basic | Single blog post | cnt-01 | ~$0.20 | $15 | 98.7% |
| Standard | Blog + 5 social posts | cnt-01, cnt-03 x5 | ~$0.40 | $35 | 98.9% |
| Premium | 30-day content calendar + 10 posts + newsletter | cnt-06, cnt-01 x10, cnt-04 | ~$3.00 | $150 | 98.0% |
| Enterprise | Full content empire (mega-project) | content_empire template | ~$15.00 | $500 | 97.0% |

**Revenue Projection:** 20 basic orders/week × $15 = $1,200/mo minimum (conservative).

**Existing Infrastructure:**
- `workflows/content-factory-daily.yaml` — automated daily content pipeline
- `MegaProjectService.TEMPLATES["content_empire"]` — full 6-week content engine
- `command-center/backend/app/api/routers/revenue.py` — pipeline endpoints exist

---

### Stream 2: Research Reports
**Feasibility: HIGH — 1-2 weeks to activate**

**What:** Market research, competitive analysis, SEO audits, industry reports.

**Skills Required (8 existing):**

| Skill ID | Name | Agent | Output |
|----------|------|-------|--------|
| e12-market-research-analyst | Market Research | strategy_lead | Research report |
| b02-competitive-analyzer | Competitive Analysis | strategy_lead | Competitive landscape |
| k55-seo-keyword-researcher | SEO Research | strategy_lead | Keyword analysis |
| f09-pricing-strategist | Pricing Strategy | growth_revenue_lead | Pricing model |
| int-05-cross-platform-scraper | Data Collection | engineering_lead | Raw data |
| a01-arch-spec-writer | Spec Writer | product_architect | Technical spec |

**Agent Assignment:**
- **Lead:** Nadia (strategy_lead, L2)
- **Support:** Omar (growth_revenue_lead, L3), Layla (product_architect, L3)

**Pricing Model:**

| Tier | Deliverable | Skills Chained | LLM Cost | Sell Price |
|------|------------|----------------|----------|------------|
| Quick Scan | 2-page competitive overview | b02 | ~$0.30 | $25 |
| Standard | Full market research report | e12 + b02 + k55 | ~$1.50 | $75 |
| Deep Dive | Comprehensive + pricing strategy | e12 + b02 + k55 + f09 | ~$4.00 | $200 |
| Strategic | Full research initiative (mega-project) | research_initiative template | ~$8.00 | $400 |

**Existing Infrastructure:**
- `MegaProjectService.TEMPLATES["research_initiative"]` — 3-week research project
- `workflows/pipeline-v2.yaml` — market-to-product pipeline

---

### Stream 3: Client Engagement Packages
**Feasibility: MEDIUM — 2-3 weeks to activate**

**What:** End-to-end client service: onboarding → proposal → deliverables → reporting.

**Skills Required (12 existing):**

| Skill ID | Name | Agent | Output |
|----------|------|-------|--------|
| s01-outreach-email-writer | Outreach Emails | sales_outreach_lead | Email sequences |
| s02-proposal-generator | Proposal Generator | sales_outreach_lead | PDF proposal |
| k57-nda-generator | NDA Generator | operations_lead | Legal NDA |
| k61-weekly-client-reporter | Weekly Reporter | client_success_lead | Client report |
| k40-deal-pipeline-tracker | Deal Tracker | growth_revenue_lead | Pipeline update |

**Agent Assignment:**
- **Lead:** Hassan (sales_outreach_lead, L4)
- **Support:** Amira (client_success_lead, L4), Khalid (operations_lead, L2)

**Pricing Model:**

| Package | Deliverables | Sell Price |
|---------|-------------|------------|
| Starter | Proposal + NDA + 1 deliverable | $250 |
| Growth | Proposal + NDA + 4 deliverables + weekly reports | $750 |
| Enterprise | Full client engagement mega-project | $1,500 |

**Existing Infrastructure:**
- `MegaProjectService.TEMPLATES["client_engagement"]` — 4-week engagement
- `command-center/backend/app/services/onboarding_service.py` — E-11 lifecycle
- `command-center/backend/app/services/deliverable_service.py` — deliverable tracking

---

### Stream 4: SaaS Build Packages
**Feasibility: MEDIUM-LOW — 3-4 weeks to activate**

**What:** Technical specifications, database designs, API blueprints, test suites.

**Skills Required (10+ existing):**

| Skill ID | Name | Agent |
|----------|------|-------|
| a01-arch-spec-writer | Architecture Spec | product_architect |
| a02-database-schema-designer | DB Schema Designer | engineering_lead |
| a05-api-endpoint-builder | API Builder | engineering_lead |
| a06-frontend-component-gen | Frontend Generator | engineering_lead |
| a07-test-case-generator | Test Generator | engineering_lead |
| a08-code-review-assistant | Code Review | engineering_lead |

**Agent Assignment:**
- **Lead:** Layla (product_architect, L3)
- **Support:** Faisal (engineering_lead, L3), Nadia (strategy_lead, L2)

**Pricing:** $500-$2,000 per project (mega-project template: `saas_builder`)

**Existing Infrastructure:**
- `MegaProjectService.TEMPLATES["saas_builder"]` — 12-week SaaS build

---

### Stream 5: Agent-as-a-Service API (A2A)
**Feasibility: LOW (requires A2A implementation first) — 4-6 weeks**

**What:** External agents discover and invoke NemoClaw skills via A2A protocol. Per-invocation billing.

**Revenue model:** Credit-based (following Microsoft/Salesforce pattern)
- 1 credit = 1 lightweight skill execution (~$0.05 LLM cost)
- Packs: 100 credits/$25, 500 credits/$100, 2000 credits/$350
- Enterprise: unlimited credits/$500/mo

**Requires:** A2A integration (see `docs/a2a-integration-spec.md`)

**Existing Infrastructure:**
- `command-center/backend/app/api/routers/marketplace.py` — skill discovery
- `command-center/backend/app/services/skill_marketplace_service.py` — install/update

---

## 2. Minimum Viable Revenue Pipeline (MVRP)

### Architecture

```
Client Request                                      Delivery
    │                                                   ▲
    ▼                                                   │
[Intake API] ──→ [Task Workflow Service] ──→ [Execution Service] ──→ [Output Packager]
POST /api/orders    create_workflow()           submit()                markdown→PDF
                    brainstorm→plan→            skill-runner.py         brand template
                    execute→validate            subprocess              email delivery
                         │                          │                       │
                         ▼                          ▼                       ▼
                    [Progress Webhook]         [Cost Tracker]          [Payment Webhook]
                    SSE or push notification    skill_metrics.py        Stripe/PayPal
                    to client                   budget tracking         invoice + receipt
```

### New Components Needed

**1. Order Intake API** (`command-center/backend/app/api/routers/orders.py`)

```python
class OrderRequest(BaseModel):
    service_type: str          # "content", "research", "engagement", "saas"
    tier: str                  # "basic", "standard", "premium", "enterprise"
    details: dict              # Service-specific parameters
    client_email: str
    payment_method: str        # "stripe", "invoice"

@router.post("/api/orders")
async def create_order(order: OrderRequest):
    # 1. Validate + price calculation
    price = pricing_engine.calculate(order.service_type, order.tier)
    # 2. Create workflow
    wf_id = task_workflow_service.create_workflow(
        goal=order.details.get("goal", ""),
        agent_id=_best_agent_for_service(order.service_type)
    )
    # 3. Create deal in pipeline
    pipeline_service.create_deal(wf_id, order.client_email, price.total, ...)
    # 4. Return order confirmation
    return {"order_id": wf_id, "price": price, "estimated_completion": "..."}
```

**2. Pricing Engine** (`command-center/backend/app/services/pricing_engine.py`)

```python
class PricingEngine:
    """Dynamic pricing based on skill costs + markup."""

    def __init__(self, budget_config, skill_metrics):
        self.budget_config = budget_config      # from budget-config.yaml
        self.skill_metrics = skill_metrics      # from lib/skill_metrics.py

    def calculate(self, service_type: str, tier: str) -> Price:
        skills = TIER_SKILL_MAP[service_type][tier]
        base_cost = sum(
            self.skill_metrics.get_skill_stats(s).get("avg_cost", 0.10)
            for s in skills
        )
        markup = MARKUP_TABLE[tier]  # basic=10x, standard=8x, premium=6x
        return Price(
            base_cost=base_cost,
            markup=markup,
            total=round(base_cost * markup, 2),
            currency="USD"
        )
```

**Data sources for pricing:**
- `config/routing/budget-config.yaml` — per-alias LLM costs
- `lib/skill_metrics.py:get_skill_stats()` — avg_cost and avg_duration per skill
- `config/routing/routing-config.yaml` — estimated_cost_per_call per alias

**3. Output Packager** (`command-center/backend/app/services/output_packager.py`)

```python
class OutputPackager:
    """Converts skill artifacts to client-deliverable formats."""

    def package(self, workflow_id: str, format: str = "pdf") -> Path:
        workflow = task_workflow_service.get_workflow(workflow_id)
        artifacts = self._collect_artifacts(workflow)

        if format == "pdf":
            return self._markdown_to_pdf(artifacts, brand_template="default")
        elif format == "zip":
            return self._zip_artifacts(artifacts)
        elif format == "markdown":
            return artifacts[0] if artifacts else None
```

**Dependency:** `pip install weasyprint` or `pip install fpdf2` for PDF generation.

**4. Delivery Service** (extend existing `deliverable_service.py`)

Wire output_packager → email delivery (via existing Gmail MCP or SMTP) → Stripe webhook for payment confirmation.

### Implementation Order

| Step | What | Files | Effort |
|------|------|-------|--------|
| 1 | Pricing engine | NEW `pricing_engine.py` | 1 day |
| 2 | Order intake API | NEW `orders.py` router | 1 day |
| 3 | Output packager (markdown→PDF) | NEW `output_packager.py` | 1-2 days |
| 4 | Wire to existing pipeline service | `revenue.py`, `main.py` | 0.5 days |
| 5 | Email delivery | Extend `deliverable_service.py` | 1 day |
| 6 | Stripe integration | NEW `payment_service.py` | 2-3 days |

**Total MVRP effort:** 6-8 days

---

## 3. Pricing Engine Design

### Cost Basis

From `config/routing/routing-config.yaml`:

| Alias | Model | Cost/Call |
|-------|-------|----------|
| cheap_openai | gpt-5.4-mini | $0.0004 |
| cheap_google | gemini-2.5-flash | $0.0004 |
| cheap_claude | haiku-4-5 | $0.008 |
| reasoning_claude | sonnet-4-6 | $0.060 |
| reasoning_openai | gpt-5.4 | $0.010 |
| premium_claude | opus-4-6 | $0.200 |

### Markup Strategy

| Service Tier | Target Markup | Rationale |
|-------------|---------------|-----------|
| Basic (single skill) | 10-15x | Commodity content, high volume |
| Standard (2-5 skills) | 6-8x | Multi-step quality output |
| Premium (5-10 skills) | 4-6x | Complex chains, critic loops |
| Enterprise (mega-project) | 3-4x | High-touch, long-running |

### Dynamic Adjustments

```python
def adjust_price(base_price: float, context: dict) -> float:
    price = base_price

    # Rush delivery: +50%
    if context.get("rush"):
        price *= 1.5

    # High-quality enforcement (critic loops): +20%
    if context.get("quality_guarantee"):
        price *= 1.2

    # Volume discount: -10% for 10+ orders/month
    if context.get("monthly_orders", 0) >= 10:
        price *= 0.9

    return round(price, 2)
```

### Pricing Data Pipeline

```
routing-config.yaml (cost/call)
        │
        ▼
skill_metrics.py (avg_cost/execution, avg_duration)
        │
        ▼
pricing_engine.py (base_cost × markup × adjustments)
        │
        ▼
orders.py (quote → client)
        │
        ▼
pipeline_service.py (deal tracking)
        │
        ▼
attribution_service.py (revenue per skill/agent)
```

---

## 4. Quality Gates for Revenue-Generating Skills

### Current State
- `skill-runner.py` has critic loops (generate → critic → improve if score < acceptance)
- Quality scoring from critic step output (JSON `quality_score` field)
- `lib/skill_metrics.py` tracks `avg_quality` per skill

### Gap
- Critic loops are optional per skill.yaml — not enforced for revenue skills
- No minimum quality threshold for paid deliverables
- No client-facing quality guarantee

### Recommendation

**Enforce critic loops on all revenue skills:**

In each revenue-generating skill's `skill.yaml`, ensure:
```yaml
critic_loop:
  enabled: true
  acceptance_score: 8.0      # Minimum for paid output (was 7.0)
  max_iterations: 3
  score_field: quality_score
```

**Quality gate in output packager:**

```python
def package(self, workflow_id, format="pdf"):
    # Check quality before packaging
    envelope = self._load_envelope(workflow_id)
    quality = envelope.get("metrics", {}).get("final_quality_score", 0)
    if quality < 8.0:
        raise QualityGateError(
            f"Quality score {quality} below minimum 8.0 for paid deliverables. "
            f"Re-run with critic loop or escalate to human review."
        )
    # Proceed with packaging
```

**Affected skills:** All skills in Stream 1-4 skill tables above. Check and update each `skill.yaml` to enforce `critic_loop.enabled: true` and `acceptance_score: 8.0`.

---

## 5. Revenue Stream → Agent → Skill Mapping (Complete)

```
Stream 1: Content-as-a-Service
├── Lead: Yasmin (narrative_content_lead)
│   ├── cnt-01 blog-post-writer
│   ├── cnt-02 viral-hook-generator
│   ├── cnt-04 newsletter-composer
│   ├── cnt-05 video-script-writer
│   ├── cnt-06 content-calendar-builder
│   ├── cnt-07 content-performance-analyzer
│   ├── cnt-08 script-to-video-planner
│   ├── cnt-09 thumbnail-brief-writer
│   └── cnt-10 content-strategy-analyzer
├── Support: Zara (social_media_lead)
│   ├── cnt-03 social-caption-writer
│   └── cnt-11 agent-self-promo-generator
└── Support: Nadia (strategy_lead)
    └── k55 seo-keyword-researcher

Stream 2: Research Reports
├── Lead: Nadia (strategy_lead)
│   ├── e12 market-research-analyst
│   ├── b02 competitive-analyzer
│   └── k55 seo-keyword-researcher
└── Support: Omar (growth_revenue_lead)
    └── f09 pricing-strategist

Stream 3: Client Engagement
├── Lead: Hassan (sales_outreach_lead)
│   ├── s01 outreach-email-writer
│   └── s02 proposal-generator
├── Support: Amira (client_success_lead)
│   └── k61 weekly-client-reporter
└── Support: Khalid (operations_lead)
    └── k57 nda-generator

Stream 4: SaaS Build Packages
├── Lead: Layla (product_architect)
│   └── a01 arch-spec-writer
└── Support: Faisal (engineering_lead)
    ├── a02 database-schema-designer
    ├── a05 api-endpoint-builder
    ├── a06 frontend-component-gen
    ├── a07 test-case-generator
    └── a08 code-review-assistant

Stream 5: Agent-as-a-Service (A2A)
├── All 11 agents exposed via A2A Agent Cards
└── All 124 skills available per-invocation
```

---

## 6. Implementation Roadmap

### Week 1: Content-as-a-Service (Stream 1)
- [ ] Build pricing engine (`pricing_engine.py`)
- [ ] Build order intake API (`orders.py`)
- [ ] Build output packager (markdown→PDF)
- [ ] Wire to existing pipeline service
- [ ] Test: submit content order → workflow → artifact → PDF → email

### Week 2: Research Reports (Stream 2) + Quality Gates
- [ ] Add research-specific order types
- [ ] Enforce critic loops on all revenue skills (update skill.yaml files)
- [ ] Quality gate in output packager (min score 8.0)
- [ ] Test: submit research order → workflow → report → quality check → delivery

### Week 3: Client Engagement (Stream 3) + Payments
- [ ] Stripe integration (`payment_service.py`)
- [ ] Proposal generation workflow
- [ ] Client onboarding automation
- [ ] Weekly reporting automation

### Week 4: A2A Integration (Stream 5 foundation)
- [ ] Agent Card generation
- [ ] Task lifecycle mapping
- [ ] SSE streaming
- [ ] Bearer auth
- [ ] Test: external agent discovers NemoClaw → submits task → receives output

### Weeks 5-6: SaaS Packages (Stream 4) + Enterprise
- [ ] SaaS project templates
- [ ] Multi-deliverable packaging
- [ ] Client portal (frontend)
- [ ] Usage-based billing for A2A

---

## 7. Revenue Targets

| Timeline | Stream | Monthly Revenue | Cumulative |
|----------|--------|-----------------|------------|
| Week 2 | Content-as-a-Service | $500-1,500 | $500-1,500 |
| Week 4 | + Research Reports | $1,000-3,000 | $1,500-4,500 |
| Week 6 | + Client Engagement | $2,000-5,000 | $3,500-9,500 |
| Week 8 | + SaaS Packages | $1,000-3,000 | $4,500-12,500 |
| Week 12 | + A2A API Credits | $500-2,000 | $5,000-14,500 |

**Break-even target:** $200/mo (covers Claude Max subscription). Achievable with ~13 basic content orders/month.

---

## Sources

- MetaGPT MGX revenue data: [GetLatka](https://getlatka.com/companies/deepwisdom.ai) ($2.2M by June 2025)
- CrewAI pricing: [CrewAI.com](https://crewai.com/pricing) ($99/mo - $120K/yr)
- Microsoft credit pricing: [Copilot Studio](https://learn.microsoft.com/en-us/microsoft-copilot-studio/pricing) (25K credits/$200)
- Salesforce Agentforce: $500/100K message credits
- NemoClaw cost data: `config/routing/routing-config.yaml`, `config/routing/budget-config.yaml`

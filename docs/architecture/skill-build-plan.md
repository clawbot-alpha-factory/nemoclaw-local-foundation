# Skill Build Plan

> **Location:** `docs/architecture/skill-build-plan.md`
> **Version:** 1.0
> **Date:** 2026-03-24
> **Phase:** Pre-Step — Skill System Foundation
> **Status:** APPROVED — all decisions locked
> **Scope:** Applies to all 64 families, 479 skills, 12 domains

---

## Pre-Step A — Skill ID Convention

### The Problem

479 skills need IDs that are instantly identifiable in logs, dashboards, file paths, and debugging. Without a convention, skill directories become unnavigable and log lines become unreadable.

### Proposed Convention

**Format:** `{domain_letter}{family_number_zero_padded}-{skill_slug}`

**Examples:**

| Domain | Family | Skill | Skill ID | Directory |
|---|---|---|---|---|
| A (Core System) | F01 (System Architecture) | Architecture Specification Writer | `a01-arch-spec-writer` | `skills/a01-arch-spec-writer/` |
| B (Engineering) | F05 (Code Generation) | Feature Implementation Writer | `b05-feature-impl-writer` | `skills/b05-feature-impl-writer/` |
| E (Intelligence) | F12 (Research) | Market Research Analyst | `e12-market-research-analyst` | `skills/e12-market-research-analyst/` |
| I (Lead Gen) | F37 (Cold Email) | Cold Email Sequence Writer | `i37-cold-email-seq-writer` | `skills/i37-cold-email-seq-writer/` |
| L (Content Empire) | F56 (Viral Content) | Viral Hook Generator | `l56-viral-hook-generator` | `skills/l56-viral-hook-generator/` |

**Rules:**

- Domain letter: lowercase a–l (matches the 12 domains A–L)
- Family number: zero-padded to 2 digits — `a01` not `a1`, `f05` not `f5`
- Skill slug: lowercase, hyphenated, max 30 chars, descriptive
- Full ID max length: 40 chars
- The existing `research-brief` skill becomes `c08-research-brief` (Domain C, Family 08, Skill #1)

**What this enables:**

- `grep "a01-" logs` → all Domain A Family 01 activity
- `ls skills/b*` → all Engineering domain skills
- `ls skills/i37-*` → all Cold Email skills
- Log line: `[budget] a01-arch-spec-writer alias=premium_claude` → instantly readable

### Migration

The existing `research-brief` skill stays at `skills/research-brief/` for now. It can be aliased or renamed to `c08-research-brief` after the template generator is built, or kept as a legacy reference.

---

## Pre-Step B — Standard Skill I/O Interchange Format

### The Problem

If every skill has its own bespoke output format, chaining skills requires custom glue code for every connection. The real power comes when Skill A feeds into Skill B feeds into Skill C. This requires a standard interchange format decided before the first new skill is built.

### Proposed Format: SkillOutput JSON Envelope

Every skill produces two outputs:

1. **Human artifact** — the markdown/text file in `outputs/` (what the user reads)
2. **Machine envelope** — a JSON file that wraps the output with metadata (what other skills read)

**Envelope schema:**

```json
{
  "schema_version": 1,
  "skill_id": "e12-market-research-analyst",
  "skill_version": "1.0.0",
  "thread_id": "skill-e12-market-research-analyst-20260324-150829-03d040b0",
  "timestamp": "2026-03-24T15:09:05Z",
  "status": "complete",
  "error": null,
  "inputs": {
    "topic": "AI agent frameworks market",
    "depth": "standard"
  },
  "outputs": {
    "primary": "The structured output text or data here...",
    "sections": {
      "background": "...",
      "key_findings": "...",
      "open_questions": "...",
      "recommendations": "..."
    },
    "artifact_path": "skills/e12-market-research-analyst/outputs/market_research_20260324.md"
  },
  "metadata": {
    "total_cost_usd": 0.012,
    "total_steps": 5,
    "llm_steps": 1,
    "provider_used": "anthropic",
    "model_used": "claude-sonnet-4-6",
    "duration_seconds": 36
  },
  "composable": {
    "can_feed_into": ["i29-lead-list-builder", "f16-gtm-plan-writer"],
    "accepts_input_from": ["a01-arch-spec-writer"],
    "output_type": "research_brief"
  }
}
```

**Error field convention:** `error` is `null` on success. On failure, it contains an error string describing what went wrong. Downstream skills consuming an envelope via `--input-from` must check `error` is `null` before processing outputs. If `error` is non-null, the downstream skill must refuse to proceed and report the upstream failure. skill-runner.py must refuse to start and exit with a clear error message if the loaded envelope contains a non-null error field.

**Key design decisions:**

| Decision | Choice | Why |
|---|---|---|
| Envelope format | JSON | Machine-parseable, typed, composable |
| Human artifact | Markdown | Readable, storable, shareable |
| Both produced | Always | Human reads markdown, machines read JSON |
| Sections in envelope | Skill-specific keys | Enables downstream skills to grab specific sections |
| Composable block | Declares compatibility | Skills self-document what they chain with |
| Output type | String tag | Enables routing: "any skill that produces `research_brief` can feed into X" |

**Envelope file location:** `skills/{skill-id}/outputs/{thread_id}_envelope.json`

**How chaining works:**

```
Skill A completes → writes envelope JSON
     │
     ▼
Skill B reads: --input-from skills/a01-arch-spec-writer/outputs/{latest}_envelope.json
     │
     ▼
skill-runner.py parses envelope, extracts outputs.primary or outputs.sections.{key}
     │
     ▼
Passes extracted data as inputs to Skill B's step_1
```

This means skill-runner.py needs a `--input-from` flag that accepts an envelope path. That's a small addition to the runner.

---

## Pre-Step C — Family Tags: Internal / Customer-Facing / Dual-Use

### The Problem

A skill that generates internal meeting notes has different quality requirements than one that generates client-facing proposals. The tag determines routing tier, error tolerance, output polish, and testing depth.

### Tag Definitions

| Tag | Routing Default | Quality Bar | Error Handling | Testing |
|---|---|---|---|---|
| Internal | cheap or production tier | Functional — gets the job done | Fail and retry is acceptable | Smoke test + manual review |
| Customer-Facing | premium or enterprise tier | Polished — represents the company | Graceful failure with fallback | Regression testing required |
| Dual-Use | Switchable per invocation | Both bars must be met | Graceful failure | Both test levels |

### All 64 Families Tagged

**Domain A — Core System and Infrastructure**

| Family | Name | Tag | Rationale |
|---|---|---|---|
| F01 | System Architecture and Design | Internal | Internal engineering tooling |
| F02 | Environment and Runtime Management | Internal | Ops tooling |
| F03 | Observability and Monitoring | Internal | Ops tooling |

**Domain B — Engineering Delivery**

| Family | Name | Tag | Rationale |
|---|---|---|---|
| F04 | Software Quality and Review | Internal | Internal code quality |
| F05 | Code Generation and Engineering | Dual-Use | Internal code + sellable products |
| F06 | Deployment, DevOps, and Release | Internal | Internal ops |

**Domain C — Documentation and Knowledge**

| Family | Name | Tag | Rationale |
|---|---|---|---|
| F07 | Technical Documentation | Dual-Use | Internal docs + client deliverables |
| F08 | Knowledge Management and Synthesis | Dual-Use | Internal research + client research briefs |

**Domain D — Product, Design, and Creative**

| Family | Name | Tag | Rationale |
|---|---|---|---|
| F09 | Product Strategy and Design | Dual-Use | Internal strategy + client consulting |
| F10 | UI/UX and Frontend | Customer-Facing | User-facing products |
| F11 | Creative Production | Customer-Facing | Content that reaches audiences |

**Domain E — Intelligence, Data, and Analytics**

| Family | Name | Tag | Rationale |
|---|---|---|---|
| F12 | Research and Intelligence | Dual-Use | Internal intel + client reports |
| F13 | Data Collection and Enrichment | Internal | Data pipeline tooling |
| F14 | Analytics, Forecasting, and Prediction | Dual-Use | Internal dashboards + client analytics |
| F15 | Social Media and Trend Monitoring | Internal | Intelligence gathering |

**Domain F — Business Operations and Growth**

| Family | Name | Tag | Rationale |
|---|---|---|---|
| F16 | Growth Strategy and Go-to-Market | Dual-Use | Own GTM + client consulting |
| F17 | Advertising and Paid Acquisition | Internal | Own ad campaigns |
| F18 | Sales and Revenue Operations | Customer-Facing | Client-facing proposals and pitches |
| F19 | Finance, Planning, and FP&A | Internal | Internal financial management |
| F20 | Operations and Project Management | Internal | Internal ops |
| F21 | HR, Recruiting, and People Operations | Internal | Internal HR |
| F22 | Legal and Compliance | Dual-Use | Own legal + client legal docs |

**Domain G — Governance, Coordination, and Meta-Skills**

| Family | Name | Tag | Rationale |
|---|---|---|---|
| F23 | Governance, Approval, and Audit | Internal | Internal governance |
| F24 | Multi-Agent Coordination | Internal | System infrastructure |
| F25 | Prompt Engineering and Model Optimization | Internal | Internal tooling |
| F26 | Skill System Meta-Skills | Internal | Meta-tooling |
| F27 | Trust, Safety, and Ethical Review | Internal | Internal safety |
| F28 | Company Intelligence and Self-Improvement | Internal | Internal ops |

**Domain H — Trust, Safety, and Self-Improvement (absorbed into G above per catalog)**

*Note: The catalog lists Domains G and H separately but they share governance concerns. Tags applied to each family individually.*

**Domain I — Lead Generation, Outreach, and Sales Tools**

| Family | Name | Tag | Rationale |
|---|---|---|---|
| F29 | Lead Generation and Prospecting | Internal | Own pipeline |
| F30 | Apollo.io Integration Skills | Internal | Tool integration |
| F31 | n8n Workflow Automation Skills | Internal | Automation infrastructure |
| F32 | OCR and Document Intelligence | Customer-Facing | Sellable document processing service |
| F33 | Computer Vision and Visual Intelligence | Dual-Use | Internal processing + sellable service |
| F34 | Self-Learning and Continuous Improvement | Internal | System self-improvement |
| F35 | Humanizer and Communication Quality | Customer-Facing | All outward content |
| F36 | Serial Entrepreneur and Business Builder | Internal | Own business planning |
| F37 | Cold Email Outreach | Internal | Own outreach |
| F38 | LinkedIn Marketing and Personal Brand | Customer-Facing | Public-facing content |
| F39 | Public Relations and Communications | Customer-Facing | Media-facing content |

**Domain J — Startup, Finance, and Monetization**

| Family | Name | Tag | Rationale |
|---|---|---|---|
| F40 | Startup Planning and Execution | Dual-Use | Own planning + client consulting |
| F41 | Revenue Generation and Monetization | Internal | Own revenue strategy |
| F42 | Health, Nutrition, and Wellness Advisory | Customer-Facing | End-user advisory content |
| F43 | GTM Strategy and Execution | Dual-Use | Own GTM + client consulting |
| F44 | Creative Problem Solving and Solution Finding | Customer-Facing | Client-facing consulting tool |

**Domain K — Specialized Industry and Vertical Skills**

| Family | Name | Tag | Rationale |
|---|---|---|---|
| F45 | Real Estate and Property | Customer-Facing | Client-facing analysis |
| F46 | E-Commerce and Digital Commerce | Customer-Facing | Client-facing ops |
| F47 | Education and Training | Customer-Facing | Learner-facing content |
| F48 | Customer Success and Support | Customer-Facing | End-user facing |
| F49 | Personal Productivity and Life Management | Dual-Use | Founder's tools + sellable productivity service |
| F50 | Localization and International | Customer-Facing | Client-facing adaptation |
| F51 | Community and Developer Relations | Customer-Facing | Public-facing community |
| F52 | Security and Risk Operations | Internal | Internal security |
| F53 | Accounting and Tax | Internal | Internal finance |
| F54 | Networking and Relationship Management | Internal | Founder's networking |

**Domain L — Content Empire and Social Media Monetization**

| Family | Name | Tag | Rationale |
|---|---|---|---|
| F55 | Automation and Integration Orchestration | Internal | Infrastructure |
| F56 | Viral Content Engine | Customer-Facing | Public-facing content |
| F57 | Platform-Specific Growth and Account Management | Customer-Facing | Public-facing accounts |
| F58 | Social Media Monetization | Customer-Facing | Revenue-generating public content |
| F59 | SaaS and Digital Product Monetization | Customer-Facing | Sellable products |
| F60 | AI-Powered Video and Visual Production | Customer-Facing | Public-facing video |
| F61 | Personal Assistant and Daily Life Management | Internal | Founder's personal ops |
| F62 | Monetizable AI Model and Skill Creation | Customer-Facing | Sellable AI capabilities |
| F63 | Niche Account Empire Builder | Customer-Facing | Public-facing accounts |
| F64 | Creator Economy and Influencer Operations | Customer-Facing | Public-facing creator ops |

### Summary

| Tag | Families | Count |
|---|---|---|
| Internal | F01–F04, F06, F13, F15, F17, F19–F21, F23–F31, F34, F36–F37, F41, F52–F55, F61 | 29 |
| Customer-Facing | F10–F11, F18, F32, F35, F38–F39, F42, F44–F48, F50–F51, F56–F60, F62–F64 | 23 |
| Dual-Use | F05, F07–F09, F12, F14, F16, F22, F33, F40, F43, F49 | 12 |

---

## Pre-Step D — Family Dependency Chains

### The Problem

Some families cannot be built until their upstream dependencies exist. Building F62 (Monetizable AI Skill Creation) before F05 (Code Generation) and F59 (SaaS Monetization) means F62 has nothing to package and sell.

### Dependency Map

**Tier 0 — No Dependencies (Foundation)**

These families depend only on the existing routing/budget/skill infrastructure:

F01, F02, F03, F07, F08, F09, F11, F12, F14, F19, F20, F21, F22, F23, F25, F26, F27, F28, F32, F34, F35, F36, F40, F42, F44, F47, F49, F52, F53, F54, F61

**Tier 1 — Depends on Tier 0 families**

| Family | Depends On | Why |
|---|---|---|
| F04 (Software Quality) | F01, F07 | Reviews architecture and docs that must exist |
| F05 (Code Generation) | F01 | Needs architecture specs to generate code against |
| F06 (Deployment) | F05 | Deploys code that must be generated |
| F10 (UI/UX) | F05, F11 | Builds on generated code and creative assets |
| F13 (Data Collection) | F12 | Collects data based on research intelligence |
| F15 (Social Monitoring) | F12 | Monitors based on intelligence framework |
| F16 (Growth/GTM) | F09, F12 | Growth strategy needs product strategy and research |
| F17 (Advertising) | F11, F16 | Ads need creative and growth strategy |
| F18 (Sales) | F12, F16 | Sales needs research and GTM |
| F29 (Lead Gen) | F12 | Lead gen needs research to define ICP |
| F43 (GTM Execution) | F16 | Executes strategy designed by F16 |
| F50 (Localization) | F07, F11 | Localizes docs and content that must exist |

**Tier 2 — Depends on Tier 1 families**

| Family | Depends On | Why |
|---|---|---|
| F24 (Multi-Agent) | F26 | Coordinates skills that must exist |
| F30 (Apollo Integration) | F29 | Apollo serves lead gen pipelines |
| F31 (n8n Workflows) | F20, F55 | Automates operations |
| F33 (Computer Vision) | F32 | Builds on OCR foundation |
| F37 (Cold Email) | F29, F35 | Needs lead data + humanized copy |
| F38 (LinkedIn) | F11, F35 | Needs content + humanization |
| F39 (PR/Comms) | F11, F35 | Needs content + humanization |
| F41 (Revenue/Monetization) | F09, F18 | Revenue needs product + sales |
| F46 (E-Commerce) | F10, F41 | Commerce needs UI + monetization |
| F48 (Customer Support) | F07, F08 | Support needs docs + knowledge base |
| F55 (Automation/Integration) | F20, F31 | Orchestrates ops and workflows |
| F56 (Viral Content) | F11, F35 | Content factory needs creative + humanizer |

**Tier 3 — Depends on Tier 2 families**

| Family | Depends On | Why |
|---|---|---|
| F45 (Real Estate) | F14, F46 | Vertical needs analytics + commerce |
| F51 (Community/DevRel) | F07, F38 | Community needs docs + social presence |
| F57 (Platform Growth) | F56 | Growth needs content engine |
| F58 (Social Monetization) | F57 | Monetizes accounts built by F57 |
| F59 (SaaS Monetization) | F05, F10, F41 | SaaS needs code + UI + monetization |
| F60 (AI Video) | F56 | Video production needs content strategy |

**Tier 4 — Depends on Tier 3 families**

| Family | Depends On | Why |
|---|---|---|
| F62 (Monetizable AI Skills) | F05, F26, F59 | Packages skills as sellable products |
| F63 (Niche Account Empire) | F56, F57, F58 | Empire needs content + growth + monetization |
| F64 (Creator Operations) | F58, F63 | Creator ops sits on top of the empire |

### Dependency Visualization

```
Tier 0 (Foundation) ─── 31 families ─── no dependencies
    │
    ▼
Tier 1 ─── 12 families ─── depend on Tier 0
    │
    ▼
Tier 2 ─── 12 families ─── depend on Tier 1
    │
    ▼
Tier 3 ─── 6 families ─── depend on Tier 2
    │
    ▼
Tier 4 ─── 3 families ─── depend on Tier 3
    │
    ▼
Total: 64 families mapped — all accounted for (F32 is Tier 0, no dependencies)
```

---

## Pre-Step E — Build Tiers (Priority Batches)

### The Problem

You cannot build 479 skills at once. You need to pick the 20–30 skills that drive 80% of value and build those first. The dependency chain constrains order. Business value determines priority within each tier.

### Proposed Build Tiers

**Build Tier 1 — Foundation Skills (Build First)**

Skills that the system itself needs to scale skill production, plus the highest-value immediate capabilities.

| Family | Skills to Build | Count | Why First |
|---|---|---|---|
| F26 | Skill Spec Writer, Skill Template Generator | 2 | Meta-skills that accelerate all other skill building |
| F25 | System Prompt Designer, Output Format Enforcer | 2 | Prompt quality drives all skill quality |
| F08 | Research Brief Writer (exists), Competitive Intelligence Synthesizer | 1 new | Research powers all downstream decisions |
| F07 | Setup Guide Writer, Runbook Author | 2 | Documentation quality for everything built |
| F01 | Architecture Specification Writer | 1 | Architecture specs for new subsystems |
| F35 | Tone Calibrator, AI Detection Bypasser | 2 | All outward content needs humanization |

**Total Tier 1: ~10 skills** (including existing research-brief)

**Tier 1 Build Order:** F35 (Humanizer — Tone Calibrator) is built second, immediately after the template generator (Pre-Step F). F35 is priority 1 within Tier 1 because all outward-facing content across every subsequent tier depends on humanization quality. All other Tier 1 skills are built after F35 is confirmed working.

**Build Tier 2 — Revenue Foundation**

Skills that directly enable generating revenue.

| Family | Skills to Build | Count | Why |
|---|---|---|---|
| F05 | Feature Implementation Writer, Script Automator | 2 | Code generation is core capability |
| F09 | Product Requirements Writer, Pricing Strategy Analyst | 2 | Product definition before building |
| F11 | Copywriting Specialist, Video Script Writer | 2 | Content production for marketing |
| F12 | Market Research Analyst, Technology Trend Scanner | 2 | Intelligence for decisions |
| F36 | Business Idea Validator, MVP Scope Definer | 2 | Startup validation tools |

**Total Tier 2: ~10 skills**

**Build Tier 3 — Growth Engine**

Skills for customer acquisition and outreach.

| Family | Skills to Build | Count | Why |
|---|---|---|---|
| F16 | Go-to-Market Plan Writer, Funnel Optimizer | 2 | Growth strategy |
| F18 | Sales Pitch Crafter, Proposal Generator | 2 | Revenue generation |
| F29 | Ideal Customer Profile Builder, Lead Scoring Engine | 2 | Lead pipeline |
| F37 | Cold Email Sequence Writer, Email Personalization Engine | 2 | Outreach execution |
| F38 | LinkedIn Post Writer, LinkedIn Lead Generation Workflow | 2 | Social selling |

**Total Tier 3: ~10 skills**

**Build Tier 4 — Product and Monetization**

Skills for building and selling products.

| Family | Skills to Build | Count | Why |
|---|---|---|---|
| F10 | Landing Page Builder, UI Component Designer | 2 | Product UI |
| F41 | Monetization Strategy Designer, Subscription Churn Reduction Planner | 2 | Revenue mechanics |
| F46 | Product Listing Optimizer | 1 | E-commerce |
| F56 | Viral Hook Generator, Video Script Writer (Short-Form) | 2 | Content engine |
| F59 | SaaS Idea Validator, Micro-SaaS Revenue Model Designer | 2 | SaaS products |

**Total Tier 4: ~9 skills**

**Build Tier 5 — Scale and Empire**

Skills for scaling operations and building the content empire.

| Family | Skills to Build | Count | Depends On |
|---|---|---|---|
| F57 | YouTube Channel Architect, TikTok Account Growth Strategist | 2 | Tier 4 content |
| F58 | Sponsorship Deal Negotiator, Affiliate Marketing Strategy Designer | 2 | Tier 4 accounts |
| F62 | Custom Skill Blueprint Writer, Skill-as-a-Service Packager | 2 | Tier 1 meta-skills |
| F63 | Niche Profitability Assessor, Account Portfolio Strategist | 2 | Tier 4 content |
| F30 | Apollo Search Query Builder, Apollo Contact Enrichment Workflow | 2 | Tier 3 lead gen |

**Total Tier 5: ~10 skills**

**Remaining families and skills** — Built on demand as business needs dictate, after Tiers 1–5 are solid.

### Summary

| Tier | Focus | Skills | Cumulative |
|---|---|---|---|
| 1 | Foundation + Meta-Skills | ~10 | 10 |
| 2 | Revenue Foundation | ~10 | 20 |
| 3 | Growth Engine | ~10 | 30 |
| 4 | Product + Monetization | ~9 | 39 |
| 5 | Scale + Empire | ~10 | 49 |
| Remaining | On-demand | ~430 | 479 |

**The first 49 skills cover the critical path from foundation to revenue to scale.** The remaining 430 are built as specific business needs arise — not speculatively.

---

## Pre-Step F — Skill Template Generator

### The Problem

Building 49+ skills by hand-creating skill.yaml, run.py, README.md, and outputs/.gitignore every time is slow and error-prone. The boilerplate should be generated.

### Proposed Tool

A script at `scripts/new-skill.py` that generates the complete boilerplate for a new skill.

**Usage:**

```bash
python3 scripts/new-skill.py \
  --id a01-arch-spec-writer \
  --name "Architecture Specification Writer" \
  --family 01 \
  --domain A \
  --tag internal \
  --steps 5 \
  --llm-steps "2,3"
```

**What it generates:**

```
skills/a01-arch-spec-writer/
├── skill.yaml          # Complete template with inputs, outputs, steps, routing
├── run.py              # Step handler boilerplate with routing integration
├── README.md           # Template README with routing table placeholder
└── outputs/
    └── .gitignore      # "*" to gitignore all artifacts
```

**skill.yaml template includes:**

- Correct naming following Pre-Step A convention
- Input/output sections with validation stubs
- Steps with `makes_llm_call` correctly set based on `--llm-steps`
- Task class defaults based on family tag (internal → cheap, customer-facing → premium)
- Approval boundaries defaulting to safe for internal, approval_gated for customer-facing external effects
- Composable output envelope generation in final step

**run.py template includes:**

- Step handler functions for each step
- Routing integration: reads `context["resolved_model"]` and `context["resolved_provider"]`
- Provider dispatch: call_openai, call_anthropic, call_google based on resolved provider
- Envelope JSON generation in the final step
- TODO placeholders for prompt engineering (the actual work)

**What it does NOT generate:**

- Actual prompts — those are 60-70% of the work and must be hand-crafted per skill
- Business logic — step handlers are stubs that need implementation
- Validation rules — input/output validation must be defined per skill

### Implementation

This is actually F26 Skill #6 from the catalog (Skill Template Generator) — but implemented as a standalone script rather than a LangGraph skill, because it's a dev tool, not an inference workflow.

**Estimated implementation:** ~150 lines of Python. No LLM calls. Pure code generation.

---

## Decision Points for Your Approval

| # | Decision | Options | My Recommendation |
|---|---|---|---|
| 1 | Naming convention | `a01-arch-spec-writer` format (zero-padded) | Approve as proposed |
| 2 | I/O interchange | JSON envelope + Markdown artifact + error field | Approve as proposed |
| 3 | Family tags | 29 internal, 23 customer-facing, 12 dual-use | Approve with corrections applied |
| 4 | Dependencies | 5-tier dependency chain | Approve as proposed |
| 5 | Build order | Tiers 1–5 (~49 skills), F35 priority 1 in Tier 1 | Approve as proposed |
| 6 | Template generator | `scripts/new-skill.py` | Approve — build this first |
| 7 | Existing research-brief | Keep at `skills/research-brief/` or rename to `c08-research-brief` | Keep as-is, document the alias |
| 8 | Build sequence | Pre-Step F first (template generator), then F35 Tone Calibrator, then remaining Tier 1 | Approve sequence |

**After you approve (with any modifications), the implementation order is:**

1. Build `scripts/new-skill.py` (Pre-Step F)
2. Update skill-runner.py to support `--input-from` envelope chaining (Pre-Step B)
3. Generate F35 Tone Calibrator boilerplate using new-skill.py
4. Implement, test, commit F35 Tone Calibrator (Tier 1 priority 1)
5. Generate and implement remaining Tier 1 skills in approved order
6. Repeat for each subsequent tier

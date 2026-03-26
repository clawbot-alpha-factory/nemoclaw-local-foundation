# d11-copywriting-specialist — Copywriting Specialist

> **Family:** F11 | **Domain:** D | **Tag:** customer-facing | **Type:** executor
> **Schema:** v2 | **Runner:** v4.0+ | **Routing:** premium

## What It Does

Takes a copy brief, target audience, format, brand voice, and reference material.
Produces polished, conversion-oriented marketing copy with single CTA enforcement,
persuasion mechanics, format-specific structure, and anti-hallucination controls.

Supports: landing pages, emails, ad copy, product descriptions, sales pages, general.

## Inputs

| Name | Type | Required | Description |
|---|---|---|---|
| copy_brief | string | yes | What to write: product/service, key message, goal (min 30 chars) |
| target_audience | string | yes | Who reads this: role, pain points, decision stage (min 15 chars) |
| copy_format | string | yes | landing_page, email, ad_copy, product_description, sales_page, general |
| brand_voice | string | no | Tone, style, vocabulary constraints |
| reference_material | string | no | Testimonials, data points, product specs to incorporate |
| copy_length | string | no | short (under 300 words), standard (300-800), long (800+). Default: standard |

## Usage

```bash
python3 skills/skill-runner.py --skill d11-copywriting-specialist \
  --input copy_brief "Write a landing page for ClawBot AI, an AI-powered customer onboarding platform for B2B SaaS. Reduces time-to-value from 14 days to 3 days. Pricing starts at 299/month. Goal: free trial signups." \
  --input target_audience "VP of Customer Success at B2B SaaS companies with 50-500 employees. Frustrated with manual onboarding causing churn." \
  --input copy_format landing_page \
  --input brand_voice "Professional but warm. Direct, not salesy. Data-driven." \
  --input reference_material "Acme Corp reduced onboarding time by 72 percent. NPS improved from 34 to 67. 150+ B2B SaaS companies use ClawBot. SOC 2 Type II certified." \
  --input copy_length standard
```

## Routing

| Step | Task Class | Default Alias | Model |
|---|---|---|---|
| step_2 (generate) | premium | premium_claude | claude-sonnet-4-6 |
| step_3 (critic) | moderate | cheap_claude | claude-haiku-4-5 |
| step_4 (improve) | premium | premium_claude | claude-sonnet-4-6 |

## Key Deterministic Checks

- Format-specific required sections
- Single CTA enforcement (flag >2 competing CTAs)
- Headline benefit/hook detection
- Persuasion technique counting (social proof, urgency, benefit stacking, objection handling, specificity)
- Feature-benefit separation (flag feature-only bullets)
- Banned filler phrases (cutting-edge, best-in-class, etc.)
- Fabricated testimonials and statistics detection
- Tone consistency with brand voice

## Composability

**Feeds into:** i35-tone-calibrator, d11-video-script-writer
**Accepts from:** f09-product-req-writer, e12-market-research-analyst, f09-pricing-strategist

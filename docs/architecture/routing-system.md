# Routing System

> **Location:** `docs/architecture/routing-system.md`
> **Version:** 1.0
> **Date:** 2026-03-24
> **Phase:** 12 — Documentation Consolidation
> **Config source of truth:** `config/routing/routing-config.yaml`

---

## Purpose

This document explains how model routing works in the NemoClaw local foundation. Every inference call in the system passes through the routing layer, which resolves a task class to a specific provider, model, and cost estimate.

---

## How Routing Works

The routing system has three concepts: task classes, aliases, and providers.

1. Each skill step declares a **task class** in its `skill.yaml` (e.g., `complex_reasoning`, `general_short`)
2. The routing config maps that task class to an **alias** (e.g., `reasoning_claude`)
3. The alias resolves to a specific **provider and model** (e.g., Anthropic → claude-sonnet-4-6)

```
skill.yaml step → task_class → routing_rules lookup → alias → provider + model
```

The budget enforcer (`scripts/budget-enforcer.py`) performs this resolution at runtime and checks the provider budget before allowing the call.

---

## Providers

Three inference providers, each accessed via direct API.

| Provider | Library | API Key Variable | Base URL |
|---|---|---|---|
| OpenAI | langchain-openai | OPENAI_API_KEY | https://api.openai.com/v1 |
| Anthropic | langchain-anthropic | ANTHROPIC_API_KEY | https://api.anthropic.com/v1 |
| Google | google-generativeai | GOOGLE_API_KEY | https://generativelanguage.googleapis.com/v1beta |

All keys stored in `config/.env`, never committed.

---

## Alias Table

Nine aliases covering three providers. Cost estimates are set at 2x real pricing for conservative budget tracking.

| Alias | Provider | Model | Max Tokens | Est. Cost/Call | Role |
|---|---|---|---|---|---|
| cheap_openai | OpenAI | gpt-5.4-mini | 4096 | $0.0004 | Default. Classification, structured output, short tasks |
| reasoning_openai | OpenAI | gpt-5.4 | 8096 | $0.010 | Heavy reasoning, coding, agentic tasks |
| reasoning_o3 | OpenAI | o3 | 8096 | $0.060 | Deep STEM reasoning, math. Use sparingly — expensive |
| cheap_claude | Anthropic | claude-haiku-4-5-20251001 | 4096 | $0.004 | Moderate complexity. Fast, cheap Claude |
| reasoning_claude | Anthropic | claude-sonnet-4-6 | 8096 | $0.012 | Complex reasoning, long context, code, synthesis |
| premium_claude | Anthropic | claude-opus-4-6 | 8096 | $0.030 | Highest quality. Critical outputs only |
| cheap_google | Google | gemini-2.5-flash | 4096 | $0.0004 | Fast multimodal and long context |
| reasoning_google | Google | gemini-2.5-pro-preview-03-25 | 8096 | $0.008 | Google flagship. Complex reasoning, multimodal |
| fallback_openai | OpenAI | gpt-5.4-mini | 8096 | $0.0004 | Emergency fallback for any provider failure |

---

## Task Class Routing

Ten task classes, each mapped to exactly one alias. This is the `routing_rules` section of the config.

| Task Class | Routes To | When To Use |
|---|---|---|
| general_short | cheap_openai | Simple input validation, short structured output |
| structured_short | cheap_openai | Classification, extraction, pass/fail checks |
| moderate | cheap_claude | Mid-complexity tasks needing better instruction following |
| complex_reasoning | reasoning_claude | Deep analysis, synthesis, multi-step reasoning |
| code | reasoning_openai | Code generation, debugging, refactoring |
| agentic | reasoning_claude | Agent planning, tool selection, workflow decisions |
| long_document | reasoning_google | Large document processing (benefits from 1M context) |
| vision | cheap_google | Image analysis, OCR, multimodal input |
| deep_reasoning | reasoning_o3 | Math, formal logic, multi-step STEM problems |
| premium | premium_claude | Mission-critical outputs, investor materials, legal |

**Default alias** (when no task class matches): `cheap_openai`

---

## How a Skill Step Gets Routed

Concrete example using the research-brief skill:

| Step | Name | Task Class | Resolved Alias | Model |
|---|---|---|---|---|
| step_1 | Validate input and plan research | general_short | cheap_openai | gpt-5.4-mini |
| step_2 | Research topic | complex_reasoning | reasoning_claude | claude-sonnet-4-6 |
| step_3 | Structure findings into brief | moderate | cheap_claude | claude-haiku-4-5-20251001 |
| step_4 | Validate output | general_short | cheap_openai | gpt-5.4-mini |
| step_5 | Write artifact to output | general_short | cheap_openai | gpt-5.4-mini (no inference — file write only) |

Total estimated cost per research-brief run: ~$0.017

---

## Fallback Behavior

The current routing system uses a single global fallback alias: `fallback_openai` (gpt-5.4-mini on OpenAI).

When a provider is unavailable or the provider's budget is exhausted, the budget enforcer routes to the fallback alias. This is logged to both terminal and `~/.nemoclaw/logs/budget-audit.log`.

**Current fallback logic:**

1. Resolve task class → alias → provider
2. Check provider budget: spend < hard stop?
3. If budget exhausted (100%) → route to `fallback_openai`, log the downgrade
4. If budget at warning (90%) AND alias is non-OpenAI → route to `fallback_openai`, log warning
5. If budget at warning (90%) AND alias is OpenAI → proceed with warning only, no fallback
6. If API call fails → error reported, no automatic retry in current implementation
**What is not yet implemented:**

- Per-alias fallback chains (e.g., Opus → Sonnet → GPT-5.4)
- Automatic retry with backoff
- Complexity-based tier upgrades

These are defined in the master routing planning document but have not been built. They are future extension candidates, not current system behavior. See `docs/reference/design-decisions-log.md` for the planning-to-reality mapping.

---

## Cost Tracking

Every routed call logs its estimated cost. The budget enforcer writes to two files:

| File | Location | Format | Content |
|---|---|---|---|
| provider-spend.json | ~/.nemoclaw/logs/ | JSON | Cumulative spend per provider |
| provider-usage.jsonl | ~/.nemoclaw/logs/ | JSONL (append) | Per-call record with alias, model, cost, budget remaining |

Logged fields per call:

- timestamp
- task_class
- alias_selected
- model_used
- provider
- estimated_cost_usd
- provider_cumulative_spend_usd
- provider_budget_remaining_usd
- provider_budget_pct_used
- fallback_used
- override

---

## Real Pricing vs Tracked Pricing

The config uses **2x real pricing** for conservative tracking. This means the system reports higher spend than actual API bills.

| Model | Real Input/1M | Real Output/1M | Tracked Est. Cost/Call |
|---|---|---|---|
| gpt-5.4-mini | $0.15 | $0.60 | $0.0004 (2x buffer) |
| gpt-5.4 | $1.75 | $14.00 | $0.010 (2x buffer) |
| o3 | $10.00 | $40.00 | $0.060 (2x buffer) |
| claude-haiku-4-5-20251001 | $1.00 | $5.00 | $0.004 (2x buffer) |
| claude-sonnet-4-6 | $3.00 | $15.00 | $0.012 (2x buffer) |
| claude-opus-4-6 | $5.00 | $25.00 | $0.030 (2x buffer) |
| gemini-2.5-flash | $0.15 | $0.60 | $0.0004 (2x buffer) |
| gemini-2.5-pro-preview-03-25 | $1.25 | $10.00 | $0.008 (2x buffer) |

The 2x buffer ensures budget limits are hit before actual spend limits, providing a safety margin.

---

## Config File Reference

**File:** `config/routing/routing-config.yaml`

Top-level sections:

| Section | Purpose |
|---|---|
| `providers:` | Defines all 9 aliases with provider, model, max_tokens, estimated cost, and notes |
| `routing_rules:` | Maps each of the 10 task classes to an alias |
| `defaults:` | Sets the default alias (`cheap_openai`) and active provider |

Note: Despite the key name `providers:`, this section defines aliases, not just providers. This is a naming artifact from an earlier config version. The alias concept is the correct mental model.

---

## Adding a New Task Class

1. Add the task class and its alias mapping to `routing_rules:` in `routing-config.yaml`
2. Reference the task class in a skill step's `task_class` field in `skill.yaml`
3. Run `python3 scripts/validate.py` to confirm routing resolves correctly
4. The budget enforcer will automatically handle the new class

---

## Adding a New Alias

1. Add the alias definition under `providers:` in `routing-config.yaml` with provider, model, max_tokens, and estimated cost
2. Map at least one task class to it in `routing_rules:`
3. Ensure the provider's API key is in `config/.env`
4. Run `python3 scripts/validate.py`

---

## Drift from Planning Documents

The master routing planning document (external to repo) defined a 7-alias system with names like `cheap_default`, `enterprise_max`, `premium_quality`. The implemented system uses 9 aliases with provider-suffixed names like `cheap_openai`, `premium_claude`, `reasoning_google`.

Key differences:

| Planning Doc | Implemented System |
|---|---|
| 7 aliases | 9 aliases |
| Tiered names (T1–T5) | Provider-suffixed names |
| Complexity pre-classifier | Not implemented |
| Per-alias fallback chains with retry | Global fallback only |
| o4-mini for reasoning | o3 for reasoning |

The implemented system is simpler, more transparent, and easier to extend. The planning doc's more complex features (pre-classifier, per-alias chains) remain valid future extensions. See `docs/reference/design-decisions-log.md`.

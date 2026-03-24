# Config Reference

> **Location:** `docs/reference/config-reference.md`
> **Version:** 1.0
> **Date:** 2026-03-24
> **Phase:** 12 — Documentation Consolidation

---

## Purpose

This document is the field-level reference for every configuration file in the NemoClaw local foundation. It explains what each file controls, where it lives, whether it is committed to the repo, and what every field means.

---

## Config File Inventory

| File | Location | Committed | Purpose |
|---|---|---|---|
| .env | config/ | No (gitignored) | All API keys and credentials |
| .env.example | config/ | Yes | Placeholder template for .env |
| routing-config.yaml | config/routing/ | Yes | Model routing — aliases, task classes, defaults |
| budget-config.yaml | config/routing/ | Yes | Per-provider budget limits and logging config |
| skill.yaml | skills/{name}/ | Yes | Per-skill definition (one per skill) |
| sandbox-policy.yaml | docs/architecture/ | Yes | OpenShell sandbox policy (reference only) |
| openclaw.json | repo root | Yes | OpenClaw sandbox configuration (sandbox-managed) |

---

## config/.env

**Purpose:** Stores all API keys and credentials. This is the single source of secrets for the entire system.

**Location:** `config/.env`

**Committed:** No — gitignored. Never commit this file.

**Template:** `config/.env.example` (committed with placeholder values)

**How to load:** Before running any script that needs API access:

```bash
set -a && source config/.env && set +a
```

### Variables

| Variable | Provider | Required By | Description |
|---|---|---|---|
| OPENAI_API_KEY | OpenAI | Routing, skill execution | OpenAI API key from platform.openai.com |
| ANTHROPIC_API_KEY | Anthropic | Routing, skill execution | Anthropic API key from console.anthropic.com |
| GOOGLE_API_KEY | Google | Routing, skill execution | Google AI API key from ai.google.dev |
| NGC_API_KEY | NVIDIA | NemoClaw sandbox, Docker registry | NVIDIA NGC API key from ngc.nvidia.com |
| NVIDIA_INFERENCE_API_KEY | NVIDIA | NemoClaw sandbox inference | NVIDIA inference endpoint key |
| ASANA_ACCESS_TOKEN | Asana | External tools (Asana integration) | Personal access token from app.asana.com |

**Future variables** (Phase 12 placeholders, not yet required):

| Variable | Provider | When Needed |
|---|---|---|
| SUPABASE_URL | Supabase | Phase 12 — first SaaS |
| SUPABASE_ANON_KEY | Supabase | Phase 12 — first SaaS |
| SUPABASE_SERVICE_ROLE_KEY | Supabase | Phase 12 — first SaaS |
| VERCEL_TOKEN | Vercel | Phase 12 — first SaaS |
| LEMONSQUEEZY_API_KEY | Lemon Squeezy | Phase 12 — first monetized product |
| LEMONSQUEEZY_WEBHOOK_SECRET | Lemon Squeezy | Phase 12 — first monetized product |
| APOLLO_API_KEY | Apollo.io | Phase 12 — lead gen skills |
| INSTANTLY_API_KEY | Instantly.ai | Phase 12 — outreach skills |
| RESEND_API_KEY | Resend | Phase 12 — first product sending email |
| PAYONEER_API_KEY | Payoneer | When international wire clients arrive |
| OPUSCLIP_API_KEY | OpusClip | Phase 12 — video content skills |
| APIFY_TOKEN | Apify | Phase 12 — web scraping at scale |

**Security rules:**

- Never commit `config/.env` to the repo
- Never hardcode keys in scripts
- Never print key values in logs (print key names only)
- Rotate keys immediately if exposed
- Compare against `.env.example` when setting up a new machine

---

## config/routing/routing-config.yaml

**Purpose:** Defines the model routing system — all aliases, their provider and model mappings, task class routing rules, and defaults.

**Location:** `config/routing/routing-config.yaml`

**Committed:** Yes

**Current version:** v3.0

**Full doc:** `docs/architecture/routing-system.md`

### Section: providers

Despite the key name, this section defines **aliases** (not just providers). Each alias maps to a provider, model, token limit, and cost estimate.

| Field | Type | Description |
|---|---|---|
| provider | string | Provider name: `openai`, `anthropic`, or `google` |
| model | string | Exact model string sent to the API |
| max_tokens | integer | Maximum tokens for this alias |
| estimated_cost_per_call | float | Estimated USD per call (2x real pricing for conservative tracking) |
| notes | string | Human-readable description of when to use this alias |

**Current aliases:** cheap_openai, reasoning_openai, reasoning_o3, cheap_claude, reasoning_claude, premium_claude, cheap_google, reasoning_google, fallback_openai

### Section: routing_rules

Maps task classes to aliases. Each key is a task class name, each value is an alias name.

```yaml
routing_rules:
  complex_reasoning:  reasoning_claude
  long_document:      reasoning_google
  code:               reasoning_openai
  agentic:            reasoning_claude
  moderate:           cheap_claude
  vision:             cheap_google
  structured_short:   cheap_openai
  general_short:      cheap_openai
  deep_reasoning:     reasoning_o3
  premium:            premium_claude
```

**To add a new task class:** Add a line mapping the class name to an alias. No restart needed — takes effect on next inference call.

### Section: defaults

| Field | Type | Description |
|---|---|---|
| default_alias | string | Alias used when no task class matches (`cheap_openai`) |
| active_provider | string | Default provider hint (`openai`) |

---

## config/routing/budget-config.yaml

**Purpose:** Defines per-provider budget limits, warning and hard-stop thresholds, and logging configuration.

**Location:** `config/routing/budget-config.yaml`

**Committed:** Yes

**Current version:** v2.0

**Full doc:** `docs/architecture/budget-system.md`

### Section: budgets

Three entries (one per provider), each with identical structure:

| Field | Type | Description |
|---|---|---|
| total_usd | float | Maximum spend allowed for this provider |
| tracking | string | `cumulative_across_sessions` — spend persists between runs |
| threshold_warn | float | Fraction of budget that triggers a warning (0.90 = 90%) |
| threshold_hard_stop | float | Fraction of budget that blocks calls (1.00 = 100%) |
| warn_message | string | Text printed to terminal at warning threshold |
| exhausted_message | string | Text printed to terminal at hard stop |
| log_to_file | boolean | Whether to write events to budget-audit.log |
| log_to_terminal | boolean | Whether to print events to terminal |

**Current budgets:** $10.00 per provider (Anthropic, OpenAI, Google)

**To change a budget:** Edit `total_usd` for the provider. No restart needed.

### Section: log

| Field | Type | Description |
|---|---|---|
| path | string | Location of the per-call usage log (`~/.nemoclaw/logs/provider-usage.jsonl`) |
| fields | list | Fields recorded per call (timestamp, task_class, alias_selected, model_used, provider, estimated_cost_usd, provider_cumulative_spend_usd, provider_budget_remaining_usd, provider_budget_pct_used, fallback_used, override) |

---

## skills/{name}/skill.yaml

**Purpose:** Complete definition of a single skill — inputs, outputs, steps, routing, validation, and approval boundaries.

**Location:** `skills/{skill-name}/skill.yaml` (one per skill)

**Committed:** Yes

**Full doc:** `docs/architecture/skill-system.md` (contains the complete field-level specification)

### Key Sections

| Section | Purpose |
|---|---|
| Top-level fields | Name, version, description, author, compatibility |
| inputs | Typed input parameters with validation rules |
| outputs | Expected outputs with quality validation |
| artifacts | Output file storage configuration |
| steps | Ordered list of execution steps with task class, idempotency, approval |
| validation | Input/output validation rules and failure actions |
| approval_boundaries | Step safety classification |
| routing | Skill-level routing defaults |

**Current skills:**

| Skill | Location |
|---|---|
| research-brief | skills/research-brief/skill.yaml |

---

## docs/architecture/sandbox-policy.yaml

**Purpose:** The OpenShell sandbox security policy. Defines filesystem access, network policies, process isolation, and Landlock configuration for the NemoClaw sandbox.

**Location:** `docs/architecture/sandbox-policy.yaml`

**Committed:** Yes (reference only — not consumed by any script)

**Full doc:** `docs/architecture/sandbox-policy-design.md`

**Note:** This policy is enforced by the OpenShell sandbox, which is retained but not required for skill execution. The direct API architecture bypasses the sandbox entirely. This file is kept as a reference for the governance model that was in place during Phases 1–5.

### Key Sections

| Section | What It Controls |
|---|---|
| filesystem_policy | Read-only and read-write paths inside the sandbox |
| landlock | Linux Landlock LSM configuration |
| process | User and group identity inside the sandbox |
| network_policies | Per-binary endpoint allowlists (Anthropic, GitHub, npm, PyPI, NVIDIA, etc.) |

---

## openclaw.json

**Purpose:** OpenClaw configuration file at the repo root. Managed by the sandbox — not manually edited.

**Location:** Repo root

**Committed:** Yes

**Known issue:** After sandbox restart, this file's permissions reset to root inside the sandbox container. Fix with `bash scripts/fix-sandbox-permissions.sh`.

---

## Runtime Files (Not Config, But Referenced by Config)

These files are created at runtime, not committed to the repo, and referenced by the config files above.

| File | Location | Created By | Purpose |
|---|---|---|---|
| provider-spend.json | ~/.nemoclaw/logs/ | budget-enforcer.py | Cumulative spend per provider |
| provider-usage.jsonl | ~/.nemoclaw/logs/ | budget-enforcer.py | Per-call usage log |
| budget-audit.log | ~/.nemoclaw/logs/ | budget-enforcer.py | Budget threshold events |
| tools-audit.log | ~/.nemoclaw/logs/ | tools.py | External tool call events |
| validation-runs.jsonl | ~/.nemoclaw/logs/ | validate.py | Validation run history |
| langgraph.db | ~/.nemoclaw/checkpoints/ | skill-runner.py | LangGraph checkpoint database |

**If any runtime file is missing:** The creating script will recreate it on next run. Previous data in that file will be lost. See `docs/setup/restart-recovery-runbook.md` Section 3 for recovery procedures.

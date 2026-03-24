# External Tools Registry

> **Location:** `docs/extensions/external-tools-registry.md`
> **Version:** 2.0
> **Date:** 2026-03-24
> **Phase:** 12 — Documentation Consolidation
> **Status:** ACTIVE — framework built, 2 tools connected, 14 placeholder
> **Framework script:** `scripts/tools.py`
> **Source document:** the_ai_company_external_tool_stack.md v1.0 March 2026

---

## Purpose

This file is the single source of truth for all external tool integrations in the NemoClaw local foundation. It defines every tool, its integration status, credential requirements, activation prerequisites, and relationship to the budget and routing systems.

---

## Integration Architecture

Every external tool follows the same integration pattern defined in `scripts/tools.py`:

```
config/.env (credentials)
      │
      ▼
tools.py loads and validates credentials at startup
      │
      ▼
Tool wrapper: standardized call interface
      │
      ├── Audit log → ~/.nemoclaw/logs/tools-audit.log
      ├── Error handling → retry, fallback, or halt
      └── Cost tracking → where applicable
```

**Integration rules:**

- All tool API keys stored in `config/.env` following the same pattern as provider keys
- Every tool credential is validated by `validate.py` (when the tool is active)
- Every tool call is logged to `~/.nemoclaw/logs/tools-audit.log`
- Error handling follows retry → fallback → halt, matching model routing patterns
- No tool integration is built until the Skill that needs it is in active development

---

## Tool Status Summary

| Status | Count | Meaning |
|---|---|---|
| ✅ Active | 2 | Connected, credential validated, in use |
| ⏳ Placeholder | 11 | Registered, credential slot in .env.example, not yet connected |
| 🚫 No API | 3 | Manual-use tools with no programmatic API |

---

## Tier 1 — Essential Infrastructure

### GitHub

| Field | Value |
|---|---|
| Status | ✅ Active |
| URL | github.com |
| Credential | None needed (public repo, SSH key on machine) |
| Phase activated | Phase 1 |
| Integration depth | Full — git CLI, used by all phases |
| Activation prerequisite | Git installed, SSH key configured |
| Budget impact | None — free tier |

### Asana

| Field | Value |
|---|---|
| Status | ✅ Active — connection validated |
| URL | asana.com |
| Credential variable | ASANA_ACCESS_TOKEN |
| Phase activated | Phase 10.5 |
| Integration depth | Credential validated, API reachable (validate.py check [17]) |
| Activation prerequisite | Personal access token from app.asana.com/0/developer-console |
| Budget impact | None — free tier |
| Validation check | [16] ASANA_ACCESS_TOKEN present, [17] Asana connection valid |

### Supabase

| Field | Value |
|---|---|
| Status | ⏳ Placeholder |
| URL | supabase.com |
| Credential variables | SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY |
| Activate when | First SaaS Skill enters development |
| Activation prerequisite | Create Supabase project, copy URL and keys from project settings |
| Budget impact | Free tier (500MB DB, 1GB storage) → Pro $25/month when limits hit |
| Provides | Postgres database, auth, real-time, file storage, vector search |

### Vercel

| Field | Value |
|---|---|
| Status | ⏳ Placeholder |
| URL | vercel.com |
| Credential variable | VERCEL_TOKEN |
| Activate when | First SaaS Skill needs deployment |
| Activation prerequisite | Create Vercel account, generate token from account settings |
| Budget impact | Free hobby tier → Pro $20/month for commercial use |
| Provides | Frontend deployment, serverless functions, preview deploys |

### n8n (Self-Hosted)

| Field | Value |
|---|---|
| Status | ⏳ Placeholder |
| URL | n8n.io |
| Credential variable | None (self-hosted on Docker) |
| Activate when | Workflow automation Skills enter development |
| Activation prerequisite | `docker run` n8n container, configure via web UI |
| Budget impact | $0 self-hosted |
| Provides | Visual workflow automation, 500+ integrations, webhooks |

---

## Tier 1 — Payment Gateways (Jordan-Optimized)

### Lemon Squeezy

| Field | Value |
|---|---|
| Status | ⏳ Placeholder |
| URL | lemonsqueezy.com |
| Credential variables | LEMONSQUEEZY_API_KEY, LEMONSQUEEZY_WEBHOOK_SECRET |
| Activate when | First monetized product is ready to sell |
| Activation prerequisite | Create Lemon Squeezy account, set up store, generate API key |
| Budget impact | 5% + $0.50 per transaction (no monthly fee) |
| Provides | Global payments, subscriptions, Merchant of Record, tax compliance |
| Jordan note | Lemon Squeezy handles merchant responsibilities — no Jordan merchant account needed |

### CliQ

| Field | Value |
|---|---|
| Status | 🚫 No API |
| Credential variable | None (bank-level service) |
| Activate when | Jordanian clients pay for local services |
| Budget impact | $0 — free instant transfers |
| Provides | Jordan domestic instant bank-to-bank payments |
| Limitation | No API, no international payments, no subscription billing |

### Payoneer

| Field | Value |
|---|---|
| Status | ⏳ Placeholder |
| URL | payoneer.com |
| Credential variable | PAYONEER_API_KEY |
| Activate when | International clients prefer wire transfer over credit card |
| Budget impact | Per-transfer fees, currency conversion fees |
| Provides | USD/EUR/GBP receiving accounts, transfer to Jordanian bank |

---

## Tier 2 — Development Acceleration

### Cursor

| Field | Value |
|---|---|
| Status | 🚫 No separate API key |
| URL | cursor.com |
| Credential variable | None — uses existing OPENAI_API_KEY and ANTHROPIC_API_KEY |
| Activate when | SaaS code writing begins |
| Budget impact | Free (2000 completions) → Pro $20/month |
| Provides | AI code editor with codebase awareness, multi-file editing |

### Lovable

| Field | Value |
|---|---|
| Status | 🚫 No backend API |
| URL | lovable.dev |
| Credential variable | None (web-based) |
| Activate when | Rapid MVP prototyping needed |
| Budget impact | Free (5 messages/day) → Starter $20/month |
| Provides | Full-stack app generation from natural language, GitHub sync |

---

## Tier 3 — Platform Integrations

### Apollo.io

| Field | Value |
|---|---|
| Status | ⏳ Placeholder |
| URL | apollo.io |
| Credential variable | APOLLO_API_KEY |
| Activate when | Lead generation Skills (F29/F30) enter development |
| Activation prerequisite | Create Apollo account, generate API key |
| Budget impact | Free (basic) → $49/month (750 credits) |
| Provides | B2B contact database, lead enrichment, email sequencing |

### Instantly.ai

| Field | Value |
|---|---|
| Status | ⏳ Placeholder |
| URL | instantly.ai |
| Credential variable | INSTANTLY_API_KEY |
| Activate when | Cold email Skills (F37) enter development |
| Activation prerequisite | Create Instantly account, set up email accounts for warmup |
| Budget impact | $30/month (1000 active contacts) |
| Provides | Cold email infrastructure, inbox warmup, deliverability optimization |
| Stack pairing | Apollo (data) + n8n (orchestration) + Instantly (delivery) |

### Resend

| Field | Value |
|---|---|
| Status | ⏳ Placeholder |
| URL | resend.com |
| Credential variable | RESEND_API_KEY |
| Activate when | Any product needs transactional email |
| Activation prerequisite | Create Resend account, verify sending domain |
| Budget impact | Free (3000 emails/month) → Pro $20/month |
| Provides | Transactional email API, React email templates |

---

## Tier 4 — Content Production

### OpusClip

| Field | Value |
|---|---|
| Status | ⏳ Placeholder |
| URL | opus.pro |
| Credential variable | OPUSCLIP_API_KEY |
| Activate when | Video content Skills (F56/F60) enter development |
| Budget impact | Free (60 min/month) → Starter $9/month |
| Provides | AI video clipping, auto-captions, virality scoring |

### CapCut

| Field | Value |
|---|---|
| Status | 🚫 No API |
| URL | capcut.com |
| Credential variable | None |
| Activate when | Video editing needed alongside OpusClip |
| Budget impact | $0 — free |
| Provides | Video editing, auto-captions, AI effects |

---

## Tier 5 — Specialized

### Apify

| Field | Value |
|---|---|
| Status | ⏳ Placeholder |
| URL | apify.com |
| Credential variable | APIFY_TOKEN |
| Activate when | Data collection Skills (F13) need web scraping at scale |
| Activation prerequisite | Create Apify account, select or build scraper actors |
| Budget impact | Free (limited) → Starter $49/month |
| Provides | Web scraping platform, pre-built scrapers, proxy management |
| Alternative | n8n has basic HTTP scraping — only add Apify for scale or anti-bot |

---

## Tools Explicitly Rejected

| Tool | Reason | Revisit Condition |
|---|---|---|
| Stripe | Does not support Jordan as merchant country | If Stripe adds Jordan support |
| Manus.im | Acquired by Meta, volatile credits, quality issues | Never — permanently excluded |
| CamelAI | LangGraph already covers multi-agent coordination | If specialized debate patterns needed |
| V0 by Vercel | Lovable + Cursor covers this | If Lovable is insufficient |
| Windsurf/Codeium | Cursor is clear market leader at $20/month | If Cursor pricing becomes untenable |
| Gumroad | 10% fee vs Lemon Squeezy 5% + $0.50 | Never — permanently excluded |
| Self-hosted open models | Not justified until API spend > $2000/month | When monthly spend exceeds threshold |

---

## Credential Storage Convention

All tool credentials follow the same pattern as inference provider keys:

| Rule | Details |
|---|---|
| Storage | `config/.env` |
| Variable naming | `TOOLNAME_API_KEY` or `TOOLNAME_TOKEN` |
| Template | `config/.env.example` (committed with placeholders) |
| Committed | Never — .env is gitignored |
| Validation | `validate.py` checks active tool credentials |
| Audit | All tool calls logged to `~/.nemoclaw/logs/tools-audit.log` |

---

## Budget Relationship

External tools have costs separate from model inference. The model budget system (budget-enforcer.py) tracks inference spend only.

| Cost Type | Tracked By | Where |
|---|---|---|
| Model inference | budget-enforcer.py | provider-spend.json |
| Tool subscription fees | Not tracked (manual) | Monthly billing from each tool |
| Tool per-transaction fees | tools.py audit log | tools-audit.log (logged, not enforced) |

**Future extension:** Per-tool budget limits in budget-config.yaml, matching the provider budget pattern. Not needed until tool transaction costs become significant.

---

## Activation Timeline

| When | Tools to Activate | Monthly Cost Impact |
|---|---|---|
| Now (active) | GitHub, Asana | $0 |
| First SaaS Skill | Supabase Pro, Vercel Pro, Cursor Pro, Lovable Starter | +$65–85 |
| Lead Gen Skills | Apollo.io, Instantly.ai | +$79–109 |
| Outreach Skills | Resend | +$0 (free tier) |
| Content Skills | OpusClip | +$0–9 |
| Data Collection at Scale | Apify | +$0–49 |
| First monetized product | Lemon Squeezy | 5% per transaction |
| Local Jordanian clients | CliQ | $0 |
| International wire clients | Payoneer | Per-transfer fees |

**Rule:** Do not subscribe to a tool until the Skill that needs it is in active development. No speculative subscriptions.

---

## Adding a New Tool

1. Add the tool to this registry with all fields filled
2. Add the credential variable to `config/.env.example` as a placeholder
3. Add credential validation to `scripts/tools.py`
4. Add a validation check to `scripts/validate.py` if the tool is active
5. Implement the tool wrapper in `scripts/tools.py` following the standard pattern
6. Document the activation in a commit message
7. Update this file's status summary counts

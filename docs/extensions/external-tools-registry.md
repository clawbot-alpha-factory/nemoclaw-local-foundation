# External Tools Registry

**Phase:** 10.5 — External Tool Integrations  
**Status:** ACTIVE — framework built, keys configured  
**Approach:** Hybrid — API keys stored and validated now, active integration built per tool in Phase 12 alongside Skills  
**Version:** 1.0 — 2026-03-24  

---

## Purpose

This file is the single source of truth for all external tool integrations in the NemoClaw system.
Source document: the_ai_company_external_tool_stack.md v1.0 March 2026

---

## Key Storage Convention

All tool API keys follow the same pattern as provider keys:
- stored in config/.env
- variable name: TOOLNAME_API_KEY or TOOLNAME_TOKEN
- never committed to repo
- validated by validate.py
- placeholder entries in config/.env.example

---

## Tool Registry

### Tier 1 — Essential Infrastructure

| Tool | Variable | Phase | Status | URL |
|---|---|---|---|---|
| GitHub | none needed | Now | ✅ Active — already in use | github.com |
| Asana | ASANA_ACCESS_TOKEN | 10.5 | ✅ Key present, connection validated | asana.com |
| Supabase | SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY | 12 | ⏳ Placeholder only | supabase.com |
| Vercel | VERCEL_TOKEN | 12 | ⏳ Placeholder only | vercel.com |
| n8n | none (self-hosted) | 12 | ⏳ Self-hosted, no key needed yet | n8n.io |

### Tier 1 — Payment Gateways (Jordan-Optimized)

| Tool | Variable | Phase | Status | Notes |
|---|---|---|---|---|
| Lemon Squeezy | LEMONSQUEEZY_API_KEY, LEMONSQUEEZY_WEBHOOK_SECRET | 12 | ⏳ Placeholder only | Primary global payments — MoR |
| CliQ | none (bank-level) | When needed | ⏳ No API | Jordan domestic instant payments |
| Payoneer | PAYONEER_API_KEY | When needed | ⏳ Placeholder only | International wire backup |

### Tier 2 — Development Acceleration

| Tool | Variable | Phase | Status | Notes |
|---|---|---|---|---|
| Cursor | none (uses existing OpenAI/Anthropic keys) | 12 | ⏳ No separate key needed | AI code editor |
| Lovable | none (web-based) | 12 | ⏳ No backend API key needed | MVP builder |

### Tier 3 — Platform Integrations

| Tool | Variable | Phase | Status | Notes |
|---|---|---|---|---|
| Apollo.io | APOLLO_API_KEY | 12 | ⏳ Placeholder only | Activate when F29/F30 Skills built |
| Instantly.ai | INSTANTLY_API_KEY | 12 | ⏳ Placeholder only | Activate when F37 Skills built |
| Resend | RESEND_API_KEY | 12 | ⏳ Placeholder only | Activate when first product sends email |

### Tier 4 — Content Production

| Tool | Variable | Phase | Status | Notes |
|---|---|---|---|---|
| OpusClip | OPUSCLIP_API_KEY | 12 | ⏳ Placeholder only | Activate when F56/F60 Skills built |
| CapCut | none (no API) | 12 | ⏳ Manual tool only | No programmatic API available |

### Tier 5 — Specialized

| Tool | Variable | Phase | Status | Notes |
|---|---|---|---|---|
| Apify | APIFY_TOKEN | 12 | ⏳ Placeholder only | Activate when F13 needs scale scraping |

---

## Tools Explicitly Rejected

| Tool | Reason |
|---|---|
| Stripe | Does not support Jordan as merchant country |
| Manus.im | Acquired by Meta, volatile credit system, quality issues |
| CamelAI | Deferred — LangGraph already covers multi-agent coordination |
| V0 by Vercel | Deferred — Lovable + Cursor covers this |
| Windsurf/Codeium | Deferred — Cursor is clear market leader |
| Gumroad | 10% fee vs Lemon Squeezy 5% + $0.50, less developer-friendly |
| Self-hosted open models | Premature — not justified until monthly API spend exceeds $2,000+ |

---

## Integration Framework

Every tool integration in Phase 12 must implement the standard wrapper defined in scripts/tools.py:
- credential loading from config/.env
- connection validation
- audit logging for all tool calls
- error handling with retry and fallback
- cost tracking where applicable

---

## Activation Timeline

| Phase | Tools | Cost Impact |
|---|---|---|
| Now | GitHub (active) | $0 |
| Phase 10.5 | Asana (key validated) | $0 free tier |
| Phase 12 First SaaS | Supabase Pro, Vercel Pro, Cursor Pro, Lovable Starter | +$65-85/month |
| Phase 12 Lead Gen | Apollo.io, Instantly.ai | +$79-109/month |
| Phase 12 Outreach | Resend | +$0 free tier |
| Phase 12 Content | OpusClip | +$0-9/month |
| Phase 12 Data Scale | Apify (evaluate need) | +$0-49/month |
| When monetizing | Lemon Squeezy | 5% per transaction |
| Local clients | CliQ | $0 |
| International wire | Payoneer | Per-transfer fees |

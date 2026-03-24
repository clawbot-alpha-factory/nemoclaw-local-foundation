# Design Decisions Log

> **Location:** `docs/reference/design-decisions-log.md`
> **Version:** 1.0
> **Date:** 2026-03-24
> **Phase:** 12 — Documentation Consolidation

---

## Purpose

This document captures where the implemented system diverged from the original planning documents, why the divergences happened, and what remains as valid future work. It prevents the planning docs from being mistaken for reality and ensures drift is explicit, not hidden.

---

## Planning Documents Referenced

These documents were created before or during implementation and informed the system design. They are not in the repo — they live in the project knowledge files and uploaded reference docs.

| Document | Version | Scope |
|---|---|---|
| Master Model Recommendation | v1.0 | Model landscape, per-family recommendations |
| Master Model Recommendation | v2.0 | Enterprise quality philosophy, updated model tiers |
| Master Model Recommendation | v2.1 | 8 models, 3 providers, zero deprecated paths |
| Master Routing System | v1.0 | 7 aliases, fallback cascades, complexity classifier |
| Master External Tool Stack | v1.0 | 16 tools, activation timeline, Jordan-optimized payments |

---

## Decision 1 — Architecture Path

| Aspect | Planning Assumption | Implemented Reality |
|---|---|---|
| Runtime | NemoClaw/OpenShell sandbox | Custom LangGraph + Direct API on host Mac |
| Inference path | OpenShell proxy (inference.local) | Direct langchain calls to provider APIs |
| Governance | OpenShell Landlock + seccomp + network policy | Application-layer budget enforcement + audit logging |
| State persistence | Custom checkpoint_utils.py | LangGraph SqliteSaver |

**Why it changed:** NemoClaw is alpha. The OpenShell sandbox blocked native Mac execution and full internet access. The inference proxy bound calls to the sandbox network namespace. LangGraph provides superior graph primitives. The shift happened in Phase 6 after evaluating extraction cost — 4 of 5 governance components were already portable.

**What was lost:** OS-level network policy, filesystem sandboxing, Landlock isolation, governed credential injection. These are replaced by weaker application-layer controls. This is an accepted tradeoff documented in `architecture-lock.md`.

**Future validity:** If NemoClaw matures past alpha and resolves macOS support gaps, re-evaluation is warranted. The sandbox policy is preserved in `docs/architecture/sandbox-policy.yaml` as reference.

---

## Decision 2 — Alias Naming and Count

| Aspect | Planning (Master Routing v1.0) | Implemented |
|---|---|---|
| Alias count | 7 | 9 |
| Naming pattern | Tiered: cheap_default, production_standard, premium_quality, enterprise_max, multimodal_vision, reasoning_deep, fallback_budget | Provider-suffixed: cheap_openai, reasoning_openai, reasoning_o3, cheap_claude, reasoning_claude, premium_claude, cheap_google, reasoning_google, fallback_openai |
| Tier system | T1–T5 + reasoning + fallback | No tiers — flat alias list |

**Why it changed:** Provider-suffixed names are more transparent. When reading a log line, `reasoning_claude` immediately tells you the provider and role. `premium_quality` requires a lookup. The 9-alias system also separates OpenAI and Google at the cheap tier (cheap_openai vs cheap_google), which the 7-alias plan collapsed into one.

**What was kept:** The fundamental concept — task classes route to aliases, aliases resolve to models — is identical.

**Future validity:** The 7-alias tiered system from the planning doc is a valid alternative if the team prefers abstracted tier names. The current system can be renamed without structural changes.

---

## Decision 3 — Task Class Count

| Aspect | Planning | Implemented |
|---|---|---|
| Task classes | 64-family mapping (one per skill family) | 10 generic task classes |

**Why it changed:** 64 task classes (one per skill family) was premature — only one skill exists. The 10 generic classes (general_short, complex_reasoning, code, etc.) cover all current needs and are extensible.

**Future validity:** As skills multiply, family-specific task classes may become useful. The routing system supports unlimited task classes — just add lines to `routing_rules` in the config.

---

## Decision 4 — Complexity Pre-Classifier

| Aspect | Planning (Master Routing v1.0) | Implemented |
|---|---|---|
| Complexity classifier | GPT-5 Mini scores input 1–10 before every step; score ≥ 5 triggers tier upgrade | Not implemented |

**Why it changed:** With only one skill in production, automatic tier upgrades add overhead without value. The task class assignment in skill.yaml already determines the right model tier at design time.

**Future validity:** This is a strong feature for when multiple skills run diverse inputs. Implementation would add a pre-call step in budget-enforcer.py. The planning doc's specification is implementation-ready.

---

## Decision 5 — Per-Alias Fallback Chains

| Aspect | Planning (Master Routing v1.0) | Implemented |
|---|---|---|
| Opus fallback | 5 retries at 30s → Sonnet → GPT-5 → HALT | Global fallback to fallback_openai (gpt-5.4-mini) |
| Sonnet fallback | 3 retries at 30s → GPT-5 → Gemini Flash | Same global fallback |
| GPT-5 fallback | 3 retries at 15s → Gemini Flash | Same global fallback |
| Retry logic | Per-tier retry counts and wait intervals | No automatic retry |

**Why it changed:** The per-alias fallback cascade adds significant complexity. The current global fallback is simple, reliable, and sufficient for foundation-phase usage. Building cascaded retry before proving the need would be premature engineering.

**Future validity:** The planning doc's cascade logic is well-specified and ready for implementation. Priority should increase once multiple skills run concurrently and provider outages become a real operational concern.

---

## Decision 6 — Model Strings

| Aspect | Planning (Master Model v2.1) | Implemented |
|---|---|---|
| OpenAI flagship | gpt-5 ($1.25/$10) | gpt-5.4 ($1.75/$14) |
| OpenAI budget | gpt-5-mini ($0.25/$2) | gpt-5.4-mini ($0.15/$0.60) |
| OpenAI reasoning | o4-mini ($1.10/$4.40) | o3 ($10/$40) |
| Anthropic models | Same | Same |
| Google models | Same (gemini-2.5-pro, gemini-2.5-flash) | gemini-2.5-pro-preview-03-25 (preview string), gemini-2.5-flash |

**Why it changed:** OpenAI released GPT-5.4 after the planning docs were written. The o3 model was chosen for deep reasoning because o4-mini was not yet available at implementation time. Google's model string uses the preview suffix for the current API version.

**Future validity:** Model strings will continue to drift as providers release new versions. The routing config is the source of truth — update model strings there, not in planning docs.

---

## Decision 7 — Budget Limits

| Aspect | Planning (Master Routing v1.0) | Implemented |
|---|---|---|
| OpenAI budget | $20/month | $10.00 cumulative |
| Anthropic budget | $30/month | $10.00 cumulative |
| Google budget | $5/month | $10.00 cumulative |
| Total | $55/month | $30.00 cumulative |
| Reset cycle | Monthly (1st of each month) | Manual reset |
| Hard stop action | Pause and ask human | Route to fallback automatically |

**Why it changed:** The foundation phase has lower usage than the planning doc projected. Equal $10 budgets per provider simplify management. Manual reset is appropriate at current scale — automated monthly reset adds complexity without current need.

**Future validity:** As usage grows, the planning doc's differentiated budgets ($20/$30/$5) and monthly auto-reset are correct targets. The budget-config.yaml supports all these values — just change the numbers.

---

## Decision 8 — External Tools

| Aspect | Planning (External Tool Stack v1.0) | Implemented |
|---|---|---|
| Total tools | 16 | 16 (same list) |
| Active now | GitHub, Asana | GitHub, Asana |
| Framework | Described conceptually | Built — scripts/tools.py with credential validation, audit logging |
| Integration depth | Per-skill integrations in Phase 12 | Framework only — no deep integrations yet |

**Why it changed:** Minimal drift. The planning doc accurately predicted the activation timeline. The framework was built in Phase 10.5 as planned.

**Future validity:** The tool registry and activation timeline remain valid. Phase 12 tool integrations should follow the framework in tools.py.

---

## Decision 9 — Validation Check Count

| Aspect | Earlier State | Current |
|---|---|---|
| Phase 7 | 20 checks | — |
| Phase 8 (README written) | 25 checks | — |
| Phase 10.5 (current) | 31 checks | Current |

**What was added:** Asana validation (check 17), Google budget check (check 21), obs.py execution (check 26), graph patterns (check 27), additional skill system checks (28–31).

**Note:** The README was last updated in Phase 8 and still references "25 checks" and "5 aliases." This will be corrected in step 12.10.

---

## Decision 10 — Cost Tracking Method

| Aspect | Planning | Implemented |
|---|---|---|
| Cost tracking | Token-counted from API response | Flat estimated cost per call per alias |
| Pricing basis | Real API pricing | 2x real pricing (conservative buffer) |

**Why it changed:** Flat estimation is simpler to implement and sufficient for budget enforcement. Token-counted tracking requires parsing provider-specific response fields, which varies by provider.

**Future validity:** Token-proportional tracking is the correct long-term approach. It should be prioritized when monthly spend exceeds $50 and cost accuracy becomes operationally important.

---

## Summary Table

| Decision | Planning State | Implemented State | Status |
|---|---|---|---|
| Architecture path | NemoClaw/OpenShell | LangGraph + Direct API | Diverged — locked in Phase 6 |
| Alias naming | 7 tiered aliases | 9 provider-suffixed aliases | Diverged — simpler, more transparent |
| Task classes | 64 family-specific | 10 generic | Diverged — extensible when needed |
| Complexity classifier | Pre-call classifier | Not implemented | Deferred — valid future extension |
| Fallback chains | Per-alias with retry | Global fallback only | Deferred — valid future extension |
| Model strings | GPT-5, o4-mini | GPT-5.4, o3 | Drifted — models updated |
| Budget limits | $20/$30/$5 monthly | $10/$10/$10 cumulative manual | Adjusted for foundation phase |
| External tools | 16 tools | 16 tools (same) | Aligned |
| Validation checks | 25 (at README write time) | 31 | Grown — README not updated |
| Cost tracking | Token-counted | Flat estimate at 2x | Simplified — future upgrade target |

---

## How to Use This Document

- When reading planning docs, check this log first to see what actually shipped
- When planning future features, check the "Future validity" notes for each decision
- When updating the system, add a new decision entry if the change diverges from any planning doc
- This document should be updated alongside any architectural change

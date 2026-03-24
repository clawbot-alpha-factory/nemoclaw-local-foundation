# Budget System

> **Location:** `docs/architecture/budget-system.md`
> **Version:** 1.0
> **Date:** 2026-03-24
> **Phase:** 12 — Documentation Consolidation
> **Config source of truth:** `config/routing/budget-config.yaml`

---

## Purpose

This document explains how budget enforcement works in the NemoClaw local foundation. Every inference call passes through the budget system before execution. The system tracks cumulative spend per provider across sessions and enforces hard limits to prevent unbounded API costs.

---

## How Budget Enforcement Works

The budget enforcer runs before every inference call. The sequence is:

1. `budget-enforcer.py` receives a task class from the skill step
2. It resolves the task class to an alias and provider via `routing-config.yaml`
3. It reads cumulative spend from `provider-spend.json`
4. It checks: is the provider's spend below the hard stop threshold?
5. If yes → call proceeds, cost is logged, spend is updated
6. If at warning threshold (90%) → call proceeds but warning is printed and logged
7. If at hard stop (100%) → call is blocked, routed to fallback, event is logged

```
task_class → alias → provider
                       │
                       ▼
              Read provider-spend.json
                       │
                       ▼
              spend < hard_stop? ──No──► Route to fallback_openai
                       │                 Log to budget-audit.log
                      Yes
                       │
                       ▼
              spend >= warn (90%)? ──Yes──► Print warning, log warning
                       │
                      No
                       │
                       ▼
              Execute inference call
                       │
                       ▼
              Update provider-spend.json
              Append to provider-usage.jsonl
```

---

## Provider Budgets

Three providers, each with an independent budget. All values from `budget-config.yaml`.

| Provider | Budget | Warning Threshold | Hard Stop | Action at Hard Stop |
|---|---|---|---|---|
| Anthropic | $10.00 | 90% ($9.00) | 100% ($10.00) | Route to fallback, log event |
| OpenAI | $10.00 | 90% ($9.00) | 100% ($10.00) | Route to fallback, log event |
| Google | $10.00 | 90% ($9.00) | 100% ($10.00) | Route to fallback, log event |

**Total budget across all providers:** $30.00

**Current spend** (check anytime): `python3 scripts/budget-status.py`

---

## Budget Files

All budget-related files and their locations.

### Config File

| File | Location | Committed | Purpose |
|---|---|---|---|
| budget-config.yaml | config/routing/ | Yes | Budget limits, thresholds, log config |

### Runtime Files

| File | Location | Committed | Purpose |
|---|---|---|---|
| provider-spend.json | ~/.nemoclaw/logs/ | No | Cumulative spend per provider (JSON) |
| provider-usage.jsonl | ~/.nemoclaw/logs/ | No | Per-call usage log (JSONL append) |
| budget-audit.log | ~/.nemoclaw/logs/ | No | Threshold warnings and hard stop events |

---

## provider-spend.json

This is the cumulative spend tracker. It persists across sessions. The budget enforcer reads it before every call and writes it after every call.

**Structure:**

```json
{
  "anthropic": 0.626,
  "openai": 0.121,
  "google": 0.008
}
```

Each value is the total USD spent on that provider since the file was created or last reset.

**If this file is missing:** The budget enforcer creates a fresh one with all providers at $0.00. Previous spend history is lost.

**If this file is corrupt:** Delete it. The budget enforcer will recreate it. Use `provider-usage.jsonl` to reconstruct spend if needed.

---

## provider-usage.jsonl

This is the per-call audit trail. Every inference call appends one JSON line.

**Fields per line:**

| Field | Type | Description |
|---|---|---|
| timestamp | string | ISO 8601 timestamp |
| task_class | string | Task class from skill step |
| alias_selected | string | Resolved alias name |
| model_used | string | Actual model string |
| provider | string | Provider name |
| estimated_cost_usd | float | Estimated cost of this call |
| provider_cumulative_spend_usd | float | Provider total after this call |
| provider_budget_remaining_usd | float | Provider budget remaining after this call |
| provider_budget_pct_used | float | Percentage of provider budget used |
| fallback_used | boolean | Whether fallback was triggered |
| override | string/null | Any manual override applied |

**This file is append-only.** It is the reconstruction source if `provider-spend.json` is lost or corrupt.

---

## budget-audit.log

This is the threshold event log. Written only when something notable happens.

**Events logged:**

| Event | When | Severity |
|---|---|---|
| WARNING | Provider spend crosses 90% threshold | Warning |
| EXHAUSTED | Provider spend hits 100% — call blocked | Critical |
| FALLBACK | Call rerouted to fallback_openai due to budget exhaustion | Critical |

**Format:** Human-readable text with timestamps. Check with `tail -20 ~/.nemoclaw/logs/budget-audit.log`.

---

## Cost Estimation Method

The budget system uses **estimated cost per call**, not actual token-counted cost. Each alias in `routing-config.yaml` has an `estimated_cost_per_call` field.

These estimates are set at approximately **2x real pricing** as a conservative buffer. This means the system will report higher spend than actual API bills, and budget limits will be hit earlier than real spend would justify.

**Why 2x:** It is safer to underestimate remaining budget than to overestimate it. The 2x buffer ensures the system stops before actual provider billing limits are approached.

**Limitation:** Estimated cost per call is a flat value, not token-proportional. A call that uses 100 tokens and a call that uses 4000 tokens both log the same estimated cost for a given alias. This is a known approximation. Token-proportional tracking is a future extension candidate.

---

## Budget Status Commands

### Quick status

```bash
python3 scripts/budget-status.py
```

Shows all three providers with spend, budget, percentage, and visual bar.

**Example output:**

```
===========================================================
  NemoClaw Provider Budget Status
===========================================================
  ANTHROPIC  | $ 0.626 / $10.00 |   6.3% | █░░░░░░░░░░░░░░░░░░░ | active
  OPENAI     | $ 0.121 / $10.00 |   1.2% | ░░░░░░░░░░░░░░░░░░░░ | active
  GOOGLE     | $ 0.008 / $10.00 |   0.1% | ░░░░░░░░░░░░░░░░░░░░ | active
===========================================================
```

### Detailed spend history

```bash
tail -20 ~/.nemoclaw/logs/provider-usage.jsonl
```

### Audit events

```bash
tail -20 ~/.nemoclaw/logs/budget-audit.log
```

### Full observer (includes budget)

```bash
python3 scripts/obs.py
```

---

## Resetting Budgets

There is no automated monthly reset. Budgets reset when the spend file is manually reset.

### Full reset (all providers to $0)

```bash
echo '{"anthropic": 0, "openai": 0, "google": 0}' > ~/.nemoclaw/logs/provider-spend.json
```

### Reset one provider

Edit `~/.nemoclaw/logs/provider-spend.json` and set the provider's value to `0`.

### When to reset

- At the start of a new billing period
- After reviewing actual API bills and confirming tracked spend vs real spend
- After a deliberate decision to increase budget allocation

**Important:** Resetting spend does not delete the usage log. All historical calls remain in `provider-usage.jsonl`. You can always reconstruct past spend from this file.

---

## Changing Budget Limits

Edit `config/routing/budget-config.yaml` and change the `total_usd` value for the relevant provider.

```yaml
budgets:
  anthropic:
    total_usd: 20.00    # Changed from 10.00
```

The change takes effect on the next inference call — no restart required.

After changing limits, commit and push:

```bash
git add config/routing/budget-config.yaml
git commit -m "config: adjust anthropic budget to $20"
git push
```

---

## What Happens When a Budget Is Exhausted

1. The budget enforcer detects spend >= hard_stop threshold
2. The call is **not** sent to the original provider
3. The call is rerouted to `fallback_openai` (gpt-5.4-mini on OpenAI)
4. A log entry is written to `budget-audit.log` with the exhaustion event
5. A terminal message prints the exhaustion warning
6. The skill continues execution using the fallback model
7. All subsequent calls to the exhausted provider will also route to fallback until the budget is reset

**The system does not halt skill execution on budget exhaustion.** It degrades to the fallback model. This is a deliberate design choice — a running skill should not crash because one provider's budget ran out.

---

## Validation Checks

`validate.py` includes 5 budget-related checks:

| Check | What It Verifies |
|---|---|
| [18] provider-spend.json exists | Spend file is present and readable |
| [19] Anthropic budget < 100% | Anthropic has remaining budget |
| [20] OpenAI budget < 100% | OpenAI has remaining budget |
| [21] Google budget < 100% | Google has remaining budget |
| [22] provider-usage.jsonl writable | Usage log is writable |

If any budget check fails, investigate before running skills — calls may route to fallback unexpectedly.

---

## Known Limitations

| Limitation | Impact | Future Fix |
|---|---|---|
| Flat cost per call (not token-proportional) | Spend tracking is approximate | Token-counted cost from API response |
| No automated monthly reset | Manual reset required | Cron job or reset-day logic from budget-config |
| Single global fallback | All exhausted providers fall to same model | Per-provider fallback chains |
| No retry on API failure | Failed calls error immediately | Retry with backoff before fallback |
| 2x cost buffer is hardcoded per alias | Cannot adjust buffer globally | Global multiplier config option |

These are documented for transparency. The current system works correctly within these constraints.

---

## Config File Reference

**File:** `config/routing/budget-config.yaml`

```yaml
budgets:
  anthropic:
    total_usd: 10.00              # Maximum spend for this provider
    tracking: cumulative_across_sessions  # Spend persists between runs
    threshold_warn: 0.90          # Warning at 90%
    threshold_hard_stop: 1.00     # Hard stop at 100%
    warn_message: "..."           # Terminal warning text
    exhausted_message: "..."      # Terminal exhaustion text
    log_to_file: true             # Write to budget-audit.log
    log_to_terminal: true         # Print to terminal

log:
  path: ~/.nemoclaw/logs/provider-usage.jsonl
  fields: [timestamp, task_class, alias_selected, ...]
```

All three providers follow the same structure. See the full file at `config/routing/budget-config.yaml`.

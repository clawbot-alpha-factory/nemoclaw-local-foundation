# Validation System

> **Location:** `docs/architecture/validation-system.md`
> **Version:** 1.0
> **Date:** 2026-03-24
> **Phase:** 12 — Documentation Consolidation
> **Source of truth:** `scripts/validate.py`

---

## Purpose

This document explains the validation system that verifies the health of the NemoClaw local foundation. The validation script runs 31 checks across 6 categories, covering the entire stack from Docker to skill execution.

---

## When to Run Validation

Run `python3 scripts/validate.py` in these situations:

- After every Mac reboot (part of the cold start procedure)
- After every code or config change
- After every git commit (before push)
- After every phase completion
- Before running any skill
- When something seems wrong
- After upgrading any dependency

**Rule:** If validation does not show 31/31 passing, do not run skills or push code until the failure is diagnosed and fixed.

---

## How to Run

```bash
python3 scripts/validate.py
```

Note: `validate.py` runs on system python3, not `.venv312/bin/python`. It does not import LangGraph or langchain directly.

**Expected output when healthy:**

```
=======================================================
  NemoClaw Validation — 2026-03-24 12:45 UTC
=======================================================

Category 1 — Environment
  ✅ [01] Docker Desktop running
  ...

=======================================================
  Results: 31 passed  0 warnings  0 failed
=======================================================
```

---

## Check Reference — All 31 Checks

### Category 1 — Environment (5 checks)

These verify that the local MacBook environment has the required tooling.

| # | Check | What It Verifies | Pass Criteria | If It Fails |
|---|---|---|---|---|
| 01 | Docker Desktop running | Docker daemon is responsive | `docker info` succeeds | Launch Docker Desktop, wait 60s |
| 02 | Docker version >= 29.0 | Docker is recent enough | Version string >= 29.0 | Update Docker Desktop |
| 03 | Python version >= 3.11 | System python3 meets minimum | `python3 --version` >= 3.11 | Install via Homebrew |
| 04 | openshell in PATH | OpenShell CLI is available | `which openshell` succeeds | `source ~/.zshrc` |
| 05 | Node >= 20 | Node.js meets minimum | `node --version` >= 20 | `brew install node` |

### Category 2 — NemoClaw Runtime (5 checks)

These verify the NemoClaw/OpenShell sandbox is operational. The sandbox is retained but not required for inference.

| # | Check | What It Verifies | Pass Criteria | If It Fails |
|---|---|---|---|---|
| 06 | Gateway reachable | OpenShell gateway responds | HTTPS connection to 127.0.0.1:8080 | `nemoclaw start`, wait 30s |
| 07 | Sandbox nemoclaw-assistant Ready | Sandbox pod is running | Status shows Ready | `nemoclaw nemoclaw-assistant connect` |
| 08 | Inference provider = openai | Sandbox inference config correct | Provider is openai | `openshell inference set --provider openai --model gpt-4o-mini` |
| 09 | Inference model = gpt-4o-mini | Sandbox model config correct | Model is gpt-4o-mini | Same as above |
| 10 | openclaw.json writable | Sandbox config file has correct permissions | File is writable by sandbox user | `bash scripts/fix-sandbox-permissions.sh` |

**Note:** Checks 06–10 verify the sandbox, which is retained for reference but not used for skill inference. Skills use direct API calls. If the sandbox is intentionally stopped, these checks will fail — that is expected and acceptable if you are not using the sandbox.

### Category 3 — API Keys (7 checks)

These verify that all required API keys are present and, where possible, that they work.

| # | Check | What It Verifies | Pass Criteria | If It Fails |
|---|---|---|---|---|
| 11 | NGC_API_KEY present | NVIDIA NGC key in environment | Variable is set and non-empty | Check config/.env |
| 12 | ANTHROPIC_API_KEY present | Anthropic key in environment | Variable is set and non-empty | Check config/.env |
| 13 | OPENAI_API_KEY present | OpenAI key in environment | Variable is set and non-empty | Check config/.env |
| 14 | NVIDIA_INFERENCE_API_KEY present | NVIDIA inference key in environment | Variable is set and non-empty | Check config/.env |
| 15 | GOOGLE_API_KEY present | Google key in environment | Variable is set and non-empty | Check config/.env |
| 16 | ASANA_ACCESS_TOKEN present | Asana token in environment | Variable is set and non-empty | Check config/.env |
| 17 | Asana connection valid | Asana API responds to token | API call returns user data | Verify token at app.asana.com |

**Key loading:** Before running validation, environment variables must be loaded:
```bash
set -a && source config/.env && set +a
```

### Category 4 — Budget System (5 checks)

These verify the budget tracking infrastructure is intact.

| # | Check | What It Verifies | Pass Criteria | If It Fails |
|---|---|---|---|---|
| 18 | provider-spend.json exists | Spend tracker file present | File exists at ~/.nemoclaw/logs/ | Budget enforcer recreates on next run |
| 19 | Anthropic budget < 100% | Anthropic has remaining budget | Spend < $10.00 | Reset spend or increase budget |
| 20 | OpenAI budget < 100% | OpenAI has remaining budget | Spend < $10.00 | Reset spend or increase budget |
| 21 | Google budget < 100% | Google has remaining budget | Spend < $10.00 | Reset spend or increase budget |
| 22 | provider-usage.jsonl writable | Usage log can be written to | File exists and is writable | Check ~/.nemoclaw/logs/ directory permissions |

### Category 5 — Routing System (3 checks)

These verify that the routing system resolves task classes correctly.

| # | Check | What It Verifies | Pass Criteria | If It Fails |
|---|---|---|---|---|
| 23 | budget-enforcer.py runs | Enforcer script executes without error | Exit code 0 | Check script syntax, check config YAML |
| 24 | general_short → cheap_openai | Spot-check: general_short routes correctly | Resolves to cheap_openai alias | Check routing_rules in routing-config.yaml |
| 25 | complex_reasoning → reasoning_claude | Spot-check: complex_reasoning routes correctly | Resolves to reasoning_claude alias | Check routing_rules in routing-config.yaml |

**Note:** Only 2 of the 10 task classes are spot-checked. This catches config corruption but does not exhaustively verify all routes. If you change routing rules, manually verify the changed routes.

### Category 6 — Skill System (6 checks)

These verify that the skill execution infrastructure is ready.

| # | Check | What It Verifies | Pass Criteria | If It Fails |
|---|---|---|---|---|
| 26 | obs.py executes cleanly | Observer script runs without error | Exit code 0 | Check obs.py for syntax or runtime errors |
| 27 | LangGraph graph patterns validated | Phase 9 graph test harness passes | All 5 patterns pass | Run graph-validation/validate_graph.py for details |
| 28 | skill-runner.py exists | Execution engine is present | File exists at skills/skill-runner.py | Check if file was accidentally deleted or moved |
| 29 | research-brief/skill.yaml valid | Skill definition is parseable | YAML loads and has required fields | Check YAML syntax |
| 30 | research-brief/outputs/ writable | Artifact directory is usable | Directory exists and is writable | `mkdir -p skills/research-brief/outputs` |
| 31 | LangGraph checkpoint DB exists | Checkpoint database is present | File exists at ~/.nemoclaw/checkpoints/langgraph.db | Run any skill once to create it |

---

## Validation Output Format

Each check prints one line:

```
  ✅ [01] Docker Desktop running          # Pass
  ⚠️ [19] Anthropic budget < 100%        # Warning (if applicable)
  ❌ [06] Gateway reachable               # Fail
```

The summary line shows totals:

```
  Results: 31 passed  0 warnings  0 failed
```

---

## Validation Run History

Every validation run is logged to `~/.nemoclaw/logs/validation-runs.jsonl`. Each line records the timestamp, total passed, warnings, and failed counts.

Check recent history:

```bash
tail -5 ~/.nemoclaw/logs/validation-runs.jsonl
```

The observer (`obs.py`) also displays the last validation run result.

---

## Adding a New Validation Check

To add a new check to validate.py:

1. Identify which category it belongs to (1–6) or create a new category
2. Add the check function in validate.py under the appropriate category
3. Increment the expected total in the summary
4. Test that the check passes on a healthy system and fails correctly on an unhealthy one
5. Update this document with the new check number, description, and failure guidance
6. Commit both the script change and the doc update together

**Naming convention:** Checks are numbered sequentially across all categories. If adding check 32, it goes in the category that matches its purpose.

---

## Relationship to Other Observability Tools

| Tool | Purpose | Overlap with validate.py |
|---|---|---|
| validate.py | Point-in-time health check — binary pass/fail per check | Definitive system health |
| obs.py | Dashboard view — health, spend, recent runs, checkpoints, failures | Includes last validation result |
| budget-status.py | Budget-only view — spend bars per provider | Subset of what validate.py checks |

`validate.py` is the authoritative health check. `obs.py` and `budget-status.py` are operational dashboards. Run `validate.py` for verification; use the others for monitoring.

---

## Known Limitations

| Limitation | Impact | Future Fix |
|---|---|---|
| Only 2 of 10 routing rules spot-checked | Config corruption in other routes not caught | Exhaustive route validation |
| No live API reachability test | Key present ≠ key works (except Asana) | Lightweight ping per provider |
| Sandbox checks fail if sandbox intentionally stopped | False negatives for non-sandbox users | Conditional sandbox check category |
| No check for stale spend data | Spend file could be from months ago | Check last-modified timestamp |
| No check for config file consistency | routing-config.yaml could mismatch budget-config.yaml | Cross-config validation |

# Startup and Failure Point Map

> **Location:** `docs/troubleshooting/startup-and-failure-point-map.md`
> **Version:** 3.0
> **Date:** 2026-03-24
> **Phase:** 12 — Documentation Consolidation
> **Supersedes:** v2 (Phase 2 — NemoClaw/OpenShell-only failure points)

---

## Purpose

This document maps every known failure point in the NemoClaw local foundation, organized by the system layer where the failure occurs. It covers the current LangGraph + Direct API architecture and retains sandbox-specific failures as a reference section.

For cold-start recovery procedures, see `docs/setup/restart-recovery-runbook.md`.

---

## Quick Diagnostic

Run this first when something breaks:

```bash
python3 scripts/validate.py
```

If 31/31 passes, the system is healthy. If any check fails, find the failed check number below.

For a broader status view:

```bash
python3 scripts/obs.py
```

---

## Layer 1 — Environment Failures

### F1 — Docker Desktop Not Running

**Symptom:** validate.py check [01] fails. `docker info` returns socket error.

**Cause:** Docker Desktop does not auto-start at login.

**Fix:**
```bash
open -a Docker
# Wait 60 seconds
docker info --format "{{.ServerVersion}}"
```

### F2 — Python Version Wrong

**Symptom:** validate.py check [03] fails. `python3 --version` shows unexpected version.

**Cause:** New terminal session without sourcing zshrc, or Homebrew updated system Python.

**Fix:**
```bash
source ~/.zshrc
python3 --version
# If still wrong, check: /opt/homebrew/bin/python3.12 --version
```

### F3 — .venv313 Missing or Corrupt

**Symptom:** `.venv313/bin/python --version` fails or shows wrong version. Skill runs fail with import errors.

**Cause:** Venv deleted, corrupted by OS update, or created with wrong Python.

**Fix:**
```bash
rm -rf .venv313
/opt/homebrew/bin/python3.12 -m venv .venv313
.venv313/bin/pip install langgraph langgraph-checkpoint-sqlite langchain-openai langchain-anthropic pyyaml
```

### F4 — Node.js Missing

**Symptom:** validate.py check [05] fails.

**Fix:** `brew install node`

---

## Layer 2 — API Key Failures

### F5 — Environment Variables Not Loaded

**Symptom:** validate.py checks [11]–[16] fail. Scripts report missing keys.

**Cause:** `config/.env` not sourced in current terminal session.

**Fix:**
```bash
set -a && source config/.env && set +a
```

**Prevention:** Add this to your cold-start routine. See restart-recovery-runbook.md Section 1.4.

### F6 — API Key Invalid or Expired

**Symptom:** validate.py key presence checks pass but skill runs fail with 401/403 errors. Asana check [17] may fail specifically.

**Cause:** Key was revoked, expired, or copied incorrectly.

**Fix:** Regenerate the key from the provider's dashboard and update `config/.env`. See `docs/reference/config-reference.md` for the source URL of each key.

### F7 — .env File Missing

**Symptom:** All key checks fail. `cat config/.env` shows file not found.

**Cause:** File deleted, or repo cloned without running setup.

**Fix:**
```bash
cp config/.env.example config/.env
# Edit and add all 6 keys
```

---

## Layer 3 — Routing Failures

### F8 — Routing Config Syntax Error

**Symptom:** validate.py check [23] fails. budget-enforcer.py crashes with YAML parse error.

**Cause:** Invalid YAML in `config/routing/routing-config.yaml`.

**Fix:** Check YAML syntax. Common issues: wrong indentation, missing colon, tab characters.
```bash
python3 -c "import yaml; yaml.safe_load(open('config/routing/routing-config.yaml')); print('OK')"
```

### F9 — Task Class Not Found in Routing Rules

**Symptom:** Skill step fails with "unknown task class" error.

**Cause:** skill.yaml references a task_class that doesn't exist in routing_rules.

**Fix:** Add the missing task class to `routing_rules:` in `config/routing/routing-config.yaml`, or correct the task_class in the skill.yaml step.

### F10 — Wrong Model Routed

**Symptom:** Skill runs but uses unexpected model. Budget logs show wrong alias.

**Cause:** routing_rules maps the task class to a different alias than intended.

**Fix:** Check `config/routing/routing-config.yaml` routing_rules section. Verify the task class → alias → model chain.

---

## Layer 4 — Budget Failures

### F11 — Provider Budget Exhausted

**Symptom:** validate.py checks [19]–[21] fail. Skill steps route to fallback_openai unexpectedly. budget-audit.log shows EXHAUSTED event.

**Cause:** Cumulative spend reached $30 for that provider.

**Fix:** Reset the provider's spend:
```bash
# View current spend
python3 scripts/budget-status.py

# Reset all providers
echo '{"anthropic": 0, "openai": 0, "google": 0}' > ~/.nemoclaw/logs/provider-spend.json
```

### F12 — provider-spend.json Missing or Corrupt

**Symptom:** validate.py check [18] fails. Budget enforcer creates a fresh file on next run.

**Cause:** File deleted, or hard shutdown during write corrupted it.

**Fix:** Delete the corrupt file. Budget enforcer recreates it. Previous spend data is lost but can be reconstructed from `provider-usage.jsonl`:
```bash
rm ~/.nemoclaw/logs/provider-spend.json
python3 scripts/budget-enforcer.py --task-class general_short
# Fresh spend file created
```

### F13 — Usage Log Not Writable

**Symptom:** validate.py check [22] fails.

**Cause:** Directory permissions or disk full.

**Fix:**
```bash
mkdir -p ~/.nemoclaw/logs
touch ~/.nemoclaw/logs/provider-usage.jsonl
```

---

## Layer 5 — Skill Execution Failures

### F14 — skill.yaml Parse Error

**Symptom:** validate.py check [29] fails. skill-runner.py crashes on startup.

**Cause:** Invalid YAML syntax in the skill definition.

**Fix:**
```bash
python3 -c "import yaml; yaml.safe_load(open('skills/research-brief/skill.yaml')); print('OK')"
```

### F15 — Skill Output Directory Not Writable

**Symptom:** validate.py check [30] fails. Skill completes steps 1–4 but fails on step 5 (artifact write).

**Fix:**
```bash
mkdir -p skills/research-brief/outputs
```

### F16 — Checkpoint Database Missing

**Symptom:** validate.py check [31] fails. Resume (`--resume`) fails.

**Cause:** Database file deleted or never created.

**Fix:** Run any skill once to create it:
```bash
.venv313/bin/python skills/skill-runner.py \
  --skill research-brief \
  --input topic "checkpoint test" \
  --input depth brief
```

Or create the directory:
```bash
mkdir -p ~/.nemoclaw/checkpoints
```

### F17 — Skill Hangs During API Call

**Symptom:** Skill progress stops at a step. No output for 60+ seconds.

**Cause:** API timeout, network issue, or provider outage.

**Fix:** Ctrl+C to interrupt. Check network connectivity. Check provider status pages. Retry the skill. If the step was checkpointed before the hang, use `--resume`.

### F18 — LangGraph Import Error

**Symptom:** skill-runner.py crashes with `ModuleNotFoundError: No module named 'langgraph'`.

**Cause:** Running with system python3 instead of .venv313, or venv packages not installed.

**Fix:** Use the correct Python:
```bash
~/nemoclaw-local-foundation/.venv313/bin/python skills/skill-runner.py --skill ...
```

If packages are missing, reinstall:
```bash
.venv313/bin/pip install langgraph langgraph-checkpoint-sqlite langchain-openai langchain-anthropic pyyaml
```

---

## Layer 6 — Observability Failures

### F19 — obs.py Fails

**Symptom:** validate.py check [26] fails. obs.py crashes with an error.

**Cause:** Missing log files, corrupt spend JSON, or script syntax error after modification.

**Fix:** Check each data source obs.py reads:
```bash
# Spend file
python3 -c "import json; json.load(open('$HOME/.nemoclaw/logs/provider-spend.json')); print('OK')"

# Usage log
test -f ~/.nemoclaw/logs/provider-usage.jsonl && echo "OK" || echo "MISSING"

# Validation history
test -f ~/.nemoclaw/logs/validation-runs.jsonl && echo "OK" || echo "MISSING"
```

### F20 — Graph Validation Fails

**Symptom:** validate.py check [27] fails.

**Cause:** LangGraph upgrade broke a graph pattern, or validate_graph.py was modified incorrectly.

**Fix:**
```bash
~/nemoclaw-local-foundation/.venv313/bin/python \
  ~/nemoclaw-local-foundation/skills/graph-validation/validate_graph.py
```

Check which pattern failed. If LangGraph was upgraded, check release notes for breaking changes.

---

## Layer 7 — Sandbox Failures (Reference Only)

These failures apply only when the NemoClaw/OpenShell sandbox is running. The sandbox is not required for skill execution.

### F21 — Gateway Not Reachable

**Symptom:** validate.py check [06] fails. Connection refused at https://127.0.0.1:8080.

**Fix:**
```bash
nemoclaw start
# Wait 30 seconds
nemoclaw nemoclaw-assistant status
```

### F22 — Sandbox Not Running

**Symptom:** validate.py check [07] fails.

**Fix:**
```bash
nemoclaw nemoclaw-assistant connect
# If missing entirely:
nemoclaw onboard
```

### F23 — openclaw.json Permission Reset

**Symptom:** validate.py check [10] fails. Agent shows wrong model in TUI.

**Cause:** After sandbox restart, OpenShell resets file to root ownership.

**Fix:**
```bash
bash scripts/fix-sandbox-permissions.sh
```

This must be reapplied after every sandbox restart, Mac restart, or `nemoclaw onboard`.

### F24 — openshell Not in PATH

**Symptom:** validate.py check [04] fails. `which openshell` returns nothing.

**Fix:** `source ~/.zshrc`

### F25 — NGC Authentication Failed

**Symptom:** Docker pull from nvcr.io fails with authentication error.

**Fix:**
```bash
grep NGC_API_KEY ~/nemoclaw-local-foundation/config/.env | cut -d= -f2 | docker login nvcr.io --username \$oauthtoken --password-stdin
```

---

## Failure Quick Reference

| # | Failure | Layer | Severity | Fix Summary |
|---|---|---|---|---|
| F1 | Docker not running | Environment | Blocking | `open -a Docker` |
| F2 | Python version wrong | Environment | Blocking | `source ~/.zshrc` |
| F3 | .venv313 missing | Environment | Blocking | Recreate venv |
| F4 | Node.js missing | Environment | Warning | `brew install node` |
| F5 | Env vars not loaded | API Keys | Blocking | Source config/.env |
| F6 | API key invalid | API Keys | Blocking | Regenerate from provider |
| F7 | .env file missing | API Keys | Blocking | Copy from .env.example |
| F8 | Routing config syntax | Routing | Blocking | Fix YAML |
| F9 | Unknown task class | Routing | Blocking | Add to routing_rules |
| F10 | Wrong model routed | Routing | Degraded | Check routing_rules |
| F11 | Budget exhausted | Budget | Degraded | Reset spend file |
| F12 | Spend file corrupt | Budget | Warning | Delete, let recreate |
| F13 | Usage log not writable | Budget | Warning | Fix permissions |
| F14 | skill.yaml parse error | Skills | Blocking | Fix YAML |
| F15 | Output dir not writable | Skills | Blocking | mkdir outputs |
| F16 | Checkpoint DB missing | Skills | Warning | Run any skill once |
| F17 | Skill hangs on API | Skills | Recoverable | Ctrl+C, retry |
| F18 | LangGraph import error | Skills | Blocking | Use .venv313 python |
| F19 | obs.py fails | Observability | Warning | Check data sources |
| F20 | Graph validation fails | Observability | Warning | Check LangGraph version |
| F21–F25 | Sandbox failures | Sandbox (ref) | Non-blocking | See sandbox section |

**Severity levels:**

- **Blocking:** Must fix before running skills
- **Degraded:** System works but at reduced quality (e.g., fallback model)
- **Warning:** Non-critical — system functions but with a gap
- **Recoverable:** Fix mid-session without restart
- **Non-blocking:** Sandbox-only, does not affect skill execution

# Restart and Recovery Runbook

> **Location:** `docs/setup/restart-recovery-runbook.md`
> **Phase:** 11
> **Last validated:** 2026-03-24
> **System:** NemoClaw local foundation on MacBook Apple Silicon M1 / macOS Sequoia

---

## 1 — Cold Start After Mac Reboot

Run these steps in order after a full Mac reboot or cold power-on.

### 1.1 Open Terminal

Open Terminal.app (or your preferred terminal). All commands assume `zsh`.

### 1.2 Navigate to repo root

```bash
cd ~/nemoclaw-local-foundation
```

### 1.3 Activate the Python 3.12 virtual environment

```bash
source .venv313/bin/activate
```

Verify:

```bash
python --version
```

**Expected:** `Python 3.12.13`

If the output shows any other version (especially 3.14.x), stop. The venv is not activated correctly. Re-run the `source` command and confirm the prompt prefix shows `(.venv313)`.

### 1.4 Verify environment variables load

```bash
set -a && source config/.env && set +a
```

Quick check that keys are present (prints key names only, not values):

```bash
env | grep -E '^(OPENAI_API_KEY|ANTHROPIC_API_KEY|GOOGLE_API_KEY|NGC_API_KEY|NVIDIA_INFERENCE_API_KEY|ASANA_ACCESS_TOKEN)=' | cut -d= -f1 | sort
```

**Expected output (6 lines):**

```
ANTHROPIC_API_KEY
ASANA_ACCESS_TOKEN
GOOGLE_API_KEY
NGC_API_KEY
NVIDIA_INFERENCE_API_KEY
OPENAI_API_KEY
```

If any key is missing, check `config/.env` for typos or missing entries. Compare against `config/.env.example`.

### 1.5 Start Docker / Colima (if using NemoClaw sandbox)

If you are running the NemoClaw/OpenShell sandbox (not required for direct-API inference):

```bash
# If using Colima:
colima start

# If using Docker Desktop:
# Launch Docker Desktop from Applications, wait for the whale icon to show "running"
```

Verify Docker is responsive:

```bash
docker info > /dev/null 2>&1 && echo "Docker OK" || echo "Docker NOT running"
```

### 1.6 Start the NemoClaw sandbox (if applicable)

Only if you need the OpenShell sandbox for this session:

```bash
docker start openshell-cluster-nemoclaw
```

Wait 10–15 seconds, then verify:

```bash
docker ps --filter name=openshell-cluster-nemoclaw --format '{{.Status}}'
```

**Expected:** `Up ...` with a recent timestamp.

### 1.7 Fix sandbox permissions (required after every sandbox restart)

```bash
bash scripts/fix-sandbox-permissions.sh
```

This fixes the known issue where `openclaw.json` resets to root ownership after sandbox restart.

---

## 2 — Service Verification Order

After cold start, verify services in this exact order. Each step depends on the previous one passing.

| Step | Check | Command | Pass Criteria |
|------|-------|---------|---------------|
| 2.1 | Python venv | `python --version` | `Python 3.12.13` |
| 2.2 | Env vars loaded | `echo $ANTHROPIC_API_KEY \| head -c4` | Prints first 4 chars (not empty) |
| 2.3 | Docker (if needed) | `docker info > /dev/null 2>&1 && echo OK` | `OK` |
| 2.4 | Sandbox (if needed) | `docker ps --filter name=openshell-cluster-nemoclaw` | Shows `Up` |
| 2.5 | Permissions (if sandbox) | `bash scripts/fix-sandbox-permissions.sh` | Exits 0 |
| 2.6 | Full validation | `python3 scripts/validate.py` | `31/31 passing` |
| 2.7 | Observer | `python3 scripts/obs.py` | No critical errors |
| 2.8 | Budget status | `python3 scripts/budget-status.py` | Shows 3 providers, no over-budget |

**Rule:** If step 2.6 does not show 31/31, do NOT proceed to any skill runs or workflow resumes. Diagnose first using Section 5.

---

## 3 — Environment Verification (Deep Check)

Use this section when the quick checks in Section 2 pass but something still feels wrong, or after any system update.

### 3.1 Python 3.12 venv integrity

```bash
# Confirm venv python path
which python
# Expected: ~/nemoclaw-local-foundation/.venv313/bin/python

# Confirm pip is venv-local
which pip
# Expected: ~/nemoclaw-local-foundation/.venv313/bin/pip

# Confirm key packages
python -c "import langchain; print('langchain', langchain.__version__)"
python -c "import langgraph; print('langgraph', langgraph.__version__)"
python -c "import anthropic; print('anthropic OK')"
python -c "import openai; print('openai OK')"
python -c "import google.generativeai; print('google OK')"
```

If any import fails, reinstall from requirements:

```bash
pip install -r requirements.txt
```

### 3.2 API key validation

Run the full validation suite which includes live API reachability checks:

```bash
python3 scripts/validate.py
```

Check specifically for any `API_KEY` or `REACHABILITY` failures in the output.

### 3.3 Budget files

```bash
# Spend tracker exists and is valid JSON
python3 -c "import json; json.load(open('$HOME/.nemoclaw/logs/provider-spend.json')); print('spend OK')"

# Usage log exists
test -f ~/.nemoclaw/logs/provider-usage.jsonl && echo "usage log OK" || echo "usage log MISSING"

# Budget audit log exists
test -f ~/.nemoclaw/logs/budget-audit.log && echo "budget audit OK" || echo "budget audit MISSING"
```

If `provider-spend.json` is missing or corrupt, the budget enforcer will create a fresh one on next run. Previous spend history will be lost — check `provider-usage.jsonl` to reconstruct if needed.

### 3.4 Checkpoint database

```bash
# SQLite DB exists and is readable
python3 -c "
import sqlite3
conn = sqlite3.connect('$HOME/.nemoclaw/checkpoints/langgraph.db')
tables = conn.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall()
print(f'Checkpoint DB OK — {len(tables)} tables')
conn.close()
"
```

If the DB is corrupt or missing, LangGraph will create a new one. Any in-progress workflow state from before the corruption will be lost.

### 3.5 Routing config

```bash
# Routing config is valid YAML
python3 -c "
import yaml
with open('config/routing/routing-config.yaml') as f:
    cfg = yaml.safe_load(f)
print(f'Routing OK — {len(cfg.get(\"aliases\", cfg.get(\"models\", {})))} aliases')
"

# Budget config is valid YAML
python3 -c "
import yaml
with open('config/routing/budget-config.yaml') as f:
    cfg = yaml.safe_load(f)
print(f'Budget config OK')
"
```

---

## 4 — Permission Reset Steps

### When to run

Run `fix-sandbox-permissions.sh` whenever:

- The NemoClaw sandbox container has been restarted
- You see permission-denied errors accessing `openclaw.json`
- After any Docker/Colima restart
- After a Mac reboot (if using the sandbox)

### How to run

```bash
bash ~/nemoclaw-local-foundation/scripts/fix-sandbox-permissions.sh
```

### What it does

Fixes ownership of `openclaw.json` inside the sandbox container, which reverts to root after container restart. This is a known upstream issue.

### Verification after running

```bash
python3 scripts/validate.py 2>&1 | grep -i "permission\|sandbox\|openclaw"
```

No permission errors should appear.

---

## 5 — Log Verification

After a restart, inspect logs for anomalies before resuming work.

### 5.1 Provider spend log

```bash
cat ~/.nemoclaw/logs/provider-spend.json | python3 -m json.tool
```

**Check for:** Reasonable cumulative totals. If totals look wrong (e.g., negative values, nulls), the file may have been corrupted during a hard shutdown.

### 5.2 Provider usage log (recent entries)

```bash
tail -5 ~/.nemoclaw/logs/provider-usage.jsonl
```

**Check for:** Last entry timestamp. If it's from before the restart, that's expected. If entries appear with timestamps during the shutdown, something wrote to the log unexpectedly.

### 5.3 Budget audit log

```bash
tail -20 ~/.nemoclaw/logs/budget-audit.log
```

**Check for:** Any `THRESHOLD` or `EXCEEDED` warnings. These indicate a provider was approaching or hit its budget limit before shutdown.

### 5.4 Tools audit log

```bash
tail -10 ~/.nemoclaw/logs/tools-audit.log
```

**Check for:** Any failed tool calls from the last session that may need retry.

### 5.5 Validation run history

```bash
tail -3 ~/.nemoclaw/logs/validation-runs.jsonl
```

**Check for:** Last run result. If the last run before shutdown was not 31/31, investigate what was failing before proceeding.

---

## 6 — Recovery Checks

### 6.1 Detect paused workflows

Check the LangGraph checkpoint database for incomplete runs:

```bash
python3 -c "
import sqlite3, json

db_path = '$HOME/.nemoclaw/checkpoints/langgraph.db'
try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    # List tables to understand schema
    tables = cursor.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall()
    table_names = [t[0] for t in tables]
    print(f'Tables: {table_names}')

    # Look for checkpoints (schema may vary by LangGraph version)
    for t in table_names:
        count = cursor.execute(f'SELECT COUNT(*) FROM \"{t}\"').fetchone()[0]
        print(f'  {t}: {count} rows')
    conn.close()
except Exception as e:
    print(f'Error reading checkpoint DB: {e}')
"
```

If rows exist in checkpoint tables, there may be paused or incomplete workflows.

### 6.2 Diagnose failed workflows

If a skill run was interrupted mid-execution (e.g., by a crash or reboot):

1. Check the tools audit log for the last action taken:
   ```bash
   grep "research-brief" ~/.nemoclaw/logs/tools-audit.log | tail -5
   ```

2. Check provider usage for the last API call:
   ```bash
   tail -10 ~/.nemoclaw/logs/provider-usage.jsonl
   ```

3. Determine whether the workflow reached a safe stopping point or was interrupted mid-API-call.

### 6.3 Assess whether to resume or restart a workflow

**Resume if:**
- The checkpoint DB shows a valid checkpoint for the workflow
- The last completed step was a natural graph node boundary
- No API call was left hanging (check usage log timestamps)

**Restart from scratch if:**
- The checkpoint DB is empty or corrupt
- The workflow was interrupted during an API call (partial response risk)
- You are unsure what state the workflow is in

When in doubt, restart from scratch. A clean re-run is safer than resuming from uncertain state.

---

## 7 — Safe Resume Procedure

### 7.1 Pre-resume checklist

Before resuming any workflow or running any skill, confirm ALL of the following:

- [ ] Python 3.12 venv is active (`python --version` → `3.12.13`)
- [ ] Env vars are loaded (Section 1.4)
- [ ] `validate.py` shows 31/31
- [ ] `obs.py` shows no critical errors
- [ ] `budget-status.py` shows no over-budget providers
- [ ] Logs reviewed (Section 5) — no anomalies
- [ ] If using sandbox: permissions fixed (Section 4)

### 7.2 Resume a paused skill run

```bash
~/nemoclaw-local-foundation/.venv313/bin/python \
  ~/nemoclaw-local-foundation/skills/skill-runner.py \
  --skill research-brief \
  --input topic "your topic" \
  --input depth standard \
  --resume
```

> **Note:** The `--resume` flag tells skill-runner to check for an existing checkpoint. If no checkpoint exists, it starts fresh. Check skill-runner.py for current flag support — if `--resume` is not implemented, start a fresh run instead.

### 7.3 Start a fresh skill run (safe default)

```bash
~/nemoclaw-local-foundation/.venv313/bin/python \
  ~/nemoclaw-local-foundation/skills/skill-runner.py \
  --skill research-brief \
  --input topic "your topic" \
  --input depth standard
```

### 7.4 Post-run verification

After any skill run completes:

```bash
# Check budget hasn't been exceeded
python3 scripts/budget-status.py

# Check for errors in recent tool calls
tail -5 ~/.nemoclaw/logs/tools-audit.log

# Re-run validation to confirm system is still healthy
python3 scripts/validate.py
```

---

## 8 — Quick Reference Card

Copy this to a sticky note or keep it open in a tab.

```
=== NemoClaw Cold Start (after reboot) ===

cd ~/nemoclaw-local-foundation
source .venv313/bin/activate
set -a && source config/.env && set +a
python --version                        # Must be 3.12.13
python3 scripts/validate.py             # Must be 31/31
python3 scripts/obs.py                  # No critical errors
python3 scripts/budget-status.py        # No over-budget

# If using sandbox:
colima start                            # or Docker Desktop
docker start openshell-cluster-nemoclaw
bash scripts/fix-sandbox-permissions.sh

# Then safe to run skills
```

---

## 9 — Failure Quick Reference

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| `python --version` shows 3.14.x | Venv not activated | `source .venv313/bin/activate` |
| `validate.py` shows < 31 | Env vars not loaded or API key expired | Re-source `.env`, check key validity |
| Permission denied on `openclaw.json` | Sandbox restart reset ownership | `bash scripts/fix-sandbox-permissions.sh` |
| `docker: command not found` | Colima/Docker not started | `colima start` or launch Docker Desktop |
| `provider-spend.json` corrupt | Hard shutdown during write | Delete file; budget enforcer recreates it. Reconstruct from `provider-usage.jsonl` if needed |
| Checkpoint DB errors | Corrupt SQLite after crash | Delete `~/.nemoclaw/checkpoints/langgraph.db`; LangGraph recreates. In-progress state is lost |
| Budget shows over-limit | Spend accumulated before restart | Review `budget-config.yaml` limits; reset spend file if appropriate for new billing period |
| Skill run hangs | API timeout or network issue | Ctrl+C, check logs, retry |

---

## 10 — End-to-End Test Procedure

Use this procedure to validate the runbook itself after writing or updating it.

### Test steps

1. **Save all work and commit.** Ensure no uncommitted changes will be lost.

2. **Close Terminal completely.** This simulates loss of shell state.

3. **Optionally restart Mac** for a true cold-start test. If not restarting, at minimum open a fresh Terminal window with no inherited environment.

4. **Follow Sections 1 through 5 exactly as written.** Do not skip steps or rely on memory.

5. **Run a validation cycle:**
   ```bash
   python3 scripts/validate.py
   ```
   Confirm 31/31.

6. **Run a live skill to confirm inference works:**
   ```bash
   ~/nemoclaw-local-foundation/.venv313/bin/python \
     ~/nemoclaw-local-foundation/skills/skill-runner.py \
     --skill research-brief \
     --input topic "restart test" \
     --input depth standard
   ```
   Confirm it completes without error.

7. **Check budget status after the test run:**
   ```bash
   python3 scripts/budget-status.py
   ```

8. **Record the test result** by updating the "Last validated" date at the top of this file.

### Pass criteria

- All Section 2 checks pass
- `validate.py` returns 31/31
- A live skill run completes successfully
- Budget status shows no anomalies
- No permission errors encountered

### If the test fails

Document what failed, at which step, and update this runbook with the fix before committing.

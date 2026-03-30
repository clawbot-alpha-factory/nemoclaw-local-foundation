# Local Environment Setup

> **Location:** `docs/setup/local-environment-setup.md`
> **Version:** 3.0
> **Date:** 2026-03-24
> **Phase:** 12 — Documentation Consolidation
> **Target:** MacBook Apple Silicon M1, 16GB RAM, macOS 15+ Sequoia

---

## Prerequisites

| Requirement | Version | Check Command | Install |
|---|---|---|---|
| macOS | 15+ Apple Silicon | `sw_vers` | — |
| Docker Desktop | >= 29.0 | `docker --version` | docker.com/products/docker-desktop |
| Homebrew | any | `brew --version` | brew.sh |
| Python 3.12 | 3.12.x | `/opt/homebrew/bin/python3.12 --version` | `brew install python@3.12` |
| Node.js | >= 20 | `node --version` | `brew install node` |
| Git | any | `git --version` | `brew install git` |

**Critical:** Python 3.14 (current Homebrew default) has Pydantic V1 compatibility issues with LangGraph. You must use Python 3.12 for the virtual environment.

---

## Step 1 — Install Python 3.12

```bash
brew install python@3.12
/opt/homebrew/bin/python3.12 --version
# Expected: Python 3.12.x
```

---

## Step 2 — Clone the Repo

```bash
git clone https://github.com/clawbot-alpha-factory/nemoclaw-local-foundation.git
cd nemoclaw-local-foundation
```

---

## Step 3 — Configure API Keys

```bash
cp config/.env.example config/.env
```

Edit `config/.env` and populate all 6 keys:

```
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key
GOOGLE_API_KEY=your_google_key
NGC_API_KEY=your_ngc_key
NVIDIA_INFERENCE_API_KEY=your_nvidia_inference_key
ASANA_ACCESS_TOKEN=your_asana_token
```

**Where to get each key:**

| Key | Source |
|---|---|
| OPENAI_API_KEY | platform.openai.com → API keys |
| ANTHROPIC_API_KEY | console.anthropic.com → API keys |
| GOOGLE_API_KEY | ai.google.dev → Get API key |
| NGC_API_KEY | ngc.nvidia.com → Setup → Generate API Key |
| NVIDIA_INFERENCE_API_KEY | Same NGC console, inference-specific key |
| ASANA_ACCESS_TOKEN | app.asana.com/0/developer-console → Personal access tokens |

**Never commit config/.env** — it is gitignored.

---

## Step 4 — Create Python 3.12 Virtual Environment

```bash
/opt/homebrew/bin/python3.12 -m venv .venv313
.venv313/bin/pip install --upgrade pip
.venv313/bin/pip install langgraph langgraph-checkpoint-sqlite langchain-openai langchain-anthropic pyyaml
```

Verify:

```bash
.venv313/bin/python --version
# Expected: Python 3.12.x

.venv313/bin/python -c "import langgraph, langchain_openai, langchain_anthropic, yaml; print('OK')"
# Expected: OK — no Pydantic warnings
```

**.venv313/ is gitignored** — recreate on each new machine using this step.

---

## Step 5 — Create Log and Checkpoint Directories

```bash
mkdir -p ~/.nemoclaw/logs
mkdir -p ~/.nemoclaw/checkpoints
```

These directories store runtime data (spend tracking, usage logs, checkpoints) outside the repo.

---

## Step 6 — Start Docker Desktop

Docker Desktop must be running before validation (checks [01]–[02] and [06]–[10] require it).

```bash
open -a Docker
# Wait 60 seconds for Docker to fully start
docker info --format "{{.ServerVersion}}"
# Expected: 29.x.x
```

---

## Step 7 — Start NemoClaw Sandbox (Optional)

The LangGraph + Direct API architecture does not require the OpenShell sandbox for inference. The sandbox is retained for reference and verified by validation checks [06]–[10].

If you want the sandbox running:

```bash
source ~/.zshrc
which openshell
nemoclaw start
# Wait 30 seconds
nemoclaw nemoclaw-assistant status
```

After sandbox start, fix permissions:

```bash
bash scripts/fix-sandbox-permissions.sh
```

---

## Step 8 — Load Environment and Validate

```bash
set -a && source config/.env && set +a
python3 scripts/validate.py
# Expected: 31 passed, 0 warnings, 0 failed
```

If any checks fail, see `docs/architecture/validation-system.md` for per-check failure guidance.

---

## Step 9 — Run a Skill (Verification)

```bash
.venv313/bin/python skills/skill-runner.py \
  --skill research-brief \
  --input topic "setup test" \
  --input depth brief
```

This confirms inference, routing, budget enforcement, checkpointing, and artifact writing all work end-to-end.

---

## Step 10 — Check System Status

```bash
python3 scripts/obs.py          # Full health dashboard
python3 scripts/budget-status.py # Budget summary
python3 scripts/tools.py         # External tool status
```

---

## Python Runtime Rules

| Context | Python to Use | Why |
|---|---|---|
| Skill execution (skill-runner.py) | .venv313/bin/python | Imports LangGraph, langchain |
| Graph validation (validate_graph.py) | .venv313/bin/python | Imports LangGraph |
| validate.py | python3 (system) | No LangGraph imports |
| obs.py | python3 (system) | No LangGraph imports |
| budget-enforcer.py | python3 (system) | No LangGraph imports |
| budget-status.py | python3 (system) | No LangGraph imports |
| tools.py | python3 (system) | No LangGraph imports |

**Rule:** Only scripts that import LangGraph or langchain require .venv313. All other scripts use system python3.

---

## Environment Notes

| Item | Location | Committed | Notes |
|---|---|---|---|
| .venv313/ | Repo root | No (gitignored) | Recreate per machine via Step 4 |
| config/.env | config/ | No (gitignored) | Never commit API keys |
| config/.env.example | config/ | Yes | Template with placeholder values |
| skills/*/outputs/ | Per skill | No (gitignored) | Artifacts are local only |
| ~/.nemoclaw/logs/ | Home directory | No (not in repo) | Runtime logs and spend tracking |
| ~/.nemoclaw/checkpoints/ | Home directory | No (not in repo) | LangGraph checkpoint database |

---

## Dependency Version Pins

| Package | Required Version | Risk if Wrong |
|---|---|---|
| Python | 3.12.x | 3.14 breaks Pydantic V1 compatibility with LangGraph |
| LangGraph | latest (1.1.3 at time of writing) | Check for breaking changes on upgrade |
| langchain-core | latest | Monitor Python 3.14 support announcements |
| langchain-openai | latest | Must support gpt-5.4 model strings |
| langchain-anthropic | latest | Must support claude-sonnet-4-6 model strings |
| pyyaml | latest | Stable — low risk |
| Docker Desktop | >= 29.0 | Older versions may not support required container features |
| Node.js | >= 20 | Required by validation check [05] |

**After upgrading any dependency:**

1. Run `python3 scripts/validate.py` — confirm 31/31
2. Run `.venv313/bin/python skills/graph-validation/validate_graph.py` — confirm 5/5 patterns
3. Run a test skill to confirm end-to-end inference works

---

## Troubleshooting Setup Issues

| Symptom | Cause | Fix |
|---|---|---|
| `python3 --version` shows 3.9.6 | New terminal without sourcing zshrc | `source ~/.zshrc` |
| `.venv313/bin/python --version` shows wrong version | Venv created with wrong Python | Delete .venv313/, recreate with `/opt/homebrew/bin/python3.12 -m venv .venv313` |
| `import langgraph` fails | Packages not installed in venv | Run Step 4 pip install command |
| validate.py shows < 31 passing | Env vars not loaded | `set -a && source config/.env && set +a` |
| Docker checks fail | Docker Desktop not running | `open -a Docker`, wait 60s |
| Asana check fails | Token expired or invalid | Regenerate at app.asana.com/0/developer-console |
| Sandbox checks fail | Sandbox not started | Run Step 7, or accept these failures if not using sandbox |

For detailed failure guidance, see `docs/troubleshooting/startup-and-failure-point-map.md` and `docs/setup/restart-recovery-runbook.md`.

---

## Post-Setup Verification Checklist

After completing all steps, confirm:

- [ ] `python3 scripts/validate.py` → 31 passed, 0 failed
- [ ] `python3 scripts/obs.py` → No critical errors
- [ ] `python3 scripts/budget-status.py` → 3 providers showing, none over budget
- [ ] Skill test run completed with artifact output
- [ ] `.venv313/bin/python --version` → Python 3.12.13

If all boxes are checked, the environment is ready.

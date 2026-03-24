# Local Environment Setup

**Version:** v2.0 — Updated 2026-03-23  
**Phase:** 8 — Architecture Lock  
**Target:** MacBook Apple Silicon, macOS 15+  

---

## Prerequisites

| Requirement | Version | Check Command |
|---|---|---|
| macOS | 15+ Apple Silicon | `sw_vers` |
| Docker Desktop | >= 29.0 | `docker --version` |
| Homebrew | any | `brew --version` |
| Python 3.12 | 3.12.x | `/opt/homebrew/bin/python3.12 --version` |
| Node.js | >= 20 | `node --version` |
| Git | any | `git --version` |

---

## Step 1 — Install Python 3.12

Python 3.12 is required. Python 3.14 (Homebrew default) has Pydantic V1 compatibility issues with LangGraph.

    brew install python@3.12
    /opt/homebrew/bin/python3.12 --version
    # Expected: Python 3.12.x

---

## Step 2 — Clone the Repo

    git clone https://github.com/clawbot-alpha-factory/nemoclaw-local-foundation.git
    cd nemoclaw-local-foundation

---

## Step 3 — Configure API Keys

    cp config/.env.example config/.env

Edit config/.env and populate all four keys:

    NGC_API_KEY=your_ngc_key
    ANTHROPIC_API_KEY=your_anthropic_key
    OPENAI_API_KEY=your_openai_key
    NVIDIA_INFERENCE_API_KEY=your_nvidia_key

Never commit config/.env — it is gitignored.

---

## Step 4 — Create Python 3.12 Virtual Environment

    /opt/homebrew/bin/python3.12 -m venv .venv312
    .venv312/bin/pip install --upgrade pip
    .venv312/bin/pip install langgraph langgraph-checkpoint-sqlite langchain-openai langchain-anthropic pyyaml

Verify:

    .venv312/bin/python --version
    # Expected: Python 3.12.x

    .venv312/bin/python -c "import langgraph, langchain_openai, langchain_anthropic, yaml; print('OK')"
    # Expected: OK — no Pydantic warnings

---

## Step 5 — Start Docker Desktop

Docker Desktop must be running before any NemoClaw or OpenShell commands.

    open -a Docker
    # Wait 60 seconds
    docker info --format "{{.ServerVersion}}"
    # Expected: 29.x.x

---

## Step 6 — Start OpenShell Gateway (if using NemoClaw sandbox)

Note: The LangGraph + Direct API architecture does not require the OpenShell sandbox for inference.
OpenShell is retained for reference only.

    source ~/.zshrc
    which openshell
    nemoclaw start
    nemoclaw nemoclaw-assistant status

---

## Step 7 — Validate the System

    python3 scripts/validate.py
    # Expected: 25 passed, 0 warnings, 0 failed

---

## Step 8 — Run a Skill

    .venv312/bin/python skills/skill-runner.py \
      --skill research-brief \
      --input topic "test topic" \
      --input depth brief

---

## Python Runtime Rules

| Context | Python to Use |
|---|---|
| Skill execution | .venv312/bin/python |
| validate.py | python3 (system — no LangGraph imports) |
| budget-status.py | python3 (system — no LangGraph imports) |
| budget-enforcer.py | python3 (system — no LangGraph imports) |

Only scripts that import LangGraph, langchain-openai, or langchain-anthropic require .venv312.

---

## Environment Notes

- .venv312/ is gitignored — recreate on each new machine using Step 4
- config/.env is gitignored — never commit API keys
- skills/research-brief/outputs/ is gitignored — artifacts are local only
- ~/.nemoclaw/checkpoints/langgraph.db — LangGraph checkpoint database, not in repo

---

## Compatibility Notes

| Package | Required Version | Risk |
|---|---|---|
| Python | 3.12.x | Python 3.14 breaks Pydantic V1 compatibility with LangGraph |
| LangGraph | latest | Check for breaking changes on upgrade |
| langchain-core | latest | Monitor Python 3.14 support announcements |
| Pydantic | V2 only | V1 not supported on Python 3.14+ |

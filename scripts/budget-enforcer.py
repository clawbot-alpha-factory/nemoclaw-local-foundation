#!/usr/bin/env python3
"""
NemoClaw Budget Enforcer v2
Atomic writes, hash verification, full enforcement, provider logging.
Doc 15 — Model Routing System Spec v3
"""

import json, os, sys, argparse, tempfile, hashlib
from datetime import datetime, timezone

BASE_DIR   = os.path.expanduser("~/nemoclaw-local-foundation")
SPEND_FILE = os.path.expanduser("~/.nemoclaw/logs/provider-spend.json")
USAGE_LOG  = os.path.expanduser("~/.nemoclaw/logs/provider-usage.jsonl")
AUDIT_LOG  = os.path.expanduser("~/.nemoclaw/logs/budget-audit.log")

COST_ESTIMATES = {
    "cheap_openai":     0.001,
    "reasoning_claude": 0.050,
    "vision_openai":    0.020,
    "fallback_openai":  0.030,
}

ROUTING_RULES = {
    "complex_reasoning": "reasoning_claude",
    "long_document":     "reasoning_claude",
    "code":              "reasoning_claude",
    "agentic":           "reasoning_claude",
    "vision":            "vision_openai",
    "structured_short":  "cheap_openai",
    "general_short":     "cheap_openai",
}
DEFAULT_ALIAS = "cheap_openai"

ALIAS_PROVIDER = {
    "cheap_openai":     "openai",
    "reasoning_claude": "anthropic",
    "vision_openai":    "openai",
    "fallback_openai":  "openai",
}

ALIAS_MODEL = {
    "cheap_openai":     "gpt-4o-mini",
    "reasoning_claude": "claude-sonnet-4-6",
    "vision_openai":    "gpt-4o",
    "fallback_openai":  "gpt-4o",
}

BUDGET_LIMIT    = 10.00
WARN_THRESHOLD  = 0.90

# ── Atomic write helpers ──────────────────────────────────────────────────────

def ensure_dir(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)

def atomic_write_json(path, data):
    ensure_dir(path)
    content = json.dumps(data, indent=2)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
    try:
        with os.fdopen(fd, 'w') as f:
            f.write(content)
        with open(tmp, 'r') as f:
            json.load(f)
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise

def atomic_append_jsonl(path, entry):
    ensure_dir(path)
    line = json.dumps(entry) + "\n"
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
    try:
        existing = ""
        if os.path.exists(path):
            with open(path, 'r') as f:
                existing = f.read()
        with os.fdopen(fd, 'w') as f:
            f.write(existing + line)
        with open(tmp, 'r') as f:
            for ln in f:
                if ln.strip():
                    json.loads(ln.strip())
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise

def atomic_append_log(path, message):
    ensure_dir(path)
    ts = datetime.now(timezone.utc).isoformat()
    line = f"[{ts}] {message}\n"
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
    try:
        existing = ""
        if os.path.exists(path):
            with open(path, 'r') as f:
                existing = f.read()
        with os.fdopen(fd, 'w') as f:
            f.write(existing + line)
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()

# ── Spend management ──────────────────────────────────────────────────────────

def load_spend():
    if not os.path.exists(SPEND_FILE):
        data = {
            "anthropic": {"cumulative_spend_usd": 0.0, "last_updated": str(datetime.now(timezone.utc).date()), "status": "active"},
            "openai":    {"cumulative_spend_usd": 0.0, "last_updated": str(datetime.now(timezone.utc).date()), "status": "active"},
        }
        atomic_write_json(SPEND_FILE, data)
        return data
    with open(SPEND_FILE, 'r') as f:
        return json.load(f)

def check_budget(provider, spend_data):
    spend = spend_data[provider]["cumulative_spend_usd"]
    pct = spend / BUDGET_LIMIT
    if pct >= 1.0:
        return "exhausted"
    if pct >= WARN_THRESHOLD:
        return "warning"
    return "active"

def select_alias(task_class, spend_data):
    primary = ROUTING_RULES.get(task_class, DEFAULT_ALIAS)
    provider = ALIAS_PROVIDER[primary]
    status = check_budget(provider, spend_data)
    fallback_used = False

    if status == "exhausted":
        msg = f"PROVIDER BUDGET EXHAUSTED — SWITCHED TO FALLBACK | provider={provider} | task={task_class}"
        print(f"\n{'='*60}")
        print(f"PROVIDER BUDGET EXHAUSTED — SWITCHED TO FALLBACK")
        print(f"Provider: {provider.upper()} | Task: {task_class}")
        print(f"{'='*60}\n")
        atomic_append_log(AUDIT_LOG, msg)
        if primary == "reasoning_claude":
            primary = "fallback_openai"
        else:
            print("ERROR: All providers exhausted. No calls permitted.")
            sys.exit(1)
        fallback_used = True

    elif status == "warning":
        msg = f"YOU HIT 90% OF YOUR BUDGET | provider={provider} | spend=${spend_data[provider]['cumulative_spend_usd']:.2f}/$10.00 | task={task_class}"
        print(f"\n{'='*60}")
        print(f"YOU HIT 90% OF YOUR BUDGET")
        print(f"Provider: {provider.upper()} | Spent: ${spend_data[provider]['cumulative_spend_usd']:.2f} of $10.00")
        print(f"{'='*60}\n")
        atomic_append_log(AUDIT_LOG, msg)
        if primary == "reasoning_claude":
            primary = "fallback_openai"
            fallback_used = True

    return primary, fallback_used

def enforce(task_class):
    spend_data = load_spend()
    alias, fallback_used = select_alias(task_class, spend_data)
    provider = ALIAS_PROVIDER[alias]
    model    = ALIAS_MODEL[alias]
    cost     = COST_ESTIMATES[alias]

    spend_data[provider]["cumulative_spend_usd"] += cost
    spend_data[provider]["last_updated"] = str(datetime.now(timezone.utc).date())
    atomic_write_json(SPEND_FILE, spend_data)

    cumulative = spend_data[provider]["cumulative_spend_usd"]
    remaining  = BUDGET_LIMIT - cumulative
    pct_used   = cumulative / BUDGET_LIMIT

    entry = {
        "timestamp":                    datetime.now(timezone.utc).isoformat(),
        "task_class":                   task_class,
        "alias_selected":               alias,
        "model_used":                   model,
        "provider":                     provider,
        "estimated_cost_usd":           cost,
        "provider_cumulative_spend_usd": round(cumulative, 4),
        "provider_budget_remaining_usd": round(remaining, 4),
        "provider_budget_pct_used":      round(pct_used, 4),
        "fallback_used":                fallback_used,
        "override":                     False,
    }
    atomic_append_jsonl(USAGE_LOG, entry)

    result = {
        "alias":               alias,
        "model":               model,
        "provider":            provider,
        "estimated_cost_usd":  cost,
        "budget_remaining_usd": round(remaining, 4),
        "budget_pct_used":     round(pct_used, 4),
        "fallback_used":       fallback_used,
    }
    print(json.dumps(result, indent=2))
    return result

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NemoClaw Budget Enforcer v2")
    parser.add_argument("--task-class", required=True,
        choices=["complex_reasoning","long_document","code","agentic","vision","structured_short","general_short"],
        help="Task class to route")
    args = parser.parse_args()
    enforce(args.task_class)

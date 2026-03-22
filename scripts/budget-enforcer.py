#!/usr/bin/env python3
"""
NemoClaw Budget Enforcer
Enforces routing rules, budget controls, and provider logging.
Doc 15 — Model Routing System Spec v3
"""

import json
import os
import sys
import argparse
from datetime import datetime, timezone

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.expanduser("~/nemoclaw-local-foundation")
ROUTING_CONFIG = os.path.join(BASE_DIR, "config/routing/routing-config.yaml")
BUDGET_CONFIG  = os.path.join(BASE_DIR, "config/routing/budget-config.yaml")
SPEND_FILE     = os.path.expanduser("~/.nemoclaw/logs/provider-spend.json")
USAGE_LOG      = os.path.expanduser("~/.nemoclaw/logs/provider-usage.jsonl")
AUDIT_LOG      = os.path.expanduser("~/.nemoclaw/logs/budget-audit.log")

# ── Cost estimates per alias (USD per call average) ───────────────────────────
COST_ESTIMATES = {
    "cheap_openai":    0.001,
    "reasoning_claude": 0.050,
    "vision_openai":   0.020,
    "fallback_openai": 0.030,
}

# ── Routing rules by task class ───────────────────────────────────────────────
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

# ── Alias to provider mapping ─────────────────────────────────────────────────
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

BUDGET_LIMIT = 10.00
WARN_THRESHOLD = 0.90

def ensure_log_dir():
    os.makedirs(os.path.expanduser("~/.nemoclaw/logs"), exist_ok=True)

def load_spend():
    ensure_log_dir()
    if not os.path.exists(SPEND_FILE):
        data = {
            "anthropic": {"cumulative_spend_usd": 0.0, "last_updated": str(datetime.now(timezone.utc).date()), "status": "active"},
            "openai":    {"cumulative_spend_usd": 0.0, "last_updated": str(datetime.now(timezone.utc).date()), "status": "active"},
        }
        with open(SPEND_FILE, "w") as f:
            json.dump(data, f, indent=2)
        return data
    with open(SPEND_FILE, "r") as f:
        return json.load(f)

def save_spend(data):
    with open(SPEND_FILE, "w") as f:
        json.dump(data, f, indent=2)

def write_audit(message):
    ensure_log_dir()
    ts = datetime.now(timezone.utc).isoformat()
    with open(AUDIT_LOG, "a") as f:
        f.write(f"[{ts}] {message}\n")

def write_usage_log(entry):
    ensure_log_dir()
    with open(USAGE_LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")

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
        write_audit(msg)
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
        write_audit(msg)
        if primary == "reasoning_claude":
            primary = "fallback_openai"
            fallback_used = True

    return primary, fallback_used

def enforce(task_class):
    spend_data = load_spend()
    alias, fallback_used = select_alias(task_class, spend_data)
    provider = ALIAS_PROVIDER[alias]
    model = ALIAS_MODEL[alias]
    cost = COST_ESTIMATES[alias]

    # Update cumulative spend
    spend_data[provider]["cumulative_spend_usd"] += cost
    spend_data[provider]["last_updated"] = str(datetime.now(timezone.utc).date())
    save_spend(spend_data)

    cumulative = spend_data[provider]["cumulative_spend_usd"]
    remaining = BUDGET_LIMIT - cumulative
    pct_used = cumulative / BUDGET_LIMIT

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "task_class": task_class,
        "alias_selected": alias,
        "model_used": model,
        "provider": provider,
        "estimated_cost_usd": cost,
        "provider_cumulative_spend_usd": round(cumulative, 4),
        "provider_budget_remaining_usd": round(remaining, 4),
        "provider_budget_pct_used": round(pct_used, 4),
        "fallback_used": fallback_used,
        "override": False,
    }

    write_usage_log(entry)

    result = {
        "alias": alias,
        "model": model,
        "provider": provider,
        "estimated_cost_usd": cost,
        "budget_remaining_usd": round(remaining, 4),
        "budget_pct_used": round(pct_used, 4),
        "fallback_used": fallback_used,
    }

    print(json.dumps(result, indent=2))
    return result

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NemoClaw Budget Enforcer")
    parser.add_argument("--task-class", required=True,
        choices=["complex_reasoning","long_document","code","agentic","vision","structured_short","general_short"],
        help="Task class to route")
    args = parser.parse_args()
    enforce(args.task_class)

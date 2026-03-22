#!/usr/bin/env python3
"""
NemoClaw Budget Enforcer v1.1
Enforces routing rules, budget controls, and provider logging.
Doc 15 — Model Routing System Spec v3
Updated March 23 2026 — corrected cost estimates, added cheaper_claude alias
"""

import json
import os
import sys
import argparse
from datetime import datetime, timezone

BASE_DIR = os.path.expanduser("~/nemoclaw-local-foundation")
SPEND_FILE = os.path.expanduser("~/.nemoclaw/logs/provider-spend.json")
USAGE_LOG  = os.path.expanduser("~/.nemoclaw/logs/provider-usage.jsonl")
AUDIT_LOG  = os.path.expanduser("~/.nemoclaw/logs/budget-audit.log")

# Cost estimates at 2x real pricing — conservative but realistic
# Based on ~500 input + 300 output tokens average per call
# Real pricing: Anthropic $3/$15 Sonnet, $1/$5 Haiku; OpenAI $0.15/$0.60 mini, $2.50/$10 4o
COST_ESTIMATES = {
    "cheap_openai":    0.0006,
    "cheaper_claude":  0.004,
    "reasoning_claude": 0.012,
    "vision_openai":   0.008,
    "fallback_openai": 0.008,
}

ROUTING_RULES = {
    "complex_reasoning": "reasoning_claude",
    "long_document":     "reasoning_claude",
    "code":              "reasoning_claude",
    "agentic":           "reasoning_claude",
    "moderate":          "cheaper_claude",
    "vision":            "vision_openai",
    "structured_short":  "cheap_openai",
    "general_short":     "cheap_openai",
}
DEFAULT_ALIAS = "cheap_openai"

ALIAS_PROVIDER = {
    "cheap_openai":     "openai",
    "cheaper_claude":   "anthropic",
    "reasoning_claude": "anthropic",
    "vision_openai":    "openai",
    "fallback_openai":  "openai",
}

ALIAS_MODEL = {
    "cheap_openai":     "gpt-4o-mini",
    "cheaper_claude":   "claude-haiku-4-5-20251001",
    "reasoning_claude": "claude-sonnet-4-6",
    "vision_openai":    "gpt-4o",
    "fallback_openai":  "gpt-4o",
}

BUDGET_LIMIT    = 10.00
WARN_THRESHOLD  = 0.90

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
    with open(SPEND_FILE) as f:
        return json.load(f)

def save_spend(data):
    tmp = SPEND_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, SPEND_FILE)

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
        if primary in ("reasoning_claude", "cheaper_claude"):
            primary = "fallback_openai"
        else:
            print("ERROR: All providers exhausted. No calls permitted.")
            sys.exit(1)
        fallback_used = True

    elif status == "warning":
        msg = f"YOU HIT 90% OF YOUR BUDGET | provider={provider} | spend=${spend_data[provider]['cumulative_spend_usd']:.4f}/$10.00 | task={task_class}"
        print(f"\n{'='*60}")
        print(f"YOU HIT 90% OF YOUR BUDGET")
        print(f"Provider: {provider.upper()} | Spent: ${spend_data[provider]['cumulative_spend_usd']:.4f} of $10.00")
        print(f"{'='*60}\n")
        write_audit(msg)
        if primary in ("reasoning_claude", "cheaper_claude"):
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
    save_spend(spend_data)

    cumulative = spend_data[provider]["cumulative_spend_usd"]
    remaining  = BUDGET_LIMIT - cumulative
    pct_used   = cumulative / BUDGET_LIMIT

    entry = {
        "timestamp":                     datetime.now(timezone.utc).isoformat(),
        "task_class":                    task_class,
        "alias_selected":                alias,
        "model_used":                    model,
        "provider":                      provider,
        "estimated_cost_usd":            cost,
        "provider_cumulative_spend_usd": round(cumulative, 6),
        "provider_budget_remaining_usd": round(remaining, 6),
        "provider_budget_pct_used":      round(pct_used, 6),
        "fallback_used":                 fallback_used,
        "override":                      False,
    }
    write_usage_log(entry)

    result = {
        "alias":                alias,
        "model":                model,
        "provider":             provider,
        "estimated_cost_usd":   cost,
        "budget_remaining_usd": round(remaining, 6),
        "budget_pct_used":      round(pct_used, 6),
        "fallback_used":        fallback_used,
    }
    print(json.dumps(result, indent=2))
    return result

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NemoClaw Budget Enforcer v1.1")
    parser.add_argument("--task-class", required=True,
        choices=["complex_reasoning","long_document","code","agentic","moderate","vision","structured_short","general_short"],
        help="Task class to route")
    args = parser.parse_args()
    enforce(args.task_class)

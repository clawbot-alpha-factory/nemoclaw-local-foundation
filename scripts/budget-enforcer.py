#!/usr/bin/env python3
"""
NemoClaw Budget Enforcer v3.0
Phase 8: Three providers — OpenAI, Anthropic, Google. 9-alias routing system.
Reads all routing and budget config from YAML files. No hardcoded values.
"""

import json
import os
import sys
import argparse
from datetime import datetime, timezone

import yaml

BASE_DIR       = os.path.expanduser("~/nemoclaw-local-foundation")
ROUTING_CONFIG = os.path.join(BASE_DIR, "config/routing/routing-config.yaml")
BUDGET_CONFIG  = os.path.join(BASE_DIR, "config/routing/budget-config.yaml")
SPEND_FILE     = os.path.expanduser("~/.nemoclaw/logs/provider-spend.json")
USAGE_LOG      = os.path.expanduser("~/.nemoclaw/logs/provider-usage.jsonl")
AUDIT_LOG      = os.path.expanduser("~/.nemoclaw/logs/budget-audit.log")

PROVIDERS = ["anthropic", "openai", "google", "nvidia"]

def load_configs():
    with open(ROUTING_CONFIG) as f:
        routing = yaml.safe_load(f)
    with open(BUDGET_CONFIG) as f:
        budget = yaml.safe_load(f)
    return routing, budget

def build_maps(routing):
    providers      = routing.get("providers", {})
    rules          = routing.get("routing_rules", {})
    default        = routing.get("defaults", {}).get("default_alias", "cheap_openai")
    alias_provider = {k: v["provider"] for k, v in providers.items()}
    alias_model    = {k: v["model"]    for k, v in providers.items()}
    cost_estimates = {k: v["estimated_cost_per_call"] for k, v in providers.items()}
    return rules, default, alias_provider, alias_model, cost_estimates

def ensure_log_dir():
    os.makedirs(os.path.expanduser("~/.nemoclaw/logs"), exist_ok=True)

def load_spend(budget_cfg):
    ensure_log_dir()
    if not os.path.exists(SPEND_FILE):
        data = {}
        for p in PROVIDERS:
            if p in budget_cfg.get("budgets", {}):
                data[p] = {
                    "cumulative_spend_usd": 0.0,
                    "last_updated": str(datetime.now(timezone.utc).date()),
                    "status": "active"
                }
        with open(SPEND_FILE, "w") as f:
            json.dump(data, f, indent=2)
        return data
    with open(SPEND_FILE) as f:
        data = json.load(f)
    # Add google if missing from older spend file
    for p in PROVIDERS:
        if p not in data and p in budget_cfg.get("budgets", {}):
            data[p] = {
                "cumulative_spend_usd": 0.0,
                "last_updated": str(datetime.now(timezone.utc).date()),
                "status": "active"
            }
    return data

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

def check_budget(provider, spend_data, budget_cfg):
    if provider not in budget_cfg.get("budgets", {}):
        return "active", 0.0, 999.0
    spend    = spend_data.get(provider, {}).get("cumulative_spend_usd", 0.0)
    limit    = budget_cfg["budgets"][provider]["total_usd"]
    warn_pct = budget_cfg["budgets"][provider]["threshold_warn"]
    stop_pct = budget_cfg["budgets"][provider]["threshold_hard_stop"]
    pct      = spend / limit
    if pct >= stop_pct:
        return "exhausted", spend, limit
    if pct >= warn_pct:
        return "warning", spend, limit
    return "active", spend, limit

def select_alias(task_class, spend_data, routing_rules, default_alias,
                 alias_provider, budget_cfg):
    primary  = routing_rules.get(task_class, default_alias)
    provider = alias_provider.get(primary, "openai")
    status, spend, limit = check_budget(provider, spend_data, budget_cfg)
    fallback_used = False

    if status == "exhausted":
        warn_msg = budget_cfg["budgets"][provider]["exhausted_message"]
        print(f"\n{'='*60}")
        print(warn_msg)
        print(f"Provider: {provider.upper()} | Task: {task_class}")
        print(f"{'='*60}\n")
        write_audit(f"{warn_msg} | provider={provider} | task={task_class}")
        primary = "fallback_openai"
        fallback_used = True

    elif status == "warning":
        warn_msg = budget_cfg["budgets"][provider]["warn_message"]
        print(f"\n{'='*60}")
        print(warn_msg)
        print(f"Provider: {provider.upper()} | Spent: ${spend:.4f} of ${limit:.2f}")
        print(f"{'='*60}\n")
        write_audit(f"{warn_msg} | provider={provider} | spend=${spend:.4f}/${limit:.2f} | task={task_class}")
        if primary not in ("cheap_openai", "fallback_openai", "reasoning_openai"):
            primary = "fallback_openai"
            fallback_used = True

    return primary, fallback_used

def enforce(task_class):
    routing_cfg, budget_cfg = load_configs()
    routing_rules, default_alias, alias_provider, alias_model, cost_estimates = build_maps(routing_cfg)
    spend_data = load_spend(budget_cfg)

    alias, fallback_used = select_alias(
        task_class, spend_data, routing_rules, default_alias,
        alias_provider, budget_cfg
    )
    provider = alias_provider.get(alias, "openai")
    _default_model = alias_model.get(default_alias, "") if alias_model else ""
    model    = alias_model.get(alias, _default_model)
    cost     = cost_estimates.get(alias, 0.001)
    limit    = budget_cfg["budgets"].get(provider, {}).get("total_usd", 10.0)

    if provider not in spend_data:
        spend_data[provider] = {"cumulative_spend_usd": 0.0,
                                "last_updated": str(datetime.now(timezone.utc).date()),
                                "status": "active"}

    spend_data[provider]["cumulative_spend_usd"] += cost
    spend_data[provider]["last_updated"] = str(datetime.now(timezone.utc).date())
    save_spend(spend_data)

    cumulative = spend_data[provider]["cumulative_spend_usd"]
    remaining  = limit - cumulative
    pct_used   = cumulative / limit

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
    parser = argparse.ArgumentParser(description="NemoClaw Budget Enforcer v3.0")
    parser.add_argument("--task-class", required=True,
        choices=["complex_reasoning","long_document","code","agentic","moderate",
                 "vision","structured_short","general_short","deep_reasoning",
                 "premium","strategic"],
        help="Task class to route")
    args = parser.parse_args()
    enforce(args.task_class)

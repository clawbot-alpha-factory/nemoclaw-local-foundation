#!/usr/bin/env python3
"""
NemoClaw Provider Budget Status v2.0
Phase 8: Three providers — OpenAI, Anthropic, Google
"""
import json
import os

SPEND_FILE = os.path.expanduser("~/.nemoclaw/logs/provider-spend.json")
BUDGET_CONFIG = os.path.expanduser("~/nemoclaw-local-foundation/config/routing/budget-config.yaml")

def load_spend():
    if not os.path.exists(SPEND_FILE):
        return {}
    with open(SPEND_FILE) as f:
        return json.load(f)

def load_limit(provider):
    try:
        import yaml
        with open(BUDGET_CONFIG) as f:
            cfg = yaml.safe_load(f)
        return cfg["budgets"][provider]["total_usd"]
    except Exception:
        return 30.00

def bar(pct, width=20):
    filled = int(pct * width)
    return "█" * filled + "░" * (width - filled)

def main():
    spend = load_spend()
    providers = ["anthropic", "openai", "google"]
    print()
    print("=" * 59)
    print("  NemoClaw Provider Budget Status")
    print("=" * 59)
    for p in providers:
        data  = spend.get(p, {"cumulative_spend_usd": 0.0})
        used  = data.get("cumulative_spend_usd", 0.0)
        limit = load_limit(p)
        pct   = used / limit
        pct_display = pct * 100
        status = "active"
        if pct >= 1.0:
            status = "EXHAUSTED"
        elif pct >= 0.9:
            status = "WARNING"
        print(f"  {p.upper():10s} | ${used:6.3f} / ${limit:.2f} | {pct_display:5.1f}% | {bar(pct)} | {status}")
    print("=" * 59)
    print()

if __name__ == "__main__":
    main()

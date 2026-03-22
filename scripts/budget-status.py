#!/usr/bin/env python3
"""
NemoClaw Budget Status
Shows current spend, remaining budget, and provider status at a glance.
"""

import json
import os
from datetime import datetime, timezone

SPEND_FILE = os.path.expanduser("~/.nemoclaw/logs/provider-spend.json")
BUDGET_LIMIT = 10.00
WARN_THRESHOLD = 0.90

def load_spend():
    if not os.path.exists(SPEND_FILE):
        print("No spend data found. Run budget-enforcer.py first.")
        return None
    with open(SPEND_FILE) as f:
        return json.load(f)

def status_label(spend):
    pct = spend / BUDGET_LIMIT
    if pct >= 1.0:
        return "EXHAUSTED"
    if pct >= WARN_THRESHOLD:
        return "WARNING — 90% REACHED"
    return "active"

def show():
    data = load_spend()
    if not data:
        return

    print()
    print("=" * 55)
    print("  NemoClaw Provider Budget Status")
    print("=" * 55)
    for provider, info in data.items():
        spend = info["cumulative_spend_usd"]
        remaining = BUDGET_LIMIT - spend
        pct = spend / BUDGET_LIMIT * 100
        status = status_label(spend)
        bar_filled = int(pct / 5)
        bar = "█" * bar_filled + "░" * (20 - bar_filled)
        print(f"  {provider.upper():<12} | ${spend:>6.3f} / ${BUDGET_LIMIT:.2f} | {pct:>5.1f}% | {bar} | {status}")
    print("=" * 55)
    print()

if __name__ == "__main__":
    show()

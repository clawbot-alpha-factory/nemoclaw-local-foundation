#!/usr/bin/env python3
"""
NemoClaw System Observer v1.0.0
Phase 10 — Observability Layer

Single command unified system view.
Run with: python3 scripts/obs.py

Shows:
  - System health
  - Active workflow status
  - Recent runs
  - Provider usage and spend
  - Budget thresholds
  - Checkpoint state
  - Skill output history
  - Failure summary
"""

import json
import os
import sqlite3
import sys
from datetime import datetime, timezone, timedelta

REPO            = os.path.expanduser("~/nemoclaw-local-foundation")
SPEND_FILE      = os.path.expanduser("~/.nemoclaw/logs/provider-spend.json")
USAGE_LOG       = os.path.expanduser("~/.nemoclaw/logs/provider-usage.jsonl")
CHECKPOINT_DB   = os.path.expanduser("~/.nemoclaw/checkpoints/langgraph.db")
OUTPUTS_DIR     = os.path.join(REPO, "skills/research-brief/outputs")
BUDGET_CONFIG   = os.path.join(REPO, "config/routing/budget-config.yaml")
VALIDATION_LOG  = os.path.expanduser("~/.nemoclaw/logs/validation-runs.jsonl")

WIDTH = 61

def bar(pct, width=20):
    filled = int(pct * width)
    return "█" * filled + "░" * (width - filled)

def hline():
    print("=" * WIDTH)

def section(title):
    print(f"\n{title}")
    print("-" * WIDTH)

def load_spend():
    if not os.path.exists(SPEND_FILE):
        return {}
    with open(SPEND_FILE) as f:
        return json.load(f)

def load_budget_limits():
    limits = {"anthropic": 10.0, "openai": 10.0, "google": 10.0}
    try:
        import yaml
        with open(BUDGET_CONFIG) as f:
            cfg = yaml.safe_load(f)
        for p in limits:
            if p in cfg.get("budgets", {}):
                limits[p] = cfg["budgets"][p]["total_usd"]
    except Exception:
        pass
    return limits

def load_recent_usage(n=20):
    if not os.path.exists(USAGE_LOG):
        return []
    lines = []
    with open(USAGE_LOG) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    lines.append(json.loads(line))
                except Exception:
                    pass
    return lines[-n:]

def load_checkpoint_stats():
    if not os.path.exists(CHECKPOINT_DB):
        return None
    try:
        conn = sqlite3.connect(CHECKPOINT_DB)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(DISTINCT thread_id) FROM checkpoints")
        total = cur.fetchone()[0]
        conn.close()
        return {"total_threads": total}
    except Exception:
        return None

def load_recent_outputs(n=5):
    if not os.path.exists(OUTPUTS_DIR):
        return []
    files = []
    for f in os.listdir(OUTPUTS_DIR):
        if f.endswith(".md") and not f.startswith("."):
            path = os.path.join(OUTPUTS_DIR, f)
            stat = os.stat(path)
            files.append({
                "name": f,
                "size_kb": round(stat.st_size / 1024, 1),
                "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
            })
    files.sort(key=lambda x: x["modified"], reverse=True)
    return files[:n]

def check_system_health():
    import subprocess
    checks = []

    # Docker
    r = subprocess.run("docker info --format {{.ServerVersion}} 2>/dev/null",
                       shell=True, capture_output=True, text=True)
    if r.returncode == 0 and r.stdout.strip():
        checks.append(("Docker Desktop", True, r.stdout.strip()))
    else:
        checks.append(("Docker Desktop", False, "not running"))

    # venv312
    venv = os.path.expanduser("~/nemoclaw-local-foundation/.venv312/bin/python")
    if os.path.exists(venv):
        checks.append((".venv312 Python 3.12", True, "present"))
    else:
        checks.append((".venv312 Python 3.12", False, "missing — run setup"))

    # Gateway
    r2 = subprocess.run("openshell gateway info 2>/dev/null",
                        shell=True, capture_output=True, text=True)
    if r2.returncode == 0 and "127.0.0.1:8080" in r2.stdout:
        checks.append(("OpenShell gateway", True, "reachable"))
    else:
        checks.append(("OpenShell gateway", False, "not reachable"))

    # API keys
    env_path = os.path.join(REPO, "config/.env")
    keys_found = []
    keys_missing = []
    for key in ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY"]:
        found = False
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    if line.strip().startswith(f"{key}=") and len(line.strip().split("=",1)[1]) > 10:
                        found = True
                        break
        if found:
            keys_found.append(key.replace("_API_KEY",""))
        else:
            keys_missing.append(key)
    if keys_missing:
        checks.append(("API Keys", False, f"missing: {keys_missing}"))
    else:
        checks.append(("API Keys", True, f"{', '.join(keys_found)} present"))

    return checks

def get_recent_runs(usage_lines, n=5):
    runs = {}
    for entry in reversed(usage_lines):
        ts = entry.get("timestamp", "")[:16].replace("T", " ")
        alias = entry.get("alias_selected", "unknown")
        skill = "research-brief" if "claude" in alias or "openai" in alias or "google" in alias else "unknown"
        cost = entry.get("estimated_cost_usd", 0)
        provider = entry.get("provider", "unknown")
        key = ts[:13]
        if key not in runs:
            runs[key] = {"timestamp": ts, "skill": skill,
                         "provider": provider, "cost": cost, "calls": 1}
        else:
            runs[key]["calls"] += 1
            runs[key]["cost"] += cost
    return list(runs.values())[:n]

def get_failures(usage_lines, hours=24):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    failures = []
    for entry in usage_lines:
        if entry.get("fallback_used", False):
            ts = entry.get("timestamp", "")
            try:
                entry_time = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                if entry_time > cutoff:
                    failures.append(entry)
            except Exception:
                pass
    return failures

def main():
    now = datetime.now(timezone.utc)

    hline()
    print(f"  NemoClaw System Observer — {now.strftime('%Y-%m-%d %H:%M UTC')}")
    hline()

    # ── System Health ─────────────────────────────────────────
    section("SYSTEM HEALTH")
    health = check_system_health()
    for name, ok, detail in health:
        icon = "✅" if ok else "❌"
        print(f"  {icon} {name:<25} {detail}")

    # ── Provider Usage ────────────────────────────────────────
    section("PROVIDER USAGE & BUDGET")
    spend  = load_spend()
    limits = load_budget_limits()
    for p in ["anthropic", "openai", "google"]:
        used  = spend.get(p, {}).get("cumulative_spend_usd", 0.0)
        limit = limits.get(p, 10.0)
        pct   = used / limit
        status = "EXHAUSTED" if pct >= 1.0 else "WARNING" if pct >= 0.9 else "active"
        print(f"  {p.upper():<10} ${used:6.3f}/${limit:.0f}  {bar(pct)}  {pct*100:4.1f}%  {status}")

    # ── Recent Runs ───────────────────────────────────────────
    section("RECENT RUNS (last 5 sessions)")
    usage_lines = load_recent_usage(100)
    runs = get_recent_runs(usage_lines, 5)
    if not runs:
        print("  No runs recorded yet")
    else:
        for r in runs:
            print(f"  {r['timestamp']}  {r['provider']:<12}  {r['calls']} calls  ${r['cost']:.4f}")

    # ── Checkpoint State ──────────────────────────────────────
    section("CHECKPOINT STATE")
    cp_stats = load_checkpoint_stats()
    if cp_stats:
        print(f"  DB:             {CHECKPOINT_DB}")
        print(f"  Total threads:  {cp_stats['total_threads']}")
    else:
        print("  Checkpoint DB not found — run a skill to initialize")

    # ── Skill Output History ──────────────────────────────────
    section("SKILL OUTPUT HISTORY (last 5)")
    outputs = load_recent_outputs(5)
    if not outputs:
        print("  No skill outputs found")
    else:
        for o in outputs:
            ts = o["modified"].strftime("%Y-%m-%d %H:%M")
            print(f"  {ts}  {o['size_kb']:>5}KB  {o['name'][:45]}")

    # ── Failure Summary ───────────────────────────────────────
    section("FAILURE SUMMARY (last 24h)")
    failures = get_failures(usage_lines, 24)
    if not failures:
        print("  No fallbacks triggered in last 24 hours")
    else:
        print(f"  {len(failures)} fallback(s) triggered:")
        for f in failures[-3:]:
            ts = f.get("timestamp","")[:16].replace("T"," ")
            print(f"  {ts}  {f.get('task_class','?')} → fallback due to budget/error")

    # ── Last Validation ───────────────────────────────────────
    section("LAST VALIDATION RUN")
    if os.path.exists(VALIDATION_LOG):
        lines = open(VALIDATION_LOG).readlines()
        if lines:
            try:
                last = json.loads(lines[-1])
                ts   = last.get("timestamp","")[:16].replace("T"," ")
                p    = last.get("total_pass", 0)
                w    = last.get("total_warn", 0)
                f    = last.get("total_fail", 0)
                icon = "✅" if f == 0 else "❌"
                print(f"  {icon} {ts}  {p} passed  {w} warnings  {f} failed")
            except Exception:
                print("  Could not parse last validation run")
        else:
            print("  No validation runs recorded")
    else:
        print("  No validation log found — run: python3 scripts/validate.py")

    print()
    hline()
    print()

if __name__ == "__main__":
    main()

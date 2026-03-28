#!/usr/bin/env python3
"""
NemoClaw Production Operations Hub v1.0

Unified operational interface for the entire multi-agent system.
One command to rule all 20 MA systems.

Usage:
  python3 scripts/prod-ops.py status          # Full system status
  python3 scripts/prod-ops.py health          # System health dashboard
  python3 scripts/prod-ops.py agents          # Agent roster + performance
  python3 scripts/prod-ops.py run GOAL        # Execute a full agent workflow
  python3 scripts/prod-ops.py approvals       # Pending human approvals
  python3 scripts/prod-ops.py costs           # Budget + cost report
  python3 scripts/prod-ops.py lessons         # Learning system summary
  python3 scripts/prod-ops.py conflicts       # Open conflicts
  python3 scripts/prod-ops.py reviews         # Pending reviews
  python3 scripts/prod-ops.py security        # Security audit summary
  python3 scripts/prod-ops.py compete GOAL    # Run internal competition
  python3 scripts/prod-ops.py validate        # Run 31-check validation
  python3 scripts/prod-ops.py integration     # Run MA-20 integration test
  python3 scripts/prod-ops.py report          # Full executive report
"""

import argparse
import json
import os
import sys
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path.home() / "nemoclaw-local-foundation"
sys.path.insert(0, str(REPO / "scripts"))

# ═══════════════════════════════════════════════════════════════════════════════
# SYSTEM STATUS
# ═══════════════════════════════════════════════════════════════════════════════

def cmd_status():
    """Full system status — one screen to see everything."""
    print(f"\n  {'═' * 60}")
    print(f"  NEMOCLAW PRODUCTION STATUS")
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"  {'═' * 60}\n")

    # ── INFRASTRUCTURE ──
    print(f"  ── Infrastructure ──")

    # Skills
    skill_count = len([d for d in (REPO / "skills").iterdir()
                       if d.is_dir() and "__pycache__" not in d.name
                       and "graph-validation" not in d.name]) if (REPO / "skills").exists() else 0
    print(f"  Skills: {skill_count}")

    # MA Scripts
    ma_scripts = [f.stem for f in (REPO / "scripts").glob("*.py")]
    print(f"  Scripts: {len(ma_scripts)}")

    # Agents
    try:
        from agent_registry import AgentRegistry
        reg = AgentRegistry()
        agents = reg.list_agents()
        print(f"  Agents: {len(agents)}")
        print(f"  Capabilities: {len(reg.capabilities)}")
    except Exception:
        print(f"  Agents: (could not load)")

    # Budget
    try:
        spend_path = Path.home() / ".nemoclaw" / "logs" / "provider-spend.json"
        if spend_path.exists():
            with open(spend_path) as f:
                spend = json.load(f)
            print(f"\n  ── Budget ──")
            for provider in ["anthropic", "openai", "google"]:
                s = spend.get(provider, {})
                if isinstance(s, dict):
                    spent = s.get("cumulative_spend_usd", 0)
                else:
                    spent = 0
                remaining = 30.0 - spent
                pct = (spent / 30.0) * 100
                bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
                print(f"  {provider:<12} ${spent:>6.2f}/$30 {bar} {pct:.0f}%")
    except Exception:
        pass

    # Health (quick)
    try:
        from system_health import SystemHealthObserver
        obs = SystemHealthObserver()
        h = obs.check_all()
        status_icon = {"HEALTHY": "🟢", "DEGRADED": "🟡", "CRITICAL": "🔴"}.get(h["status"], "?")
        print(f"\n  ── System Health ──")
        print(f"  {status_icon} {h['status']} ({h['composite_score']:.0%})")
        if h.get("anomalies"):
            for a in h["anomalies"][:3]:
                sev = {"critical": "🔴", "warning": "🟡"}.get(a["severity"], "?")
                print(f"    {sev} {a['message']}")
    except Exception:
        pass

    # Pending approvals
    try:
        from human_loop import HumanLoopManager
        hlm = HumanLoopManager()
        pending = hlm.get_pending()
        if pending:
            print(f"\n  ── Pending Approvals ({len(pending)}) ──")
            for a in pending[:3]:
                prio = {"critical": "🔴", "high": "🟠", "medium": "🟡"}.get(a["priority"], "⚪")
                print(f"    {prio} [{a['id']}] {a['title'][:50]}")
        else:
            print(f"\n  ✅ No pending approvals")
    except Exception:
        pass

    # Git
    try:
        result = subprocess.run(["git", "-C", str(REPO), "log", "--oneline", "-1"],
                                 capture_output=True, text=True)
        print(f"\n  ── Git ──")
        print(f"  Latest: {result.stdout.strip()}")
        result2 = subprocess.run(["git", "-C", str(REPO), "status", "--porcelain"],
                                  capture_output=True, text=True)
        clean = len(result2.stdout.strip()) == 0
        print(f"  Status: {'✅ Clean' if clean else '⚠️ Uncommitted changes'}")
    except Exception:
        pass

    print()


# ═══════════════════════════════════════════════════════════════════════════════
# HEALTH DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════════

def cmd_health():
    """Run full system health dashboard."""
    try:
        subprocess.run([sys.executable, str(REPO / "scripts" / "system_health.py"),
                        "--dashboard"])
    except Exception as e:
        print(f"  Error: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# AGENT ROSTER
# ═══════════════════════════════════════════════════════════════════════════════

def cmd_agents():
    """Show agent roster with performance data."""
    print(f"\n  {'═' * 60}")
    print(f"  AGENT ROSTER & PERFORMANCE")
    print(f"  {'═' * 60}\n")

    try:
        from agent_registry import AgentRegistry
        reg = AgentRegistry()
        agents = reg.list_agents()

        # Load performance data
        perf_data = {}
        try:
            from agent_performance import PerformanceManager
            pm = PerformanceManager()
            for agent in agents:
                aid = agent.get("agent_id", agent.get("id", ""))
                report = pm.get_agent_report(aid)
                perf_data[aid] = report
        except Exception:
            pass

        # Load compliance data
        compliance_data = {}
        try:
            from behavior_guard import BehaviorGuard
            guard = BehaviorGuard()
            compliance_data = guard.get_compliance()
        except Exception:
            pass

        print(f"  {'Agent':<25} {'Level':>5} {'Composite':>10} {'Compliance':>11} {'Trend':>8}")
        print(f"  {'-'*25} {'-'*5} {'-'*10} {'-'*11} {'-'*8}")

        for agent in agents:
            aid = agent.get("agent_id", agent.get("id", ""))
            level = agent.get("authority_level", "?")
            
            perf = perf_data.get(aid, {})
            composite = perf.get("composite_score")
            comp_str = f"{composite:.0%}" if composite is not None else "N/A"

            comp = compliance_data.get(aid, {})
            comp_score = comp.get("compliance_score")
            comp_str2 = f"{comp_score:.0%}" if comp_score is not None else "N/A"

            trend = perf.get("trend_direction", "—")
            trend_icon = {"improving": "📈", "declining": "📉", "stable": "➡️"}.get(trend, "—")

            print(f"  {aid:<25} L{level:>3} {comp_str:>10} {comp_str2:>11} {trend_icon:>6}")

    except Exception as e:
        print(f"  Error loading agents: {e}")
    print()


# ═══════════════════════════════════════════════════════════════════════════════
# RUN WORKFLOW
# ═══════════════════════════════════════════════════════════════════════════════

def cmd_run(goal, dry_run=False):
    """Execute a full agent workflow from goal to output."""
    print(f"\n  {'═' * 60}")
    print(f"  EXECUTING WORKFLOW")
    print(f"  Goal: {goal[:60]}")
    print(f"  Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    print(f"  {'═' * 60}\n")

    try:
        # Step 1: Decompose
        print(f"  ── Step 1: Task Decomposition (MA-5) ──")
        from task_decomposer import decompose
        plan, source, error = decompose(goal)
        if error:
            print(f"  ❌ Decomposition failed: {error}")
            return
        tasks = plan.tasks if hasattr(plan, "tasks") else []
        print(f"  ✅ {len(tasks)} tasks via {source}")
        for i, t in enumerate(tasks):
            title = t.get("title", t) if isinstance(t, dict) else str(t)
            print(f"    {i+1}. {title[:60] if isinstance(title, str) else title}")

        # Step 2: Cost estimate
        print(f"\n  ── Step 2: Cost Estimate (MA-6) ──")
        from cost_governor import CostGovernor
        cg = CostGovernor()
        total_est = len(tasks) * 0.50  # rough estimate
        print(f"  Estimated cost: ${total_est:.2f}")
        print(f"  Circuit breaker: {cg.breaker.state}")

        # Step 3: Competition check
        print(f"\n  ── Step 3: Competition Check (MA-18) ──")
        from internal_competition import CompetitionManager
        cm = CompetitionManager()
        should, num = cm.should_compete(total_est)
        if should:
            print(f"  ⚡ Competition triggered: {num} agents will compete")
        else:
            print(f"  ➡️ Single-agent execution (below $5 threshold)")

        # Step 4: Access check
        print(f"\n  ── Step 4: Access Control (MA-19) ──")
        from access_control import AccessController
        ac = AccessController()
        r = ac.check_access("strategy_lead", "skills", "execute")
        print(f"  {'✅ Access granted' if r.granted else '❌ Access denied'}")

        if dry_run:
            print(f"\n  {'─' * 40}")
            print(f"  DRY RUN COMPLETE — no tasks executed")
            print(f"  Run without --dry-run to execute")
            return

        # Step 5: Execute
        print(f"\n  ── Step 5: Execution ──")
        from task_decomposer import execute_plan
        results = execute_plan(plan, dry_run=False)
        if isinstance(results, dict):
            status = results.get("status", "unknown")
            print(f"  Result: {status}")
        else:
            print(f"  Result: {results}")

    except Exception as e:
        print(f"  ❌ Error: {e}")
    print()


# ═══════════════════════════════════════════════════════════════════════════════
# COSTS
# ═══════════════════════════════════════════════════════════════════════════════

def cmd_costs():
    """Budget and cost report."""
    try:
        subprocess.run([sys.executable, str(REPO / "scripts" / "budget-status.py")])
    except Exception as e:
        print(f"  Error: {e}")

    try:
        from cost_governor import CostGovernor
        cg = CostGovernor()
        print(f"\n  Circuit Breaker: {cg.breaker.state}")
        cg.ledger.summary()
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════════════════
# APPROVALS
# ═══════════════════════════════════════════════════════════════════════════════

def cmd_approvals(approve_id=None, reject_id=None, reason=""):
    """Manage human approvals."""
    try:
        from human_loop import HumanLoopManager
        hlm = HumanLoopManager()

        if approve_id:
            ok, msg = hlm.approve(approve_id, reason or "Approved via prod-ops")
            print(f"  {'✅' if ok else '❌'} {msg}")
            return

        if reject_id:
            ok, msg = hlm.reject(reject_id, reason or "Rejected via prod-ops")
            print(f"  {'✅' if ok else '❌'} {msg}")
            return

        pending = hlm.get_pending()
        if not pending:
            print(f"  ✅ No pending approvals")
            return

        print(f"\n  Pending Approvals ({len(pending)}):\n")
        for a in pending:
            prio = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "⚪"}.get(a["priority"], "?")
            exp = a.get("expires_at", "never")[:16] if a.get("expires_at") else "never"
            print(f"  {prio} [{a['id']}] {a['title'][:55]}")
            print(f"     Category: {a['category']} | Agent: {a['requesting_agent']} | Expires: {exp}")
            print()

        print(f"  Actions:")
        print(f"    python3 scripts/prod-ops.py approvals --approve APPROVAL_ID")
        print(f"    python3 scripts/prod-ops.py approvals --reject APPROVAL_ID --reason 'explanation'")

    except Exception as e:
        print(f"  Error: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# LESSONS
# ═══════════════════════════════════════════════════════════════════════════════

def cmd_lessons():
    """Learning system summary."""
    try:
        from learning_loop import LearningLoop
        ll = LearningLoop()
        s = ll.get_summary()
        print(f"\n  ── Learning System ──")
        print(f"  Total lessons: {s['total_lessons']}")
        print(f"  By status: {s['by_status']}")
        print(f"  By source: {s['by_source']}")
        if s.get("avg_efficacy") is not None:
            print(f"  Avg efficacy: {s['avg_efficacy']:.0%}")

        # Run cycle
        cycle = ll.run_cycle()
        if any(cycle.values()):
            print(f"\n  Cycle results:")
            print(f"    Validated: {len(cycle['validated'])}")
            print(f"    Applied: {len(cycle['applied'])}")
            print(f"    Pending approval: {len(cycle['pending_approval'])}")
            print(f"    Expired: {len(cycle['expired'])}")
    except Exception as e:
        print(f"  Error: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# CONFLICTS
# ═══════════════════════════════════════════════════════════════════════════════

def cmd_conflicts():
    """Open conflicts summary."""
    try:
        subprocess.run([sys.executable, str(REPO / "scripts" / "conflict_resolution.py"),
                        "--stats"])
    except Exception as e:
        print(f"  Error: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# REVIEWS
# ═══════════════════════════════════════════════════════════════════════════════

def cmd_reviews():
    """Peer review status."""
    try:
        subprocess.run([sys.executable, str(REPO / "scripts" / "peer_review.py"),
                        "--quality"])
    except Exception as e:
        print(f"  Error: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# SECURITY
# ═══════════════════════════════════════════════════════════════════════════════

def cmd_security():
    """Security audit summary."""
    try:
        from access_control import AccessController
        ac = AccessController()
        stats = ac.stats.data
        print(f"\n  ── Security & Access Control ──")
        print(f"  Total checks: {stats['total_checks']}")
        print(f"  Granted: {stats['total_granted']}")
        print(f"  Denied: {stats['total_denied']}")
        print(f"  Escalated: {stats['total_escalated']}")

        if stats.get("by_domain"):
            print(f"\n  By domain:")
            for domain, s in stats["by_domain"].items():
                rate = s["granted"] / (s["granted"] + s["denied"]) if (s["granted"] + s["denied"]) > 0 else 1
                print(f"    {domain}: {rate:.0%} grant rate")
    except Exception as e:
        print(f"  Error: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# COMPETE
# ═══════════════════════════════════════════════════════════════════════════════

def cmd_compete(goal):
    """Run internal competition for a goal."""
    print(f"\n  ── Internal Competition ──")
    print(f"  Goal: {goal[:60]}")

    try:
        from internal_competition import CompetitionManager
        cm = CompetitionManager()
        comp = cm.create_competition(goal, domain="general", estimated_cost=10.0)
        selected = cm.select_competitors(comp)
        print(f"  Competitors: {[s[0] for s in selected] if isinstance(selected[0], tuple) else selected}")
        print(f"  Status: Competition created [{comp.id}]")
        print(f"  Submit entries, then finalize with:")
        print(f"    comp.submit_entry(agent_id, content)")
        print(f"    cm.finalize('{comp.id}')")
    except Exception as e:
        print(f"  Error: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# VALIDATE
# ═══════════════════════════════════════════════════════════════════════════════

def cmd_validate():
    """Run validation suite."""
    subprocess.run([sys.executable, str(REPO / "scripts" / "validate.py")])


# ═══════════════════════════════════════════════════════════════════════════════
# INTEGRATION
# ═══════════════════════════════════════════════════════════════════════════════

def cmd_integration():
    """Run MA-20 integration test."""
    subprocess.run([sys.executable, str(REPO / "scripts" / "integration_test.py"), "--test"])


# ═══════════════════════════════════════════════════════════════════════════════
# EXECUTIVE REPORT
# ═══════════════════════════════════════════════════════════════════════════════

def cmd_report():
    """Generate full executive report using SCQA framework."""
    print(f"\n  {'═' * 60}")
    print(f"  NEMOCLAW EXECUTIVE REPORT")
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"  {'═' * 60}")

    # Situation
    print(f"\n  ── SITUATION ──")
    skill_count = len([d for d in (REPO / "skills").iterdir()
                       if d.is_dir() and "__pycache__" not in d.name
                       and "graph-validation" not in d.name]) if (REPO / "skills").exists() else 0
    print(f"  Multi-agent AI system with {skill_count} skills across 7 agents")
    print(f"  20 MA infrastructure systems operational")

    # Complication
    print(f"\n  ── KEY METRICS ──")

    try:
        from system_health import SystemHealthObserver
        obs = SystemHealthObserver()
        h = obs.check_all()
        print(f"  System Health: {h['status']} ({h['composite_score']:.0%})")
    except Exception:
        print(f"  System Health: (unavailable)")

    try:
        spend_path = Path.home() / ".nemoclaw" / "logs" / "provider-spend.json"
        if spend_path.exists():
            with open(spend_path) as f:
                spend = json.load(f)
            total_spent = sum(
                s.get("cumulative_spend_usd", 0) if isinstance(s, dict) else 0
                for s in spend.values()
            )
            print(f"  Total Spend: ${total_spent:.2f} / $90.00 ({total_spent/90*100:.0f}%)")
    except Exception:
        pass

    try:
        from learning_loop import LearningLoop
        ll = LearningLoop()
        s = ll.get_summary()
        print(f"  Lessons Learned: {s['total_lessons']} ({s.get('by_status', {}).get('applied', 0)} applied)")
    except Exception:
        pass

    try:
        from human_loop import HumanLoopManager
        hlm = HumanLoopManager()
        pending = hlm.get_pending()
        print(f"  Pending Approvals: {len(pending)}")
    except Exception:
        pass

    # Recommendations
    print(f"\n  ── RECOMMENDATIONS ──")
    try:
        if h.get("anomalies"):
            for a in h["anomalies"][:3]:
                print(f"  • {a['message']}")
                if a.get("recovery"):
                    print(f"    → {a['recovery'][0]}")
        else:
            print(f"  ✅ No critical issues — system operating normally")
    except Exception:
        print(f"  (Health data unavailable)")

    # Next steps
    print(f"\n  ── NEXT STEPS ──")
    print(f"  1. Review pending approvals: python3 scripts/prod-ops.py approvals")
    print(f"  2. Check agent performance: python3 scripts/prod-ops.py agents")
    print(f"  3. Run learning cycle: python3 scripts/prod-ops.py lessons")
    print()


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="NemoClaw Production Operations Hub",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  status        Full system status (one screen)
  health        System health dashboard (11 domains)
  agents        Agent roster with performance data
  run GOAL      Execute a full agent workflow
  approvals     View/manage pending human approvals
  costs         Budget and cost report
  lessons       Learning system summary + cycle
  conflicts     Open conflicts summary
  reviews       Peer review status
  security      Security audit summary
  compete GOAL  Run internal competition
  validate      Run 31-check validation suite
  integration   Run MA-20 integration test
  report        Full executive report (SCQA framework)
""")

    parser.add_argument("command", nargs="?", default="status",
                        choices=["status", "health", "agents", "run", "approvals",
                                 "costs", "lessons", "conflicts", "reviews",
                                 "security", "compete", "validate", "integration",
                                 "report"])
    parser.add_argument("goal", nargs="?", default=None, help="Goal for run/compete")
    parser.add_argument("--dry-run", action="store_true", help="Dry run for 'run' command")
    parser.add_argument("--approve", metavar="ID", help="Approve an approval")
    parser.add_argument("--reject", metavar="ID", help="Reject an approval")
    parser.add_argument("--reason", default="", help="Reason for approval action")

    args = parser.parse_args()

    if args.command == "status":
        cmd_status()
    elif args.command == "health":
        cmd_health()
    elif args.command == "agents":
        cmd_agents()
    elif args.command == "run":
        if not args.goal:
            print("  Error: 'run' requires a GOAL argument")
            print("  Example: python3 scripts/prod-ops.py run 'Research AI meeting assistants'")
            sys.exit(1)
        cmd_run(args.goal, args.dry_run)
    elif args.command == "approvals":
        cmd_approvals(args.approve, args.reject, args.reason)
    elif args.command == "costs":
        cmd_costs()
    elif args.command == "lessons":
        cmd_lessons()
    elif args.command == "conflicts":
        cmd_conflicts()
    elif args.command == "reviews":
        cmd_reviews()
    elif args.command == "security":
        cmd_security()
    elif args.command == "compete":
        if not args.goal:
            print("  Error: 'compete' requires a GOAL argument")
            sys.exit(1)
        cmd_compete(args.goal)
    elif args.command == "validate":
        cmd_validate()
    elif args.command == "integration":
        cmd_integration()
    elif args.command == "report":
        cmd_report()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

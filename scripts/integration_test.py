#!/usr/bin/env python3
"""
NemoClaw Integration Test v1.0 (MA-20)

Full 7-agent end-to-end workflow exercising all 19 MA systems.

Scenario: "Research AI meeting assistants and produce a product recommendation"

This test verifies that all MA systems can work together in a realistic
multi-agent workflow without crashes, data loss, or integration failures.

Usage:
  python3 scripts/integration_test.py --test
  python3 scripts/integration_test.py --full    # verbose output
  python3 scripts/integration_test.py --summary # quick pass/fail
"""

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

REPO = Path.home() / "nemoclaw-local-foundation"
sys.path.insert(0, str(REPO / "scripts"))


def run_integration_test(verbose=True):
    """Run full integration test across all 19 MA systems.

    Returns: (passed, total, results_list)
    """
    tp = 0
    tt = 0
    results = []

    def test(name, condition, detail=""):
        nonlocal tp, tt
        tt += 1
        passed = bool(condition)
        if passed:
            tp += 1
        results.append({"name": name, "passed": passed, "detail": detail})
        if verbose:
            icon = "✅" if passed else "❌"
            suffix = f": {detail}" if detail and not passed else ""
            print(f"  {icon} {name}{suffix}")

    if verbose:
        print("=" * 60)
        print("  MA-20 Integration Test — Full 7-Agent Workflow")
        print("=" * 60)
        print()

    # ══════════════════════════════════════════════════════════════
    # PHASE 1: SYSTEM INITIALIZATION (MA-1, MA-19)
    # ══════════════════════════════════════════════════════════════
    if verbose:
        print("  ── Phase 1: System Initialization ──")

    # MA-1: Agent Registry
    try:
        from agent_registry import AgentRegistry
        registry = AgentRegistry()
        agents = registry.list_agents()
        test("MA-1: Registry loads agents", len(agents) >= 7, f"{len(agents)} agents")
    except Exception as e:
        test("MA-1: Registry loads agents", False, str(e)[:60])
        agents = []

    # MA-1: Capabilities
    try:
        caps = registry.capabilities
        test("MA-1: Capabilities loaded", len(caps) >= 20, f"{len(caps)} capabilities")
    except Exception as e:
        test("MA-1: Capabilities loaded", False, str(e)[:60])

    # MA-19: Access Control
    try:
        from access_control import AccessController
        ac = AccessController()
        r = ac.check_access("strategy_lead", "skills", "execute")
        test("MA-19: Access control operational", r.granted)
    except Exception as e:
        test("MA-19: Access control operational", False, str(e)[:60])

    # MA-19: Unauthorized access blocked
    try:
        r = ac.check_access("narrative_content_lead", "config", "modify")
        test("MA-19: Unauthorized access blocked", not r.granted and r.escalated)
    except Exception as e:
        test("MA-19: Unauthorized access blocked", False, str(e)[:60])

    if verbose:
        print()

    # ══════════════════════════════════════════════════════════════
    # PHASE 2: TASK PLANNING (MA-5, MA-6, MA-17)
    # ══════════════════════════════════════════════════════════════
    if verbose:
        print("  ── Phase 2: Task Planning ──")

    # MA-5: Task Decomposition
    try:
        from task_decomposer import decompose
        plan, source, error = decompose("Research AI meeting assistant market and produce product recommendation")
        tasks = plan.tasks if hasattr(plan, "tasks") else []
        test("MA-5: Task decomposed",
             plan is not None and len(tasks) >= 2 and error is None,
             f"{len(tasks)} tasks, source={source}, error={error}")
    except Exception as e:
        test("MA-5: Task decomposed", False, str(e)[:80])

    # MA-6: Cost Governance
    try:
        from cost_governor import CostGovernor
        cg = CostGovernor()
        # CostGovernor loads budget config — verify it initialized
        test("MA-6: Budget governance operational",
             cg.breaker is not None and hasattr(cg, "ledger"))
    except Exception as e:
        test("MA-6: Budget governance operational", False, str(e)[:60])

    # MA-6: Circuit breaker state
    try:
        state = cg.breaker.state
        test("MA-6: Circuit breaker operational",
             state in ("CLOSED", "OPEN", "HALF_OPEN"), f"state={state}")
    except Exception as e:
        test("MA-6: Circuit breaker operational", False, str(e)[:60])

    # MA-17: Context Window
    try:
        from context_manager import ContextItem, ContextPool
        pool = ContextPool("research")
        pool.add(ContextItem("System: You are a market researcher", "system", "critical"))
        pool.add(ContextItem("Task: Research AI meeting assistants", "user", "high"))
        ctx, tokens, items = pool.build_context()
        test("MA-17: Context window allocated",
             tokens > 0 and items == 2, f"{tokens} tokens, {items} items")
    except Exception as e:
        test("MA-17: Context window allocated", False, str(e)[:60])

    if verbose:
        print()

    # ══════════════════════════════════════════════════════════════
    # PHASE 3: AGENT INTERACTION (MA-3, MA-7, MA-8)
    # ══════════════════════════════════════════════════════════════
    if verbose:
        print("  ── Phase 3: Agent Interaction ──")

    # MA-3: Messaging
    try:
        from agent_messaging import Channel, Message
        ch = Channel("integration_test_ch",
                      participants=["strategy_lead", "product_architect"])
        msg = Message("strategy_lead", "integration_test_ch", "inform",
                       "Starting market research on AI meeting assistants")
        ch.add_message(msg)
        test("MA-3: Message sent", len(ch.get_messages()) >= 1)
    except Exception as e:
        test("MA-3: Message sent", False, str(e)[:60])

    # MA-3: Second message
    try:
        msg2 = Message("product_architect", "integration_test_ch", "inform",
                         "Acknowledged, ready for requirements")
        ch.add_message(msg2)
        test("MA-3: Multi-agent messaging works", len(ch.get_messages()) >= 2)
    except Exception as e:
        test("MA-3: Multi-agent messaging works", False, str(e)[:60])

    # MA-7: Interaction Modes
    try:
        from interaction_modes import InteractionEngine
        ie = InteractionEngine()
        session, errors = ie.start_session(
            mode="brainstorm",
            topic="AI meeting assistant features",
            participants=["strategy_lead", "product_architect"])
        test("MA-7: Brainstorm session started",
             session is not None and len(errors) == 0,
             str(errors) if errors else str(type(session)))
    except Exception as e:
        test("MA-7: Brainstorm session started", False, str(e)[:60])

    # MA-8: Behavior Rules
    try:
        from behavior_guard import BehaviorGuard
        guard = BehaviorGuard()
        result = guard.check("strategy_lead", "message", {
            "confidence": 0.8,
            "presented_as_certain": False,
        })
        test("MA-8: Clean action passes", result["allowed"])
    except Exception as e:
        test("MA-8: Clean action passes", False, str(e)[:60])

    # MA-8: Violation detection
    try:
        result = guard.check("engineering_lead", "decision", {
            "domain": "market_strategy",
            "consulted_owner": False,
        })
        has_violation = len(result["violations"]) > 0
        test("MA-8: Violation detected", has_violation)
    except Exception as e:
        test("MA-8: Violation detected", False, str(e)[:60])

    if verbose:
        print()

    # ══════════════════════════════════════════════════════════════
    # PHASE 4: OUTPUT PRODUCTION (MA-15, MA-11, MA-18)
    # ══════════════════════════════════════════════════════════════
    if verbose:
        print("  ── Phase 4: Output Production ──")

    # MA-15: Quality Gate
    test_output = """## Background

The AI meeting assistant market has grown to an estimated $2.5 billion globally.
Key players include Otter.ai, Fireflies, Grain, and Microsoft Teams built-in features.
Remote and hybrid work adoption has driven 25% year-over-year growth in this segment.

## Key Findings

Enterprise adoption is accelerating with large organizations standardizing on meeting AI.
SMB segment remains underserved with most solutions priced for enterprise budgets.
AI transcription accuracy has reached 95%+ making real-time notes commercially viable.
Integration with productivity tools (Slack, Notion, Asana) is the top requested feature.

## Recommendations

Focus initial product on the SMB segment with a freemium pricing model.
Prioritize integrations with the top 5 productivity tools used by SMB teams.
Target launch within 90 days with core transcription and summary features.
Defer enterprise features (SSO, compliance, custom vocabulary) to version 2.
"""

    try:
        from quality_gate import QualityGate
        qg = QualityGate()
        gate_result = qg.validate(test_output, "strategy_lead", "research",
                                    "e12-market-research-analyst")
        test("MA-15: Output passes quality gate",
             gate_result.passed, f"score={gate_result.score}")
    except Exception as e:
        test("MA-15: Output passes quality gate", False, str(e)[:60])

    # MA-15: Bad output blocked
    try:
        bad_result = qg.validate("", "strategy_lead", "research")
        test("MA-15: Empty output blocked", not bad_result.passed)
    except Exception as e:
        test("MA-15: Empty output blocked", False, str(e)[:60])

    # MA-11: Peer Review
    try:
        from peer_review import PeerReviewEngine
        pre = PeerReviewEngine()
        req, reviewers, errs = pre.request_review(
            "strategy_lead", test_output, "research",
            skill_id="e12-market-research-analyst", domain="market_strategy")
        test("MA-11: Review requested",
             req["status"] == "in_review" and len(reviewers) > 0,
             f"{len(reviewers)} reviewers")
    except Exception as e:
        test("MA-11: Review requested", False, str(e)[:60])

    # MA-11: Submit review
    try:
        if reviewers:
            ok, _ = pre.submit_review(req["id"], reviewers[0][0],
                scores={"accuracy": 8, "completeness": 9, "actionability": 8, "clarity": 9},
                improvements=["Add competitor pricing comparison"])
            verdict, score, _ = pre.compute_verdict(req["id"])
            test("MA-11: Review scored", verdict == "APPROVE", f"verdict={verdict}")
    except Exception as e:
        test("MA-11: Review scored", False, str(e)[:60])

    # MA-18: Internal Competition
    try:
        from internal_competition import CompetitionManager
        cm = CompetitionManager()
        should, num = cm.should_compete(8.0, "high")
        test("MA-18: Competition triggered for $8 task", should and num >= 2)
    except Exception as e:
        test("MA-18: Competition triggered for $8 task", False, str(e)[:60])

    if verbose:
        print()

    # ══════════════════════════════════════════════════════════════
    # PHASE 5: DECISION & RESOLUTION (MA-4, MA-10)
    # ══════════════════════════════════════════════════════════════
    if verbose:
        print("  ── Phase 5: Decision & Resolution ──")

    # MA-4: Decision Log
    try:
        from decision_log import DecisionLog
        dl = DecisionLog()
        dec_id, status = dl.propose("strategy_lead",
            "Product direction: focus on SMB AI meeting assistant",
            "Based on market research showing underserved SMB segment",
            reversibility="reversible", confidence=0.85)
        test("MA-4: Decision proposed", dec_id is not None)
    except Exception as e:
        test("MA-4: Decision proposed", False, str(e)[:60])

    # MA-4: Decide (direct approval by executive)
    try:
        dl.decide(dec_id, "Approved: SMB AI meeting assistant",
                 "Market data supports this direction", decided_by="executive_operator")
        decision = dl.get(dec_id)
        test("MA-4: Decision approved",
             decision is not None and decision.get("status") == "decided",
             str(decision.get("status") if decision else "None"))
    except Exception as e:
        test("MA-4: Decision approved", False, str(e)[:60])

    # MA-10: Conflict Resolution
    try:
        from conflict_resolution import ConflictResolver, new_conflict
        cr = ConflictResolver()
        conflict = new_conflict("position", "Pricing strategy disagreement",
            ["strategy_lead", "growth_revenue_lead"],
            severity="moderate",
            positions={"strategy_lead": "Freemium model", "growth_revenue_lead": "Premium only"},
            evidence={"strategy_lead": ["Market data shows freemium wins in SMB"],
                       "growth_revenue_lead": ["Premium has better unit economics"]})
        result = cr.resolve(conflict)
        test("MA-10: Conflict resolved",
             result["status"] in ("resolved", "escalated"),
             f"winner={result.get('winner')}")
    except Exception as e:
        test("MA-10: Conflict resolved", False, str(e)[:60])

    if verbose:
        print()

    # ══════════════════════════════════════════════════════════════
    # PHASE 6: MEMORY & LEARNING (MA-2, MA-13)
    # ══════════════════════════════════════════════════════════════
    if verbose:
        print("  ── Phase 6: Memory & Learning ──")

    # MA-2: Memory
    try:
        from agent_memory import SharedWorkspaceMemory
        # Provide domain_patterns so strategy_lead has write permission
        dp = {"strategy_lead": ["*"], "executive_operator": ["*"]}
        ws = SharedWorkspaceMemory("integration_test_ws_3", domain_patterns=dp)
        ok, msg = ws.write("market_result", "AI meeting assistants - SMB focus recommended",
                            agent="strategy_lead")
        val = ws.read("market_result")
        entry = ws.read_entry("market_result") if hasattr(ws, "read_entry") else None
        found = ok and ((val is not None and "SMB" in str(val)) or
                        (entry is not None and "SMB" in str(entry)))
        test("MA-2: Memory write/read works", found,
             f"write_ok={ok}, msg={msg}, val={val}")
    except Exception as e:
        test("MA-2: Memory write/read works", False, str(e)[:80])

    # MA-13: Learning Loop
    try:
        from learning_loop import LearningLoop
        ll = LearningLoop()
        lid, is_new, occ = ll.collector.from_decision_outcome(
            "strategy_lead", dec_id, 8, 7,
            "SMB focus decision validated by positive market signals", 0.8)
        test("MA-13: Lesson collected", lid is not None)
    except Exception as e:
        test("MA-13: Lesson collected", False, str(e)[:60])

    # MA-13: Learning cycle
    try:
        cycle = ll.run_cycle()
        test("MA-13: Learning cycle runs",
             "validated" in cycle and "applied" in cycle)
    except Exception as e:
        test("MA-13: Learning cycle runs", False, str(e)[:60])

    if verbose:
        print()

    # ══════════════════════════════════════════════════════════════
    # PHASE 7: FAILURE & RECOVERY (MA-9)
    # ══════════════════════════════════════════════════════════════
    if verbose:
        print("  ── Phase 7: Failure & Recovery ──")

    # MA-9: Failure handling
    try:
        from failure_recovery import FailureRecovery, new_failure
        fr = FailureRecovery()

        # Simulate transient failure with retry
        attempt = 0
        def mock_retry(f):
            nonlocal attempt
            attempt += 1
            return attempt >= 2, "recovered"

        failure = new_failure("task", "API timeout during research",
                               category="transient", agent_id="strategy_lead",
                               skill_id="e12-market-research-analyst")
        result = fr.handle(failure, retry_fn=mock_retry)
        test("MA-9: Transient failure recovered",
             result["outcome"] == "recovered", result.get("outcome"))
    except Exception as e:
        test("MA-9: Transient failure recovered", False, str(e)[:60])

    # MA-9: Cascading isolation
    try:
        cascade = new_failure("task", "Parent task failed",
                                category="cascading",
                                downstream_tasks=["task_002", "task_003"])
        result = fr.handle(cascade)
        test("MA-9: Cascading failure isolated",
             result["outcome"] == "escalated" and "downstream" in result.get("message", ""))
    except Exception as e:
        test("MA-9: Cascading failure isolated", False, str(e)[:60])

    if verbose:
        print()

    # ══════════════════════════════════════════════════════════════
    # PHASE 8: PERFORMANCE & MONITORING (MA-12, MA-14)
    # ══════════════════════════════════════════════════════════════
    if verbose:
        print("  ── Phase 8: Performance & Monitoring ──")

    # MA-12: Performance tracking
    try:
        from agent_performance import PerformanceManager
        pm = PerformanceManager()
        pm.collector.record_review_score("strategy_lead", 8.5)
        pm.collector.record_task_success("strategy_lead")
        pm.collector.record_compliance_pass("strategy_lead")
        report = pm.get_agent_report("strategy_lead")
        test("MA-12: Performance tracked",
             report.get("composite_score") is not None or
             report.get("dimensions") is not None)
    except Exception as e:
        test("MA-12: Performance tracked", False, str(e)[:60])

    # MA-12: Rankings
    try:
        pm.collector.record_review_score("product_architect", 7.5)
        pm.collector.record_task_success("product_architect")
        rankings = pm.scorer.rank_agents()
        test("MA-12: Rankings produced", len(rankings) >= 1)
    except Exception as e:
        test("MA-12: Rankings produced", False, str(e)[:60])

    # MA-14: System Health
    try:
        from system_health import SystemHealthObserver
        sho = SystemHealthObserver()
        health = sho.check_all()
        test("MA-14: System health checked",
             "composite_score" in health and "status" in health,
             f"status={health.get('status')}")
    except Exception as e:
        test("MA-14: System health checked", False, str(e)[:60])

    # MA-14: All 12 domains scored
    try:
        test("MA-14: All 12 domains scored",
             len(health.get("domain_scores", {})) == 12,
             f"{len(health.get('domain_scores', {}))} domains")
    except Exception as e:
        test("MA-14: All 12 domains scored", False, str(e)[:60])

    if verbose:
        print()

    # ══════════════════════════════════════════════════════════════
    # PHASE 9: HUMAN APPROVAL (MA-16)
    # ══════════════════════════════════════════════════════════════
    if verbose:
        print("  ── Phase 9: Human Approval ──")

    # MA-16: Approval request
    try:
        from human_loop import HumanLoopManager
        hlm = HumanLoopManager()
        aid, pos = hlm.request_approval(
            "cost_override",
            "Plan estimated at $18.50 exceeds $15 threshold",
            "AI meeting assistant research plan requires premium API calls",
            "strategy_lead", priority="high",
            context={"plan_id": "plan_001", "estimated_cost": 18.50})
        test("MA-16: Approval requested", aid is not None)
    except Exception as e:
        test("MA-16: Approval requested", False, str(e)[:60])

    # MA-16: Approve
    try:
        ok, msg = hlm.approve(aid, "One-time override approved for research")
        test("MA-16: Approval processed", ok)
    except Exception as e:
        test("MA-16: Approval processed", False, str(e)[:60])

    if verbose:
        print()

    # ══════════════════════════════════════════════════════════════
    # PHASE 10: CROSS-SYSTEM VERIFICATION
    # ══════════════════════════════════════════════════════════════
    if verbose:
        print("  ── Phase 10: Cross-System Verification ──")

    # Verify MA-4 decisions exist
    try:
        decision = dl.get(dec_id)
        test("Cross: Decisions logged across workflow",
             decision is not None and decision.get("status") == "decided")
    except Exception as e:
        test("Cross: Decisions logged across workflow", False, str(e)[:60])

    # Verify MA-19 audit trail
    try:
        audit_path = Path.home() / ".nemoclaw" / "security" / "access-audit.jsonl"
        test("Cross: Security audit trail exists", audit_path.exists())
    except Exception as e:
        test("Cross: Security audit trail exists", False, str(e)[:60])

    # Verify MA-14 snapshot saved
    try:
        snap_path = Path.home() / ".nemoclaw" / "health" / "snapshots.jsonl"
        test("Cross: Health snapshots saved", snap_path.exists())
    except Exception as e:
        test("Cross: Health snapshots saved", False, str(e)[:60])

    # Verify MA-12 metrics persisted
    try:
        pm.save_metrics()
        metrics_path = Path.home() / ".nemoclaw" / "performance" / "agent-metrics.json"
        test("Cross: Performance metrics saved", metrics_path.exists())
    except Exception as e:
        test("Cross: Performance metrics saved", False, str(e)[:60])

    # Verify all imports work together
    try:
        import agent_registry
        import agent_memory
        import agent_messaging
        import decision_log
        import task_decomposer
        import cost_governor
        import interaction_modes
        import behavior_guard
        import failure_recovery
        import conflict_resolution
        import peer_review
        import agent_performance
        import learning_loop
        import system_health
        import quality_gate
        import human_loop
        import context_manager
        import internal_competition
        import access_control
        import web_browser
        test("Cross: All 19 MA modules + browser bridge import cleanly", True)
    except Exception as e:
        test("Cross: All 19 MA modules + browser bridge import cleanly", False, str(e)[:60])

    if verbose:
        print()

    # ══════════════════════════════════════════════════════════════
    # PHASE 11: BROWSER AUTOMATION (PinchTab)
    # ══════════════════════════════════════════════════════════════
    if verbose:
        print("  ── Phase 11: Browser Automation ──")

    # MA-19: Web access domain exists
    try:
        from access_control import AccessController, ACCESS_DOMAINS
        test("MA-19: Web access domain exists", "web" in ACCESS_DOMAINS)
    except Exception as e:
        test("MA-19: Web access domain exists", False, str(e)[:60])

    # MA-19: Growth lead has web navigate permission
    try:
        ac_web = AccessController()
        r_web = ac_web.check_access("growth_revenue_lead", "web", "navigate")
        test("MA-19: Growth lead web navigate OK", r_web.granted)
    except Exception as e:
        test("MA-19: Growth lead web navigate OK", False, str(e)[:60])

    # MA-19: Engineering lead blocked from web click
    try:
        r_eng_web = ac_web.check_access("engineering_lead", "web", "click")
        test("MA-19: Engineering web click blocked", not r_eng_web.granted)
    except Exception as e:
        test("MA-19: Engineering web click blocked", False, str(e)[:60])

    # MA-8: Web safety rules exist
    try:
        from behavior_guard import BehaviorGuard, RULES
        web_rules = [r for r in RULES if r.startswith("web_")]
        test("MA-8: 4 web safety rules defined", len(web_rules) == 4)
    except Exception as e:
        test("MA-8: 4 web safety rules defined", False, str(e)[:60])

    # MA-8: Payment form blocked
    try:
        bg_web = BehaviorGuard()
        r_pay = bg_web.check("growth_revenue_lead", "task", {
            "web_action": True,
            "web_form_fields": ["name", "credit_card_number", "cvv"],
        })
        has_payment = any(v["rule"] == "web_never_submit_payment" for v in r_pay["violations"])
        test("MA-8: Payment form blocked", has_payment)
    except Exception as e:
        test("MA-8: Payment form blocked", False, str(e)[:60])

    # MA-8: Screenshot before submit enforced
    try:
        r_ss = bg_web.check("narrative_content_lead", "task", {
            "web_action": True,
            "web_is_form_submit": True,
            "web_screenshot_taken": False,
        })
        has_ss = any(v["rule"] == "web_screenshot_before_submit" for v in r_ss["violations"])
        test("MA-8: Screenshot before submit enforced", has_ss)
    except Exception as e:
        test("MA-8: Screenshot before submit enforced", False, str(e)[:60])

    # MA-14: Browser health domain exists
    try:
        from system_health import HEALTH_DOMAINS as HD
        test("MA-14: Browser health domain exists", "browser" in HD)
    except Exception as e:
        test("MA-14: Browser health domain exists", False, str(e)[:60])

    # MA-14: Browser health check runs
    try:
        from system_health import DomainChecker
        dc = DomainChecker()
        b_score, b_count, b_notes = dc.check_browser()
        test("MA-14: Browser health check runs", 0 <= b_score <= 1.0)
    except Exception as e:
        test("MA-14: Browser health check runs", False, str(e)[:60])

    # MA-6: Browser budgets defined
    try:
        from cost_governor import BROWSER_BUDGETS, AgentLedger
        test("MA-6: Browser budgets defined", len(BROWSER_BUDGETS) == 4)
    except Exception as e:
        test("MA-6: Browser budgets defined", False, str(e)[:60])

    # MA-6: Browser action tracking works
    try:
        bl = AgentLedger()
        bl.record_browser("integration_test_agent", "navigate", "plan_int", "task_int")
        usage = bl.get_browser_usage("integration_test_agent")
        test("MA-6: Browser action tracking works", usage["total"] >= 1)
    except Exception as e:
        test("MA-6: Browser action tracking works", False, str(e)[:60])

    # Bridge: PinchTabClient importable
    try:
        from web_browser import PinchTabClient
        client = PinchTabClient(agent_id="integration_test")
        test("Bridge: PinchTabClient importable", True)
    except Exception as e:
        test("Bridge: PinchTabClient importable", False, str(e)[:60])

    # Bridge: Health check returns tuple
    try:
        ok, result = client.health()
        test("Bridge: Health returns (bool, data) tuple",
             isinstance(ok, bool) and result is not None)
    except Exception as e:
        test("Bridge: Health returns (bool, data) tuple", False, str(e)[:60])

    # Config: pinchtab-config.yaml exists
    try:
        import yaml as yaml_mod
        config_path = Path.home() / "nemoclaw-local-foundation" / "config" / "pinchtab-config.yaml"
        test("Config: pinchtab-config.yaml exists", config_path.exists())
    except Exception as e:
        test("Config: pinchtab-config.yaml exists", False, str(e)[:60])

    if verbose:
        print()

    # ══════════════════════════════════════════════════════════════
    # Phase 12: GAMIFICATION ENGINE
    # ══════════════════════════════════════════════════════════════
    if verbose:
        print(f"\n  Phase 12 — Gamification Engine")

    try:
        from agent_performance import (
            PerformanceManager, MetricsCollector, PerformanceScorer,
            TrendTracker, GamificationEngine, ACHIEVEMENT_DEFS,
        )

        # Build a performance manager with mock data
        pm = PerformanceManager()
        pm.collector.record_review_score("strategy_lead", 8.5)
        pm.collector.record_task_duration("strategy_lead", 30, 25)
        pm.collector.record_cost_efficiency("strategy_lead", 0.05, 0.04)
        pm.collector.record_task_success("strategy_lead")
        pm.collector.record_compliance_pass("strategy_lead")

        pm.collector.record_review_score("sales_outreach_lead", 9.0)
        pm.collector.record_task_duration("sales_outreach_lead", 20, 15)
        pm.collector.record_cost_efficiency("sales_outreach_lead", 0.03, 0.02)
        pm.collector.record_task_success("sales_outreach_lead")
        pm.collector.record_compliance_pass("sales_outreach_lead")

        # Need 3+ samples for sufficient data
        for _ in range(3):
            pm.collector.record_review_score("strategy_lead", 8.0)
            pm.collector.record_review_score("sales_outreach_lead", 8.5)

        test("Gamification: Engine instantiated",
             isinstance(GamificationEngine(pm), GamificationEngine))

        ge = GamificationEngine(pm)
        # Clear stale state for clean test
        ge.achievements = {}
        ge.leaderboard = {"rankings": [], "last_updated": None, "employee_of_month": None, "monthly_scores": {}}

        # Test rankings
        rankings = ge.update_rankings()
        test("Gamification: Rankings produced",
             isinstance(rankings, list) and len(rankings) >= 2)

        # Test Employee of Month
        eom = ge.determine_employee_of_month()
        test("Gamification: Employee of Month selected",
             eom is not None and "agent_id" in eom and "score" in eom)

        # Test achievement granting
        granted = ge.grant_achievement("strategy_lead", "first_task")
        test("Gamification: Achievement granted",
             granted is True)

        # Test rivalry
        rivalry = ge.get_rivalry("strategy_lead", "sales_outreach_lead")
        test("Gamification: Rivalry comparison works",
             rivalry is not None and "dimensions" in rivalry and "overall" in rivalry)

        # Test dashboard
        dash = ge.get_dashboard()
        test("Gamification: Dashboard produced",
             "leaderboard" in dash and "employee_of_month" in dash and "achievements" in dash)

        test("Gamification: Achievement defs complete",
             len(ACHIEVEMENT_DEFS) >= 10)

    except Exception as e:
        test("Gamification: Engine test", False, str(e)[:80])

    # ══════════════════════════════════════════════════════════════
    # SUMMARY
    # ══════════════════════════════════════════════════════════════
    if verbose:
        print(f"  {'═' * 56}")
        status = "PASS ✅" if tp == tt else f"PARTIAL ({tp}/{tt})"
        print(f"  Integration Test: {status}")
        print(f"  Systems tested: 19 + browser + gamification")
        print(f"  Phases completed: 11")
        print(f"  Checks: {tp}/{tt} passed")
        print(f"  {'═' * 56}")

    return tp, tt, results


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="NemoClaw Integration Test (MA-20)")
    parser.add_argument("--test", action="store_true", help="Run integration test")
    parser.add_argument("--full", action="store_true", help="Run with verbose output")
    parser.add_argument("--summary", action="store_true", help="Quick pass/fail summary")
    args = parser.parse_args()

    if args.test or args.full:
        passed, total, results = run_integration_test(verbose=True)
        sys.exit(0 if passed == total else 1)

    elif args.summary:
        passed, total, results = run_integration_test(verbose=False)
        failed = [r for r in results if not r["passed"]]

        if passed == total:
            print(f"  ✅ PASS: {passed}/{total} checks across 19 MA systems + browser")
        else:
            print(f"  ❌ PARTIAL: {passed}/{total} checks")
            print(f"  Failures:")
            for f in failed:
                print(f"    ❌ {f['name']}: {f['detail']}")

        sys.exit(0 if passed == total else 1)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()

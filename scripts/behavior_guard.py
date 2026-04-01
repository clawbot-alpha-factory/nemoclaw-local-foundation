#!/usr/bin/env python3
"""
NemoClaw Behavior Rules & Role Integrity v1.0 (MA-8)

Behavioral enforcement layer for multi-agent system:
- 7 rule categories with numeric thresholds
- Graduated enforcement: warn 3x then block
- Per-rule severity (WARN-only vs blockable)
- Per-agent compliance scoring
- Auto-escalation after repeated violations
- Cross-mode exceptions (brainstorm = relaxed)
- Historical consistency tracking
- MA-4 decision log integration

Usage:
  python3 scripts/behavior_guard.py --test
  python3 scripts/behavior_guard.py --rules
  python3 scripts/behavior_guard.py --compliance
  python3 scripts/behavior_guard.py --violations
"""

import argparse
import json
import os
import sys
import uuid
import yaml
from datetime import datetime, timezone
from pathlib import Path

REPO = Path.home() / "nemoclaw-local-foundation"
GUARD_DIR = Path.home() / ".nemoclaw" / "behavior"
VIOLATIONS_PATH = GUARD_DIR / "violations.jsonl"
COMPLIANCE_PATH = GUARD_DIR / "compliance.json"
POSITIONS_PATH = GUARD_DIR / "position-history.json"

# Graduated enforcement
WARN_BEFORE_BLOCK = 3  # warn N times per agent per rule, then block
AUTO_ESCALATE_THRESHOLD = 5  # escalate after N total violations per session

# ═══════════════════════════════════════════════════════════════════════════════
# RULE DEFINITIONS
# ═══════════════════════════════════════════════════════════════════════════════

RULES = {
    # ── IDENTITY ──
    "identity_role_drift": {
        "category": "identity",
        "description": "Agent must not act outside their domain boundaries",
        "severity": "blockable",  # blockable | warn_only
        "check": "domain_check",
    },
    "identity_capability_claim": {
        "category": "identity",
        "description": "Agent must not claim capabilities they don't own",
        "severity": "blockable",
        "check": "capability_check",
    },

    # ── CONSISTENCY ──
    "consistency_position_reversal": {
        "category": "consistency",
        "description": "Agent must acknowledge when reversing a previous position",
        "severity": "warn_only",
        "check": "position_reversal_check",
    },
    "consistency_contradiction": {
        "category": "consistency",
        "description": "Agent must not contradict own prior statements without explanation",
        "severity": "warn_only",
        "check": "contradiction_check",
    },

    # ── CONSULTATION ──
    "consultation_cross_domain": {
        "category": "consultation",
        "description": "Agent must consult domain owner before cross-domain decisions",
        "severity": "blockable",
        "check": "cross_domain_check",
    },

    # ── CONFIDENCE ──
    "confidence_misrepresentation": {
        "category": "confidence",
        "description": "Agent must not present low-confidence (<0.5) conclusions as certain",
        "severity": "blockable",
        "threshold": 0.5,
        "check": "confidence_check",
    },
    "confidence_disclosure": {
        "category": "confidence",
        "description": "Agent must disclose confidence level on strategic recommendations",
        "severity": "warn_only",
        "check": "confidence_disclosure_check",
    },

    # ── PROPORTIONALITY ──
    "proportionality_domination": {
        "category": "proportionality",
        "description": "Agent must not exceed 60% of contributions in multi-agent interactions",
        "severity": "warn_only",
        "threshold_warn": 0.60,
        "threshold_block": 0.75,
        "check": "proportionality_check",
        "mode_exceptions": ["brainstorm"],  # relaxed in brainstorm
    },

    # ── ESCALATION ──
    "escalation_irreversible": {
        "category": "escalation",
        "description": "Agent must escalate irreversible decisions to higher authority",
        "severity": "blockable",
        "check": "irreversible_escalation_check",
    },
    "escalation_budget": {
        "category": "escalation",
        "description": "Agent must escalate decisions exceeding $5 cost impact",
        "severity": "blockable",
        "threshold": 5.0,
        "check": "budget_escalation_check",
    },

    # ── TRANSPARENCY ──
    "transparency_self_critique": {
        "category": "transparency",
        "description": "Agent must disclose when critiquing own work",
        "severity": "warn_only",
        "check": "self_critique_check",
    },
    "transparency_conflict_of_interest": {
        "category": "transparency",
        "description": "Agent must disclose conflicts of interest",
        "severity": "warn_only",
        "check": "conflict_of_interest_check",
    },

    # ── WEB SAFETY ──
    "web_never_submit_payment": {
        "category": "web_safety",
        "description": "Agent must never submit forms containing payment fields via browser",
        "severity": "blockable",
        "check": "web_payment_check",
    },
    "web_never_delete_production": {
        "category": "web_safety",
        "description": "Agent must never perform destructive actions (delete, remove, destroy) on production systems via browser",
        "severity": "blockable",
        "check": "web_destructive_check",
    },
    "web_screenshot_before_submit": {
        "category": "web_safety",
        "description": "Agent must capture screenshot evidence before submitting any form via browser",
        "severity": "blockable",
        "check": "web_screenshot_check",
    },
    "web_first_login_approval": {
        "category": "web_safety",
        "description": "First login to any new service via browser requires MA-16 human approval",
        "severity": "blockable",
        "check": "web_first_login_check",
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
# POSITION HISTORY (for consistency checks)
# ═══════════════════════════════════════════════════════════════════════════════

class PositionHistory:
    """Tracks all agent positions for consistency checking."""

    def __init__(self):
        self.positions = {}  # agent_id → [{topic, position, timestamp, decision_id}]
        self._load()

    def _load(self):
        GUARD_DIR.mkdir(parents=True, exist_ok=True)
        if POSITIONS_PATH.exists():
            try:
                with open(POSITIONS_PATH) as f:
                    self.positions = json.load(f)
            except (json.JSONDecodeError, IOError):
                self.positions = {}

    def _save(self):
        GUARD_DIR.mkdir(parents=True, exist_ok=True)
        with open(POSITIONS_PATH, "w") as f:
            json.dump(self.positions, f, indent=2)

    def record(self, agent_id, topic, position, decision_id=None):
        """Record an agent's position on a topic."""
        if agent_id not in self.positions:
            self.positions[agent_id] = []
        self.positions[agent_id].append({
            "topic": topic,
            "position": position,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "decision_id": decision_id,
        })
        # Keep last 200 positions per agent
        if len(self.positions[agent_id]) > 200:
            self.positions[agent_id] = self.positions[agent_id][-200:]
        self._save()

    def get_positions(self, agent_id, topic=None):
        """Get all positions for an agent, optionally filtered by topic."""
        entries = self.positions.get(agent_id, [])
        if topic:
            entries = [e for e in entries if topic.lower() in e.get("topic", "").lower()]
        return entries

    def check_reversal(self, agent_id, topic, new_position, acknowledged=False):
        """Check if new position contradicts previous ones.

        Returns: (is_reversal: bool, previous_positions: list)
        """
        prev = self.get_positions(agent_id, topic)
        if not prev:
            return False, []

        # Simple check: if any previous position on same topic differs
        reversals = []
        for p in prev:
            if p["position"].lower().strip() != new_position.lower().strip():
                reversals.append(p)

        return len(reversals) > 0, reversals


# ═══════════════════════════════════════════════════════════════════════════════
# VIOLATION TRACKER
# ═══════════════════════════════════════════════════════════════════════════════

class ViolationTracker:
    """Tracks violations per agent per rule with graduated enforcement."""

    def __init__(self):
        self.violations = {}  # agent_id → {rule_id → count}
        self.session_total = {}  # agent_id → total violations this session
        self.all_violations = []  # full log

    def record(self, agent_id, rule_id, action_type, context=None, decision_id=None):
        """Record a violation.

        Returns: (enforcement: "warn"|"block"|"escalate", count: int)
        """
        if agent_id not in self.violations:
            self.violations[agent_id] = {}
            self.session_total[agent_id] = 0

        if rule_id not in self.violations[agent_id]:
            self.violations[agent_id][rule_id] = 0

        self.violations[agent_id][rule_id] += 1
        self.session_total[agent_id] += 1
        count = self.violations[agent_id][rule_id]

        rule = RULES.get(rule_id, {})
        severity = rule.get("severity", "warn_only")

        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": agent_id,
            "rule": rule_id,
            "category": rule.get("category", "unknown"),
            "action_type": action_type,
            "violation_count": count,
            "context": context,
            "decision_id": decision_id,
        }

        # Determine enforcement level
        if self.session_total[agent_id] >= AUTO_ESCALATE_THRESHOLD:
            enforcement = "escalate"
        elif severity == "blockable" and count > WARN_BEFORE_BLOCK:
            enforcement = "block"
        elif severity == "warn_only":
            enforcement = "warn"
        elif count <= WARN_BEFORE_BLOCK:
            enforcement = "warn"
        else:
            enforcement = "block"

        entry["enforcement"] = enforcement
        self.all_violations.append(entry)

        # Persist to disk
        self._log_violation(entry)

        # Log to MA-4 decision system
        if enforcement in ("block", "escalate"):
            self._log_to_decisions(entry)

        return enforcement, count

    def get_agent_violations(self, agent_id):
        """Get violation counts for an agent."""
        return self.violations.get(agent_id, {})

    def get_session_total(self, agent_id):
        """Get total violations this session."""
        return self.session_total.get(agent_id, 0)

    def get_compliance_score(self, agent_id, total_actions=None):
        """Calculate compliance score (0.0 - 1.0).

        Score = 1.0 - (violations / max(total_actions, 10))
        """
        total_v = sum(self.violations.get(agent_id, {}).values())
        actions = max(total_actions or 10, 10)
        return round(max(0.0, 1.0 - (total_v / actions)), 3)

    def _log_violation(self, entry):
        """Append violation to persistent log."""
        GUARD_DIR.mkdir(parents=True, exist_ok=True)
        with open(VIOLATIONS_PATH, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def _log_to_decisions(self, entry):
        """Log block/escalate violations to MA-4."""
        try:
            from decision_log import DecisionLog
            dl = DecisionLog()
            title = f"Behavior violation: {entry['rule']} by {entry['agent']}"
            desc = (
                f"Rule: {entry['rule']} ({entry['category']})\n"
                f"Agent: {entry['agent']}\n"
                f"Enforcement: {entry['enforcement']}\n"
                f"Count: {entry['violation_count']}\n"
                f"Context: {entry.get('context', 'N/A')}\n"
            )
            if entry.get("decision_id"):
                desc += f"Related decision: {entry['decision_id']}\n"

            dec_id, _ = dl.propose("executive_operator", title, desc,
                                    reversibility="irreversible", confidence=0.95)
            dl.decide(dec_id, f"Violation logged: {entry['enforcement']}",
                     f"Auto-logged by BehaviorGuard", decided_by="executive_operator")
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════════════════════
# BEHAVIOR GUARD (main enforcement engine)
# ═══════════════════════════════════════════════════════════════════════════════

class BehaviorGuard:
    """Main behavioral enforcement engine.

    Usage:
        guard = BehaviorGuard()
        result = guard.check(agent_id, action_type, context)
        # result = {"allowed": bool, "enforcement": str, "violations": [...]}
    """

    def __init__(self):
        self.tracker = ViolationTracker()
        self.history = PositionHistory()
        self._agent_domains = None
        self._agent_caps = None
        self._agent_authority = None

    def _load_agent_data(self):
        """Load agent schema data (cached)."""
        if self._agent_domains is not None:
            return

        try:
            with open(REPO / "config" / "agents" / "agent-schema.yaml") as f:
                schema = yaml.safe_load(f)
            self._agent_domains = schema.get("domain_boundaries", {})
            self._agent_authority = {}
            for agent in schema.get("agents", []):
                self._agent_authority[agent["agent_id"]] = agent.get("authority_level", 3)
        except Exception:
            self._agent_domains = {}
            self._agent_authority = {}

        try:
            with open(REPO / "config" / "agents" / "capability-registry.yaml") as f:
                reg = yaml.safe_load(f)
            self._agent_caps = {}
            for cap_name, cap in reg.get("capabilities", {}).items():
                owner = cap.get("owned_by")
                if owner not in self._agent_caps:
                    self._agent_caps[owner] = set()
                self._agent_caps[owner].add(cap_name)
        except Exception:
            self._agent_caps = {}

    def check(self, agent_id, action_type, context=None):
        """Check an agent's action against all applicable rules.

        Args:
            agent_id: the acting agent
            action_type: type of action (e.g., "message", "decision", "critique", "task")
            context: dict with action-specific data:
                - domain: target domain
                - capability: claimed capability
                - confidence: confidence level (0.0-1.0)
                - topic: topic being discussed
                - position: agent's position on the topic
                - acknowledged_reversal: bool
                - interaction_mode: current mode (brainstorm, debate, etc.)
                - contribution_ratio: agent's % of contributions (0.0-1.0)
                - is_irreversible: bool
                - cost_impact: float
                - critiquing_own_work: bool
                - has_conflict_of_interest: bool
                - decision_id: related MA-4 decision
                - confidence_disclosed: bool

        Returns: dict with:
            - allowed: bool
            - enforcement: "pass"|"warn"|"block"|"escalate"
            - violations: list of {rule, message, enforcement}
        """
        self._load_agent_data()
        ctx = context or {}
        violations = []
        decision_id = ctx.get("decision_id")
        mode = ctx.get("interaction_mode")

        # ── IDENTITY CHECKS ──
        if ctx.get("domain"):
            v = self._check_domain(agent_id, ctx["domain"])
            if v:
                violations.append(v)

        if ctx.get("capability"):
            v = self._check_capability(agent_id, ctx["capability"])
            if v:
                violations.append(v)

        # ── CONSISTENCY CHECKS ──
        if ctx.get("topic") and ctx.get("position"):
            v = self._check_consistency(agent_id, ctx["topic"], ctx["position"],
                                         ctx.get("acknowledged_reversal", False))
            if v:
                violations.append(v)

        # ── CONSULTATION CHECKS ──
        if ctx.get("domain") and action_type == "decision":
            v = self._check_consultation(agent_id, ctx["domain"], ctx.get("consulted_owner", False))
            if v:
                violations.append(v)

        # ── CONFIDENCE CHECKS ──
        if ctx.get("confidence") is not None:
            v = self._check_confidence(agent_id, ctx["confidence"],
                                        ctx.get("presented_as_certain", False))
            if v:
                violations.append(v)

        if action_type in ("decision", "recommendation") and not ctx.get("confidence_disclosed", True):
            violations.append({
                "rule": "confidence_disclosure",
                "message": f"{agent_id} did not disclose confidence on strategic recommendation",
            })

        # ── PROPORTIONALITY CHECKS ──
        if ctx.get("contribution_ratio") is not None:
            v = self._check_proportionality(agent_id, ctx["contribution_ratio"], mode)
            if v:
                violations.append(v)

        # ── ESCALATION CHECKS ──
        if ctx.get("is_irreversible"):
            v = self._check_irreversible_escalation(agent_id, ctx.get("escalated", False))
            if v:
                violations.append(v)

        if ctx.get("cost_impact") is not None:
            v = self._check_budget_escalation(agent_id, ctx["cost_impact"],
                                               ctx.get("escalated", False))
            if v:
                violations.append(v)

        # ── TRANSPARENCY CHECKS ──
        if ctx.get("critiquing_own_work"):
            v = self._check_self_critique(agent_id, ctx.get("disclosed_self_critique", False))
            if v:
                violations.append(v)

        if ctx.get("has_conflict_of_interest"):
            v = self._check_conflict_of_interest(agent_id,
                                                   ctx.get("disclosed_conflict", False))
            if v:
                violations.append(v)

        # ── WEB SAFETY CHECKS ──
        if ctx.get("web_action"):
            # Payment form check
            if ctx.get("web_form_fields"):
                v = self._check_web_payment(agent_id, ctx["web_form_fields"])
                if v:
                    violations.append(v)

            # Destructive action check
            if ctx.get("web_action_label"):
                v = self._check_web_destructive(agent_id, ctx["web_action_label"])
                if v:
                    violations.append(v)

            # Screenshot before submit check
            if ctx.get("web_is_form_submit") and not ctx.get("web_screenshot_taken"):
                v = self._check_web_screenshot(agent_id, False)
                if v:
                    violations.append(v)

            # First login approval check
            if ctx.get("web_is_login") and ctx.get("web_service_domain"):
                v = self._check_web_first_login(
                    agent_id, ctx["web_service_domain"],
                    ctx.get("web_known_services", set()))
                if v:
                    violations.append(v)

        # ── PROCESS VIOLATIONS ──
        if not violations:
            return {"allowed": True, "enforcement": "pass", "violations": []}

        # Record and determine enforcement
        max_enforcement = "warn"
        processed = []
        for v in violations:
            rule_id = v["rule"]
            enforcement, count = self.tracker.record(
                agent_id, rule_id, action_type,
                context=v["message"], decision_id=decision_id)

            if enforcement == "escalate":
                max_enforcement = "escalate"
            elif enforcement == "block" and max_enforcement != "escalate":
                max_enforcement = "block"

            processed.append({
                "rule": rule_id,
                "message": v["message"],
                "enforcement": enforcement,
                "count": count,
            })

        allowed = max_enforcement == "warn"

        return {
            "allowed": allowed,
            "enforcement": max_enforcement,
            "violations": processed,
        }

    # ── INDIVIDUAL CHECK METHODS ──

    def _check_domain(self, agent_id, target_domain):
        domains = self._agent_domains.get(agent_id, {})
        allowed = domains.get("allowed_domains", [])
        if allowed and target_domain not in allowed and "*" not in allowed:
            return {
                "rule": "identity_role_drift",
                "message": f"{agent_id} acting in domain '{target_domain}' outside boundaries {allowed}",
            }
        return None

    def _check_capability(self, agent_id, capability):
        caps = self._agent_caps.get(agent_id, set())
        if capability not in caps:
            return {
                "rule": "identity_capability_claim",
                "message": f"{agent_id} claiming capability '{capability}' not in their registry",
            }
        return None

    def _check_consistency(self, agent_id, topic, new_position, acknowledged):
        is_reversal, prev = self.history.check_reversal(agent_id, topic, new_position)
        if is_reversal and not acknowledged:
            prev_summary = prev[-1]["position"][:60] if prev else "unknown"
            return {
                "rule": "consistency_position_reversal",
                "message": f"{agent_id} reversed position on '{topic}' without acknowledgment (was: '{prev_summary}')",
            }
        # Record the new position
        self.history.record(agent_id, topic, new_position)
        return None

    def _check_consultation(self, agent_id, domain, consulted):
        if consulted:
            return None
        # Check if agent owns this domain
        own_domains = self._agent_domains.get(agent_id, {}).get("allowed_domains", [])
        if domain in own_domains or "*" in own_domains:
            return None
        return {
            "rule": "consultation_cross_domain",
            "message": f"{agent_id} making decision in domain '{domain}' without consulting owner",
        }

    def _check_confidence(self, agent_id, confidence, presented_as_certain):
        threshold = RULES["confidence_misrepresentation"]["threshold"]
        if confidence < threshold and presented_as_certain:
            return {
                "rule": "confidence_misrepresentation",
                "message": f"{agent_id} presenting {confidence:.1%} confidence as certain (threshold: {threshold:.0%})",
            }
        return None

    def _check_proportionality(self, agent_id, ratio, mode=None):
        rule = RULES["proportionality_domination"]
        # Check mode exceptions
        if mode and mode in rule.get("mode_exceptions", []):
            return None

        if ratio >= rule["threshold_block"]:
            return {
                "rule": "proportionality_domination",
                "message": f"{agent_id} dominating interaction at {ratio:.0%} (block threshold: {rule['threshold_block']:.0%})",
            }
        elif ratio >= rule["threshold_warn"]:
            return {
                "rule": "proportionality_domination",
                "message": f"{agent_id} approaching domination at {ratio:.0%} (warn threshold: {rule['threshold_warn']:.0%})",
            }
        return None

    def _check_irreversible_escalation(self, agent_id, escalated):
        if escalated:
            return None
        level = self._agent_authority.get(agent_id, 3)
        if level > 1:  # only level 1 can make irreversible decisions alone
            return {
                "rule": "escalation_irreversible",
                "message": f"{agent_id} (level {level}) making irreversible decision without escalation",
            }
        return None

    def _check_budget_escalation(self, agent_id, cost_impact, escalated):
        threshold = RULES["escalation_budget"]["threshold"]
        if cost_impact > threshold and not escalated:
            return {
                "rule": "escalation_budget",
                "message": f"{agent_id} decision with ${cost_impact:.2f} impact (>${threshold:.2f}) without escalation",
            }
        return None

    def _check_self_critique(self, agent_id, disclosed):
        if not disclosed:
            return {
                "rule": "transparency_self_critique",
                "message": f"{agent_id} critiquing own work without disclosure",
            }
        return None

    def _check_conflict_of_interest(self, agent_id, disclosed):
        if not disclosed:
            return {
                "rule": "transparency_conflict_of_interest",
                "message": f"{agent_id} has undisclosed conflict of interest",
            }
        return None

    # ── WEB SAFETY CHECK METHODS ──

    def _check_web_payment(self, agent_id, form_fields):
        """Check if form contains payment-related fields."""
        payment_keywords = ["card", "cvv", "cvc", "expir", "payment", "billing",
                           "credit", "debit", "account_number", "routing_number",
                           "iban", "swift", "paypal", "stripe"]
        if form_fields:
            fields_lower = " ".join(str(f).lower() for f in form_fields)
            for kw in payment_keywords:
                if kw in fields_lower:
                    return {
                        "rule": "web_never_submit_payment",
                        "message": f"{agent_id} attempting to submit form with payment field '{kw}' via browser",
                    }
        return None

    def _check_web_destructive(self, agent_id, web_action_label):
        """Check if browser action is destructive."""
        destructive_keywords = ["delete", "remove", "destroy", "drop", "purge",
                               "erase", "wipe", "unsubscribe", "cancel_account",
                               "close_account", "terminate"]
        if web_action_label:
            label_lower = web_action_label.lower()
            for kw in destructive_keywords:
                if kw in label_lower:
                    return {
                        "rule": "web_never_delete_production",
                        "message": f"{agent_id} attempting destructive action '{web_action_label}' via browser",
                    }
        return None

    def _check_web_screenshot(self, agent_id, has_screenshot):
        """Check if screenshot was taken before form submission."""
        if not has_screenshot:
            return {
                "rule": "web_screenshot_before_submit",
                "message": f"{agent_id} submitting form via browser without prior screenshot evidence",
            }
        return None

    def _check_web_first_login(self, agent_id, service_domain, known_services=None):
        """Check if this is a first login to a new service."""
        known = known_services or set()
        if service_domain and service_domain not in known:
            return {
                "rule": "web_first_login_approval",
                "message": f"{agent_id} first login to '{service_domain}' requires MA-16 human approval",
            }
        return None

    # ── COMPLIANCE REPORTING ──

    def get_compliance(self, agent_id=None):
        """Get compliance scores for one or all agents."""
        self._load_agent_data()
        agents = [agent_id] if agent_id else list(self._agent_authority.keys())

        scores = {}
        for aid in agents:
            violations = self.tracker.get_agent_violations(aid)
            total_v = sum(violations.values())
            score = self.tracker.get_compliance_score(aid)
            scores[aid] = {
                "compliance_score": score,
                "total_violations": total_v,
                "by_rule": violations,
                "session_total": self.tracker.get_session_total(aid),
            }
        return scores


# ═══════════════════════════════════════════════════════════════════════════════
# TESTS
# ═══════════════════════════════════════════════════════════════════════════════

def run_tests():
    print("=" * 60)
    print("  MA-8 Behavior Rules & Role Integrity Tests")
    print("=" * 60)

    tp = 0
    tt = 0

    def test(name, condition, detail=""):
        nonlocal tp, tt
        tt += 1
        if condition:
            tp += 1
            print(f"  ✅ {name}")
        else:
            print(f"  ❌ {name}: {detail}")

    # Test 1: Rules defined
    test("16 rules defined", len(RULES) == 16, f"{len(RULES)}")

    # Test 2: All rules have required fields
    for rule_id, rule in RULES.items():
        has_fields = all(k in rule for k in ["category", "description", "severity", "check"])
        if not has_fields:
            test(f"Rule {rule_id} has required fields", False, str(rule.keys()))
            break
    else:
        test("All rules have required fields", True)

    # Test 3: Clean action passes
    guard = BehaviorGuard()
    result = guard.check("strategy_lead", "message", {})
    test("Clean action passes", result["allowed"] and result["enforcement"] == "pass")

    # Test 4: Domain/consultation violation detected
    result = guard.check("engineering_lead", "decision", {
        "domain": "market_strategy",
    })
    has_violation = any(v["rule"] in ("identity_role_drift", "consultation_cross_domain")
                        for v in result["violations"])
    test("Domain violation detected", has_violation and len(result["violations"]) > 0,
         str([v["rule"] for v in result["violations"]]))

    # Test 5: Capability violation detected
    result = guard.check("engineering_lead", "task", {
        "capability": "market_research",
    })
    has_cap = any(v["rule"] == "identity_capability_claim" for v in result["violations"])
    test("Capability violation detected", has_cap)

    # Test 6: Confidence misrepresentation
    result = guard.check("strategy_lead", "recommendation", {
        "confidence": 0.3,
        "presented_as_certain": True,
    })
    has_conf = any(v["rule"] == "confidence_misrepresentation" for v in result["violations"])
    test("Confidence misrepresentation caught", has_conf)

    # Test 7: High confidence OK
    result = guard.check("strategy_lead", "recommendation", {
        "confidence": 0.8,
        "presented_as_certain": True,
    })
    test("High confidence passes", result["allowed"])

    # Test 8: Proportionality warning
    result = guard.check("strategy_lead", "message", {
        "contribution_ratio": 0.65,
        "interaction_mode": "debate",
    })
    has_prop = any(v["rule"] == "proportionality_domination" for v in result["violations"])
    test("Proportionality >60% warned", has_prop)

    # Test 9: Proportionality OK in brainstorm (mode exception)
    result = guard.check("strategy_lead", "message", {
        "contribution_ratio": 0.70,
        "interaction_mode": "brainstorm",
    })
    test("Proportionality relaxed in brainstorm", result["allowed"])

    # Test 10: Irreversible escalation required
    result = guard.check("strategy_lead", "decision", {
        "is_irreversible": True,
        "escalated": False,
    })
    has_esc = any(v["rule"] == "escalation_irreversible" for v in result["violations"])
    test("Irreversible without escalation caught", has_esc)

    # Test 11: Executive can make irreversible decisions alone
    guard2 = BehaviorGuard()
    result = guard2.check("executive_operator", "decision", {
        "is_irreversible": True,
        "escalated": False,
    })
    no_esc = not any(v["rule"] == "escalation_irreversible" for v in result["violations"])
    test("Executive bypasses irreversible escalation", no_esc)

    # Test 12: Budget escalation
    guard3 = BehaviorGuard()
    result = guard3.check("product_architect", "decision", {
        "cost_impact": 8.0,
        "escalated": False,
    })
    has_budget = any(v["rule"] == "escalation_budget" for v in result["violations"])
    test("Budget >$5 escalation required", has_budget)

    # Test 13: Self-critique transparency
    guard4 = BehaviorGuard()
    result = guard4.check("strategy_lead", "critique", {
        "critiquing_own_work": True,
        "disclosed_self_critique": False,
    })
    has_sc = any(v["rule"] == "transparency_self_critique" for v in result["violations"])
    test("Self-critique without disclosure caught", has_sc)

    # Test 14: Graduated enforcement (warn → warn → warn → block)
    guard5 = BehaviorGuard()
    for i in range(WARN_BEFORE_BLOCK):
        r = guard5.check("engineering_lead", "task", {"capability": "market_research"})
    test(f"First {WARN_BEFORE_BLOCK} violations = warn", r["enforcement"] == "warn",
         f"got {r['enforcement']} after {WARN_BEFORE_BLOCK} checks")

    # 4th violation should block (blockable rule, count > WARN_BEFORE_BLOCK)
    # But need fresh guard to avoid auto-escalate from accumulated violations
    guard5b = BehaviorGuard()
    for i in range(WARN_BEFORE_BLOCK + 1):
        r = guard5b.check("narrative_content_lead", "task", {"capability": "market_research"})
    test("Violation after warn threshold = block", r["enforcement"] == "block" and not r["allowed"],
         f"got {r['enforcement']}")

    # Test 15: Auto-escalation after threshold
    guard6 = BehaviorGuard()
    for i in range(AUTO_ESCALATE_THRESHOLD):
        guard6.check("product_architect", "decision", {
            "cost_impact": 10.0, "escalated": False
        })
    r = guard6.check("product_architect", "decision", {
        "cost_impact": 10.0, "escalated": False
    })
    test(f"Auto-escalate after {AUTO_ESCALATE_THRESHOLD}+ violations",
         r["enforcement"] == "escalate", f"got {r['enforcement']}")

    # Test 16: Position history — no reversal
    guard7 = BehaviorGuard()
    guard7.history.record("strategy_lead", "pricing", "freemium")
    r = guard7.check("strategy_lead", "message", {
        "topic": "pricing", "position": "freemium",
    })
    test("Consistent position passes", r["allowed"])

    # Test 17: Position reversal detected
    r = guard7.check("strategy_lead", "message", {
        "topic": "pricing", "position": "premium only",
    })
    has_rev = any(v["rule"] == "consistency_position_reversal" for v in r["violations"])
    test("Position reversal detected", has_rev)

    # Test 18: Acknowledged reversal passes
    r = guard7.check("strategy_lead", "message", {
        "topic": "pricing", "position": "enterprise tier",
        "acknowledged_reversal": True,
    })
    no_rev = not any(v["rule"] == "consistency_position_reversal" for v in r["violations"])
    test("Acknowledged reversal passes", no_rev)

    # Test 19: Compliance score
    scores = guard5.get_compliance("engineering_lead")
    score = scores["engineering_lead"]["compliance_score"]
    test("Compliance score calculated", 0.0 <= score <= 1.0, f"score={score}")

    # Test 20: Cross-domain consultation
    guard8 = BehaviorGuard()
    r = guard8.check("engineering_lead", "decision", {
        "domain": "market_strategy",
        "consulted_owner": False,
    })
    has_consult = any(v["rule"] == "consultation_cross_domain" for v in r["violations"])
    test("Cross-domain without consultation caught", has_consult)

    # Test 21: Cross-domain with consultation passes
    guard9 = BehaviorGuard()
    r = guard9.check("engineering_lead", "decision", {
        "domain": "market_strategy",
        "consulted_owner": True,
    })
    no_consult = not any(v["rule"] == "consultation_cross_domain" for v in r["violations"])
    test("Cross-domain with consultation passes", no_consult)

    # Test 22: Confidence disclosure
    guard10 = BehaviorGuard()
    r = guard10.check("strategy_lead", "recommendation", {
        "confidence_disclosed": False,
    })
    has_disc = any(v["rule"] == "confidence_disclosure" for v in r["violations"])
    test("Missing confidence disclosure caught", has_disc)

    # Test 23: Proportionality block at 75%
    guard11 = BehaviorGuard()
    r = guard11.check("strategy_lead", "message", {
        "contribution_ratio": 0.80,
        "interaction_mode": "debate",
    })
    has_block = any(v["rule"] == "proportionality_domination" and "block" in v["message"].lower()
                    for v in r["violations"])
    test("Proportionality >75% uses block-level message", has_block)

    # Test 24: Conflict of interest
    guard12 = BehaviorGuard()
    r = guard12.check("strategy_lead", "decision", {
        "has_conflict_of_interest": True,
        "disclosed_conflict": False,
    })
    has_coi = any(v["rule"] == "transparency_conflict_of_interest" for v in r["violations"])
    test("Undisclosed conflict of interest caught", has_coi)

    # ── Web Safety Rule Tests ──

    # Test: Web payment form blocked
    guard_w1 = BehaviorGuard()
    r = guard_w1.check("growth_revenue_lead", "task", {
        "web_action": True,
        "web_form_fields": ["name", "email", "credit_card_number", "cvv"],
    })
    has_payment = any(v["rule"] == "web_never_submit_payment" for v in r["violations"])
    test("Web: payment form submission blocked", has_payment)

    # Test: Non-payment form allowed
    guard_w2 = BehaviorGuard()
    r = guard_w2.check("growth_revenue_lead", "task", {
        "web_action": True,
        "web_form_fields": ["name", "email", "company"],
    })
    no_payment = not any(v["rule"] == "web_never_submit_payment" for v in r["violations"])
    test("Web: non-payment form passes", no_payment)

    # Test: Destructive action blocked
    guard_w3 = BehaviorGuard()
    r = guard_w3.check("operations_lead", "task", {
        "web_action": True,
        "web_action_label": "Delete All Records",
    })
    has_destructive = any(v["rule"] == "web_never_delete_production" for v in r["violations"])
    test("Web: destructive action blocked", has_destructive)

    # Test: Non-destructive action allowed
    guard_w4 = BehaviorGuard()
    r = guard_w4.check("operations_lead", "task", {
        "web_action": True,
        "web_action_label": "View Dashboard",
    })
    no_destructive = not any(v["rule"] == "web_never_delete_production" for v in r["violations"])
    test("Web: non-destructive action passes", no_destructive)

    # Test: Form submit without screenshot blocked
    guard_w5 = BehaviorGuard()
    r = guard_w5.check("narrative_content_lead", "task", {
        "web_action": True,
        "web_is_form_submit": True,
        "web_screenshot_taken": False,
    })
    has_screenshot = any(v["rule"] == "web_screenshot_before_submit" for v in r["violations"])
    test("Web: form submit without screenshot blocked", has_screenshot)

    # Test: Form submit with screenshot passes
    guard_w6 = BehaviorGuard()
    r = guard_w6.check("narrative_content_lead", "task", {
        "web_action": True,
        "web_is_form_submit": True,
        "web_screenshot_taken": True,
    })
    no_screenshot = not any(v["rule"] == "web_screenshot_before_submit" for v in r["violations"])
    test("Web: form submit with screenshot passes", no_screenshot)

    # Test: First login requires approval
    guard_w7 = BehaviorGuard()
    r = guard_w7.check("growth_revenue_lead", "task", {
        "web_action": True,
        "web_is_login": True,
        "web_service_domain": "linkedin.com",
        "web_known_services": set(),
    })
    has_login = any(v["rule"] == "web_first_login_approval" for v in r["violations"])
    test("Web: first login requires approval", has_login)

    # Test: Known service login passes
    guard_w8 = BehaviorGuard()
    r = guard_w8.check("growth_revenue_lead", "task", {
        "web_action": True,
        "web_is_login": True,
        "web_service_domain": "linkedin.com",
        "web_known_services": {"linkedin.com", "twitter.com"},
    })
    no_login = not any(v["rule"] == "web_first_login_approval" for v in r["violations"])
    test("Web: known service login passes", no_login)

    # Test: Web rules count
    web_rules = [r for r in RULES if r.startswith("web_")]
    test("4 web safety rules defined", len(web_rules) == 4)

    # Test: 8 rule categories total
    categories = set(r["category"] for r in RULES.values())
    test("8 rule categories (including web_safety)", len(categories) == 8 and "web_safety" in categories,
         f"categories={categories}")

    print(f"\n  Results: {tp}/{tt} passed")
    return tp == tt


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="NemoClaw Behavior Guard")
    parser.add_argument("--test", action="store_true", help="Run all tests")
    parser.add_argument("--rules", action="store_true", help="List all rules")
    parser.add_argument("--compliance", action="store_true", help="Show compliance scores")
    parser.add_argument("--violations", action="store_true", help="Show recent violations")
    args = parser.parse_args()

    if args.test:
        success = run_tests()
        sys.exit(0 if success else 1)

    elif args.rules:
        print(f"Behavior Rules ({len(RULES)}):")
        for rule_id, rule in RULES.items():
            sev = "⚠️ WARN" if rule["severity"] == "warn_only" else "🛑 BLOCKABLE"
            threshold = ""
            if "threshold" in rule:
                threshold = f" (threshold: {rule['threshold']})"
            elif "threshold_warn" in rule:
                threshold = f" (warn: {rule['threshold_warn']:.0%}, block: {rule['threshold_block']:.0%})"
            print(f"  [{sev}] {rule_id}")
            print(f"    {rule['description']}{threshold}")
            if rule.get("mode_exceptions"):
                print(f"    Exceptions: {rule['mode_exceptions']}")
            print()

    elif args.compliance:
        guard = BehaviorGuard()
        scores = guard.get_compliance()
        if not scores:
            print("  No compliance data yet.")
        else:
            print(f"  {'Agent':<25s} {'Score':>6s} {'Violations':>11s}")
            print(f"  {'-'*25} {'-'*6} {'-'*11}")
            for agent, data in sorted(scores.items()):
                s = data["compliance_score"]
                v = data["total_violations"]
                icon = "✅" if s >= 0.9 else ("⚠️" if s >= 0.7 else "❌")
                print(f"  {icon} {agent:<23s} {s:>5.1%} {v:>11d}")

    elif args.violations:
        if VIOLATIONS_PATH.exists():
            with open(VIOLATIONS_PATH) as f:
                for line in f:
                    try:
                        v = json.loads(line.strip())
                        ts = v.get("timestamp", "?")[:19]
                        enf = {"warn": "⚠️", "block": "🛑", "escalate": "🚨"}.get(v["enforcement"], "?")
                        print(f"  [{ts}] {enf} {v['agent']}: {v['rule']} ({v['category']}) #{v['violation_count']}")
                    except json.JSONDecodeError:
                        continue
        else:
            print("  No violations yet.")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()

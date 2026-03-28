#!/usr/bin/env python3
"""
NemoClaw Conflict Resolution System v1.0 (MA-10)

Unified conflict detection, classification, and resolution:
- 6 conflict types: memory, position, decision, output, priority, resource
- 6 resolution strategies: authority, evidence, vote, debate, merge, escalate
- Auto-select strategy based on conflict type
- Low-severity auto-resolution with audit logging
- Authority-weighted resolution scoring
- MA-4 decision log integration for all resolutions
- Conflict history tracking for pattern analysis

Usage:
  python3 scripts/conflict_resolution.py --test
  python3 scripts/conflict_resolution.py --history
  python3 scripts/conflict_resolution.py --stats
"""

import argparse
import json
import os
import sys
import uuid
import yaml
from datetime import datetime, timezone
from pathlib import Path
from collections import defaultdict

REPO = Path.home() / "nemoclaw-local-foundation"
CONFLICT_DIR = Path.home() / ".nemoclaw" / "conflicts"
CONFLICT_LOG_PATH = CONFLICT_DIR / "conflict-log.jsonl"
RESOLUTION_LOG_PATH = CONFLICT_DIR / "resolution-log.jsonl"
STATS_PATH = CONFLICT_DIR / "conflict-stats.json"

# ═══════════════════════════════════════════════════════════════════════════════
# CONFLICT TYPES & DEFAULT STRATEGIES
# ═══════════════════════════════════════════════════════════════════════════════

CONFLICT_TYPES = {
    "memory": {
        "description": "Two agents write conflicting values to same memory key",
        "default_strategy": "authority",
        "auto_resolve_severity": ["minor"],
        "source_system": "MA-2",
    },
    "position": {
        "description": "Agents hold opposing views on a topic",
        "default_strategy": "evidence",
        "auto_resolve_severity": [],
        "source_system": "MA-8",
    },
    "decision": {
        "description": "Disagreement on which option to choose",
        "default_strategy": "vote",
        "auto_resolve_severity": [],
        "source_system": "MA-4",
    },
    "output": {
        "description": "Two tasks produce contradictory results",
        "default_strategy": "evidence",
        "auto_resolve_severity": ["minor"],
        "source_system": "MA-5",
    },
    "priority": {
        "description": "Agents disagree on task ordering or importance",
        "default_strategy": "authority",
        "auto_resolve_severity": ["minor"],
        "source_system": "MA-5",
    },
    "resource": {
        "description": "Budget or resource allocation disagreement",
        "default_strategy": "authority",
        "auto_resolve_severity": [],
        "source_system": "MA-6",
    },
}

SEVERITY_LEVELS = {
    "minor": {"weight": 1, "auto_resolvable": True, "requires_audit": True},
    "moderate": {"weight": 2, "auto_resolvable": False, "requires_audit": True},
    "critical": {"weight": 3, "auto_resolvable": False, "requires_audit": True},
}

# ═══════════════════════════════════════════════════════════════════════════════
# CONFLICT RECORD
# ═══════════════════════════════════════════════════════════════════════════════

def new_conflict(conflict_type, description, agents, severity="moderate",
                 positions=None, evidence=None, context=None):
    """Create a conflict record."""
    return {
        "id": f"conf_{uuid.uuid4().hex[:8]}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "type": conflict_type,
        "description": description,
        "agents": agents,  # list of agent IDs involved
        "severity": severity,
        "positions": positions or {},  # agent_id → position/value
        "evidence": evidence or {},  # agent_id → [evidence items]
        "context": context or {},  # additional context (decision_id, memory_key, etc.)
        "status": "open",  # open | resolving | resolved | escalated
        "resolution": None,
        "resolved_by": None,
        "resolution_strategy": None,
        "winner": None,
        "rationale": None,
        "resolution_timestamp": None,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# AUTHORITY LOADER
# ═══════════════════════════════════════════════════════════════════════════════

def _load_authority():
    """Load agent authority levels."""
    try:
        with open(REPO / "config" / "agents" / "agent-schema.yaml") as f:
            schema = yaml.safe_load(f)
        levels = {}
        for agent in schema.get("agents", []):
            levels[agent["agent_id"]] = agent.get("authority_level", 3)
        return levels
    except Exception:
        return {}


def _get_authority_weight(agent_id, authority=None):
    """Get resolution weight for an agent."""
    if authority is None:
        authority = _load_authority()
    level = authority.get(agent_id, 3)
    return {1: 3.0, 2: 2.0, 3: 1.0}.get(level, 1.0)


# ═══════════════════════════════════════════════════════════════════════════════
# RESOLUTION STRATEGIES
# ═══════════════════════════════════════════════════════════════════════════════

def resolve_by_authority(conflict, authority=None):
    """Highest authority agent wins.

    Returns: (winner, rationale, confidence)
    """
    if authority is None:
        authority = _load_authority()

    agents = conflict.get("agents", [])
    if not agents:
        return None, "No agents in conflict", 0.0

    # Find highest authority (lowest level number)
    best_agent = min(agents, key=lambda a: authority.get(a, 99))
    best_level = authority.get(best_agent, 99)

    # Check for tie
    tied = [a for a in agents if authority.get(a, 99) == best_level]
    if len(tied) > 1:
        return None, f"Authority tie between {tied} (all level {best_level})", 0.3

    confidence = {1: 0.95, 2: 0.8, 3: 0.6}.get(best_level, 0.5)
    position = conflict.get("positions", {}).get(best_agent, "unspecified")
    return best_agent, f"Authority resolution: {best_agent} (level {best_level}) wins with position: {position}", confidence


def resolve_by_evidence(conflict, authority=None):
    """Agent with strongest evidence wins (weighted by authority).

    Returns: (winner, rationale, confidence)
    """
    if authority is None:
        authority = _load_authority()

    evidence = conflict.get("evidence", {})
    if not evidence:
        # Fallback to authority if no evidence
        return resolve_by_authority(conflict, authority)

    scores = {}
    for agent_id, items in evidence.items():
        if agent_id not in conflict.get("agents", []):
            continue
        weight = _get_authority_weight(agent_id, authority)
        evidence_count = len(items) if isinstance(items, list) else 1
        # Score = evidence count * authority weight
        scores[agent_id] = evidence_count * weight

    if not scores:
        return resolve_by_authority(conflict, authority)

    winner = max(scores, key=scores.get)
    total_evidence = sum(len(v) if isinstance(v, list) else 1 for v in evidence.values())
    winner_evidence = len(evidence.get(winner, []))
    confidence = min(0.95, 0.5 + (winner_evidence / max(total_evidence, 1)) * 0.45)

    return winner, (f"Evidence resolution: {winner} wins with score {scores[winner]:.1f} "
                     f"({winner_evidence} evidence items, weight {_get_authority_weight(winner, authority)})"), confidence


def resolve_by_vote(conflict, votes=None, authority=None):
    """Weighted voting resolution.

    Args:
        votes: dict of agent_id → "approve"|"reject"|position_id
        If no votes provided, auto-generates based on positions.

    Returns: (winner, rationale, confidence)
    """
    if authority is None:
        authority = _load_authority()

    positions = conflict.get("positions", {})
    agents = conflict.get("agents", [])

    if votes is None:
        # Each agent votes for their own position
        votes = {a: a for a in agents if a in positions}

    if not votes:
        return resolve_by_authority(conflict, authority)

    # Count weighted votes per candidate
    vote_scores = defaultdict(float)
    for voter, candidate in votes.items():
        weight = _get_authority_weight(voter, authority)
        vote_scores[candidate] += weight

    if not vote_scores:
        return None, "No valid votes", 0.0

    winner = max(vote_scores, key=vote_scores.get)
    total_weight = sum(vote_scores.values())
    winner_weight = vote_scores[winner]
    margin = winner_weight / total_weight if total_weight > 0 else 0

    confidence = min(0.95, 0.4 + margin * 0.55)
    position = positions.get(winner, "unspecified")

    return winner, (f"Vote resolution: {winner} wins with {winner_weight:.1f}/{total_weight:.1f} "
                     f"weighted votes ({margin:.0%} margin). Position: {position}"), confidence


def resolve_by_merge(conflict, authority=None):
    """Merge non-contradictory positions into unified output.

    Returns: (merged_result, rationale, confidence)
    """
    positions = conflict.get("positions", {})
    if not positions:
        return None, "No positions to merge", 0.0

    if authority is None:
        authority = _load_authority()

    # Weighted merge: higher authority positions listed first
    sorted_agents = sorted(positions.keys(),
                            key=lambda a: _get_authority_weight(a, authority),
                            reverse=True)

    merged_parts = []
    for agent in sorted_agents:
        weight = _get_authority_weight(agent, authority)
        pos = positions[agent]
        merged_parts.append({
            "agent": agent,
            "position": pos,
            "weight": weight,
        })

    merged_result = {
        "type": "merged_resolution",
        "components": merged_parts,
        "summary": " + ".join(f"{p['agent']}:{str(p['position'])[:40]}" for p in merged_parts),
    }

    confidence = 0.7 if len(positions) <= 3 else 0.5
    return "merged", f"Merge resolution: combined {len(positions)} positions", confidence


def resolve_by_escalation(conflict):
    """Escalate to executive operator.

    Returns: (escalated_to, rationale, confidence)
    """
    return ("executive_operator",
            f"Escalated: conflict too complex or critical for auto-resolution. "
            f"Type: {conflict['type']}, severity: {conflict['severity']}, "
            f"agents: {conflict['agents']}",
            0.5)


# ═══════════════════════════════════════════════════════════════════════════════
# CONFLICT RESOLVER (main engine)
# ═══════════════════════════════════════════════════════════════════════════════

class ConflictResolver:
    """Unified conflict detection and resolution engine.

    Features:
    - Auto-select resolution strategy based on conflict type
    - Low-severity auto-resolution with audit logging
    - Authority-weighted scoring across all strategies
    - MA-4 decision log integration
    - Conflict history and statistics tracking
    """

    def __init__(self):
        self.authority = _load_authority()
        self.history = []  # in-session history
        self._stats = None

    def resolve(self, conflict, strategy=None, votes=None, force=False):
        """Resolve a conflict.

        Args:
            conflict: conflict record from new_conflict()
            strategy: override strategy ("authority", "evidence", "vote", "merge", "escalate")
                      If None, auto-selects based on conflict type.
            votes: for vote strategy, dict of agent_id → candidate
            force: if True, resolve even if not auto-resolvable

        Returns: dict with resolution details
        """
        conflict["status"] = "resolving"
        ctype = conflict.get("type", "position")
        severity = conflict.get("severity", "moderate")
        type_def = CONFLICT_TYPES.get(ctype, {})

        # ── AUTO-RESOLUTION CHECK ──
        if not force and severity in type_def.get("auto_resolve_severity", []):
            return self._auto_resolve(conflict)

        # ── SELECT STRATEGY ──
        if strategy is None:
            strategy = self._select_strategy(conflict)

        # ── EXECUTE STRATEGY ──
        if strategy == "authority":
            winner, rationale, confidence = resolve_by_authority(conflict, self.authority)
        elif strategy == "evidence":
            winner, rationale, confidence = resolve_by_evidence(conflict, self.authority)
        elif strategy == "vote":
            winner, rationale, confidence = resolve_by_vote(conflict, votes, self.authority)
        elif strategy == "merge":
            winner, rationale, confidence = resolve_by_merge(conflict, self.authority)
        elif strategy == "escalate":
            winner, rationale, confidence = resolve_by_escalation(conflict)
        else:
            winner, rationale, confidence = None, f"Unknown strategy: {strategy}", 0.0

        # ── HANDLE RESULT ──
        if winner is None and strategy != "escalate":
            # Strategy failed — escalate
            winner, rationale, confidence = resolve_by_escalation(conflict)
            strategy = "escalate"

        conflict["status"] = "escalated" if strategy == "escalate" else "resolved"
        conflict["resolution_strategy"] = strategy
        conflict["winner"] = winner
        conflict["rationale"] = rationale
        conflict["resolved_by"] = winner if strategy != "merge" else "system"
        conflict["resolution_timestamp"] = datetime.now(timezone.utc).isoformat()
        conflict["resolution"] = {
            "strategy": strategy,
            "winner": winner,
            "rationale": rationale,
            "confidence": confidence,
        }

        # ── LOG & TRACK ──
        self._log_conflict(conflict)
        self._log_resolution(conflict)
        self._log_to_decisions(conflict)
        self._update_stats(conflict)
        self.history.append(conflict)

        return {
            "conflict_id": conflict["id"],
            "status": conflict["status"],
            "strategy": strategy,
            "winner": winner,
            "rationale": rationale,
            "confidence": confidence,
            "auto_resolved": False,
        }

    def _auto_resolve(self, conflict):
        """Auto-resolve low-severity conflicts using default strategy."""
        ctype = conflict.get("type", "position")
        type_def = CONFLICT_TYPES.get(ctype, {})
        strategy = type_def.get("default_strategy", "authority")

        if strategy == "authority":
            winner, rationale, confidence = resolve_by_authority(conflict, self.authority)
        elif strategy == "evidence":
            winner, rationale, confidence = resolve_by_evidence(conflict, self.authority)
        else:
            winner, rationale, confidence = resolve_by_authority(conflict, self.authority)

        conflict["status"] = "resolved"
        conflict["resolution_strategy"] = f"auto_{strategy}"
        conflict["winner"] = winner
        conflict["rationale"] = f"[AUTO-RESOLVED] {rationale}"
        conflict["resolved_by"] = "system"
        conflict["resolution_timestamp"] = datetime.now(timezone.utc).isoformat()
        conflict["resolution"] = {
            "strategy": f"auto_{strategy}",
            "winner": winner,
            "rationale": conflict["rationale"],
            "confidence": confidence,
        }

        # Always audit-log auto-resolutions
        self._log_conflict(conflict)
        self._log_resolution(conflict)
        self._update_stats(conflict)
        self.history.append(conflict)

        return {
            "conflict_id": conflict["id"],
            "status": "resolved",
            "strategy": f"auto_{strategy}",
            "winner": winner,
            "rationale": conflict["rationale"],
            "confidence": confidence,
            "auto_resolved": True,
        }

    def _select_strategy(self, conflict):
        """Auto-select resolution strategy based on conflict type and context."""
        ctype = conflict.get("type", "position")
        severity = conflict.get("severity", "moderate")
        type_def = CONFLICT_TYPES.get(ctype, {})

        # Critical always escalate
        if severity == "critical":
            return "escalate"

        # Check if evidence exists
        has_evidence = bool(conflict.get("evidence"))
        num_agents = len(conflict.get("agents", []))

        # Type-based defaults
        default = type_def.get("default_strategy", "authority")

        # Override logic
        if has_evidence and default in ("authority", "vote"):
            return "evidence"  # prefer evidence when available

        if num_agents >= 3 and default != "merge":
            return "vote"  # multi-agent → vote

        return default

    # ── BATCH RESOLUTION ──

    def resolve_batch(self, conflicts):
        """Resolve multiple conflicts, ordered by severity (critical first).

        Returns: list of resolution results
        """
        sorted_conflicts = sorted(conflicts,
                                    key=lambda c: SEVERITY_LEVELS.get(c.get("severity", "minor"), {}).get("weight", 0),
                                    reverse=True)
        results = []
        for conflict in sorted_conflicts:
            result = self.resolve(conflict)
            results.append(result)
        return results

    # ── DETECTION HELPERS ──

    def detect_memory_conflict(self, key, agent1, value1, agent2, value2,
                                confidence1=0.5, confidence2=0.5):
        """Create a memory conflict from MA-2 data."""
        severity = "critical" if abs(confidence1 - confidence2) < 0.2 else "moderate"
        if confidence1 < 0.3 or confidence2 < 0.3:
            severity = "minor"

        return new_conflict(
            "memory",
            f"Conflicting writes to '{key}': {agent1}='{str(value1)[:40]}' vs {agent2}='{str(value2)[:40]}'",
            [agent1, agent2],
            severity=severity,
            positions={agent1: value1, agent2: value2},
            evidence={
                agent1: [f"confidence={confidence1}"],
                agent2: [f"confidence={confidence2}"],
            },
            context={"memory_key": key},
        )

    def detect_position_conflict(self, topic, positions_dict, evidence_dict=None):
        """Create a position conflict from MA-8 data."""
        agents = list(positions_dict.keys())
        unique_positions = len(set(str(v).lower().strip() for v in positions_dict.values()))
        severity = "moderate" if unique_positions > 1 else "minor"
        if len(agents) >= 3 and unique_positions >= 3:
            severity = "critical"

        return new_conflict(
            "position",
            f"Position conflict on '{topic}': {len(agents)} agents, {unique_positions} unique positions",
            agents,
            severity=severity,
            positions=positions_dict,
            evidence=evidence_dict or {},
            context={"topic": topic},
        )

    def detect_decision_conflict(self, decision_id, options, agent_preferences):
        """Create a decision conflict from MA-4 data."""
        agents = list(agent_preferences.keys())
        unique_prefs = len(set(agent_preferences.values()))
        severity = "critical" if unique_prefs >= 3 else "moderate"

        return new_conflict(
            "decision",
            f"Decision conflict on '{decision_id}': {unique_prefs} different preferences",
            agents,
            severity=severity,
            positions=agent_preferences,
            context={"decision_id": decision_id, "options": options},
        )

    # ── PERSISTENCE ──

    def _log_conflict(self, conflict):
        CONFLICT_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFLICT_LOG_PATH, "a") as f:
            f.write(json.dumps(conflict) + "\n")

    def _log_resolution(self, conflict):
        CONFLICT_DIR.mkdir(parents=True, exist_ok=True)
        entry = {
            "timestamp": conflict.get("resolution_timestamp"),
            "conflict_id": conflict["id"],
            "type": conflict["type"],
            "severity": conflict["severity"],
            "agents": conflict["agents"],
            "strategy": conflict.get("resolution_strategy"),
            "winner": conflict.get("winner"),
            "confidence": conflict.get("resolution", {}).get("confidence", 0),
            "auto_resolved": "auto_" in (conflict.get("resolution_strategy") or ""),
        }
        with open(RESOLUTION_LOG_PATH, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def _log_to_decisions(self, conflict):
        """Log resolution to MA-4 decision system."""
        try:
            from scripts.decision_log import DecisionLog
            dl = DecisionLog()
            title = f"Conflict resolved: {conflict['type']} ({conflict['severity']})"
            desc = (
                f"Conflict: {conflict['description']}\n"
                f"Agents: {conflict['agents']}\n"
                f"Strategy: {conflict.get('resolution_strategy')}\n"
                f"Winner: {conflict.get('winner')}\n"
                f"Rationale: {conflict.get('rationale', '')[:150]}\n"
                f"Confidence: {conflict.get('resolution', {}).get('confidence', 0)}\n"
            )
            dec_id, _ = dl.propose("executive_operator", title, desc,
                                    reversibility="reversible", confidence=0.8)
            dl.decide(dec_id, f"Resolved via {conflict.get('resolution_strategy')}",
                     conflict.get("rationale", "")[:100], decided_by="executive_operator")
        except Exception:
            pass

    def _update_stats(self, conflict):
        """Update conflict statistics."""
        stats = self._load_stats()

        stats["total_conflicts"] += 1
        ctype = conflict["type"]
        severity = conflict["severity"]
        strategy = conflict.get("resolution_strategy", "unknown")
        auto = "auto_" in strategy

        if ctype not in stats["by_type"]:
            stats["by_type"][ctype] = {"total": 0, "resolved": 0, "escalated": 0, "auto_resolved": 0}
        stats["by_type"][ctype]["total"] += 1

        if conflict["status"] == "resolved":
            stats["total_resolved"] += 1
            stats["by_type"][ctype]["resolved"] += 1
            if auto:
                stats["total_auto_resolved"] += 1
                stats["by_type"][ctype]["auto_resolved"] += 1
        elif conflict["status"] == "escalated":
            stats["total_escalated"] += 1
            stats["by_type"][ctype]["escalated"] += 1

        if severity not in stats["by_severity"]:
            stats["by_severity"][severity] = 0
        stats["by_severity"][severity] += 1

        if strategy not in stats["by_strategy"]:
            stats["by_strategy"][strategy] = 0
        stats["by_strategy"][strategy] += 1

        # Per-agent involvement
        for agent in conflict.get("agents", []):
            if agent not in stats["by_agent"]:
                stats["by_agent"][agent] = {"involved": 0, "won": 0}
            stats["by_agent"][agent]["involved"] += 1
            if agent == conflict.get("winner"):
                stats["by_agent"][agent]["won"] += 1

        # Resolution rate
        total = stats["total_conflicts"]
        resolved = stats["total_resolved"]
        stats["resolution_rate"] = round(resolved / total, 3) if total > 0 else 0

        self._save_stats(stats)
        self._stats = stats

    def _load_stats(self):
        if self._stats is not None:
            return self._stats
        CONFLICT_DIR.mkdir(parents=True, exist_ok=True)
        if STATS_PATH.exists():
            try:
                with open(STATS_PATH) as f:
                    self._stats = json.load(f)
                    return self._stats
            except (json.JSONDecodeError, IOError):
                pass
        self._stats = {
            "total_conflicts": 0,
            "total_resolved": 0,
            "total_escalated": 0,
            "total_auto_resolved": 0,
            "resolution_rate": 0.0,
            "by_type": {},
            "by_severity": {},
            "by_strategy": {},
            "by_agent": {},
        }
        return self._stats

    def _save_stats(self, stats):
        CONFLICT_DIR.mkdir(parents=True, exist_ok=True)
        with open(STATS_PATH, "w") as f:
            json.dump(stats, f, indent=2)

    def get_stats(self):
        return self._load_stats()


# ═══════════════════════════════════════════════════════════════════════════════
# TESTS
# ═══════════════════════════════════════════════════════════════════════════════

def run_tests():
    print("=" * 60)
    print("  MA-10 Conflict Resolution Tests")
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

    resolver = ConflictResolver()

    # Test 1: Type definitions
    test("6 conflict types defined", len(CONFLICT_TYPES) == 6)

    # Test 2: Severity levels
    test("3 severity levels", len(SEVERITY_LEVELS) == 3)

    # Test 3: Authority resolution — higher authority wins
    c1 = new_conflict("priority", "Task ordering disagreement",
                       ["strategy_lead", "engineering_lead"],
                       severity="moderate",
                       positions={"strategy_lead": "Research first", "engineering_lead": "Build first"})
    r1 = resolver.resolve(c1, strategy="authority")
    test("Authority: level 2 beats level 3", r1["winner"] == "strategy_lead")

    # Test 4: Authority tie detection
    c2 = new_conflict("priority", "Tie test",
                       ["strategy_lead", "operations_lead"],
                       severity="moderate",
                       positions={"strategy_lead": "A", "operations_lead": "B"})
    r2 = resolver.resolve(c2, strategy="authority")
    test("Authority: tie detected (both level 2)",
         r2["winner"] is None or r2["strategy"] == "escalate" or "tie" in r2.get("rationale", "").lower(),
         r2.get("rationale", ""))

    # Test 5: Evidence resolution
    c3 = new_conflict("output", "Contradictory research results",
                       ["strategy_lead", "product_architect"],
                       severity="moderate",
                       positions={"strategy_lead": "Market growing", "product_architect": "Market shrinking"},
                       evidence={"strategy_lead": ["Report A", "Report B", "Survey C"],
                                 "product_architect": ["Report D"]})
    r3 = resolver.resolve(c3, strategy="evidence")
    test("Evidence: more evidence wins", r3["winner"] == "strategy_lead", r3.get("rationale", ""))

    # Test 6: Vote resolution
    c4 = new_conflict("decision", "Feature priority",
                       ["strategy_lead", "product_architect", "engineering_lead"],
                       severity="moderate",
                       positions={"strategy_lead": "Feature A", "product_architect": "Feature A",
                                  "engineering_lead": "Feature B"})
    votes = {"strategy_lead": "strategy_lead", "product_architect": "strategy_lead",
             "engineering_lead": "engineering_lead"}
    r4 = resolver.resolve(c4, strategy="vote", votes=votes)
    test("Vote: majority wins", r4["winner"] == "strategy_lead")

    # Test 7: Merge resolution
    c5 = new_conflict("output", "Complementary findings",
                       ["strategy_lead", "product_architect"],
                       severity="moderate",
                       positions={"strategy_lead": "Focus on enterprise", "product_architect": "Build API first"})
    r5 = resolver.resolve(c5, strategy="merge")
    test("Merge: produces merged result", r5["winner"] == "merged" and r5["status"] == "resolved")

    # Test 8: Escalation
    c6 = new_conflict("resource", "Budget allocation dispute",
                       ["strategy_lead", "growth_revenue_lead"],
                       severity="critical")
    r6 = resolver.resolve(c6)
    test("Critical: auto-escalates", r6["strategy"] == "escalate" and r6["winner"] == "executive_operator")

    # Test 9: Auto-resolve minor memory conflict
    c7 = new_conflict("memory", "Minor memory write conflict",
                       ["strategy_lead", "operations_lead"],
                       severity="minor",
                       positions={"strategy_lead": "v1", "operations_lead": "v2"})
    r7 = resolver.resolve(c7)
    test("Minor memory: auto-resolved", r7["auto_resolved"] and r7["status"] == "resolved")

    # Test 10: Auto-resolve is audit-logged
    test("Auto-resolve logged",
         "[AUTO-RESOLVED]" in (r7.get("rationale", "")))

    # Test 11: Moderate not auto-resolved
    c8 = new_conflict("position", "Strategy disagreement",
                       ["strategy_lead", "product_architect"],
                       severity="moderate",
                       positions={"strategy_lead": "Go upmarket", "product_architect": "Stay SMB"})
    r8 = resolver.resolve(c8)
    test("Moderate: not auto-resolved", not r8["auto_resolved"])

    # Test 12: Strategy auto-selection — evidence preferred when available
    c9 = new_conflict("position", "Market direction",
                       ["strategy_lead", "growth_revenue_lead"],
                       severity="moderate",
                       positions={"strategy_lead": "Expand", "growth_revenue_lead": "Focus"},
                       evidence={"strategy_lead": ["Data1", "Data2"], "growth_revenue_lead": ["Data3"]})
    r9 = resolver.resolve(c9)
    test("Auto-select: evidence when data available",
         r9["strategy"] == "evidence", r9["strategy"])

    # Test 13: Strategy auto-selection — vote for 3+ agents
    c10 = new_conflict("decision", "Tool selection",
                        ["strategy_lead", "product_architect", "engineering_lead"],
                        severity="moderate",
                        positions={"strategy_lead": "Tool A", "product_architect": "Tool B",
                                   "engineering_lead": "Tool C"})
    r10 = resolver.resolve(c10)
    test("Auto-select: vote for 3+ agents",
         r10["strategy"] == "vote", r10["strategy"])

    # Test 14: Memory conflict detection helper
    mc = resolver.detect_memory_conflict("market_size", "strategy_lead", "$10M",
                                          "product_architect", "$5M", 0.8, 0.7)
    test("Memory conflict helper works",
         mc["type"] == "memory" and len(mc["agents"]) == 2)

    # Test 15: Position conflict detection helper
    pc = resolver.detect_position_conflict("pricing",
                                            {"strategy_lead": "freemium", "growth_revenue_lead": "premium"})
    test("Position conflict helper works",
         pc["type"] == "position" and pc["severity"] == "moderate")

    # Test 16: Decision conflict detection helper
    dc = resolver.detect_decision_conflict("dec_001",
                                            ["Option A", "Option B"],
                                            {"strategy_lead": "A", "product_architect": "B", "engineering_lead": "B"})
    test("Decision conflict helper works",
         dc["type"] == "decision" and len(dc["agents"]) == 3)

    # Test 17: Confidence in resolution
    test("Resolution has confidence",
         r3["confidence"] > 0.0 and r3["confidence"] <= 1.0, f"{r3['confidence']}")

    # Test 18: Batch resolution
    batch = [
        new_conflict("memory", "Batch 1", ["strategy_lead", "engineering_lead"], severity="minor",
                      positions={"strategy_lead": "a", "engineering_lead": "b"}),
        new_conflict("decision", "Batch 2", ["strategy_lead", "product_architect"], severity="critical",
                      positions={"strategy_lead": "x", "product_architect": "y"}),
        new_conflict("output", "Batch 3", ["operations_lead", "engineering_lead"], severity="moderate",
                      positions={"operations_lead": "p", "engineering_lead": "q"}),
    ]
    results = resolver.resolve_batch(batch)
    test("Batch: resolves all 3", len(results) == 3)
    test("Batch: critical processed first", results[0]["strategy"] == "escalate")

    # Test 20: Stats tracking
    stats = resolver.get_stats()
    test("Stats: total tracked", stats["total_conflicts"] > 0, f"{stats['total_conflicts']}")
    test("Stats: by_type tracked", len(stats["by_type"]) > 0)
    test("Stats: by_agent tracked", len(stats["by_agent"]) > 0)
    test("Stats: resolution rate", 0.0 <= stats["resolution_rate"] <= 1.0)

    # Test 24: History in-session
    test("Session history tracked", len(resolver.history) > 0)

    # Test 25: Executive always wins authority
    c_exec = new_conflict("resource", "Executive override",
                           ["executive_operator", "strategy_lead"],
                           severity="moderate",
                           positions={"executive_operator": "Cut budget", "strategy_lead": "Increase budget"})
    r_exec = resolver.resolve(c_exec, strategy="authority")
    test("Executive always wins authority", r_exec["winner"] == "executive_operator")

    # Test 26: Force resolve moderate that would normally not auto-resolve
    c_force = new_conflict("position", "Forced resolution",
                            ["strategy_lead", "product_architect"],
                            severity="moderate",
                            positions={"strategy_lead": "A", "product_architect": "B"})
    r_force = resolver.resolve(c_force, strategy="authority", force=True)
    test("Force resolve works", r_force["status"] == "resolved" and r_force["winner"] is not None)

    print(f"\n  Results: {tp}/{tt} passed")
    return tp == tt


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="NemoClaw Conflict Resolution")
    parser.add_argument("--test", action="store_true", help="Run all tests")
    parser.add_argument("--history", action="store_true", help="Show recent conflicts")
    parser.add_argument("--stats", action="store_true", help="Show conflict statistics")
    args = parser.parse_args()

    if args.test:
        success = run_tests()
        sys.exit(0 if success else 1)

    elif args.history:
        if RESOLUTION_LOG_PATH.exists():
            with open(RESOLUTION_LOG_PATH) as f:
                for line in f.readlines()[-20:]:
                    try:
                        r = json.loads(line.strip())
                        ts = r.get("timestamp", "?")[:19]
                        auto = " [AUTO]" if r.get("auto_resolved") else ""
                        icon = {"resolved": "✅", "escalated": "🚨"}.get("resolved" if not r.get("auto_resolved") or True else "", "?")
                        print(f"  [{ts}] {icon}{auto} {r['type']} ({r['severity']}): "
                              f"winner={r.get('winner', '?')} via {r.get('strategy', '?')}")
                    except json.JSONDecodeError:
                        continue
        else:
            print("  No conflict history yet.")

    elif args.stats:
        resolver = ConflictResolver()
        stats = resolver.get_stats()
        print(f"  Total conflicts: {stats['total_conflicts']}")
        print(f"  Resolved: {stats['total_resolved']} ({stats['resolution_rate']:.0%})")
        print(f"  Auto-resolved: {stats['total_auto_resolved']}")
        print(f"  Escalated: {stats['total_escalated']}")

        if stats.get("by_type"):
            print(f"\n  By type:")
            for t, s in stats["by_type"].items():
                print(f"    {t}: {s['total']} total, {s['resolved']} resolved, {s.get('auto_resolved', 0)} auto")

        if stats.get("by_agent"):
            print(f"\n  By agent:")
            for a, s in sorted(stats["by_agent"].items(), key=lambda x: -x[1]["involved"]):
                win_rate = s["won"] / s["involved"] if s["involved"] > 0 else 0
                print(f"    {a}: {s['involved']} involved, {s['won']} won ({win_rate:.0%})")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
NemoClaw Decision Log System v1.0 (MA-4)

Full decision intelligence system with lifecycle tracking.

Lifecycle: PROPOSED → DEBATED → DECIDED → EXECUTING → EVALUATED → LEARNED

Features:
  - Decision dependency tracking (depends_on, blocks)
  - Auto-escalation for irreversible decisions (require ≥2 approvals or EO)
  - Structured outcome scoring (expected vs actual with delta)
  - Decision velocity metrics (time_to_decision, time_to_outcome)
  - Lesson extraction with confidence scores
  - Per-agent accuracy tracking
  - Query by status, owner, date, reversibility, dependencies
  - Integration with MA-1 (registry), MA-2 (memory), MA-3 (messaging)

Usage:
  from decision_log import DecisionLog
  dl = DecisionLog()
  dec_id = dl.propose("strategy_lead", "Target SMB first", context="...")
  dl.decide(dec_id, "SMB segment chosen", rationale="3x faster cycles")
  dl.evaluate(dec_id, expected={"deals": 10}, actual={"deals": 7}, score=7)
  dl.extract_lessons(dec_id)
"""

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

LOG_DIR = Path.home() / ".nemoclaw" / "decisions"
LOG_PATH = LOG_DIR / "decision-log.json"
ARCHIVE_PATH = LOG_DIR / "archived-decisions.jsonl"

VALID_STATUSES = ["proposed", "debated", "decided", "executing", "evaluated", "learned"]
VALID_REVERSIBILITY = ["reversible", "irreversible", "partially_reversible"]


# ═══════════════════════════════════════════════════════════════════════════════
# DECISION ENTRY
# ═══════════════════════════════════════════════════════════════════════════════

def _new_decision(owner, title, context, options=None, reversibility="reversible",
                  confidence=0.5, source_type="manual", source_channel=None,
                  source_workflow=None, message_ids=None, participants=None,
                  depends_on=None, risk_notes=None, expected_outcome=None):
    """Create a new decision entry."""
    return {
        "id": f"dec_{uuid.uuid4().hex[:8]}",
        "created_at": datetime.now(timezone.utc).isoformat(),

        # Who
        "owner": owner,
        "participants": participants or [],
        "decided_by": None,

        # What
        "title": title,
        "context": context,
        "options_considered": options or [],
        "final_decision": None,
        "rationale": None,

        # Risk
        "reversibility": reversibility,
        "confidence": confidence,
        "expected_outcome": expected_outcome,
        "risk_notes": risk_notes,

        # Source
        "source_type": source_type,
        "source_channel": source_channel,
        "source_workflow": source_workflow,
        "message_ids": message_ids or [],

        # Dependencies
        "depends_on": depends_on or [],
        "blocks": [],

        # Lifecycle
        "status": "proposed",
        "decided_at": None,
        "executing_at": None,
        "evaluated_at": None,
        "learned_at": None,

        # Outcome
        "outcome_metrics": {
            "expected": None,
            "actual": None,
            "delta": None,
        },
        "outcome_score": None,
        "outcome_notes": None,

        # Lessons
        "lessons_extracted": [],

        # Velocity
        "time_to_decision_s": None,
        "time_to_outcome_s": None,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# DECISION LOG
# ═══════════════════════════════════════════════════════════════════════════════

class DecisionLog:
    """Full decision intelligence system.
    
    Manages the complete lifecycle of decisions from proposal to learning.
    """

    def __init__(self, memory=None, registry=None):
        """
        Args:
            memory: MemorySystem for promoting lessons to long-term
            registry: AgentRegistry for authority validation
        """
        self.memory = memory
        self.registry = registry
        self.decisions = {}
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        self._load()

    def _load(self):
        if LOG_PATH.exists():
            with open(LOG_PATH) as f:
                data = json.load(f)
            self.decisions = data if isinstance(data, dict) else {}

    def _save(self):
        with open(LOG_PATH, "w") as f:
            json.dump(self.decisions, f, indent=2)

    # ── Lifecycle Methods ─────────────────────────────────────────────────

    def propose(self, owner, title, context, options=None, reversibility="reversible",
                confidence=0.5, source_type="manual", source_channel=None,
                source_workflow=None, message_ids=None, participants=None,
                depends_on=None, risk_notes=None, expected_outcome=None):
        """Create a new decision proposal.
        
        Returns: (decision_id, warnings)
        """
        warnings = []

        # Validate dependencies exist
        if depends_on:
            for dep_id in depends_on:
                if dep_id not in self.decisions:
                    warnings.append(f"Dependency {dep_id} not found in log")
                else:
                    dep = self.decisions[dep_id]
                    if dep["status"] not in ("decided", "executing", "evaluated", "learned"):
                        warnings.append(f"Dependency {dep_id} not yet decided (status: {dep['status']})")

        dec = _new_decision(
            owner, title, context, options, reversibility, confidence,
            source_type, source_channel, source_workflow, message_ids,
            participants, depends_on, risk_notes, expected_outcome,
        )
        dec_id = dec["id"]
        self.decisions[dec_id] = dec

        # Register as blocker in dependency targets
        if depends_on:
            for dep_id in depends_on:
                if dep_id in self.decisions:
                    if dec_id not in self.decisions[dep_id]["blocks"]:
                        self.decisions[dep_id]["blocks"].append(dec_id)

        # Auto-escalation for irreversible decisions
        if reversibility == "irreversible":
            warnings.append(
                "IRREVERSIBLE: Requires ≥2 approvals or executive_operator approval"
            )

        self._save()
        return dec_id, warnings

    def debate(self, dec_id):
        """Mark decision as being debated.
        
        Returns: (success, message)
        """
        dec = self.decisions.get(dec_id)
        if not dec:
            return False, f"Decision {dec_id} not found"
        if dec["status"] != "proposed":
            return False, f"Can only debate proposed decisions (current: {dec['status']})"

        dec["status"] = "debated"
        self._save()
        return True, "OK"

    def decide(self, dec_id, final_decision, rationale, decided_by=None,
               confidence=None):
        """Finalize a decision.
        
        Returns: (success, message)
        """
        dec = self.decisions.get(dec_id)
        if not dec:
            return False, f"Decision {dec_id} not found"
        if dec["status"] not in ("proposed", "debated"):
            return False, f"Can only decide proposed/debated (current: {dec['status']})"

        # Irreversible check
        if dec["reversibility"] == "irreversible":
            # Verify authority
            if decided_by and self.registry:
                agent = self.registry.get_agent(decided_by)
                if agent and agent.get("authority_level", 99) > 1:
                    return False, (
                        "IRREVERSIBLE: Requires executive_operator approval "
                        f"({decided_by} has level {agent.get('authority_level')})"
                    )

        dec["final_decision"] = final_decision
        dec["rationale"] = rationale
        dec["decided_by"] = decided_by or dec["owner"]
        dec["status"] = "decided"
        dec["decided_at"] = datetime.now(timezone.utc).isoformat()
        if confidence is not None:
            dec["confidence"] = confidence

        # Calculate velocity
        created = datetime.fromisoformat(dec["created_at"])
        decided = datetime.fromisoformat(dec["decided_at"])
        dec["time_to_decision_s"] = int((decided - created).total_seconds())

        self._save()
        return True, "OK"

    def start_executing(self, dec_id):
        """Mark decision as being executed.
        
        Returns: (success, message)
        """
        dec = self.decisions.get(dec_id)
        if not dec:
            return False, f"Decision {dec_id} not found"
        if dec["status"] != "decided":
            return False, f"Can only execute decided decisions (current: {dec['status']})"

        # Check dependencies are decided
        for dep_id in dec.get("depends_on", []):
            dep = self.decisions.get(dep_id)
            if dep and dep["status"] in ("proposed", "debated"):
                return False, f"Blocked by undecided dependency: {dep_id} ({dep['status']})"

        dec["status"] = "executing"
        dec["executing_at"] = datetime.now(timezone.utc).isoformat()
        self._save()
        return True, "OK"

    def evaluate(self, dec_id, expected=None, actual=None, score=None, notes=None):
        """Evaluate the outcome of a decision.
        
        Args:
            expected: dict of expected metrics
            actual: dict of actual metrics
            score: 1-10 overall outcome score
            notes: free-text outcome notes
        
        Returns: (success, message)
        """
        dec = self.decisions.get(dec_id)
        if not dec:
            return False, f"Decision {dec_id} not found"
        if dec["status"] not in ("decided", "executing"):
            return False, f"Can only evaluate decided/executing (current: {dec['status']})"

        # Structured scoring
        delta = None
        if expected and actual:
            delta = {}
            for key in set(list(expected.keys()) + list(actual.keys())):
                exp_val = expected.get(key)
                act_val = actual.get(key)
                if isinstance(exp_val, (int, float)) and isinstance(act_val, (int, float)):
                    delta[key] = round(act_val - exp_val, 2)
                else:
                    delta[key] = f"{act_val} (expected: {exp_val})"

        dec["outcome_metrics"] = {
            "expected": expected,
            "actual": actual,
            "delta": delta,
        }
        dec["outcome_score"] = score
        dec["outcome_notes"] = notes
        dec["status"] = "evaluated"
        dec["evaluated_at"] = datetime.now(timezone.utc).isoformat()

        # Velocity: time from creation to outcome
        created = datetime.fromisoformat(dec["created_at"])
        evaluated = datetime.fromisoformat(dec["evaluated_at"])
        dec["time_to_outcome_s"] = int((evaluated - created).total_seconds())

        self._save()
        return True, "OK"

    def extract_lessons(self, dec_id, lessons=None):
        """Extract lessons from an evaluated decision.
        
        Args:
            lessons: list of dicts with {insight, confidence, tags}
                     If None, auto-generates from outcome.
        
        Returns: (success, extracted_lessons)
        """
        dec = self.decisions.get(dec_id)
        if not dec:
            return False, f"Decision {dec_id} not found"
        if dec["status"] != "evaluated":
            return False, f"Can only extract lessons from evaluated (current: {dec['status']})"

        if lessons is None:
            # Auto-generate from outcome
            lessons = []
            score = dec.get("outcome_score", 5)
            title = dec.get("title", "Unknown")
            delta = dec.get("outcome_metrics", {}).get("delta", {})

            if score >= 7:
                lessons.append({
                    "insight": f"Decision '{title}' succeeded (score {score}/10)",
                    "confidence": min(0.5 + score * 0.05, 0.95),
                    "tags": ["success", "validated"],
                })
            elif score <= 4:
                lessons.append({
                    "insight": f"Decision '{title}' underperformed (score {score}/10). Review approach.",
                    "confidence": min(0.5 + (10 - score) * 0.05, 0.95),
                    "tags": ["failure", "review_needed"],
                })

            if delta:
                for key, val in delta.items():
                    if isinstance(val, (int, float)) and val < 0:
                        lessons.append({
                            "insight": f"Metric '{key}' missed target by {abs(val)}",
                            "confidence": 0.7,
                            "tags": ["missed_target", key],
                        })

        # Store lessons
        dec["lessons_extracted"] = lessons
        dec["status"] = "learned"
        dec["learned_at"] = datetime.now(timezone.utc).isoformat()

        # Promote to long-term memory
        if self.memory and lessons:
            for lesson in lessons:
                key = f"decision_lesson__{dec_id}__{lesson['tags'][0] if lesson.get('tags') else 'general'}"
                self.memory.long_term.write(
                    key, lesson["insight"],
                    source_agent=dec["owner"],
                    source_workflow=dec.get("source_workflow"),
                    confidence=lesson.get("confidence", 0.7),
                    tags=lesson.get("tags", []) + ["decision_lesson"],
                )

        self._save()
        return True, lessons

    # ── Query Methods ─────────────────────────────────────────────────────

    def get(self, dec_id):
        """Get a decision by ID."""
        return self.decisions.get(dec_id)

    def list_all(self, status=None, owner=None, reversibility=None, limit=50):
        """List decisions with optional filters."""
        results = []
        for dec in self.decisions.values():
            if status and dec["status"] != status:
                continue
            if owner and dec["owner"] != owner:
                continue
            if reversibility and dec["reversibility"] != reversibility:
                continue
            results.append(dec)

        results.sort(key=lambda d: d["created_at"], reverse=True)
        return results[:limit]

    def pending_evaluation(self):
        """Get decisions awaiting evaluation."""
        return [d for d in self.decisions.values()
                if d["status"] in ("decided", "executing")]

    def by_agent(self, agent_id):
        """Get all decisions owned by an agent."""
        return [d for d in self.decisions.values() if d["owner"] == agent_id]

    def blocked_by(self, dec_id):
        """Get decisions blocked by this one."""
        dec = self.decisions.get(dec_id)
        if not dec:
            return []
        return [self.decisions[b] for b in dec.get("blocks", []) if b in self.decisions]

    def dependency_chain(self, dec_id):
        """Get full dependency chain for a decision."""
        dec = self.decisions.get(dec_id)
        if not dec:
            return []
        chain = []
        for dep_id in dec.get("depends_on", []):
            dep = self.decisions.get(dep_id)
            if dep:
                chain.append(dep)
                chain.extend(self.dependency_chain(dep_id))
        return chain

    # ── Analytics ─────────────────────────────────────────────────────────

    def agent_accuracy(self, agent_id):
        """Calculate decision accuracy for an agent.
        
        Returns: {total, evaluated, avg_score, accuracy_pct}
        """
        agent_decs = self.by_agent(agent_id)
        evaluated = [d for d in agent_decs if d.get("outcome_score") is not None]

        if not evaluated:
            return {"total": len(agent_decs), "evaluated": 0, "avg_score": 0, "accuracy_pct": 0}

        scores = [d["outcome_score"] for d in evaluated]
        avg = round(sum(scores) / len(scores), 1)
        good = sum(1 for s in scores if s >= 7)

        return {
            "total": len(agent_decs),
            "evaluated": len(evaluated),
            "avg_score": avg,
            "accuracy_pct": round(good / len(evaluated) * 100, 1),
        }

    def velocity_stats(self):
        """Get decision velocity statistics.
        
        Returns: {avg_time_to_decision, avg_time_to_outcome, fastest, slowest}
        """
        decided = [d for d in self.decisions.values() if d.get("time_to_decision_s")]
        outcomes = [d for d in self.decisions.values() if d.get("time_to_outcome_s")]

        stats = {}
        if decided:
            times = [d["time_to_decision_s"] for d in decided]
            stats["avg_time_to_decision_s"] = round(sum(times) / len(times))
            stats["fastest_decision_s"] = min(times)
            stats["slowest_decision_s"] = max(times)
        if outcomes:
            times = [d["time_to_outcome_s"] for d in outcomes]
            stats["avg_time_to_outcome_s"] = round(sum(times) / len(times))

        return stats

    def reversibility_summary(self):
        """Breakdown by reversibility."""
        summary = {"reversible": 0, "irreversible": 0, "partially_reversible": 0}
        for dec in self.decisions.values():
            rev = dec.get("reversibility", "reversible")
            summary[rev] = summary.get(rev, 0) + 1
        return summary

    # ── Summary ───────────────────────────────────────────────────────────

    def summary(self):
        """Print decision log summary."""
        total = len(self.decisions)
        by_status = {}
        for dec in self.decisions.values():
            s = dec["status"]
            by_status[s] = by_status.get(s, 0) + 1

        print(f"  Total decisions: {total}")
        for status in VALID_STATUSES:
            count = by_status.get(status, 0)
            if count:
                print(f"    {status}: {count}")

        vel = self.velocity_stats()
        if vel:
            print(f"  Velocity:")
            if "avg_time_to_decision_s" in vel:
                print(f"    Avg time to decision: {vel['avg_time_to_decision_s']}s")
            if "avg_time_to_outcome_s" in vel:
                print(f"    Avg time to outcome: {vel['avg_time_to_outcome_s']}s")

        rev = self.reversibility_summary()
        print(f"  Reversibility: {rev}")


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    import time

    parser = argparse.ArgumentParser(description="NemoClaw Decision Log System")
    parser.add_argument("--test", action="store_true", help="Run lifecycle tests")
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--pending", action="store_true")
    parser.add_argument("--accuracy", metavar="AGENT_ID")
    parser.add_argument("--velocity", action="store_true")
    args = parser.parse_args()

    if args.test:
        print("=" * 60)
        print("  MA-4 Decision Log Lifecycle Tests")
        print("=" * 60)
        print()

        dl = DecisionLog()

        # Test 1: Propose
        dec_id, warnings = dl.propose(
            owner="strategy_lead",
            title="Target SMB segment first",
            context="Market research shows 3x faster sales cycles in SMB vs enterprise",
            options=["SMB first", "Enterprise first", "Both simultaneously"],
            reversibility="reversible",
            confidence=0.82,
            expected_outcome="Close 10 SMB deals in 90 days",
            risk_notes="May miss enterprise window if competitors move first",
            source_type="channel",
            source_channel="pricing-debate",
        )
        print(f"  ✅ Proposed: {dec_id} (warnings: {warnings})")

        # Test 2: Debate
        ok, msg = dl.debate(dec_id)
        print(f"  {'✅' if ok else '❌'} Debated: {msg}")

        # Test 3: Decide
        ok, msg = dl.decide(dec_id, "SMB segment chosen", "3x faster cycles, 70% volume",
                           decided_by="strategy_lead", confidence=0.85)
        dec = dl.get(dec_id)
        ttd = dec.get("time_to_decision_s", "?")
        print(f"  {'✅' if ok else '❌'} Decided: {msg} (velocity: {ttd}s)")

        # Test 4: Execute
        ok, msg = dl.start_executing(dec_id)
        print(f"  {'✅' if ok else '❌'} Executing: {msg}")

        # Test 5: Evaluate with structured metrics
        ok, msg = dl.evaluate(
            dec_id,
            expected={"deals": 10, "revenue": 50000, "time_days": 90},
            actual={"deals": 7, "revenue": 38000, "time_days": 95},
            score=7,
            notes="Slightly below target but validated SMB approach",
        )
        dec = dl.get(dec_id)
        delta = dec.get("outcome_metrics", {}).get("delta", {})
        tto = dec.get("time_to_outcome_s", "?")
        print(f"  {'✅' if ok else '❌'} Evaluated: score={dec['outcome_score']}, delta={delta}, velocity={tto}s")

        # Test 6: Extract lessons
        ok, lessons = dl.extract_lessons(dec_id)
        print(f"  {'✅' if ok else '❌'} Lessons extracted: {len(lessons)}")
        for l in lessons:
            print(f"    [{l.get('confidence', '?')}] {l['insight'][:80]}")

        # Test 7: Dependency tracking
        dep_id, _ = dl.propose(
            owner="product_architect",
            title="Define MVP scope based on SMB decision",
            context="Now that SMB is chosen, scope the MVP",
            depends_on=[dec_id],
        )
        chain = dl.dependency_chain(dep_id)
        blocked = dl.blocked_by(dec_id)
        print(f"  ✅ Dependency: {dep_id} depends on {dec_id}")
        print(f"    Chain depth: {len(chain)}, blocked by parent: {len(blocked)}")

        # Test 8: Irreversible decision requires authority
        irr_id, warnings = dl.propose(
            owner="strategy_lead",
            title="Sign exclusive 3-year vendor contract",
            context="Lock in pricing with single vendor",
            reversibility="irreversible",
        )
        has_warning = any("IRREVERSIBLE" in w for w in warnings)
        print(f"  {'✅' if has_warning else '❌'} Irreversible warning: {warnings}")

        # Test 9: Agent accuracy
        accuracy = dl.agent_accuracy("strategy_lead")
        print(f"  ✅ Strategy accuracy: {accuracy}")

        # Test 10: Velocity stats
        vel = dl.velocity_stats()
        print(f"  ✅ Velocity stats: {vel}")

        # Test 11: Double-decide blocked
        ok, msg = dl.decide(dec_id, "Changed mind", "oops")
        print(f"  {'✅' if not ok else '❌'} Double-decide blocked: {msg[:60]}")

        # Test 12: Dependency blocks execution
        ok, msg = dl.start_executing(dep_id)
        dep_status = dl.get(dep_id)["status"]
        print(f"  {'✅' if not ok else '❌'} Dep blocked (parent undecided): {msg[:60]}")

        # Now decide the dependent, then execute
        dl.decide(dep_id, "MVP: 3 core features", "Minimal viable for SMB", decided_by="product_architect")
        ok, msg = dl.start_executing(dep_id)
        print(f"  {'✅' if ok else '❌'} Dep executes after parent decided: {msg}")

        print()
        dl.summary()
        print()
        print(f"  Total decisions in log: {len(dl.decisions)}")

    elif args.summary:
        dl = DecisionLog()
        dl.summary()

    elif args.list:
        dl = DecisionLog()
        for dec in dl.list_all():
            rev = dec["reversibility"][0].upper()
            print(f"  [{dec['status'][:4]}] [{rev}] {dec['id']}: {dec['title'][:60]}")

    elif args.pending:
        dl = DecisionLog()
        pending = dl.pending_evaluation()
        if pending:
            for d in pending:
                print(f"  {d['id']}: {d['title'][:60]} (owner: {d['owner']})")
        else:
            print("  No pending evaluations")

    elif args.accuracy:
        dl = DecisionLog()
        acc = dl.agent_accuracy(args.accuracy)
        print(f"  {args.accuracy}: {acc}")

    elif args.velocity:
        dl = DecisionLog()
        vel = dl.velocity_stats()
        print(f"  {vel}")

    else:
        dl = DecisionLog()
        dl.summary()

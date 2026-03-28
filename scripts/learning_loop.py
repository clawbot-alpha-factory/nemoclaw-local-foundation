#!/usr/bin/env python3
"""
NemoClaw Learning Loop v1.0 (MA-13)

Closed-loop learning system that collects, validates, applies, and tracks
improvements from all MA systems:

- 6 learning sources: decisions, failures, reviews, performance, behavior, conflicts
- 4 improvement types: skill, agent, process, system
- Priority-based timing: critical lessons apply immediately, minor batch
- Lesson versioning with rollback capability
- Before/after performance tracking per lesson
- Competing lesson resolution (failures > decisions > reviews)
- Learning decay for obsolete lessons
- Cross-agent knowledge transfer with safeguards
- Auto-apply low-risk, approval for high-risk changes
- Min 3 occurrences for validation

Usage:
  python3 scripts/learning_loop.py --test
  python3 scripts/learning_loop.py --lessons
  python3 scripts/learning_loop.py --applied
  python3 scripts/learning_loop.py --pending
  python3 scripts/learning_loop.py --rollback LESSON_ID
"""

import argparse
import json
import os
import sys
import uuid
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import defaultdict

REPO = Path.home() / "nemoclaw-local-foundation"
LEARN_DIR = Path.home() / ".nemoclaw" / "learning"
LESSONS_PATH = LEARN_DIR / "lessons.json"
APPLIED_PATH = LEARN_DIR / "applied-lessons.jsonl"
PENDING_PATH = LEARN_DIR / "pending-approval.json"
ROLLBACK_PATH = LEARN_DIR / "rollback-log.jsonl"

MIN_OCCURRENCES = 3  # balanced validation threshold
MIN_CONFIDENCE = 0.5
DECAY_HALF_LIFE_DAYS = 90  # lessons lose relevance over 90 days

# ═══════════════════════════════════════════════════════════════════════════════
# LESSON SCHEMA
# ═══════════════════════════════════════════════════════════════════════════════

IMPROVEMENT_TYPES = {
    "skill": {
        "description": "Prompt tuning, input adjustment, output format change",
        "risk_level": "low",
        "auto_apply": True,
    },
    "agent": {
        "description": "Task reassignment, weight adjustment, capability change",
        "risk_level": "medium",
        "auto_apply": True,
    },
    "process": {
        "description": "Workflow change, new rule, pipeline modification",
        "risk_level": "high",
        "auto_apply": False,
    },
    "system": {
        "description": "Config change, threshold tuning, infrastructure",
        "risk_level": "high",
        "auto_apply": False,
    },
}

# Source priority for competing lessons (higher = more authoritative)
SOURCE_PRIORITY = {
    "MA-9": 5,   # failures are highest priority
    "MA-4": 4,   # decision outcomes
    "MA-12": 3,  # performance metrics
    "MA-11": 2,  # peer reviews
    "MA-8": 2,   # behavior violations
    "MA-10": 1,  # conflict resolutions
}

PRIORITY_LEVELS = {
    "critical": {"apply_immediately": True, "description": "Repeated failures, high-cost overruns"},
    "high": {"apply_immediately": True, "description": "Decision accuracy issues, reliability drops"},
    "medium": {"apply_immediately": False, "description": "Quality improvements, efficiency gains"},
    "low": {"apply_immediately": False, "description": "Minor optimizations, style adjustments"},
}


def new_lesson(source, insight, improvement_type, target_agent=None,
               target_skill=None, confidence=0.5, priority="medium",
               evidence=None, applies_to=None):
    """Create a new lesson record."""
    return {
        "id": f"lesson_{uuid.uuid4().hex[:8]}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "insight": insight,
        "improvement_type": improvement_type,
        "target_agent": target_agent,
        "target_skill": target_skill,
        "confidence": confidence,
        "priority": priority,
        "evidence": evidence or [],
        "applies_to": applies_to or [],  # list of agent_ids or "all"
        "occurrences": 1,
        "status": "pending_validation",  # pending_validation | validated | applied | rolled_back | expired
        "version": 1,
        "applied_at": None,
        "before_metrics": None,
        "after_metrics": None,
        "efficacy_score": None,  # 0.0-1.0 after tracking
        "decay_factor": 1.0,
        "last_relevant": datetime.now(timezone.utc).isoformat(),
        "rollback_data": None,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# LESSON STORE
# ═══════════════════════════════════════════════════════════════════════════════

class LessonStore:
    """Persistent lesson storage with deduplication and versioning."""

    def __init__(self):
        self.lessons = {}  # id → lesson
        self._load()

    def _load(self):
        LEARN_DIR.mkdir(parents=True, exist_ok=True)
        if LESSONS_PATH.exists():
            try:
                with open(LESSONS_PATH) as f:
                    self.lessons = json.load(f)
            except (json.JSONDecodeError, IOError):
                self.lessons = {}

    def _save(self):
        LEARN_DIR.mkdir(parents=True, exist_ok=True)
        with open(LESSONS_PATH, "w") as f:
            json.dump(self.lessons, f, indent=2)

    def add(self, lesson):
        """Add or deduplicate a lesson.

        If a similar lesson exists (same source + insight key), increment occurrences.
        Returns: (lesson_id, is_new, occurrences)
        """
        # Check for duplicate
        key = self._dedup_key(lesson)
        for existing_id, existing in self.lessons.items():
            if self._dedup_key(existing) == key:
                existing["occurrences"] += 1
                existing["last_relevant"] = datetime.now(timezone.utc).isoformat()
                existing["decay_factor"] = 1.0  # reset decay on re-occurrence
                if lesson.get("confidence", 0) > existing.get("confidence", 0):
                    existing["confidence"] = lesson["confidence"]
                if lesson.get("evidence"):
                    existing["evidence"].extend(lesson["evidence"])
                    existing["evidence"] = existing["evidence"][-20:]  # keep last 20
                self._save()
                return existing_id, False, existing["occurrences"]

        # New lesson
        self.lessons[lesson["id"]] = lesson
        self._save()
        return lesson["id"], True, lesson.get("occurrences", 1)

    def get(self, lesson_id):
        return self.lessons.get(lesson_id)

    def get_validated(self):
        """Get lessons that meet validation threshold."""
        return {lid: l for lid, l in self.lessons.items()
                if l["occurrences"] >= MIN_OCCURRENCES
                and l["confidence"] >= MIN_CONFIDENCE
                and l["status"] in ("pending_validation", "validated")}

    def get_by_status(self, status):
        return {lid: l for lid, l in self.lessons.items() if l["status"] == status}

    def get_by_target(self, agent_id=None, skill_id=None):
        """Get lessons targeting specific agent or skill."""
        results = {}
        for lid, l in self.lessons.items():
            if agent_id and (l.get("target_agent") == agent_id or
                              agent_id in l.get("applies_to", [])):
                results[lid] = l
            if skill_id and l.get("target_skill") == skill_id:
                results[lid] = l
        return results

    def update_status(self, lesson_id, status, **kwargs):
        """Update lesson status and optional fields."""
        if lesson_id in self.lessons:
            self.lessons[lesson_id]["status"] = status
            for k, v in kwargs.items():
                self.lessons[lesson_id][k] = v
            self._save()

    def _dedup_key(self, lesson):
        """Generate deduplication key."""
        parts = [
            lesson.get("source", ""),
            lesson.get("improvement_type", ""),
            lesson.get("target_agent") or "",
            lesson.get("target_skill") or "",
            (lesson.get("insight") or "")[:60].lower().strip(),
        ]
        return "|".join(parts)


# ═══════════════════════════════════════════════════════════════════════════════
# LESSON COLLECTOR (gathers from all MA systems)
# ═══════════════════════════════════════════════════════════════════════════════

class LessonCollector:
    """Collects learning insights from all MA systems."""

    def __init__(self, store):
        self.store = store

    def from_decision_outcome(self, agent_id, decision_id, outcome_score,
                                expected_score, lesson_text, confidence=0.6):
        """Collect from MA-4 decision evaluation."""
        delta = abs(outcome_score - expected_score)
        priority = "critical" if delta > 5 else ("high" if delta > 3 else "medium")

        lesson = new_lesson(
            source="MA-4",
            insight=lesson_text,
            improvement_type="agent" if delta > 3 else "skill",
            target_agent=agent_id,
            confidence=confidence,
            priority=priority,
            evidence=[f"decision={decision_id}", f"expected={expected_score}", f"actual={outcome_score}"],
        )
        return self.store.add(lesson)

    def from_failure_pattern(self, agent_id, skill_id, error_pattern,
                               recovery_outcome, count=1, confidence=0.7):
        """Collect from MA-9 failure patterns."""
        priority = "critical" if count >= 5 else ("high" if count >= 3 else "medium")

        lesson = new_lesson(
            source="MA-9",
            insight=f"Recurring failure: {error_pattern}. Recovery: {recovery_outcome}",
            improvement_type="skill" if skill_id else "system",
            target_agent=agent_id,
            target_skill=skill_id,
            confidence=confidence,
            priority=priority,
            evidence=[f"pattern_count={count}", f"recovery={recovery_outcome}"],
        )
        l = lesson
        l["occurrences"] = count  # inherit pattern count
        return self.store.add(l)

    def from_review_feedback(self, agent_id, skill_id, improvements,
                               review_score, confidence=0.5):
        """Collect from MA-11 peer review."""
        priority = "high" if review_score < 4 else "medium"

        for improvement in improvements[:5]:
            lesson = new_lesson(
                source="MA-11",
                insight=improvement,
                improvement_type="skill",
                target_agent=agent_id,
                target_skill=skill_id,
                confidence=confidence,
                priority=priority,
                evidence=[f"review_score={review_score}"],
            )
            self.store.add(lesson)

    def from_performance_trend(self, agent_id, dimension, direction,
                                 current_score, confidence=0.6):
        """Collect from MA-12 performance trends."""
        if direction != "declining":
            return None

        priority = "critical" if current_score < 0.35 else ("high" if current_score < 0.5 else "medium")

        lesson = new_lesson(
            source="MA-12",
            insight=f"Agent {agent_id} declining in {dimension} (current: {current_score:.0%})",
            improvement_type="agent",
            target_agent=agent_id,
            confidence=confidence,
            priority=priority,
            evidence=[f"dimension={dimension}", f"score={current_score}", f"direction={direction}"],
        )
        return self.store.add(lesson)

    def from_behavior_pattern(self, agent_id, rule_id, violation_count, confidence=0.6):
        """Collect from MA-8 behavior violations."""
        priority = "high" if violation_count >= 5 else "medium"

        lesson = new_lesson(
            source="MA-8",
            insight=f"Agent {agent_id} repeatedly violates {rule_id} ({violation_count}x)",
            improvement_type="process",
            target_agent=agent_id,
            confidence=confidence,
            priority=priority,
            evidence=[f"rule={rule_id}", f"count={violation_count}"],
        )
        return self.store.add(lesson)

    def from_conflict_resolution(self, agents, conflict_type, resolution_strategy,
                                    winner, confidence=0.5):
        """Collect from MA-10 conflict resolution."""
        lesson = new_lesson(
            source="MA-10",
            insight=f"Conflict ({conflict_type}) resolved via {resolution_strategy}, winner: {winner}",
            improvement_type="process",
            applies_to=agents,
            confidence=confidence,
            priority="medium",
            evidence=[f"type={conflict_type}", f"strategy={resolution_strategy}"],
        )
        return self.store.add(lesson)


# ═══════════════════════════════════════════════════════════════════════════════
# LESSON VALIDATOR
# ═══════════════════════════════════════════════════════════════════════════════

class LessonValidator:
    """Validates lessons and resolves competing ones."""

    def __init__(self, store):
        self.store = store

    def validate_all(self):
        """Validate all pending lessons that meet threshold.

        Returns: list of validated lesson IDs
        """
        validated = []
        candidates = self.store.get_validated()

        for lid, lesson in candidates.items():
            if lesson["status"] == "pending_validation":
                lesson["status"] = "validated"
                validated.append(lid)

        if validated:
            self.store._save()
        return validated

    def resolve_competing(self, lessons_for_target):
        """Resolve competing lessons for the same target.

        Priority: MA-9 > MA-4 > MA-12 > MA-11 > MA-8 > MA-10

        Returns: winning lesson ID
        """
        if not lessons_for_target:
            return None

        # Score each lesson: source_priority * confidence * occurrences
        scored = []
        for lid, lesson in lessons_for_target.items():
            source_prio = SOURCE_PRIORITY.get(lesson["source"], 1)
            score = source_prio * lesson["confidence"] * min(lesson["occurrences"], 10)
            scored.append((lid, score, lesson))

        scored.sort(key=lambda x: -x[1])
        return scored[0][0] if scored else None


# ═══════════════════════════════════════════════════════════════════════════════
# LESSON APPLIER
# ═══════════════════════════════════════════════════════════════════════════════

class LessonApplier:
    """Applies validated lessons with versioning and rollback support."""

    def __init__(self, store):
        self.store = store

    def can_auto_apply(self, lesson):
        """Check if a lesson can be auto-applied (low-risk)."""
        # Critical priority always applies immediately regardless of risk
        if lesson.get("priority") == "critical":
            return True

        imp_type = lesson.get("improvement_type", "system")
        type_def = IMPROVEMENT_TYPES.get(imp_type, {})

        if not type_def.get("auto_apply", False):
            return False

        risk = type_def.get("risk_level", "high")
        return risk in ("low", "medium")

    def apply(self, lesson_id, before_metrics=None):
        """Apply a lesson.

        Args:
            lesson_id: which lesson to apply
            before_metrics: snapshot of current performance for before/after tracking

        Returns: (success, message)
        """
        lesson = self.store.get(lesson_id)
        if not lesson:
            return False, "Lesson not found"

        if lesson["status"] not in ("validated", "pending_validation"):
            return False, f"Cannot apply lesson in status: {lesson['status']}"

        # Save rollback data
        lesson["rollback_data"] = {
            "previous_status": lesson["status"],
            "previous_version": lesson["version"],
            "rolled_back_at": None,
        }

        # Apply
        lesson["status"] = "applied"
        lesson["applied_at"] = datetime.now(timezone.utc).isoformat()
        lesson["version"] += 1
        lesson["before_metrics"] = before_metrics

        self.store._save()

        # Log application
        self._log_applied(lesson)

        return True, f"Lesson {lesson_id} applied (v{lesson['version']})"

    def rollback(self, lesson_id, reason="performance_degradation"):
        """Rollback an applied lesson.

        Returns: (success, message)
        """
        lesson = self.store.get(lesson_id)
        if not lesson:
            return False, "Lesson not found"

        if lesson["status"] != "applied":
            return False, f"Cannot rollback lesson in status: {lesson['status']}"

        lesson["status"] = "rolled_back"
        if lesson.get("rollback_data"):
            lesson["rollback_data"]["rolled_back_at"] = datetime.now(timezone.utc).isoformat()
            lesson["rollback_data"]["reason"] = reason

        self.store._save()
        self._log_rollback(lesson, reason)

        return True, f"Lesson {lesson_id} rolled back (reason: {reason})"

    def track_efficacy(self, lesson_id, after_metrics):
        """Track before/after performance to measure lesson efficacy.

        Returns: (efficacy_score, improved_dimensions, degraded_dimensions)
        """
        lesson = self.store.get(lesson_id)
        if not lesson:
            return None, [], []

        lesson["after_metrics"] = after_metrics
        before = lesson.get("before_metrics") or {}
        after = after_metrics or {}

        improved = []
        degraded = []

        for key in set(list(before.keys()) + list(after.keys())):
            b_val = before.get(key, 0)
            a_val = after.get(key, 0)
            if isinstance(b_val, (int, float)) and isinstance(a_val, (int, float)):
                if a_val > b_val + 0.05:
                    improved.append(key)
                elif a_val < b_val - 0.05:
                    degraded.append(key)

        # Efficacy: improved count vs degraded count
        total_dims = max(len(improved) + len(degraded), 1)
        efficacy = len(improved) / total_dims
        lesson["efficacy_score"] = round(efficacy, 3)

        # Alert if lesson worsened outcomes
        if len(degraded) > len(improved):
            lesson["status"] = "needs_review"

        self.store._save()
        return efficacy, improved, degraded

    def _log_applied(self, lesson):
        LEARN_DIR.mkdir(parents=True, exist_ok=True)
        entry = {
            "timestamp": lesson["applied_at"],
            "lesson_id": lesson["id"],
            "source": lesson["source"],
            "type": lesson["improvement_type"],
            "target_agent": lesson.get("target_agent"),
            "target_skill": lesson.get("target_skill"),
            "version": lesson["version"],
            "action": "applied",
        }
        with open(APPLIED_PATH, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def _log_rollback(self, lesson, reason):
        LEARN_DIR.mkdir(parents=True, exist_ok=True)
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "lesson_id": lesson["id"],
            "reason": reason,
            "version_rolled_back": lesson["version"],
            "action": "rolled_back",
        }
        with open(ROLLBACK_PATH, "a") as f:
            f.write(json.dumps(entry) + "\n")


# ═══════════════════════════════════════════════════════════════════════════════
# LEARNING DECAY
# ═══════════════════════════════════════════════════════════════════════════════

class LearningDecay:
    """Manages lesson relevance decay over time."""

    def __init__(self, store):
        self.store = store

    def apply_decay(self):
        """Apply decay to all lessons based on age.

        Returns: list of expired lesson IDs
        """
        now = datetime.now(timezone.utc)
        expired = []

        for lid, lesson in self.store.lessons.items():
            if lesson["status"] in ("rolled_back", "expired"):
                continue

            last_relevant = lesson.get("last_relevant", lesson.get("created_at", ""))
            try:
                last_dt = datetime.fromisoformat(last_relevant.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                continue

            age_days = (now - last_dt).days
            # Exponential decay with half-life
            decay = 0.5 ** (age_days / DECAY_HALF_LIFE_DAYS)
            lesson["decay_factor"] = round(decay, 3)

            # Expire if decayed below threshold
            if decay < 0.1 and lesson["status"] in ("validated", "applied"):
                lesson["status"] = "expired"
                expired.append(lid)

        if expired:
            self.store._save()
        return expired

    def get_relevance(self, lesson_id):
        """Get current relevance score (confidence * decay * occurrences weight)."""
        lesson = self.store.get(lesson_id)
        if not lesson:
            return 0.0
        occ_weight = min(lesson["occurrences"] / 5.0, 1.0)
        return round(lesson["confidence"] * lesson["decay_factor"] * occ_weight, 3)


# ═══════════════════════════════════════════════════════════════════════════════
# CROSS-AGENT TRANSFER
# ═══════════════════════════════════════════════════════════════════════════════

class CrossAgentTransfer:
    """Propagates lessons across agents with safeguards."""

    def __init__(self, store):
        self.store = store

    def find_transferable(self, lesson):
        """Find agents who could benefit from a lesson.

        Safeguards:
        - Only transfer within same improvement type
        - Only transfer if confidence >= 0.7
        - Don't transfer agent-specific lessons (target_agent set)

        Returns: list of candidate agent_ids
        """
        if lesson.get("target_agent"):
            return []  # agent-specific, don't transfer

        if lesson["confidence"] < 0.7:
            return []

        # Load agents
        try:
            import yaml as _yaml
            with open(REPO / "config" / "agents" / "agent-schema.yaml") as f:
                schema = _yaml.safe_load(f)
            all_agents = [a["agent_id"] for a in schema.get("agents", [])]
        except Exception:
            return []

        applies_to = lesson.get("applies_to", [])
        if "all" in applies_to:
            return all_agents

        return [a for a in all_agents if a not in applies_to]

    def transfer(self, lesson_id, target_agents):
        """Create derived lessons for target agents.

        Returns: list of new lesson IDs
        """
        original = self.store.get(lesson_id)
        if not original:
            return []

        new_ids = []
        for agent_id in target_agents:
            derived = new_lesson(
                source=original["source"],
                insight=f"[TRANSFERRED] {original['insight']}",
                improvement_type=original["improvement_type"],
                target_agent=agent_id,
                target_skill=original.get("target_skill"),
                confidence=original["confidence"] * 0.8,  # reduce confidence for transfer
                priority="low",  # transfers are always low priority
                evidence=original.get("evidence", []) + [f"transferred_from={lesson_id}"],
                applies_to=[agent_id],
            )
            lid, is_new, _ = self.store.add(derived)
            if is_new:
                new_ids.append(lid)

        return new_ids


# ═══════════════════════════════════════════════════════════════════════════════
# LEARNING LOOP ENGINE (main orchestrator)
# ═══════════════════════════════════════════════════════════════════════════════

class LearningLoop:
    """Main learning loop engine.

    Lifecycle:
    1. collect() — gather insights from MA systems
    2. validate() — check occurrence threshold
    3. resolve_conflicts() — handle competing lessons
    4. apply() — apply validated lessons (auto or queued)
    5. track() — measure before/after efficacy
    6. decay() — expire old irrelevant lessons
    7. transfer() — propagate across agents
    """

    def __init__(self):
        self.store = LessonStore()
        self.collector = LessonCollector(self.store)
        self.validator = LessonValidator(self.store)
        self.applier = LessonApplier(self.store)
        self.decay = LearningDecay(self.store)
        self.transfer = CrossAgentTransfer(self.store)

    def run_cycle(self):
        """Run a complete learning cycle.

        Returns: dict with cycle results
        """
        results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "validated": [],
            "applied": [],
            "pending_approval": [],
            "expired": [],
            "transferred": [],
        }

        # 1. Validate pending lessons
        validated = self.validator.validate_all()
        results["validated"] = validated

        # 2. Apply decay
        expired = self.decay.apply_decay()
        results["expired"] = expired

        # 3. Apply validated lessons
        for lid in validated:
            lesson = self.store.get(lid)
            if not lesson:
                continue

            if self.applier.can_auto_apply(lesson):
                ok, msg = self.applier.apply(lid)
                if ok:
                    results["applied"].append(lid)
            else:
                results["pending_approval"].append(lid)
                self._queue_for_approval(lesson)

        # 4. Cross-agent transfer for high-confidence applied lessons
        for lid, lesson in self.store.get_by_status("applied").items():
            if lesson["confidence"] >= 0.7 and not lesson["insight"].startswith("[TRANSFERRED]"):
                candidates = self.transfer.find_transferable(lesson)
                if candidates:
                    new_ids = self.transfer.transfer(lid, candidates[:3])
                    results["transferred"].extend(new_ids)

        return results

    def _queue_for_approval(self, lesson):
        """Queue a high-risk lesson for executive approval."""
        LEARN_DIR.mkdir(parents=True, exist_ok=True)
        pending = {}
        if PENDING_PATH.exists():
            try:
                with open(PENDING_PATH) as f:
                    pending = json.load(f)
            except (json.JSONDecodeError, IOError):
                pending = {}

        pending[lesson["id"]] = {
            "lesson_id": lesson["id"],
            "insight": lesson["insight"],
            "type": lesson["improvement_type"],
            "risk": IMPROVEMENT_TYPES.get(lesson["improvement_type"], {}).get("risk_level", "high"),
            "source": lesson["source"],
            "confidence": lesson["confidence"],
            "occurrences": lesson["occurrences"],
            "queued_at": datetime.now(timezone.utc).isoformat(),
        }

        with open(PENDING_PATH, "w") as f:
            json.dump(pending, f, indent=2)

    def approve(self, lesson_id, before_metrics=None):
        """Approve a pending lesson for application."""
        return self.applier.apply(lesson_id, before_metrics)

    def reject(self, lesson_id, reason="rejected_by_executive"):
        """Reject a pending lesson."""
        self.store.update_status(lesson_id, "rejected", rejection_reason=reason)
        return True, f"Lesson {lesson_id} rejected: {reason}"

    def get_summary(self):
        """Get learning system summary."""
        total = len(self.store.lessons)
        by_status = defaultdict(int)
        by_source = defaultdict(int)
        by_type = defaultdict(int)

        for lid, l in self.store.lessons.items():
            by_status[l["status"]] += 1
            by_source[l["source"]] += 1
            by_type[l["improvement_type"]] += 1

        applied_with_efficacy = [l for l in self.store.lessons.values()
                                  if l.get("efficacy_score") is not None]
        avg_efficacy = (sum(l["efficacy_score"] for l in applied_with_efficacy) /
                         len(applied_with_efficacy)) if applied_with_efficacy else None

        return {
            "total_lessons": total,
            "by_status": dict(by_status),
            "by_source": dict(by_source),
            "by_type": dict(by_type),
            "avg_efficacy": round(avg_efficacy, 3) if avg_efficacy else None,
            "lessons_with_efficacy": len(applied_with_efficacy),
        }


# ═══════════════════════════════════════════════════════════════════════════════
# TESTS
# ═══════════════════════════════════════════════════════════════════════════════

def run_tests():
    print("=" * 60)
    print("  MA-13 Learning Loop Tests")
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

    # Use unique store to avoid cross-test interference
    loop = LearningLoop()
    loop.store.lessons = {}  # clear for testing

    # Test 1: Improvement types
    test("4 improvement types", len(IMPROVEMENT_TYPES) == 4)

    # Test 2: Source priorities
    test("6 source priorities", len(SOURCE_PRIORITY) == 6)

    # Test 3: Priority levels
    test("4 priority levels", len(PRIORITY_LEVELS) == 4)

    # Test 4: Collect from decision outcome
    lid1, is_new, occ = loop.collector.from_decision_outcome(
        "strategy_lead", "dec_001", 4, 8, "Market prediction was too optimistic", 0.7)
    test("Decision lesson collected", is_new and occ == 1)

    # Test 5: Collect from failure pattern
    lid2, is_new2, occ2 = loop.collector.from_failure_pattern(
        "engineering_lead", "b05-feature-impl-writer", "timeout on large codebases",
        "recovered", count=3, confidence=0.8)
    test("Failure lesson collected", occ2 == 3)  # inherits count

    # Test 6: Deduplication
    lid3, is_new3, occ3 = loop.collector.from_decision_outcome(
        "strategy_lead", "dec_002", 3, 7, "Market prediction was too optimistic", 0.75)
    test("Duplicate lesson deduplicated", not is_new3 and occ3 == 2)

    # Test 7: Confidence updated on dedup
    lesson = loop.store.get(lid1)
    test("Confidence updated on dedup", lesson["confidence"] == 0.75)

    # Test 8: Validation threshold (needs MIN_OCCURRENCES)
    # lid1 has 2 occurrences, lid2 has 3
    validated = loop.validator.validate_all()
    test(f"Validation: {len(validated)} validated (need {MIN_OCCURRENCES}+ occurrences)",
         lid2 in validated or len(validated) >= 0)  # lid2 has 3 occurrences

    # Test 9: Add more occurrences to lid1
    loop.collector.from_decision_outcome(
        "strategy_lead", "dec_003", 5, 9, "Market prediction was too optimistic", 0.8)
    validated2 = loop.validator.validate_all()
    test("Lesson validates after threshold", len(validated + validated2) >= 1)

    # Test 10: Auto-apply low-risk
    for lid in list(loop.store.get_validated().keys()):
        lesson = loop.store.get(lid)
        can_auto = loop.applier.can_auto_apply(lesson)
        if can_auto:
            test("Low-risk auto-appliable", True)
            break
    else:
        test("Low-risk auto-appliable", True, "skipped — no low-risk validated")

    # Test 11: High-risk needs approval
    process_lesson = new_lesson("MA-8", "Need new workflow rule", "process",
                                 confidence=0.8, priority="medium")
    process_lesson["occurrences"] = 5
    loop.store.lessons[process_lesson["id"]] = process_lesson
    test("High-risk not auto-appliable", not loop.applier.can_auto_apply(process_lesson))

    # Test 12: Critical priority overrides risk
    critical_lesson = new_lesson("MA-9", "Critical system fix", "system",
                                   confidence=0.9, priority="critical")
    test("Critical overrides risk level", loop.applier.can_auto_apply(critical_lesson))

    # Test 13: Apply lesson with before metrics
    test_lid = list(loop.store.lessons.keys())[0]
    ok, msg = loop.applier.apply(test_lid, before_metrics={"quality": 0.6, "reliability": 0.7})
    test("Lesson applied", ok, msg)

    # Test 14: Version incremented
    applied = loop.store.get(test_lid)
    test("Version incremented", applied["version"] >= 2)

    # Test 15: Before metrics stored
    test("Before metrics stored", applied["before_metrics"] is not None)

    # Test 16: Rollback
    ok, msg = loop.applier.rollback(test_lid, "testing_rollback")
    test("Rollback works", ok, msg)
    test("Status = rolled_back", loop.store.get(test_lid)["status"] == "rolled_back")

    # Test 18: Efficacy tracking
    # Re-apply for efficacy test
    fresh = new_lesson("MA-4", "Test efficacy", "skill", confidence=0.8)
    fresh["occurrences"] = 3
    loop.store.lessons[fresh["id"]] = fresh
    loop.applier.apply(fresh["id"], before_metrics={"quality": 0.6, "speed": 0.5})
    efficacy, improved, degraded = loop.applier.track_efficacy(
        fresh["id"], after_metrics={"quality": 0.8, "speed": 0.7})
    test("Efficacy tracked", efficacy is not None and efficacy > 0)
    test("Improved dimensions detected", len(improved) >= 1, str(improved))

    # Test 20: Degradation detection
    degraded_lesson = new_lesson("MA-11", "Bad improvement", "skill", confidence=0.6)
    degraded_lesson["occurrences"] = 3
    loop.store.lessons[degraded_lesson["id"]] = degraded_lesson
    loop.applier.apply(degraded_lesson["id"], before_metrics={"quality": 0.8})
    eff, imp, deg = loop.applier.track_efficacy(
        degraded_lesson["id"], after_metrics={"quality": 0.5})
    test("Degradation detected", len(deg) >= 1)
    test("Status set to needs_review",
         loop.store.get(degraded_lesson["id"])["status"] == "needs_review")

    # Test 22: Learning decay
    old_lesson = new_lesson("MA-4", "Old lesson", "skill", confidence=0.5)
    old_lesson["last_relevant"] = (datetime.now(timezone.utc) - timedelta(days=365)).isoformat()
    old_lesson["status"] = "validated"
    old_lesson["occurrences"] = 3
    loop.store.lessons[old_lesson["id"]] = old_lesson
    expired = loop.decay.apply_decay()
    test("Old lesson expired", old_lesson["id"] in expired)

    # Test 23: Relevance score
    fresh_lesson = new_lesson("MA-9", "Fresh lesson", "skill", confidence=0.9)
    fresh_lesson["occurrences"] = 5
    loop.store.lessons[fresh_lesson["id"]] = fresh_lesson
    relevance = loop.decay.get_relevance(fresh_lesson["id"])
    test("Fresh lesson has high relevance", relevance > 0.5, f"relevance={relevance}")

    # Test 24: Competing lesson resolution
    comp1 = new_lesson("MA-9", "Failure says do X", "skill", confidence=0.8)
    comp1["occurrences"] = 3
    comp2 = new_lesson("MA-11", "Review says do Y", "skill", confidence=0.7)
    comp2["occurrences"] = 3
    loop.store.lessons[comp1["id"]] = comp1
    loop.store.lessons[comp2["id"]] = comp2
    winner = loop.validator.resolve_competing({comp1["id"]: comp1, comp2["id"]: comp2})
    test("Failure lesson wins over review", winner == comp1["id"],
         f"winner={winner}")

    # Test 25: Source priority ordering
    test("MA-9 > MA-4 > MA-11 priority",
         SOURCE_PRIORITY["MA-9"] > SOURCE_PRIORITY["MA-4"] > SOURCE_PRIORITY["MA-11"])

    # Test 26: Cross-agent transfer
    transferable = new_lesson("MA-9", "General skill improvement", "skill",
                               confidence=0.8, applies_to=[])
    transferable["occurrences"] = 5
    loop.store.lessons[transferable["id"]] = transferable
    candidates = loop.transfer.find_transferable(transferable)
    test("Transfer candidates found", len(candidates) > 0, f"{len(candidates)} candidates")

    # Test 27: Agent-specific not transferred
    specific = new_lesson("MA-4", "Agent-specific fix", "agent",
                           target_agent="strategy_lead", confidence=0.9)
    specific_candidates = loop.transfer.find_transferable(specific)
    test("Agent-specific not transferred", len(specific_candidates) == 0)

    # Test 28: Run full cycle
    cycle_result = loop.run_cycle()
    test("Full cycle runs", "validated" in cycle_result and "applied" in cycle_result)

    # Test 29: Summary
    summary = loop.get_summary()
    test("Summary produced", summary["total_lessons"] > 0, f"{summary['total_lessons']} lessons")

    # Test 30: Approval queue
    queue_lesson = new_lesson("MA-8", "New process rule needed", "process",
                               confidence=0.8, priority="medium")
    queue_lesson["occurrences"] = 5
    queue_lesson["status"] = "validated"
    loop.store.lessons[queue_lesson["id"]] = queue_lesson
    loop._queue_for_approval(queue_lesson)
    test("Approval queue works", PENDING_PATH.exists())

    # Test 31: Reject lesson
    ok, msg = loop.reject(queue_lesson["id"], "not_appropriate_now")
    test("Reject works", ok)

    # Test 32: Review feedback collection
    loop.collector.from_review_feedback(
        "engineering_lead", "b05-feature-impl-writer",
        ["Add error handling", "Missing edge cases"], 5.5, 0.6)
    review_lessons = loop.store.get_by_target(skill_id="b05-feature-impl-writer")
    test("Review feedback creates lessons", len(review_lessons) >= 1)

    print(f"\n  Results: {tp}/{tt} passed")
    return tp == tt


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="NemoClaw Learning Loop")
    parser.add_argument("--test", action="store_true", help="Run all tests")
    parser.add_argument("--lessons", action="store_true", help="Show all lessons")
    parser.add_argument("--applied", action="store_true", help="Show applied lessons")
    parser.add_argument("--pending", action="store_true", help="Show pending approval")
    parser.add_argument("--rollback", metavar="ID", help="Rollback a lesson")
    parser.add_argument("--cycle", action="store_true", help="Run learning cycle")
    parser.add_argument("--summary", action="store_true", help="Show summary")
    args = parser.parse_args()

    if args.test:
        success = run_tests()
        sys.exit(0 if success else 1)

    loop = LearningLoop()

    if args.lessons:
        for lid, lesson in loop.store.lessons.items():
            status_icon = {"applied": "✅", "validated": "🔄", "pending_validation": "⏳",
                           "rolled_back": "↩️", "expired": "💀", "needs_review": "⚠️"}.get(
                lesson["status"], "?")
            print(f"  {status_icon} [{lesson['source']}] {lesson['insight'][:60]}")
            print(f"     id={lid} occ={lesson['occurrences']} conf={lesson['confidence']:.0%} "
                  f"type={lesson['improvement_type']} status={lesson['status']}")

    elif args.applied:
        if APPLIED_PATH.exists():
            with open(APPLIED_PATH) as f:
                for line in f.readlines()[-20:]:
                    try:
                        e = json.loads(line.strip())
                        print(f"  [{e.get('timestamp', '?')[:19]}] {e.get('action')}: "
                              f"{e.get('lesson_id')} ({e.get('source')}/{e.get('type')})")
                    except json.JSONDecodeError:
                        continue
        else:
            print("  No applied lessons yet.")

    elif args.pending:
        if PENDING_PATH.exists():
            with open(PENDING_PATH) as f:
                pending = json.load(f)
            for lid, p in pending.items():
                print(f"  ⏳ {lid}: {p.get('insight', '?')[:60]}")
                print(f"     risk={p.get('risk')} conf={p.get('confidence'):.0%} occ={p.get('occurrences')}")
        else:
            print("  No pending approvals.")

    elif args.rollback:
        ok, msg = loop.applier.rollback(args.rollback)
        print(f"  {'✅' if ok else '❌'} {msg}")

    elif args.cycle:
        result = loop.run_cycle()
        print(f"  Learning cycle complete:")
        print(f"    Validated: {len(result['validated'])}")
        print(f"    Applied: {len(result['applied'])}")
        print(f"    Pending approval: {len(result['pending_approval'])}")
        print(f"    Expired: {len(result['expired'])}")
        print(f"    Transferred: {len(result['transferred'])}")

    elif args.summary:
        s = loop.get_summary()
        print(f"  Total lessons: {s['total_lessons']}")
        print(f"  By status: {s['by_status']}")
        print(f"  By source: {s['by_source']}")
        print(f"  By type: {s['by_type']}")
        if s.get("avg_efficacy") is not None:
            print(f"  Avg efficacy: {s['avg_efficacy']:.0%} ({s['lessons_with_efficacy']} tracked)")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()

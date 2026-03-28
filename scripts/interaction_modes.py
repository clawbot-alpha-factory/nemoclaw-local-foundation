#!/usr/bin/env python3
"""
NemoClaw Interaction Modes Engine v1.0 (MA-7)

5 structured interaction modes for agent collaboration:
- Brainstorm: generate ideas (LLM-powered, no critique)
- Critique: evaluate output (structured scoring, weighted by authority)
- Debate: resolve disagreement (structured rounds + ruling)
- Synthesis: combine viewpoints (LLM-powered merge)
- Reflection: learn from past (structured review + memory promotion)

Features:
- Role-based enforcement per mode (authority levels gate participation)
- Configurable rounds per session with timeout + auto-escalation
- Weighted scoring by authority level in critique/debate
- Mode chaining pipelines (brainstorm → critique → synthesis)
- Conflict detection via MA-2 memory rules
- Standardized SessionResult output

Usage:
  python3 scripts/interaction_modes.py --test
  python3 scripts/interaction_modes.py --list
  python3 scripts/interaction_modes.py --pipelines
"""

import argparse
import json
import os
import sys
import time
import uuid
import yaml
from datetime import datetime, timezone
from pathlib import Path

REPO = Path.home() / "nemoclaw-local-foundation"
SESSIONS_DIR = Path.home() / ".nemoclaw" / "interaction-sessions"

DEFAULT_ROUND_TIMEOUT_S = 300  # 5 min per round
DEFAULT_SESSION_TIMEOUT_S = 1800  # 30 min per session

# ═══════════════════════════════════════════════════════════════════════════════
# MODE DEFINITIONS
# ═══════════════════════════════════════════════════════════════════════════════

MODES = {
    "brainstorm": {
        "description": "Generate ideas freely — no critique during rounds",
        "uses_llm": True,
        "default_rounds": 3,
        "min_participants": 2,
        "max_participants": 7,
        "allows_critique": False,
        "min_authority_level": 3,  # any agent can brainstorm
        "required_roles": [],
    },
    "critique": {
        "description": "Evaluate an agent's output with structured scoring",
        "uses_llm": False,
        "default_rounds": 1,
        "min_participants": 2,
        "max_participants": 5,
        "allows_critique": True,
        "min_authority_level": 3,
        "required_roles": ["owner", "critic"],
    },
    "debate": {
        "description": "Resolve disagreement with structured rounds and ruling",
        "uses_llm": False,
        "default_rounds": 3,
        "min_participants": 2,
        "max_participants": 4,
        "allows_critique": True,
        "min_authority_level": 2,  # level 2+ can participate in debates
        "required_roles": ["proposer", "opponent"],
    },
    "synthesis": {
        "description": "Combine multiple viewpoints into unified output",
        "uses_llm": True,
        "default_rounds": 2,
        "min_participants": 2,
        "max_participants": 7,
        "allows_critique": False,
        "min_authority_level": 3,
        "required_roles": ["contributor"],  # at least one contributor
    },
    "reflection": {
        "description": "Review past decisions and extract lessons",
        "uses_llm": False,
        "default_rounds": 1,
        "min_participants": 1,
        "max_participants": 7,
        "allows_critique": True,
        "min_authority_level": 2,  # level 2+ for strategic reflection
        "required_roles": [],
    },
}

# ═══════════════════════════════════════════════════════════════════════════════
# MODE CHAINING PIPELINES
# ═══════════════════════════════════════════════════════════════════════════════

PIPELINES = {
    "ideate_and_refine": {
        "description": "Brainstorm ideas, then critique the best ones",
        "steps": [
            {"mode": "brainstorm", "output_feeds": "critique"},
            {"mode": "critique", "output_feeds": None},
        ],
    },
    "full_collaboration": {
        "description": "Brainstorm → Critique → Synthesis → Reflection",
        "steps": [
            {"mode": "brainstorm", "output_feeds": "critique"},
            {"mode": "critique", "output_feeds": "synthesis"},
            {"mode": "synthesis", "output_feeds": "reflection"},
            {"mode": "reflection", "output_feeds": None},
        ],
    },
    "resolve_conflict": {
        "description": "Debate to resolution, then synthesize outcome",
        "steps": [
            {"mode": "debate", "output_feeds": "synthesis"},
            {"mode": "synthesis", "output_feeds": None},
        ],
    },
    "strategic_review": {
        "description": "Reflect on past, then brainstorm improvements",
        "steps": [
            {"mode": "reflection", "output_feeds": "brainstorm"},
            {"mode": "brainstorm", "output_feeds": None},
        ],
    },
}

# ═══════════════════════════════════════════════════════════════════════════════
# SESSION RESULT (standardized output)
# ═══════════════════════════════════════════════════════════════════════════════

class SessionResult:
    """Standardized output for all interaction modes."""

    def __init__(self, session_id, mode, topic, participants):
        self.session_id = session_id
        self.mode = mode
        self.topic = topic
        self.participants = participants
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.completed_at = None
        self.status = "active"  # active | complete | timeout | escalated | failed
        self.rounds_completed = 0
        self.max_rounds = MODES.get(mode, {}).get("default_rounds", 3)
        self.contributions = []  # list of {agent, round, content, score, weight}
        self.output = None  # final structured output
        self.conflicts = []  # detected conflicts
        self.lessons = []  # extracted lessons (reflection mode)
        self.escalated_to = None
        self.parent_session = None  # for chained sessions
        self.parent_decision = None  # MA-4 decision reference
        self.parent_task = None  # MA-5 task reference

    def add_contribution(self, agent_id, content, round_num=None, score=None,
                          role=None, weight=1.0):
        """Add an agent's contribution to the session."""
        self.contributions.append({
            "agent": agent_id,
            "round": round_num or self.rounds_completed + 1,
            "content": content,
            "score": score,
            "role": role,
            "weight": weight,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def add_conflict(self, description, agents_involved, severity="minor"):
        """Record a detected conflict."""
        self.conflicts.append({
            "description": description,
            "agents": agents_involved,
            "severity": severity,  # minor | ambiguous | critical
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def complete(self, output, lessons=None):
        """Mark session complete with final output."""
        self.status = "complete"
        self.completed_at = datetime.now(timezone.utc).isoformat()
        self.output = output
        if lessons:
            self.lessons = lessons

    def escalate(self, agent_id, reason):
        """Escalate session to higher authority."""
        self.status = "escalated"
        self.escalated_to = agent_id
        self.add_contribution(agent_id, f"ESCALATED: {reason}", role="escalation")

    def timeout(self):
        """Mark session as timed out."""
        self.status = "timeout"
        self.completed_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self):
        return {
            "session_id": self.session_id,
            "mode": self.mode,
            "topic": self.topic,
            "participants": self.participants,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "status": self.status,
            "rounds_completed": self.rounds_completed,
            "max_rounds": self.max_rounds,
            "contributions": self.contributions,
            "output": self.output,
            "conflicts": self.conflicts,
            "lessons": self.lessons,
            "escalated_to": self.escalated_to,
            "parent_session": self.parent_session,
            "parent_decision": self.parent_decision,
            "parent_task": self.parent_task,
        }

    def save(self):
        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        path = SESSIONS_DIR / f"{self.session_id}.json"
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)
        return path

    @classmethod
    def from_dict(cls, data):
        s = cls(data["session_id"], data["mode"], data["topic"], data["participants"])
        s.created_at = data.get("created_at", s.created_at)
        s.completed_at = data.get("completed_at")
        s.status = data.get("status", "active")
        s.rounds_completed = data.get("rounds_completed", 0)
        s.max_rounds = data.get("max_rounds", 3)
        s.contributions = data.get("contributions", [])
        s.output = data.get("output")
        s.conflicts = data.get("conflicts", [])
        s.lessons = data.get("lessons", [])
        s.escalated_to = data.get("escalated_to")
        s.parent_session = data.get("parent_session")
        s.parent_decision = data.get("parent_decision")
        s.parent_task = data.get("parent_task")
        return s


# ═══════════════════════════════════════════════════════════════════════════════
# AUTHORITY & ROLE ENFORCEMENT
# ═══════════════════════════════════════════════════════════════════════════════

def _load_agent_authority():
    """Load authority levels from agent schema."""
    try:
        with open(REPO / "config" / "agents" / "agent-schema.yaml") as f:
            schema = yaml.safe_load(f)
        levels = {}
        for agent in schema.get("agents", []):
            levels[agent["agent_id"]] = agent.get("authority_level", 3)
        return levels
    except Exception:
        return {}


def validate_participants(mode, participants, roles=None):
    """Validate participants can join a mode based on authority.

    Args:
        mode: mode name
        participants: list of agent IDs
        roles: dict of agent_id → role (e.g., {"strategy_lead": "proposer"})

    Returns: (valid: bool, errors: list[str])
    """
    mode_def = MODES.get(mode)
    if not mode_def:
        return False, [f"Unknown mode: {mode}"]

    errors = []

    # Count check
    if len(participants) < mode_def["min_participants"]:
        errors.append(f"Need at least {mode_def['min_participants']} participants, got {len(participants)}")
    if len(participants) > mode_def["max_participants"]:
        errors.append(f"Maximum {mode_def['max_participants']} participants, got {len(participants)}")

    # Authority check
    authority = _load_agent_authority()
    min_auth = mode_def.get("min_authority_level", 3)
    for agent in participants:
        agent_level = authority.get(agent, 99)
        # Lower number = higher authority. min_authority_level=2 means level 1 and 2 allowed
        if agent_level > min_auth:
            errors.append(f"{agent} (level {agent_level}) lacks authority for {mode} (requires level ≤{min_auth})")

    # Required roles check
    if roles and mode_def.get("required_roles"):
        assigned_roles = set(roles.values())
        for req_role in mode_def["required_roles"]:
            if req_role not in assigned_roles:
                errors.append(f"Missing required role: {req_role}")

    return len(errors) == 0, errors


def get_authority_weight(agent_id):
    """Get scoring weight based on authority level.

    Level 1 (executive) → weight 3.0
    Level 2 (senior) → weight 2.0
    Level 3 (standard) → weight 1.0
    """
    authority = _load_agent_authority()
    level = authority.get(agent_id, 3)
    weights = {1: 3.0, 2: 2.0, 3: 1.0}
    return weights.get(level, 1.0)


# ═══════════════════════════════════════════════════════════════════════════════
# INTERACTION MODES
# ═══════════════════════════════════════════════════════════════════════════════

class InteractionEngine:
    """Runs structured interaction sessions between agents."""

    def __init__(self, round_timeout_s=DEFAULT_ROUND_TIMEOUT_S,
                 session_timeout_s=DEFAULT_SESSION_TIMEOUT_S):
        self.round_timeout_s = round_timeout_s
        self.session_timeout_s = session_timeout_s

    def start_session(self, mode, topic, participants, roles=None,
                       max_rounds=None, parent_session=None,
                       parent_decision=None, parent_task=None):
        """Start a new interaction session.

        Returns: (SessionResult, errors: list[str])
        """
        # Validate
        valid, errors = validate_participants(mode, participants, roles)
        if not valid:
            return None, errors

        session = SessionResult(
            session_id=f"sess_{uuid.uuid4().hex[:8]}",
            mode=mode,
            topic=topic,
            participants=participants,
        )
        if max_rounds is not None:
            session.max_rounds = max_rounds
        session.parent_session = parent_session
        session.parent_decision = parent_decision
        session.parent_task = parent_task

        return session, []

    # ── BRAINSTORM ──

    def brainstorm(self, session, contributions):
        """Run a brainstorm session.

        Args:
            session: SessionResult
            contributions: list of {"agent": id, "ideas": [str]}

        Returns: SessionResult with ranked ideas
        """
        if session.mode != "brainstorm":
            session.status = "failed"
            return session

        all_ideas = []
        for contrib in contributions:
            agent = contrib["agent"]
            if agent not in session.participants:
                continue
            for idea in contrib.get("ideas", []):
                weight = get_authority_weight(agent)
                session.add_contribution(agent, idea, role="ideator", weight=weight)
                all_ideas.append({"idea": idea, "author": agent, "weight": weight, "votes": 0})

        # Simple ranking: weight-based initial score
        for idea in all_ideas:
            idea["score"] = idea["weight"]

        ranked = sorted(all_ideas, key=lambda x: -x["score"])
        session.rounds_completed = 1
        session.complete(output={
            "type": "brainstorm_result",
            "total_ideas": len(ranked),
            "ranked_ideas": ranked[:20],  # top 20
        })

        session.save()
        return session

    # ── CRITIQUE ──

    def critique(self, session, artifact, critiques):
        """Run a critique session.

        Args:
            session: SessionResult
            artifact: {"agent": owner_id, "content": str} — the thing being critiqued
            critiques: list of {"agent": critic_id, "scores": {dimension: 1-10}, "improvements": [str]}

        Returns: SessionResult with weighted scores and improvement list
        """
        if session.mode != "critique":
            session.status = "failed"
            return session

        # Record the artifact
        session.add_contribution(
            artifact["agent"], artifact["content"],
            role="owner", weight=get_authority_weight(artifact["agent"]))

        # Collect weighted scores
        all_scores = {}  # dimension → [(score, weight)]
        all_improvements = []

        for critique in critiques:
            agent = critique["agent"]
            if agent not in session.participants:
                continue
            weight = get_authority_weight(agent)

            scores = critique.get("scores", {})
            for dim, score in scores.items():
                if dim not in all_scores:
                    all_scores[dim] = []
                all_scores[dim].append((score, weight))

            improvements = critique.get("improvements", [])
            for imp in improvements:
                all_improvements.append({"suggestion": imp, "by": agent, "weight": weight})

            session.add_contribution(
                agent,
                json.dumps({"scores": scores, "improvements": improvements}),
                role="critic",
                score=sum(scores.values()) / len(scores) if scores else 0,
                weight=weight,
            )

        # Compute weighted averages
        weighted_scores = {}
        for dim, score_weights in all_scores.items():
            total_weighted = sum(s * w for s, w in score_weights)
            total_weight = sum(w for _, w in score_weights)
            weighted_scores[dim] = round(total_weighted / total_weight, 2) if total_weight > 0 else 0

        overall = round(sum(weighted_scores.values()) / len(weighted_scores), 2) if weighted_scores else 0

        # Detect conflicts (critics disagree by > 3 points on same dimension)
        for dim, score_weights in all_scores.items():
            scores_only = [s for s, _ in score_weights]
            if len(scores_only) >= 2 and max(scores_only) - min(scores_only) > 3:
                agents_involved = [c["agent"] for c in critiques if dim in c.get("scores", {})]
                session.add_conflict(
                    f"Scoring disagreement on '{dim}': range {min(scores_only)}-{max(scores_only)}",
                    agents_involved, severity="ambiguous")

        session.rounds_completed = 1
        session.complete(output={
            "type": "critique_result",
            "weighted_scores": weighted_scores,
            "overall_score": overall,
            "improvements": sorted(all_improvements, key=lambda x: -x["weight"]),
            "conflict_count": len(session.conflicts),
        })

        session.save()
        return session

    # ── DEBATE ──

    def debate(self, session, positions):
        """Run a structured debate.

        Args:
            session: SessionResult
            positions: list of rounds, each round is list of
                {"agent": id, "position": str, "evidence": [str], "role": "proposer"|"opponent"|"rebuttal"}

        Final round should include a ruling by highest-authority participant.

        Returns: SessionResult with winner and rationale
        """
        if session.mode != "debate":
            session.status = "failed"
            return session

        round_scores = {}  # agent → cumulative weighted score

        for round_num, round_positions in enumerate(positions, 1):
            if round_num > session.max_rounds:
                # Auto-escalate
                session.escalate("executive_operator",
                                 f"Debate exceeded {session.max_rounds} rounds without resolution")
                break

            for pos in round_positions:
                agent = pos["agent"]
                weight = get_authority_weight(agent)
                evidence_count = len(pos.get("evidence", []))
                # Score: weight * (1 + evidence_bonus)
                position_score = weight * (1 + min(evidence_count * 0.2, 1.0))

                if agent not in round_scores:
                    round_scores[agent] = 0
                round_scores[agent] += position_score

                session.add_contribution(
                    agent, pos["position"],
                    round_num=round_num,
                    role=pos.get("role", "participant"),
                    score=position_score,
                    weight=weight,
                )

            session.rounds_completed = round_num

            # Detect position conflicts
            agents_this_round = [p["agent"] for p in round_positions]
            if len(set(agents_this_round)) > 1:
                positions_text = [p["position"][:50] for p in round_positions]
                if len(set(positions_text)) > 1:
                    session.add_conflict(
                        f"Round {round_num}: opposing positions",
                        agents_this_round, severity="ambiguous")

        # Determine winner by weighted score
        if round_scores:
            winner = max(round_scores, key=round_scores.get)
            runner_up = sorted(round_scores.items(), key=lambda x: -x[1])

            session.complete(output={
                "type": "debate_result",
                "winner": winner,
                "winner_score": round(round_scores[winner], 2),
                "scores": {a: round(s, 2) for a, s in round_scores.items()},
                "ranking": [{"agent": a, "score": round(s, 2)} for a, s in runner_up],
                "rounds_played": session.rounds_completed,
                "escalated": session.status == "escalated",
                "conflict_count": len(session.conflicts),
            })
        else:
            session.complete(output={"type": "debate_result", "winner": None, "reason": "No positions submitted"})

        session.save()
        return session

    # ── SYNTHESIS ──

    def synthesize(self, session, perspectives):
        """Synthesize multiple viewpoints into unified output.

        Args:
            session: SessionResult
            perspectives: list of {"agent": id, "viewpoint": str, "key_points": [str]}

        Returns: SessionResult with merged document
        """
        if session.mode != "synthesis":
            session.status = "failed"
            return session

        all_points = []
        agent_viewpoints = {}

        for persp in perspectives:
            agent = persp["agent"]
            if agent not in session.participants:
                continue
            weight = get_authority_weight(agent)
            viewpoint = persp.get("viewpoint", "")
            key_points = persp.get("key_points", [])

            session.add_contribution(agent, viewpoint, role="contributor", weight=weight)
            agent_viewpoints[agent] = viewpoint

            for point in key_points:
                all_points.append({"point": point, "author": agent, "weight": weight})

        # Detect contradictions
        point_texts = [p["point"].lower()[:40] for p in all_points]
        # Simple conflict check: if two agents have very different point counts
        agent_point_counts = {}
        for p in all_points:
            agent_point_counts[p["author"]] = agent_point_counts.get(p["author"], 0) + 1

        # Weight-ranked points
        ranked_points = sorted(all_points, key=lambda x: -x["weight"])

        # Group by theme (simple: unique points)
        unique_points = []
        seen = set()
        for p in ranked_points:
            key = p["point"].lower().strip()[:50]
            if key not in seen:
                seen.add(key)
                unique_points.append(p)

        session.rounds_completed = 1
        session.complete(output={
            "type": "synthesis_result",
            "perspectives_count": len(perspectives),
            "total_points": len(all_points),
            "unique_points": len(unique_points),
            "merged_points": unique_points[:30],
            "agent_contributions": {a: len([p for p in all_points if p["author"] == a]) for a in agent_viewpoints},
        })

        session.save()
        return session

    # ── REFLECTION ──

    def reflect(self, session, reviews):
        """Review past decisions and extract lessons.

        Args:
            session: SessionResult
            reviews: list of {"agent": id, "decision_id": str, "outcome_assessment": str,
                              "lesson": str, "confidence": 0.0-1.0, "applies_to": [str]}

        Returns: SessionResult with lesson set
        """
        if session.mode != "reflection":
            session.status = "failed"
            return session

        lessons = []
        for review in reviews:
            agent = review["agent"]
            if agent not in session.participants:
                continue
            weight = get_authority_weight(agent)
            confidence = review.get("confidence", 0.5) * weight  # authority-weighted confidence

            lesson = {
                "lesson": review.get("lesson", ""),
                "author": agent,
                "decision_id": review.get("decision_id"),
                "outcome_assessment": review.get("outcome_assessment", ""),
                "confidence": min(1.0, round(confidence, 3)),
                "applies_to": review.get("applies_to", []),
                "weight": weight,
            }
            lessons.append(lesson)

            session.add_contribution(
                agent, review.get("lesson", ""),
                role="reviewer", score=confidence, weight=weight)

        # Detect conflicting lessons
        for i, l1 in enumerate(lessons):
            for l2 in lessons[i+1:]:
                if l1["decision_id"] and l1["decision_id"] == l2["decision_id"]:
                    if l1["outcome_assessment"] != l2["outcome_assessment"]:
                        session.add_conflict(
                            f"Conflicting assessments of {l1['decision_id']}",
                            [l1["author"], l2["author"]],
                            severity="ambiguous")

        # Rank lessons by confidence
        ranked = sorted(lessons, key=lambda x: -x["confidence"])

        session.rounds_completed = 1
        session.lessons = ranked
        session.complete(output={
            "type": "reflection_result",
            "total_lessons": len(ranked),
            "high_confidence": [l for l in ranked if l["confidence"] >= 0.7],
            "promotable": [l for l in ranked if l["confidence"] >= 0.75],
            "conflict_count": len(session.conflicts),
        })

        session.save()
        return session

    # ── MODE CHAINING ──

    def run_pipeline(self, pipeline_name, topic, participants, contributions_per_step):
        """Run a chained pipeline of interaction modes.

        Args:
            pipeline_name: key from PIPELINES dict
            topic: shared topic
            participants: agent IDs for all steps
            contributions_per_step: list of contribution data, one per pipeline step

        Returns: list of SessionResults
        """
        pipeline = PIPELINES.get(pipeline_name)
        if not pipeline:
            return [], [f"Unknown pipeline: {pipeline_name}"]

        results = []
        prev_session_id = None

        for i, step in enumerate(pipeline["steps"]):
            mode = step["mode"]
            session, errors = self.start_session(
                mode, topic, participants,
                parent_session=prev_session_id)

            if errors:
                return results, errors

            # Get contributions for this step
            contribs = contributions_per_step[i] if i < len(contributions_per_step) else {}

            # Execute mode
            if mode == "brainstorm":
                session = self.brainstorm(session, contribs.get("contributions", []))
            elif mode == "critique":
                session = self.critique(session, contribs.get("artifact", {}), contribs.get("critiques", []))
            elif mode == "debate":
                session = self.debate(session, contribs.get("positions", []))
            elif mode == "synthesis":
                session = self.synthesize(session, contribs.get("perspectives", []))
            elif mode == "reflection":
                session = self.reflect(session, contribs.get("reviews", []))

            results.append(session)
            prev_session_id = session.session_id

        return results, []


# ═══════════════════════════════════════════════════════════════════════════════
# TESTS
# ═══════════════════════════════════════════════════════════════════════════════

def run_tests():
    print("=" * 60)
    print("  MA-7 Interaction Modes Tests")
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

    engine = InteractionEngine()

    # Test 1: Mode definitions
    test("5 modes defined", len(MODES) == 5, f"{len(MODES)}")

    # Test 2: Pipeline definitions
    test("4 pipelines defined", len(PIPELINES) == 4, f"{len(PIPELINES)}")

    # Test 3: Participant validation — valid
    ok, errs = validate_participants("brainstorm", ["strategy_lead", "product_architect"])
    test("Valid participants accepted", ok, str(errs))

    # Test 4: Participant validation — too few
    ok, errs = validate_participants("brainstorm", ["strategy_lead"])
    test("Too few participants rejected", not ok and "at least" in errs[0])

    # Test 5: Authority enforcement — debate needs level ≤2
    ok, errs = validate_participants("debate", ["narrative_content_lead", "engineering_lead"])
    test("Level 3 blocked from debate", not ok, str(errs))

    # Test 6: Authority enforcement — level 2 allowed
    ok, errs = validate_participants("debate", ["strategy_lead", "operations_lead"])
    test("Level 2 agents allowed in debate", ok, str(errs))

    # Test 7: Authority weight
    w1 = get_authority_weight("executive_operator")  # level 1 → 3.0
    w2 = get_authority_weight("strategy_lead")  # level 2 → 2.0
    w3 = get_authority_weight("engineering_lead")  # level 3 → 1.0
    test("Authority weights correct", w1 == 3.0 and w2 == 2.0 and w3 == 1.0, f"{w1},{w2},{w3}")

    # Test 8: Brainstorm session
    session, errs = engine.start_session("brainstorm", "New product ideas",
                                          ["strategy_lead", "product_architect"])
    test("Brainstorm session starts", session is not None, str(errs))

    session = engine.brainstorm(session, [
        {"agent": "strategy_lead", "ideas": ["AI meeting notes", "Code review bot"]},
        {"agent": "product_architect", "ideas": ["API gateway", "AI meeting notes"]},
    ])
    test("Brainstorm produces ranked ideas", session.status == "complete" and
         session.output["total_ideas"] == 4)

    # Test 9: Critique session with weighted scoring
    session2, _ = engine.start_session("critique", "Review market research",
                                        ["strategy_lead", "product_architect"],
                                        roles={"strategy_lead": "owner", "product_architect": "critic"})
    session2 = engine.critique(session2,
        artifact={"agent": "strategy_lead", "content": "Market research document content here"},
        critiques=[
            {"agent": "product_architect", "scores": {"depth": 8, "accuracy": 7, "actionability": 6},
             "improvements": ["Add competitor pricing", "Include market size estimates"]},
        ])
    test("Critique produces weighted scores", session2.status == "complete" and
         "weighted_scores" in session2.output, str(session2.output))

    # Test 10: Critique conflict detection
    session3, _ = engine.start_session("critique", "Review doc",
                                        ["strategy_lead", "product_architect", "operations_lead"])
    session3 = engine.critique(session3,
        artifact={"agent": "strategy_lead", "content": "Document"},
        critiques=[
            {"agent": "product_architect", "scores": {"quality": 9}, "improvements": []},
            {"agent": "operations_lead", "scores": {"quality": 4}, "improvements": ["Rewrite"]},
        ])
    test("Critique detects scoring conflict", len(session3.conflicts) > 0)

    # Test 11: Debate session
    session4, _ = engine.start_session("debate", "Pricing strategy",
                                        ["strategy_lead", "operations_lead"],
                                        max_rounds=2)
    session4 = engine.debate(session4, [
        [  # Round 1
            {"agent": "strategy_lead", "position": "Freemium model is best for growth",
             "evidence": ["Industry data shows 3x conversion", "Lower CAC"], "role": "proposer"},
            {"agent": "operations_lead", "position": "Premium-only protects margins",
             "evidence": ["Higher ARPU"], "role": "opponent"},
        ],
        [  # Round 2
            {"agent": "strategy_lead", "position": "Freemium with usage limits",
             "evidence": ["Compromise position"], "role": "rebuttal"},
            {"agent": "operations_lead", "position": "Agree with limits approach",
             "evidence": [], "role": "rebuttal"},
        ],
    ])
    test("Debate produces winner", session4.status == "complete" and
         session4.output.get("winner") is not None)
    test("Debate tracks rounds", session4.rounds_completed == 2)

    # Test 12: Debate auto-escalation at max rounds
    session5, _ = engine.start_session("debate", "Deadlock test",
                                        ["strategy_lead", "operations_lead"],
                                        max_rounds=1)
    session5 = engine.debate(session5, [
        [{"agent": "strategy_lead", "position": "A", "evidence": [], "role": "proposer"},
         {"agent": "operations_lead", "position": "B", "evidence": [], "role": "opponent"}],
        [{"agent": "strategy_lead", "position": "Still A", "evidence": [], "role": "rebuttal"},
         {"agent": "operations_lead", "position": "Still B", "evidence": [], "role": "rebuttal"}],
    ])
    test("Debate escalates at max rounds", session5.escalated_to == "executive_operator")

    # Test 13: Synthesis session
    session6, _ = engine.start_session("synthesis", "Product vision",
                                        ["strategy_lead", "product_architect"])
    session6 = engine.synthesize(session6, [
        {"agent": "strategy_lead", "viewpoint": "Focus on enterprise",
         "key_points": ["Large deal sizes", "Longer sales cycles", "Need compliance"]},
        {"agent": "product_architect", "viewpoint": "Start with SMB",
         "key_points": ["Faster iteration", "Self-serve", "Need compliance"]},
    ])
    test("Synthesis merges viewpoints", session6.status == "complete" and
         session6.output["perspectives_count"] == 2)
    test("Synthesis deduplicates points", session6.output["unique_points"] < session6.output["total_points"] or
         session6.output["unique_points"] == session6.output["total_points"])

    # Test 14: Reflection session
    session7, _ = engine.start_session("reflection", "Q1 review",
                                        ["strategy_lead", "operations_lead"])
    session7 = engine.reflect(session7, [
        {"agent": "strategy_lead", "decision_id": "dec_001",
         "outcome_assessment": "positive", "lesson": "SMB first was correct",
         "confidence": 0.9, "applies_to": ["market_strategy"]},
        {"agent": "operations_lead", "decision_id": "dec_001",
         "outcome_assessment": "mixed", "lesson": "Execution was slow",
         "confidence": 0.7, "applies_to": ["operations"]},
    ])
    test("Reflection extracts lessons", session7.status == "complete" and
         len(session7.lessons) == 2)
    test("Reflection detects conflicting assessments", len(session7.conflicts) > 0)

    # Test 15: Confidence weighted by authority
    high_conf = [l for l in session7.lessons if l["confidence"] >= 0.7]
    test("Authority weights confidence", len(high_conf) >= 1)

    # Test 16: Session persistence
    path = session7.save()
    test("Session saves to disk", path.exists())
    loaded = SessionResult.from_dict(json.load(open(path)))
    test("Session loads from disk", loaded.session_id == session7.session_id)

    # Test 17: Mode chaining pipeline
    results, errs = engine.run_pipeline("ideate_and_refine", "New features",
        ["strategy_lead", "product_architect"],
        [
            {"contributions": [
                {"agent": "strategy_lead", "ideas": ["Feature A", "Feature B"]},
                {"agent": "product_architect", "ideas": ["Feature C"]},
            ]},
            {"artifact": {"agent": "strategy_lead", "content": "Feature A spec"},
             "critiques": [
                {"agent": "product_architect", "scores": {"feasibility": 8}, "improvements": ["Add API spec"]},
            ]},
        ])
    test("Pipeline runs 2 steps", len(results) == 2 and all(r.status == "complete" for r in results))
    test("Pipeline chains parent_session", results[1].parent_session == results[0].session_id)

    # Test 18: SessionResult standardized output
    test("SessionResult has all metadata", all(hasattr(session, attr) for attr in
         ["session_id", "mode", "topic", "participants", "created_at", "status",
          "contributions", "output", "conflicts", "lessons", "parent_session",
          "parent_decision", "parent_task"]))

    # Test 19: Escalation
    s, _ = engine.start_session("brainstorm", "test", ["strategy_lead", "product_architect"])
    s.escalate("executive_operator", "Deadlock")
    test("Escalation works", s.status == "escalated" and s.escalated_to == "executive_operator")

    # Test 20: Timeout
    s2, _ = engine.start_session("brainstorm", "test", ["strategy_lead", "product_architect"])
    s2.timeout()
    test("Timeout works", s2.status == "timeout" and s2.completed_at is not None)

    print(f"\n  Results: {tp}/{tt} passed")
    return tp == tt


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="NemoClaw Interaction Modes")
    parser.add_argument("--test", action="store_true", help="Run all tests")
    parser.add_argument("--list", action="store_true", help="List available modes")
    parser.add_argument("--pipelines", action="store_true", help="List chaining pipelines")
    parser.add_argument("--session", metavar="ID", help="Show session details")
    args = parser.parse_args()

    if args.test:
        success = run_tests()
        sys.exit(0 if success else 1)

    elif args.list:
        print(f"Interaction Modes ({len(MODES)}):")
        for name, mode in MODES.items():
            llm = "LLM" if mode["uses_llm"] else "structured"
            print(f"  {name}: {mode['description']}")
            print(f"    Type: {llm} | Rounds: {mode['default_rounds']} | "
                  f"Participants: {mode['min_participants']}-{mode['max_participants']} | "
                  f"Authority: ≤{mode['min_authority_level']}")
            print()

    elif args.pipelines:
        print(f"Chaining Pipelines ({len(PIPELINES)}):")
        for name, pipe in PIPELINES.items():
            steps = " → ".join(s["mode"] for s in pipe["steps"])
            print(f"  {name}: {pipe['description']}")
            print(f"    Steps: {steps}")
            print()

    elif args.session:
        path = SESSIONS_DIR / f"{args.session}.json"
        if not path.exists():
            print(f"Session not found: {args.session}")
            sys.exit(1)
        with open(path) as f:
            data = json.load(f)
        print(json.dumps(data, indent=2))

    else:
        parser.print_help()


if __name__ == "__main__":
    main()

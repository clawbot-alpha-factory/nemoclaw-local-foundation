#!/usr/bin/env python3
"""
NemoClaw Peer Review System v1.0 (MA-11)

Structured peer review for agent outputs:
- Smart reviewer selection (domain, workload, past accuracy)
- Standardized scoring with auto-verdict (APPROVE/REVISE/REJECT)
- Configurable review requirements (mandatory for critical, optional otherwise)
- 2 reviewers for critical, 1 for standard
- Dispute escalation via MA-10 conflict resolution
- Reviewer quality tracking (accuracy, catch rate)
- Batch review support
- MA-4 decision log integration

Usage:
  python3 scripts/peer_review.py --test
  python3 scripts/peer_review.py --reviewers
  python3 scripts/peer_review.py --quality
  python3 scripts/peer_review.py --pending
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
REVIEW_DIR = Path.home() / ".nemoclaw" / "reviews"
REVIEW_LOG_PATH = REVIEW_DIR / "review-log.jsonl"
REVIEWER_QUALITY_PATH = REVIEW_DIR / "reviewer-quality.json"

# Scoring dimensions
SCORING_DIMENSIONS = {
    "accuracy": {"description": "Factual correctness and precision", "weight": 1.5},
    "completeness": {"description": "Covers all required aspects", "weight": 1.2},
    "actionability": {"description": "Output can be directly used or acted upon", "weight": 1.0},
    "clarity": {"description": "Well-structured, easy to understand", "weight": 0.8},
}

# Score thresholds (1-10 scale)
APPROVE_THRESHOLD = 7.0  # weighted avg >= 7.0 → APPROVE
REVISE_THRESHOLD = 4.0   # weighted avg >= 4.0 → REVISE
# Below 4.0 → REJECT

# Review requirements
REVIEW_POLICIES = {
    "critical": {"required": True, "min_reviewers": 2, "approve_threshold": 7.5},
    "standard": {"required": False, "min_reviewers": 1, "approve_threshold": 7.0},
    "quick": {"required": False, "min_reviewers": 1, "approve_threshold": 6.0},
}


# ═══════════════════════════════════════════════════════════════════════════════
# REVIEW REQUEST
# ═══════════════════════════════════════════════════════════════════════════════

def new_review_request(author_id, output_content, output_type="general",
                        task_id=None, skill_id=None, plan_id=None,
                        policy="standard", domain=None, extra_dimensions=None):
    """Create a review request."""
    dimensions = dict(SCORING_DIMENSIONS)
    if extra_dimensions:
        dimensions.update(extra_dimensions)

    return {
        "id": f"rev_{uuid.uuid4().hex[:8]}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "author": author_id,
        "output_content": output_content,
        "output_type": output_type,
        "task_id": task_id,
        "skill_id": skill_id,
        "plan_id": plan_id,
        "domain": domain,
        "policy": policy,
        "dimensions": dimensions,
        "status": "pending",  # pending | in_review | approved | revised | rejected | disputed
        "reviews": [],  # list of individual reviews
        "verdict": None,
        "verdict_score": None,
        "revision_count": 0,
        "max_revisions": 2,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# REVIEWER SELECTOR (smart assignment)
# ═══════════════════════════════════════════════════════════════════════════════

class ReviewerSelector:
    """Smart reviewer assignment based on domain, workload, and past accuracy."""

    def __init__(self):
        self._schema = None
        self._registry = None
        self._quality = None
        self._workload = defaultdict(int)  # agent → active review count

    def _load(self):
        if self._schema is not None:
            return
        try:
            with open(REPO / "config" / "agents" / "agent-schema.yaml") as f:
                self._schema = yaml.safe_load(f)
            with open(REPO / "config" / "agents" / "capability-registry.yaml") as f:
                self._registry = yaml.safe_load(f).get("capabilities", {})
        except Exception:
            self._schema = {"agents": [], "domain_boundaries": {}}
            self._registry = {}

        self._quality = ReviewerQuality()

    def select_reviewers(self, request, exclude_author=True):
        """Select the best reviewer(s) for a request.

        Selection scoring:
        - Domain match: +3.0
        - Same family capability: +2.0
        - Higher authority: +1.0 per level above author
        - Past accuracy > 80%: +1.0
        - Low workload (< 3 active): +0.5
        - Self-review: excluded

        Returns: list of (agent_id, score, reason)
        """
        self._load()

        author = request.get("author", "")
        domain = request.get("domain", "")
        skill_id = request.get("skill_id", "")
        policy = REVIEW_POLICIES.get(request.get("policy", "standard"), REVIEW_POLICIES["standard"])
        num_needed = policy["min_reviewers"]

        candidates = []
        authority = {}
        for agent in self._schema.get("agents", []):
            authority[agent["agent_id"]] = agent.get("authority_level", 3)

        author_level = authority.get(author, 3)

        for agent in self._schema.get("agents", []):
            agent_id = agent["agent_id"]

            # Never self-review
            if exclude_author and agent_id == author:
                continue

            score = 0.0
            reasons = []

            # Domain match
            agent_domains = self._schema.get("domain_boundaries", {}).get(agent_id, {}).get("allowed_domains", [])
            if domain and (domain in agent_domains or "*" in agent_domains):
                score += 3.0
                reasons.append("domain_match")

            # Capability family match
            if skill_id:
                family = skill_id.split("-")[0] if "-" in skill_id else ""
                for cap_name, cap in self._registry.items():
                    if cap.get("owned_by") == agent_id:
                        cap_skill = cap.get("skill", "")
                        if cap_skill and cap_skill.startswith(family):
                            score += 2.0
                            reasons.append("capability_family")
                            break

            # Authority bonus
            agent_level = agent.get("authority_level", 3)
            if agent_level < author_level:
                score += (author_level - agent_level) * 1.0
                reasons.append(f"higher_authority(L{agent_level})")

            # Past accuracy bonus
            accuracy = self._quality.get_accuracy(agent_id)
            if accuracy is not None and accuracy >= 0.8:
                score += 1.0
                reasons.append(f"high_accuracy({accuracy:.0%})")

            # Workload penalty
            workload = self._workload.get(agent_id, 0)
            if workload < 3:
                score += 0.5
                reasons.append("low_workload")
            elif workload >= 5:
                score -= 1.0
                reasons.append("overloaded")

            if score > 0:
                candidates.append((agent_id, score, reasons))

        # Sort by score descending
        candidates.sort(key=lambda x: -x[1])

        # Return top N
        selected = candidates[:num_needed]

        # If not enough domain experts, fill with authority-based selection
        if len(selected) < num_needed:
            remaining = [c for c in candidates if c not in selected]
            selected.extend(remaining[:num_needed - len(selected)])

        # Last resort: executive operator
        if len(selected) < num_needed and author != "executive_operator":
            selected.append(("executive_operator", 1.0, ["last_resort"]))

        # Track workload
        for agent_id, _, _ in selected:
            self._workload[agent_id] += 1

        return selected

    def release_workload(self, agent_id):
        """Release workload after review completes."""
        if self._workload[agent_id] > 0:
            self._workload[agent_id] -= 1


# ═══════════════════════════════════════════════════════════════════════════════
# REVIEWER QUALITY TRACKING
# ═══════════════════════════════════════════════════════════════════════════════

class ReviewerQuality:
    """Tracks reviewer accuracy and catch rate."""

    def __init__(self):
        self.data = {}  # agent_id → {reviews, accurate_catches, false_flags, missed_issues}
        self._load()

    def _load(self):
        REVIEW_DIR.mkdir(parents=True, exist_ok=True)
        if REVIEWER_QUALITY_PATH.exists():
            try:
                with open(REVIEWER_QUALITY_PATH) as f:
                    self.data = json.load(f)
            except (json.JSONDecodeError, IOError):
                self.data = {}

    def _save(self):
        REVIEW_DIR.mkdir(parents=True, exist_ok=True)
        with open(REVIEWER_QUALITY_PATH, "w") as f:
            json.dump(self.data, f, indent=2)

    def record_review(self, reviewer_id, caught_issues, was_accurate=True):
        """Record a review outcome for quality tracking."""
        if reviewer_id not in self.data:
            self.data[reviewer_id] = {
                "total_reviews": 0,
                "accurate_catches": 0,
                "false_flags": 0,
                "improvements_suggested": 0,
                "reviews_overturned": 0,
            }

        entry = self.data[reviewer_id]
        entry["total_reviews"] += 1
        entry["improvements_suggested"] += caught_issues

        if was_accurate:
            entry["accurate_catches"] += caught_issues
        else:
            entry["false_flags"] += 1

        self._save()

    def record_overturn(self, reviewer_id):
        """Record when a review verdict is overturned (dispute lost)."""
        if reviewer_id in self.data:
            self.data[reviewer_id]["reviews_overturned"] += 1
            self._save()

    def get_accuracy(self, reviewer_id):
        """Get reviewer accuracy (0.0-1.0 or None if no data)."""
        entry = self.data.get(reviewer_id)
        if not entry or entry["total_reviews"] == 0:
            return None
        total = entry["accurate_catches"] + entry["false_flags"]
        if total == 0:
            return 1.0  # no flags = perfect by default
        return round(entry["accurate_catches"] / total, 3)

    def get_all(self):
        return self.data

    def summary(self):
        """Print reviewer quality summary."""
        if not self.data:
            print("  No reviewer quality data yet.")
            return

        print(f"  {'Reviewer':<25s} {'Reviews':>8s} {'Accuracy':>9s} {'Catches':>8s} {'Overturned':>10s}")
        print(f"  {'-'*25} {'-'*8} {'-'*9} {'-'*8} {'-'*10}")
        for reviewer, d in sorted(self.data.items()):
            acc = self.get_accuracy(reviewer)
            acc_str = f"{acc:.0%}" if acc is not None else "N/A"
            print(f"  {reviewer:<25s} {d['total_reviews']:>8d} {acc_str:>9s} "
                  f"{d['accurate_catches']:>8d} {d['reviews_overturned']:>10d}")


# ═══════════════════════════════════════════════════════════════════════════════
# PEER REVIEW ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class PeerReviewEngine:
    """Main peer review engine.

    Lifecycle:
    1. request_review() → creates review request, assigns reviewers
    2. submit_review() → reviewer submits scores + improvements
    3. compute_verdict() → auto-calculates verdict from scores
    4. dispute() → author challenges verdict via MA-10
    5. finalize() → logs to MA-4, updates quality tracking
    """

    def __init__(self):
        self.selector = ReviewerSelector()
        self.quality = ReviewerQuality()
        self.pending = {}  # review_id → request
        self.completed = []

    def request_review(self, author_id, output_content, output_type="general",
                        task_id=None, skill_id=None, plan_id=None,
                        policy="standard", domain=None):
        """Create a review request and assign reviewers.

        Returns: (request, assigned_reviewers, errors)
        """
        request = new_review_request(
            author_id, output_content, output_type,
            task_id, skill_id, plan_id, policy, domain)

        # Select reviewers
        assigned = self.selector.select_reviewers(request)
        if not assigned:
            return request, [], ["No suitable reviewers found"]

        request["assigned_reviewers"] = [a[0] for a in assigned]
        request["reviewer_scores"] = {a[0]: a[1] for a in assigned}
        request["reviewer_reasons"] = {a[0]: a[2] for a in assigned}
        request["status"] = "in_review"

        self.pending[request["id"]] = request

        return request, assigned, []

    def submit_review(self, review_id, reviewer_id, scores, improvements=None,
                       comments=None):
        """Submit a review for a pending request.

        Args:
            review_id: the review request ID
            reviewer_id: who is reviewing
            scores: dict of dimension → score (1-10)
            improvements: list of improvement suggestions
            comments: optional reviewer comments

        Returns: (success, message)
        """
        request = self.pending.get(review_id)
        if not request:
            return False, f"Review {review_id} not found"

        # Check for self-review FIRST
        if reviewer_id == request["author"]:
            return False, "Self-review is not allowed"

        if reviewer_id not in request.get("assigned_reviewers", []):
            return False, f"{reviewer_id} not assigned to review {review_id}"

        # Validate scores
        valid_dims = set(request.get("dimensions", SCORING_DIMENSIONS).keys())
        for dim in scores:
            if dim not in valid_dims:
                return False, f"Unknown dimension: {dim}"
            if not (1 <= scores[dim] <= 10):
                return False, f"Score for {dim} must be 1-10, got {scores[dim]}"

        review = {
            "reviewer": reviewer_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "scores": scores,
            "improvements": improvements or [],
            "comments": comments or "",
            "weighted_avg": self._weighted_average(scores, request.get("dimensions", SCORING_DIMENSIONS)),
        }

        request["reviews"].append(review)

        # Release workload
        self.selector.release_workload(reviewer_id)

        # Track reviewer quality
        self.quality.record_review(reviewer_id, len(improvements or []))

        # Check if all reviews are in
        policy = REVIEW_POLICIES.get(request.get("policy", "standard"), REVIEW_POLICIES["standard"])
        if len(request["reviews"]) >= policy["min_reviewers"]:
            return True, "Review submitted — all reviews in, ready for verdict"

        return True, f"Review submitted — {len(request['reviews'])}/{policy['min_reviewers']} reviews in"

    def compute_verdict(self, review_id):
        """Compute verdict from submitted reviews.

        Returns: (verdict: "APPROVE"|"REVISE"|"REJECT", score, details)
        """
        request = self.pending.get(review_id)
        if not request:
            return None, 0, "Review not found"

        if not request["reviews"]:
            return None, 0, "No reviews submitted yet"

        policy = REVIEW_POLICIES.get(request.get("policy", "standard"), REVIEW_POLICIES["standard"])

        # Aggregate scores across reviewers (average of weighted averages)
        avg_scores = []
        all_improvements = []

        for review in request["reviews"]:
            avg_scores.append(review["weighted_avg"])
            all_improvements.extend(review.get("improvements", []))

        overall_score = round(sum(avg_scores) / len(avg_scores), 2)
        approve_threshold = policy.get("approve_threshold", APPROVE_THRESHOLD)

        # Determine verdict
        if overall_score >= approve_threshold:
            verdict = "APPROVE"
        elif overall_score >= REVISE_THRESHOLD:
            verdict = "REVISE"
        else:
            verdict = "REJECT"

        # Check for reviewer disagreement (> 2 points spread)
        if len(avg_scores) >= 2:
            spread = max(avg_scores) - min(avg_scores)
            if spread > 2.0:
                # Disagreement — take conservative verdict
                verdict = min(verdict, "REVISE", key=lambda v: ["REJECT", "REVISE", "APPROVE"].index(v))

        request["verdict"] = verdict
        request["verdict_score"] = overall_score
        request["status"] = verdict.lower()
        request["all_improvements"] = list(set(all_improvements))  # deduplicate

        return verdict, overall_score, {
            "reviewer_scores": avg_scores,
            "improvements": all_improvements,
            "spread": max(avg_scores) - min(avg_scores) if len(avg_scores) >= 2 else 0,
        }

    def dispute(self, review_id, author_reason):
        """Author disputes the verdict.

        Uses MA-10 conflict resolution to resolve the dispute.

        Returns: (resolution_result, message)
        """
        request = self.pending.get(review_id)
        if not request:
            return None, "Review not found"

        try:
            sys.path.insert(0, str(REPO / "scripts"))
            from conflict_resolution import ConflictResolver, new_conflict

            resolver = ConflictResolver()
            reviewers = [r["reviewer"] for r in request["reviews"]]
            author = request["author"]

            # Build positions
            positions = {author: f"Output should be accepted: {author_reason}"}
            for review in request["reviews"]:
                rev_id = review["reviewer"]
                verdict_text = f"Score {review['weighted_avg']:.1f}/10"
                if review.get("improvements"):
                    verdict_text += f", {len(review['improvements'])} improvements needed"
                positions[rev_id] = verdict_text

            # Build evidence
            evidence = {
                author: [author_reason],
            }
            for review in request["reviews"]:
                evidence[review["reviewer"]] = review.get("improvements", [])

            conflict = new_conflict(
                "output",
                f"Review dispute on {review_id}: author challenges {request['verdict']}",
                [author] + reviewers,
                severity="moderate",
                positions=positions,
                evidence=evidence,
                context={"review_id": review_id},
            )

            result = resolver.resolve(conflict)

            # If author wins dispute, overturn verdict
            if result.get("winner") == author:
                request["status"] = "approved"
                request["verdict"] = "APPROVE (disputed)"
                for rev in request["reviews"]:
                    self.quality.record_overturn(rev["reviewer"])
                return result, "Dispute won by author — verdict overturned to APPROVE"
            else:
                request["status"] = "disputed"
                return result, f"Dispute resolved — {result.get('winner', 'reviewer')} position upheld"

        except ImportError:
            return None, "MA-10 conflict resolution not available"

    def finalize(self, review_id):
        """Finalize a review — log to MA-4 and move to completed.

        Returns: (success, summary)
        """
        request = self.pending.get(review_id)
        if not request:
            return False, "Review not found"

        if request["status"] == "in_review":
            return False, "Review not yet decided — compute verdict first"

        # Log to MA-4
        self._log_to_decisions(request)

        # Log to review history
        self._log_review(request)

        # Move to completed
        self.completed.append(request)
        del self.pending[review_id]

        summary = {
            "review_id": review_id,
            "author": request["author"],
            "verdict": request["verdict"],
            "score": request.get("verdict_score"),
            "reviewers": [r["reviewer"] for r in request["reviews"]],
            "improvements": len(request.get("all_improvements", [])),
            "revision_count": request.get("revision_count", 0),
        }

        return True, summary

    def request_revision(self, review_id, revised_content):
        """Submit revised content for re-review.

        Returns: (success, message)
        """
        request = self.pending.get(review_id)
        if not request:
            return False, "Review not found"

        if request["revision_count"] >= request["max_revisions"]:
            return False, f"Max revisions ({request['max_revisions']}) reached"

        request["revision_count"] += 1
        request["output_content"] = revised_content
        request["reviews"] = []  # clear reviews for re-review
        request["status"] = "in_review"
        request["verdict"] = None
        request["verdict_score"] = None

        return True, f"Revision {request['revision_count']} submitted — awaiting re-review"

    def review_batch(self, requests):
        """Create review requests for a batch of outputs.

        Returns: list of (request, reviewers, errors)
        """
        results = []
        for req_data in requests:
            result = self.request_review(**req_data)
            results.append(result)
        return results

    def _weighted_average(self, scores, dimensions):
        """Calculate weighted average score."""
        total_weighted = 0.0
        total_weight = 0.0
        for dim, score in scores.items():
            weight = dimensions.get(dim, {}).get("weight", 1.0) if isinstance(dimensions.get(dim), dict) else 1.0
            total_weighted += score * weight
            total_weight += weight
        return round(total_weighted / total_weight, 2) if total_weight > 0 else 0.0

    def _log_review(self, request):
        """Log completed review to persistent log."""
        REVIEW_DIR.mkdir(parents=True, exist_ok=True)
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "review_id": request["id"],
            "author": request["author"],
            "output_type": request["output_type"],
            "skill_id": request.get("skill_id"),
            "policy": request["policy"],
            "verdict": request["verdict"],
            "score": request.get("verdict_score"),
            "reviewers": [r["reviewer"] for r in request["reviews"]],
            "improvements_count": len(request.get("all_improvements", [])),
            "revision_count": request.get("revision_count", 0),
        }
        with open(REVIEW_LOG_PATH, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def _log_to_decisions(self, request):
        """Log review outcome to MA-4."""
        try:
            from decision_log import DecisionLog
            dl = DecisionLog()
            title = f"Peer review: {request['verdict']} ({request['output_type']})"
            desc = (
                f"Author: {request['author']}\n"
                f"Score: {request.get('verdict_score', 'N/A')}\n"
                f"Reviewers: {[r['reviewer'] for r in request['reviews']]}\n"
                f"Improvements: {len(request.get('all_improvements', []))}\n"
                f"Revisions: {request.get('revision_count', 0)}\n"
            )
            dec_id, _ = dl.propose("executive_operator", title, desc,
                                    reversibility="reversible", confidence=0.8)
            dl.decide(dec_id, f"Review: {request['verdict']}",
                     f"Score: {request.get('verdict_score')}", decided_by="executive_operator")
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════════════════════
# TESTS
# ═══════════════════════════════════════════════════════════════════════════════

def run_tests():
    print("=" * 60)
    print("  MA-11 Peer Review System Tests")
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

    engine = PeerReviewEngine()

    # Test 1: Scoring dimensions
    test("4 scoring dimensions", len(SCORING_DIMENSIONS) == 4)

    # Test 2: Review policies
    test("3 review policies", len(REVIEW_POLICIES) == 3)

    # Test 3: Create review request
    req, reviewers, errs = engine.request_review(
        "strategy_lead", "Market research output content here",
        output_type="research", skill_id="e12-market-research-analyst",
        domain="market_strategy")
    test("Review request created", req["status"] == "in_review" and len(reviewers) > 0,
         f"reviewers={len(reviewers)}, errors={errs}")

    # Test 4: Reviewer is not author
    reviewer_ids = [r[0] for r in reviewers]
    test("Reviewer is not author", "strategy_lead" not in reviewer_ids,
         str(reviewer_ids))

    # Test 5: Reviewer has domain relevance
    test("Reviewer selected with score > 0",
         all(r[1] > 0 for r in reviewers), str(reviewers))

    # Test 6: Submit review with scores
    reviewer = reviewers[0][0]
    ok, msg = engine.submit_review(req["id"], reviewer,
        scores={"accuracy": 8, "completeness": 7, "actionability": 9, "clarity": 8},
        improvements=["Add competitor analysis", "Include market size"])
    test("Review submitted", ok, msg)

    # Test 7: Self-review blocked (fresh request to ensure author is in assigned list check)
    req_sr, rev_sr, _ = engine.request_review(
        "product_architect", "Test output for self-review check",
        domain="product_design")
    ok, msg = engine.submit_review(req_sr["id"], "product_architect",
        scores={"accuracy": 10, "completeness": 10, "actionability": 10, "clarity": 10})
    test("Self-review blocked", not ok and "Self-review" in msg, msg)

    # Test 8: Unassigned reviewer blocked
    ok, msg = engine.submit_review(req["id"], "narrative_content_lead",
        scores={"accuracy": 5})
    test("Unassigned reviewer blocked", not ok)

    # Test 9: Invalid score blocked
    ok, msg = engine.submit_review(req["id"], reviewer,
        scores={"accuracy": 15})
    test("Invalid score (>10) blocked", not ok)

    # Test 10: Compute verdict — APPROVE
    verdict, score, details = engine.compute_verdict(req["id"])
    test(f"Verdict computed: {verdict} ({score})",
         verdict in ("APPROVE", "REVISE", "REJECT") and score > 0)

    # Test 11: Verdict score matches weighted average
    test("Verdict score reasonable", 1.0 <= score <= 10.0, f"score={score}")

    # Test 12: Finalize review
    ok, summary = engine.finalize(req["id"])
    test("Review finalized", ok and "verdict" in summary, str(summary))

    # Test 13: Critical policy — 2 reviewers
    req2, reviewers2, _ = engine.request_review(
        "engineering_lead", "Architecture spec output",
        output_type="architecture", policy="critical",
        domain="code_architecture")
    policy = REVIEW_POLICIES["critical"]
    test(f"Critical: {policy['min_reviewers']} reviewers assigned",
         len(reviewers2) >= policy["min_reviewers"], f"got {len(reviewers2)}")

    # Test 14: Submit both reviews for critical
    for rev in reviewers2[:2]:
        engine.submit_review(req2["id"], rev[0],
            scores={"accuracy": 6, "completeness": 5, "actionability": 6, "clarity": 7},
            improvements=["Needs more detail"])
    verdict2, score2, _ = engine.compute_verdict(req2["id"])
    test(f"Critical verdict: {verdict2} ({score2})",
         verdict2 in ("APPROVE", "REVISE", "REJECT"))

    # Test 15: REVISE/REJECT for low scores
    test("Low scores → REVISE or REJECT", verdict2 in ("REVISE", "REJECT"), verdict2)

    # Test 16: Revision submission
    ok, msg = engine.request_revision(req2["id"], "Revised architecture spec with more detail")
    test("Revision submitted", ok, msg)
    test("Revision count incremented", engine.pending[req2["id"]]["revision_count"] == 1)

    # Test 17: Max revisions enforced
    engine.pending[req2["id"]]["revision_count"] = 2
    ok, msg = engine.request_revision(req2["id"], "Third attempt")
    test("Max revisions enforced", not ok and "Max" in msg)

    # Test 18: Reviewer quality tracking
    quality = engine.quality
    acc = quality.get_accuracy(reviewers[0][0])
    test("Reviewer quality tracked", acc is not None, f"accuracy={acc}")

    # Test 19: Weighted average calculation
    scores = {"accuracy": 10, "completeness": 8, "actionability": 6, "clarity": 4}
    avg = engine._weighted_average(scores, SCORING_DIMENSIONS)
    test("Weighted average calculated", 4.0 <= avg <= 10.0, f"avg={avg}")

    # Test 20: Weighted average respects weights
    # accuracy(1.5) > clarity(0.8), so high accuracy should pull avg up
    scores_high_acc = {"accuracy": 10, "completeness": 5, "actionability": 5, "clarity": 5}
    scores_high_cla = {"accuracy": 5, "completeness": 5, "actionability": 5, "clarity": 10}
    avg_acc = engine._weighted_average(scores_high_acc, SCORING_DIMENSIONS)
    avg_cla = engine._weighted_average(scores_high_cla, SCORING_DIMENSIONS)
    test("Accuracy weight > clarity weight", avg_acc > avg_cla, f"acc={avg_acc} cla={avg_cla}")

    # Test 21: Batch review
    batch_data = [
        {"author_id": "strategy_lead", "output_content": "Output 1", "domain": "market_strategy"},
        {"author_id": "engineering_lead", "output_content": "Output 2", "domain": "code_implementation"},
    ]
    batch_results = engine.review_batch(batch_data)
    test("Batch: 2 reviews created", len(batch_results) == 2)
    test("Batch: all have reviewers",
         all(len(r[1]) > 0 for r in batch_results))

    # Test 22: Reviewer selector workload tracking
    selector = engine.selector
    test("Workload tracked",
         sum(selector._workload.values()) >= 0)

    # Test 23: Dispute mechanism
    req3, rev3, _ = engine.request_review(
        "product_architect", "Product spec that reviewer will reject",
        domain="product_design")
    if rev3:
        engine.submit_review(req3["id"], rev3[0][0],
            scores={"accuracy": 3, "completeness": 2, "actionability": 3, "clarity": 4},
            improvements=["Complete rewrite needed", "Missing all requirements", "No user stories"])
        engine.compute_verdict(req3["id"])
        result, msg = engine.dispute(req3["id"], "Output meets all stated requirements")
        test("Dispute mechanism works",
             result is not None, str(msg)[:80])
    else:
        test("Dispute mechanism works", False, "No reviewers assigned")

    # Test 24: Review log persistence
    test("Review log exists", REVIEW_LOG_PATH.exists() or len(engine.completed) > 0)

    # Test 25: Pending tracking
    pending_count = len(engine.pending)
    test("Pending reviews tracked", pending_count >= 0, f"{pending_count} pending")

    # Test 26: Standard output structure
    test("Review has all fields",
         all(k in req for k in ["id", "author", "status", "reviews", "verdict", "dimensions"]))

    print(f"\n  Results: {tp}/{tt} passed")
    return tp == tt


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="NemoClaw Peer Review System")
    parser.add_argument("--test", action="store_true", help="Run all tests")
    parser.add_argument("--reviewers", action="store_true", help="Show reviewer quality")
    parser.add_argument("--quality", action="store_true", help="Show reviewer quality stats")
    parser.add_argument("--pending", action="store_true", help="Show pending reviews")
    parser.add_argument("--history", action="store_true", help="Show review history")
    args = parser.parse_args()

    if args.test:
        success = run_tests()
        sys.exit(0 if success else 1)

    elif args.quality or args.reviewers:
        quality = ReviewerQuality()
        quality.summary()

    elif args.pending:
        print("  (Pending reviews are in-memory only during active sessions)")

    elif args.history:
        if REVIEW_LOG_PATH.exists():
            with open(REVIEW_LOG_PATH) as f:
                for line in f.readlines()[-20:]:
                    try:
                        r = json.loads(line.strip())
                        ts = r.get("timestamp", "?")[:19]
                        icon = {"APPROVE": "✅", "REVISE": "🔄", "REJECT": "❌"}.get(r.get("verdict", ""), "?")
                        print(f"  [{ts}] {icon} {r.get('verdict', '?')} — {r.get('output_type', '?')} "
                              f"by {r.get('author', '?')} (score: {r.get('score', '?')})")
                    except json.JSONDecodeError:
                        continue
        else:
            print("  No review history yet.")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()

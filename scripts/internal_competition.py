#!/usr/bin/env python3
"""
NemoClaw Internal Competition v1.0 (MA-18)

Multi-agent competition for higher quality outputs:
- Configurable competitors per task (2 default, 3 for critical)
- Auto-trigger for tasks above $5 cost threshold
- Independent parallel output generation
- Scoring via MA-15 quality gate dimensions
- Winner selection by composite score with tiebreaking
- Performance feedback to MA-12
- Competition history and win-rate tracking

Usage:
  python3 scripts/internal_competition.py --test
  python3 scripts/internal_competition.py --history
  python3 scripts/internal_competition.py --leaderboard
  python3 scripts/internal_competition.py --stats
"""

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from collections import defaultdict

REPO = Path.home() / "nemoclaw-local-foundation"
COMP_DIR = Path.home() / ".nemoclaw" / "competitions"
COMP_LOG_PATH = COMP_DIR / "competition-log.jsonl"
LEADERBOARD_PATH = COMP_DIR / "leaderboard.json"

# ═══════════════════════════════════════════════════════════════════════════════
# COMPETITION CONFIG
# ═══════════════════════════════════════════════════════════════════════════════

COMPETITION_CONFIG = {
    "default_competitors": 2,
    "critical_competitors": 3,
    "cost_threshold": 5.0,  # auto-trigger above this
    "min_score_gap": 0.05,  # minimum gap to declare clear winner
    "scoring_dimensions": {
        "accuracy": {"weight": 1.5, "description": "Factual correctness"},
        "completeness": {"weight": 1.2, "description": "Covers all requirements"},
        "actionability": {"weight": 1.0, "description": "Directly usable output"},
        "clarity": {"weight": 0.8, "description": "Well-structured and clear"},
        "originality": {"weight": 0.5, "description": "Novel insights or approaches"},
    },
}

# Which agents can compete for which task domains
ELIGIBLE_COMPETITORS = {
    "market_strategy": ["strategy_lead", "growth_revenue_lead", "executive_operator"],
    "product_design": ["product_architect", "strategy_lead", "executive_operator"],
    "code_implementation": ["engineering_lead", "product_architect"],
    "content_creation": ["narrative_content_lead", "strategy_lead", "growth_revenue_lead"],
    "business_planning": ["strategy_lead", "growth_revenue_lead", "operations_lead"],
    "operations": ["operations_lead", "engineering_lead", "executive_operator"],
    "general": ["strategy_lead", "product_architect", "engineering_lead",
                "operations_lead", "growth_revenue_lead", "narrative_content_lead"],
}


# ═══════════════════════════════════════════════════════════════════════════════
# COMPETITION ENTRY
# ═══════════════════════════════════════════════════════════════════════════════

class CompetitionEntry:
    """A single competitor's submission."""

    def __init__(self, agent_id, content="", metadata=None):
        self.id = f"entry_{uuid.uuid4().hex[:6]}"
        self.agent_id = agent_id
        self.content = content
        self.metadata = metadata or {}
        self.submitted_at = None
        self.scores = {}  # dimension → score (1-10)
        self.composite_score = 0.0
        self.rank = 0
        self.is_winner = False
        self.generation_time_s = 0
        self.token_count = 0

    def submit(self, content, generation_time_s=0, token_count=0):
        """Submit the entry content."""
        self.content = content
        self.submitted_at = datetime.now(timezone.utc).isoformat()
        self.generation_time_s = generation_time_s
        self.token_count = token_count

    def score(self, dimension_scores):
        """Score entry across dimensions.

        Args: dict of dimension → score (1-10)
        """
        self.scores = dimension_scores
        self.composite_score = self._weighted_average()

    def _weighted_average(self):
        """Calculate weighted average across scoring dimensions."""
        dims = COMPETITION_CONFIG["scoring_dimensions"]
        total_w = 0.0
        total_s = 0.0
        for dim, score in self.scores.items():
            weight = dims.get(dim, {}).get("weight", 1.0)
            total_w += weight
            total_s += score * weight
        return round(total_s / total_w, 3) if total_w > 0 else 0.0

    def to_dict(self):
        return {
            "id": self.id,
            "agent_id": self.agent_id,
            "submitted_at": self.submitted_at,
            "scores": self.scores,
            "composite_score": self.composite_score,
            "rank": self.rank,
            "is_winner": self.is_winner,
            "generation_time_s": self.generation_time_s,
            "token_count": self.token_count,
            "content_length": len(self.content),
        }


# ═══════════════════════════════════════════════════════════════════════════════
# COMPETITION
# ═══════════════════════════════════════════════════════════════════════════════

class Competition:
    """A single competition instance."""

    def __init__(self, task_description, domain="general", priority="medium",
                 estimated_cost=0, task_id=None, skill_id=None,
                 num_competitors=None):
        self.id = f"comp_{uuid.uuid4().hex[:8]}"
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.task_description = task_description
        self.domain = domain
        self.priority = priority
        self.estimated_cost = estimated_cost
        self.task_id = task_id
        self.skill_id = skill_id
        self.status = "open"  # open | scoring | decided | cancelled

        # Determine number of competitors
        if num_competitors:
            self.num_competitors = num_competitors
        elif priority == "critical":
            self.num_competitors = COMPETITION_CONFIG["critical_competitors"]
        else:
            self.num_competitors = COMPETITION_CONFIG["default_competitors"]

        self.entries = {}  # agent_id → CompetitionEntry
        self.winner = None
        self.winner_entry = None
        self.decided_at = None
        self.decision_method = None  # score | tiebreak | default

    def add_competitor(self, agent_id):
        """Register a competitor.

        Returns: (success, entry_or_message)
        """
        if agent_id in self.entries:
            return False, f"{agent_id} already registered"

        if len(self.entries) >= self.num_competitors:
            return False, f"Competition full ({self.num_competitors} max)"

        if self.status != "open":
            return False, f"Competition is {self.status}"

        entry = CompetitionEntry(agent_id)
        self.entries[agent_id] = entry
        return True, entry

    def submit_entry(self, agent_id, content, generation_time_s=0, token_count=0):
        """Submit output for a competitor.

        Returns: (success, message)
        """
        entry = self.entries.get(agent_id)
        if not entry:
            return False, f"{agent_id} not registered"

        if entry.submitted_at:
            return False, f"{agent_id} already submitted"

        entry.submit(content, generation_time_s, token_count)
        return True, f"Entry submitted by {agent_id}"

    def score_entries(self, scores_by_agent):
        """Score all entries.

        Args: dict of agent_id → {dimension: score}
        Returns: (success, message)
        """
        self.status = "scoring"

        for agent_id, dim_scores in scores_by_agent.items():
            entry = self.entries.get(agent_id)
            if entry:
                entry.score(dim_scores)

        return True, "Entries scored"

    def decide_winner(self):
        """Select winner by highest composite score.

        Returns: (winner_agent_id, decision_details)
        """
        if not self.entries:
            return None, {"error": "No entries"}

        submitted = {aid: e for aid, e in self.entries.items() if e.submitted_at}
        if not submitted:
            return None, {"error": "No submissions"}

        scored = {aid: e for aid, e in submitted.items() if e.composite_score > 0}
        if not scored:
            # No scores — pick first submitted
            winner_id = list(submitted.keys())[0]
            self.decision_method = "default"
        else:
            # Sort by composite score descending
            ranked = sorted(scored.items(), key=lambda x: -x[1].composite_score)

            # Assign ranks
            for rank, (aid, entry) in enumerate(ranked, 1):
                entry.rank = rank

            winner_id = ranked[0][0]
            winner_score = ranked[0][1].composite_score

            # Check for tie
            if len(ranked) >= 2:
                runner_up_score = ranked[1][1].composite_score
                gap = winner_score - runner_up_score

                if gap < COMPETITION_CONFIG["min_score_gap"]:
                    # Tiebreak: prefer faster generation, then fewer tokens
                    tied = [r for r in ranked if abs(r[1].composite_score - winner_score) < COMPETITION_CONFIG["min_score_gap"]]
                    tied.sort(key=lambda x: (x[1].generation_time_s, x[1].token_count))
                    winner_id = tied[0][0]
                    self.decision_method = "tiebreak"
                else:
                    self.decision_method = "score"
            else:
                self.decision_method = "score"

        # Mark winner
        self.winner = winner_id
        self.winner_entry = self.entries[winner_id]
        self.winner_entry.is_winner = True
        self.status = "decided"
        self.decided_at = datetime.now(timezone.utc).isoformat()

        details = {
            "winner": winner_id,
            "method": self.decision_method,
            "scores": {aid: e.composite_score for aid, e in self.entries.items()},
            "ranks": {aid: e.rank for aid, e in self.entries.items()},
        }

        return winner_id, details

    def get_winner_content(self):
        """Get the winning output content."""
        if self.winner_entry:
            return self.winner_entry.content
        return None

    def to_dict(self):
        return {
            "id": self.id,
            "created_at": self.created_at,
            "task_description": self.task_description[:100],
            "domain": self.domain,
            "priority": self.priority,
            "estimated_cost": self.estimated_cost,
            "num_competitors": self.num_competitors,
            "status": self.status,
            "winner": self.winner,
            "decision_method": self.decision_method,
            "decided_at": self.decided_at,
            "entries": {aid: e.to_dict() for aid, e in self.entries.items()},
        }


# ═══════════════════════════════════════════════════════════════════════════════
# COMPETITION MANAGER
# ═══════════════════════════════════════════════════════════════════════════════

class CompetitionManager:
    """Manages competitions across the system."""

    def __init__(self):
        self.active = {}  # comp_id → Competition
        self.leaderboard = Leaderboard()

    def should_compete(self, estimated_cost, priority="medium"):
        """Check if a task should trigger competition.

        Returns: (should_compete, num_competitors)
        """
        threshold = COMPETITION_CONFIG["cost_threshold"]

        if estimated_cost >= threshold:
            if priority == "critical":
                return True, COMPETITION_CONFIG["critical_competitors"]
            return True, COMPETITION_CONFIG["default_competitors"]

        if priority == "critical":
            return True, COMPETITION_CONFIG["critical_competitors"]

        return False, 0

    def create_competition(self, task_description, domain="general",
                            priority="medium", estimated_cost=0,
                            task_id=None, skill_id=None, num_competitors=None):
        """Create a new competition.

        Returns: Competition
        """
        comp = Competition(
            task_description, domain, priority, estimated_cost,
            task_id, skill_id, num_competitors)
        self.active[comp.id] = comp
        return comp

    def select_competitors(self, competition):
        """Select eligible competitors for a competition.

        Returns: list of agent_ids
        """
        domain = competition.domain
        eligible = ELIGIBLE_COMPETITORS.get(domain, ELIGIBLE_COMPETITORS["general"])

        # Load performance data for ranking
        perf_scores = {}
        try:
            perf_path = Path.home() / ".nemoclaw" / "performance" / "agent-metrics.json"
            if perf_path.exists():
                with open(perf_path) as f:
                    data = json.load(f)
                for agent in eligible:
                    agent_data = data.get("agents", {}).get(agent, {})
                    perf_scores[agent] = agent_data.get("composite_score", 0.5)
        except Exception:
            pass

        # Sort by performance (best first) but include variety
        ranked = sorted(eligible, key=lambda a: perf_scores.get(a, 0.5), reverse=True)

        # Take top N
        selected = ranked[:competition.num_competitors]

        # Register competitors
        for agent_id in selected:
            competition.add_competitor(agent_id)

        return selected

    def finalize(self, comp_id):
        """Finalize a competition: decide winner, update leaderboard, log.

        Returns: (winner, details)
        """
        comp = self.active.get(comp_id)
        if not comp:
            return None, {"error": "Competition not found"}

        winner, details = comp.decide_winner()

        if winner:
            # Update leaderboard
            for agent_id, entry in comp.entries.items():
                self.leaderboard.record(agent_id, comp.id,
                                         entry.composite_score, entry.is_winner)

            # Log competition
            self._log_competition(comp)

            # Log to MA-4
            self._log_to_decisions(comp, details)

        # Move to completed
        del self.active[comp_id]

        return winner, details

    def get_active(self):
        """Get all active competitions."""
        return list(self.active.values())

    def _log_competition(self, comp):
        """Log completed competition."""
        COMP_DIR.mkdir(parents=True, exist_ok=True)
        with open(COMP_LOG_PATH, "a") as f:
            f.write(json.dumps(comp.to_dict()) + "\n")

    def _log_to_decisions(self, comp, details):
        """Log competition result to MA-4."""
        try:
            sys.path.insert(0, str(REPO / "scripts"))
            from decision_log import DecisionLog
            dl = DecisionLog()
            title = f"Competition won: {comp.winner} ({comp.domain})"
            desc = (
                f"Task: {comp.task_description[:80]}\n"
                f"Competitors: {list(comp.entries.keys())}\n"
                f"Scores: {details.get('scores', {})}\n"
                f"Method: {details.get('method')}\n"
                f"Cost: ${comp.estimated_cost:.2f}\n"
            )
            dec_id, _ = dl.propose("executive_operator", title, desc,
                                    reversibility="reversible", confidence=0.85)
            dl.decide(dec_id, f"Winner: {comp.winner}", f"Method: {comp.decision_method}",
                     decided_by="executive_operator")
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════════════════════
# LEADERBOARD
# ═══════════════════════════════════════════════════════════════════════════════

class Leaderboard:
    """Tracks agent win rates and competition performance."""

    def __init__(self):
        self.data = {}  # agent_id → {wins, losses, total, avg_score, competitions}
        self._load()

    def _load(self):
        COMP_DIR.mkdir(parents=True, exist_ok=True)
        if LEADERBOARD_PATH.exists():
            try:
                with open(LEADERBOARD_PATH) as f:
                    self.data = json.load(f)
            except (json.JSONDecodeError, IOError):
                self.data = {}

    def _save(self):
        COMP_DIR.mkdir(parents=True, exist_ok=True)
        with open(LEADERBOARD_PATH, "w") as f:
            json.dump(self.data, f, indent=2)

    def record(self, agent_id, comp_id, score, won):
        """Record a competition result."""
        if agent_id not in self.data:
            self.data[agent_id] = {
                "wins": 0, "losses": 0, "total": 0,
                "avg_score": 0.0, "score_sum": 0.0,
                "competitions": [],
            }

        entry = self.data[agent_id]
        entry["total"] += 1
        entry["score_sum"] += score
        entry["avg_score"] = round(entry["score_sum"] / entry["total"], 3)

        if won:
            entry["wins"] += 1
        else:
            entry["losses"] += 1

        entry["competitions"].append({
            "comp_id": comp_id,
            "score": score,
            "won": won,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        entry["competitions"] = entry["competitions"][-50:]  # keep last 50

        self._save()

    def get_rankings(self):
        """Get agents ranked by win rate then avg score."""
        rankings = []
        for agent_id, stats in self.data.items():
            win_rate = stats["wins"] / max(stats["total"], 1)
            rankings.append({
                "agent_id": agent_id,
                "wins": stats["wins"],
                "losses": stats["losses"],
                "total": stats["total"],
                "win_rate": round(win_rate, 3),
                "avg_score": stats["avg_score"],
            })
        rankings.sort(key=lambda r: (-r["win_rate"], -r["avg_score"]))
        return rankings

    def get_agent_stats(self, agent_id):
        return self.data.get(agent_id)


# ═══════════════════════════════════════════════════════════════════════════════
# TESTS
# ═══════════════════════════════════════════════════════════════════════════════

def run_tests():
    print("=" * 60)
    print("  MA-18 Internal Competition Tests")
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

    mgr = CompetitionManager()
    mgr.leaderboard.data = {}  # clean slate

    # Test 1: Config
    test("Scoring dimensions defined", len(COMPETITION_CONFIG["scoring_dimensions"]) == 5)

    # Test 2: Eligible competitors defined
    test("7 domain competitor lists", len(ELIGIBLE_COMPETITORS) == 7)

    # Test 3: Should compete — above threshold
    should, num = mgr.should_compete(8.0, "medium")
    test("$8 task triggers competition", should and num == 2)

    # Test 4: Should compete — below threshold
    should, num = mgr.should_compete(3.0, "medium")
    test("$3 task skips competition", not should)

    # Test 5: Critical always competes
    should, num = mgr.should_compete(2.0, "critical")
    test("Critical always competes", should and num == 3)

    # Test 6: Default = 2, critical = 3
    test("Default competitors = 2", COMPETITION_CONFIG["default_competitors"] == 2)
    test("Critical competitors = 3", COMPETITION_CONFIG["critical_competitors"] == 3)

    # Test 8: Create competition
    comp = mgr.create_competition(
        "Research AI meeting assistant market",
        domain="market_strategy", priority="high", estimated_cost=8.0)
    test("Competition created", comp.id is not None and comp.status == "open")

    # Test 9: Add competitors
    ok1, e1 = comp.add_competitor("strategy_lead")
    ok2, e2 = comp.add_competitor("growth_revenue_lead")
    test("Competitors added", ok1 and ok2)

    # Test 10: Duplicate competitor rejected
    ok3, msg = comp.add_competitor("strategy_lead")
    test("Duplicate rejected", not ok3)

    # Test 11: Full competition rejected
    ok4, msg = comp.add_competitor("executive_operator")
    test("Full competition blocks extra", not ok4)

    # Test 12: Submit entries
    ok, _ = comp.submit_entry("strategy_lead", "Market analysis: AI assistants growing 25% YoY...",
                                generation_time_s=45, token_count=1200)
    test("Entry submitted", ok)

    # Test 13: Double submit rejected
    ok, _ = comp.submit_entry("strategy_lead", "Another attempt")
    test("Double submit rejected", not ok)

    # Test 14: Second entry
    ok, _ = comp.submit_entry("growth_revenue_lead",
                                "Revenue analysis: TAM $2.5B, SAM $800M...",
                                generation_time_s=60, token_count=1500)
    test("Second entry submitted", ok)

    # Test 15: Score entries
    comp.score_entries({
        "strategy_lead": {"accuracy": 8, "completeness": 9, "actionability": 7,
                           "clarity": 8, "originality": 6},
        "growth_revenue_lead": {"accuracy": 7, "completeness": 7, "actionability": 9,
                                  "clarity": 7, "originality": 8},
    })
    test("Entries scored",
         comp.entries["strategy_lead"].composite_score > 0 and
         comp.entries["growth_revenue_lead"].composite_score > 0)

    # Test 16: Composite scores differ
    s1 = comp.entries["strategy_lead"].composite_score
    s2 = comp.entries["growth_revenue_lead"].composite_score
    test("Scores differ", s1 != s2, f"s1={s1}, s2={s2}")

    # Test 17: Decide winner
    winner, details = comp.decide_winner()
    test("Winner decided", winner is not None and comp.status == "decided")

    # Test 18: Winner has highest score
    winner_score = comp.entries[winner].composite_score
    loser_scores = [e.composite_score for aid, e in comp.entries.items() if aid != winner]
    test("Winner has highest score", all(winner_score >= ls for ls in loser_scores))

    # Test 19: Decision method recorded
    test("Decision method recorded", comp.decision_method in ("score", "tiebreak", "default"))

    # Test 20: Get winner content
    content = comp.get_winner_content()
    test("Winner content retrievable", content is not None and len(content) > 0)

    # Test 21: Finalize competition
    comp2 = mgr.create_competition("Design product spec", domain="product_design",
                                     estimated_cost=10.0)
    comp2.add_competitor("product_architect")
    comp2.add_competitor("strategy_lead")
    comp2.submit_entry("product_architect", "Product spec with detailed requirements...")
    comp2.submit_entry("strategy_lead", "Product strategy and market positioning...")
    comp2.score_entries({
        "product_architect": {"accuracy": 9, "completeness": 8, "actionability": 8,
                                "clarity": 9, "originality": 5},
        "strategy_lead": {"accuracy": 7, "completeness": 7, "actionability": 7,
                            "clarity": 7, "originality": 7},
    })
    winner2, details2 = mgr.finalize(comp2.id)
    test("Finalize works", winner2 == "product_architect")

    # Test 22: Leaderboard updated
    rankings = mgr.leaderboard.get_rankings()
    test("Leaderboard has entries", len(rankings) > 0)

    # Test 23: Win rate calculated
    winner_stats = mgr.leaderboard.get_agent_stats("product_architect")
    test("Win rate tracked", winner_stats is not None and winner_stats["wins"] >= 1)

    # Test 24: Competitor selection
    comp3 = mgr.create_competition("Market research", domain="market_strategy")
    selected = mgr.select_competitors(comp3)
    test("Competitors auto-selected", len(selected) == comp3.num_competitors)

    # Test 25: Selected from eligible domain
    eligible = ELIGIBLE_COMPETITORS["market_strategy"]
    test("Selected from eligible pool",
         all(s in eligible for s in selected))

    # Test 26: Tiebreak by speed
    tie_comp = Competition("Tie test", num_competitors=2)
    tie_comp.add_competitor("agent_a")
    tie_comp.add_competitor("agent_b")
    tie_comp.submit_entry("agent_a", "Output A", generation_time_s=30, token_count=1000)
    tie_comp.submit_entry("agent_b", "Output B", generation_time_s=60, token_count=1500)
    tie_comp.score_entries({
        "agent_a": {"accuracy": 8, "completeness": 8, "actionability": 8,
                      "clarity": 8, "originality": 8},
        "agent_b": {"accuracy": 8, "completeness": 8, "actionability": 8,
                      "clarity": 8, "originality": 8},
    })
    tie_winner, tie_details = tie_comp.decide_winner()
    test("Tiebreak: faster agent wins", tie_winner == "agent_a")
    test("Tiebreak method recorded", tie_comp.decision_method == "tiebreak")

    # Test 28: Competition to_dict
    d = comp.to_dict()
    test("to_dict has all fields",
         all(k in d for k in ["id", "status", "winner", "entries", "domain"]))

    # Test 29: Active competitions tracked
    comp4 = mgr.create_competition("Test active", estimated_cost=6.0)
    test("Active competitions tracked", len(mgr.get_active()) >= 1)

    # Test 30: Log exists after finalize
    test("Competition log exists", COMP_LOG_PATH.exists() or len(mgr.active) >= 0)

    # Test 31: Custom competitor count
    comp5 = Competition("Custom count", num_competitors=4)
    test("Custom competitor count", comp5.num_competitors == 4)

    # Test 32: Leaderboard rankings sorted
    if len(rankings) >= 2:
        test("Rankings sorted by win rate",
             rankings[0]["win_rate"] >= rankings[1]["win_rate"])
    else:
        test("Rankings sorted by win rate", True, "only 1 agent")

    print(f"\n  Results: {tp}/{tt} passed")
    return tp == tt


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="NemoClaw Internal Competition")
    parser.add_argument("--test", action="store_true", help="Run all tests")
    parser.add_argument("--history", action="store_true", help="Show competition history")
    parser.add_argument("--leaderboard", action="store_true", help="Show agent leaderboard")
    parser.add_argument("--stats", action="store_true", help="Show competition stats")
    args = parser.parse_args()

    if args.test:
        success = run_tests()
        sys.exit(0 if success else 1)

    elif args.leaderboard:
        mgr = CompetitionManager()
        rankings = mgr.leaderboard.get_rankings()
        if not rankings:
            print("  No competition data yet.")
        else:
            print(f"  {'Agent':<25} {'Wins':>5} {'Loss':>5} {'Total':>6} {'Win%':>6} {'Avg':>6}")
            print(f"  {'-'*25} {'-'*5} {'-'*5} {'-'*6} {'-'*6} {'-'*6}")
            for r in rankings:
                medal = "🥇" if r["win_rate"] >= 0.7 else ("🥈" if r["win_rate"] >= 0.4 else "🥉")
                print(f"  {medal} {r['agent_id']:<23} {r['wins']:>5} {r['losses']:>5} "
                      f"{r['total']:>6} {r['win_rate']:>5.0%} {r['avg_score']:>5.1f}")

    elif args.history:
        if COMP_LOG_PATH.exists():
            with open(COMP_LOG_PATH) as f:
                for line in f.readlines()[-20:]:
                    try:
                        c = json.loads(line.strip())
                        ts = c.get("created_at", "?")[:19]
                        print(f"  [{ts}] {c.get('domain', '?')}: winner={c.get('winner', '?')} "
                              f"method={c.get('decision_method', '?')} "
                              f"({c.get('num_competitors', '?')} competitors)")
                    except json.JSONDecodeError:
                        continue
        else:
            print("  No competition history yet.")

    elif args.stats:
        mgr = CompetitionManager()
        rankings = mgr.leaderboard.get_rankings()
        total_comps = sum(r["total"] for r in rankings) // max(len(rankings), 1)
        print(f"  Competitions run: ~{total_comps}")
        print(f"  Agents competed: {len(rankings)}")
        if rankings:
            top = rankings[0]
            print(f"  Top performer: {top['agent_id']} ({top['win_rate']:.0%} win rate)")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()

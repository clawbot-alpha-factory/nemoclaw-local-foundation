#!/usr/bin/env python3
"""
NemoClaw Output Quality Gate v1.0 (MA-15)

Mandatory quality validation for all outputs before delivery:
- All outputs must pass — no exceptions
- Failures block and return for revision
- 6 validation dimensions: completeness, format, length, sections, accuracy signals, coherence
- Configurable rules per output type
- Revision tracking with max attempts
- MA-4 decision log integration for all gate results
- Quality trend tracking per skill and agent

Usage:
  python3 scripts/quality_gate.py --test
  python3 scripts/quality_gate.py --rules
  python3 scripts/quality_gate.py --stats
  python3 scripts/quality_gate.py --history
"""

import argparse
import json
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from collections import defaultdict

REPO = Path.home() / "nemoclaw-local-foundation"
GATE_DIR = Path.home() / ".nemoclaw" / "quality-gate"
GATE_LOG_PATH = GATE_DIR / "gate-log.jsonl"
GATE_STATS_PATH = GATE_DIR / "gate-stats.json"

MAX_REVISIONS = 3  # max revision attempts before escalation

# ═══════════════════════════════════════════════════════════════════════════════
# VALIDATION RULES
# ═══════════════════════════════════════════════════════════════════════════════

# Default rules applied to ALL outputs
DEFAULT_RULES = {
    "min_length": {
        "description": "Output must meet minimum character length",
        "dimension": "completeness",
        "severity": "critical",  # critical = blocks, minor = warns
        "default_threshold": 200,
    },
    "max_length": {
        "description": "Output must not exceed maximum length",
        "dimension": "completeness",
        "severity": "minor",
        "default_threshold": 50000,
    },
    "not_empty": {
        "description": "Output must not be empty or whitespace-only",
        "dimension": "completeness",
        "severity": "critical",
        "default_threshold": None,
    },
    "no_placeholder": {
        "description": "Output must not contain placeholder text",
        "dimension": "accuracy",
        "severity": "critical",
        "default_threshold": None,
        "patterns": [
            r"\[INSERT\s",
            r"\[TODO\]",
            r"\[PLACEHOLDER\]",
            r"Lorem ipsum",
            r"\{your_",
            r"<FILL_IN>",
            r"TBD\b",
        ],
    },
    "no_truncation": {
        "description": "Output must not appear truncated",
        "dimension": "completeness",
        "severity": "critical",
        "default_threshold": None,
        "patterns": [
            r"\.{3,}\s*$",       # ends with ...
            r"continued\.\.\.",
            r"truncated",
            r"cut off",
        ],
    },
    "has_structure": {
        "description": "Output must have markdown headings or clear structure",
        "dimension": "format",
        "severity": "minor",
        "default_threshold": 1,  # min heading count
    },
    "no_error_markers": {
        "description": "Output must not contain error messages from LLM",
        "dimension": "accuracy",
        "severity": "critical",
        "patterns": [
            r"I cannot\b",
            r"I'm unable to\b",
            r"I apologize.*cannot",
            r"As an AI",
            r"I don't have access",
        ],
    },
}

# Output-type-specific rules (extend defaults)
OUTPUT_TYPE_RULES = {
    "research": {
        "required_sections": ["Background", "Key Findings", "Recommendations"],
        "min_length": 500,
        "min_headings": 3,
    },
    "product_spec": {
        "required_sections": ["Overview", "Requirements", "Scope"],
        "min_length": 800,
        "min_headings": 4,
    },
    "architecture": {
        "required_sections": ["Overview", "Components"],
        "min_length": 600,
        "min_headings": 3,
    },
    "code": {
        "min_length": 100,
        "must_contain": ["def ", "class ", "import "],  # at least one
        "min_headings": 0,
    },
    "documentation": {
        "required_sections": ["Purpose", "Usage"],
        "min_length": 300,
        "min_headings": 2,
    },
    "creative": {
        "min_length": 200,
        "min_headings": 0,
    },
    "analysis": {
        "required_sections": ["Summary", "Analysis"],
        "min_length": 400,
        "min_headings": 2,
    },
    "general": {
        "min_length": 200,
        "min_headings": 0,
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
# GATE RESULT
# ═══════════════════════════════════════════════════════════════════════════════

class GateResult:
    """Result of a quality gate check."""

    def __init__(self, output_id, agent_id, skill_id=None, output_type="general"):
        self.id = f"gate_{uuid.uuid4().hex[:8]}"
        self.output_id = output_id
        self.agent_id = agent_id
        self.skill_id = skill_id
        self.output_type = output_type
        self.timestamp = datetime.now(timezone.utc).isoformat()
        self.passed = False
        self.verdict = "pending"  # passed | blocked | escalated
        self.checks = []  # list of {rule, dimension, passed, severity, message}
        self.critical_failures = 0
        self.minor_failures = 0
        self.score = 0.0  # 0.0-1.0 overall quality score
        self.revision_count = 0

    def add_check(self, rule, dimension, passed, severity, message=""):
        self.checks.append({
            "rule": rule,
            "dimension": dimension,
            "passed": passed,
            "severity": severity,
            "message": message,
        })
        if not passed:
            if severity == "critical":
                self.critical_failures += 1
            else:
                self.minor_failures += 1

    def finalize(self):
        """Compute final verdict."""
        total = len(self.checks)
        passed_count = sum(1 for c in self.checks if c["passed"])

        self.score = round(passed_count / max(total, 1), 3)

        if self.critical_failures > 0:
            self.passed = False
            self.verdict = "blocked"
        else:
            self.passed = True
            self.verdict = "passed"

    def to_dict(self):
        return {
            "id": self.id,
            "output_id": self.output_id,
            "agent_id": self.agent_id,
            "skill_id": self.skill_id,
            "output_type": self.output_type,
            "timestamp": self.timestamp,
            "passed": self.passed,
            "verdict": self.verdict,
            "score": self.score,
            "critical_failures": self.critical_failures,
            "minor_failures": self.minor_failures,
            "checks": self.checks,
            "revision_count": self.revision_count,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# QUALITY GATE ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class QualityGate:
    """Mandatory output quality gate.

    Every output must pass through this gate before delivery.
    Failures block the output and return it for revision.
    """

    def __init__(self):
        self.stats = GateStats()

    def validate(self, content, agent_id, output_type="general",
                  skill_id=None, output_id=None, revision_count=0,
                  custom_rules=None):
        """Validate output content against all applicable rules.

        Args:
            content: the output text to validate
            agent_id: who produced this output
            output_type: type for rule selection
            skill_id: optional skill ID
            output_id: optional output identifier
            revision_count: how many times this output has been revised
            custom_rules: additional rules dict to apply

        Returns: GateResult
        """
        result = GateResult(
            output_id or f"out_{uuid.uuid4().hex[:6]}",
            agent_id, skill_id, output_type)
        result.revision_count = revision_count

        # Get type-specific config
        type_config = OUTPUT_TYPE_RULES.get(output_type, OUTPUT_TYPE_RULES["general"])

        # ── COMPLETENESS CHECKS ──

        # Not empty
        is_empty = not content or not content.strip()
        result.add_check("not_empty", "completeness", not is_empty, "critical",
                          "Output is empty" if is_empty else "")

        if is_empty:
            result.finalize()
            self._log_and_track(result)
            return result

        content_len = len(content.strip())

        # Min length
        min_len = type_config.get("min_length", DEFAULT_RULES["min_length"]["default_threshold"])
        passes_min = content_len >= min_len
        result.add_check("min_length", "completeness", passes_min, "critical",
                          f"Length {content_len} < minimum {min_len}" if not passes_min else "")

        # Max length
        max_len = type_config.get("max_length", DEFAULT_RULES["max_length"]["default_threshold"])
        passes_max = content_len <= max_len
        result.add_check("max_length", "completeness", passes_max, "minor",
                          f"Length {content_len} > maximum {max_len}" if not passes_max else "")

        # ── FORMAT CHECKS ──

        # Structure (headings)
        min_headings = type_config.get("min_headings", 1)
        heading_count = len(re.findall(r'^#{1,3}\s', content, re.MULTILINE))
        passes_struct = heading_count >= min_headings
        result.add_check("has_structure", "format", passes_struct, "minor",
                          f"Found {heading_count} headings, need {min_headings}" if not passes_struct else "")

        # Required sections
        required_sections = type_config.get("required_sections", [])
        if required_sections:
            missing = []
            for section in required_sections:
                pattern = rf'(?:^|\n)#{1,3}\s+.*{re.escape(section)}'
                if not re.search(pattern, content, re.IGNORECASE):
                    # Also check for bold section headers
                    if section.lower() not in content.lower():
                        missing.append(section)
            passes_sections = len(missing) == 0
            result.add_check("required_sections", "completeness", passes_sections, "critical",
                              f"Missing sections: {missing}" if missing else "")

        # Must contain (for code type)
        must_contain = type_config.get("must_contain", [])
        if must_contain:
            has_any = any(mc in content for mc in must_contain)
            result.add_check("must_contain", "format", has_any, "minor",
                              f"Missing one of: {must_contain}" if not has_any else "")

        # ── ACCURACY CHECKS ──

        # No placeholders
        placeholder_found = []
        for pattern in DEFAULT_RULES["no_placeholder"]["patterns"]:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                placeholder_found.extend(matches[:2])
        result.add_check("no_placeholder", "accuracy", len(placeholder_found) == 0, "critical",
                          f"Placeholders found: {placeholder_found[:3]}" if placeholder_found else "")

        # No truncation
        truncation_found = False
        for pattern in DEFAULT_RULES["no_truncation"]["patterns"]:
            if re.search(pattern, content, re.IGNORECASE):
                truncation_found = True
                break
        result.add_check("no_truncation", "completeness", not truncation_found, "critical",
                          "Output appears truncated" if truncation_found else "")

        # No error markers
        error_found = []
        for pattern in DEFAULT_RULES["no_error_markers"]["patterns"]:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                error_found.extend(matches[:2])
        result.add_check("no_error_markers", "accuracy", len(error_found) == 0, "critical",
                          f"LLM error markers: {error_found[:3]}" if error_found else "")

        # ── COHERENCE CHECKS ──

        # Not repetitive (same paragraph repeated)
        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip() and len(p.strip()) > 50]
        if len(paragraphs) >= 2:
            unique = set(p[:100].lower() for p in paragraphs)
            repetition_ratio = len(unique) / len(paragraphs)
            passes_rep = repetition_ratio > 0.7
            result.add_check("no_repetition", "coherence", passes_rep, "minor",
                              f"Repetition detected: {repetition_ratio:.0%} unique" if not passes_rep else "")

        # ── CUSTOM RULES ──
        if custom_rules:
            for rule_name, rule_fn in custom_rules.items():
                try:
                    passed, msg = rule_fn(content)
                    result.add_check(rule_name, "custom", passed, "critical", msg)
                except Exception as e:
                    result.add_check(rule_name, "custom", False, "minor", f"Rule error: {str(e)[:60]}")

        # Finalize
        result.finalize()
        self._log_and_track(result)

        # Escalate if max revisions reached and still failing
        if not result.passed and revision_count >= MAX_REVISIONS:
            result.verdict = "escalated"
            self._log_escalation(result)

        return result

    def validate_batch(self, outputs):
        """Validate multiple outputs.

        Args: list of {content, agent_id, output_type, skill_id, ...}
        Returns: list of GateResults
        """
        results = []
        for output in outputs:
            result = self.validate(
                output.get("content", ""),
                output.get("agent_id", "unknown"),
                output.get("output_type", "general"),
                output.get("skill_id"),
                output.get("output_id"),
            )
            results.append(result)
        return results

    def get_revision_feedback(self, result):
        """Generate actionable revision feedback from a failed gate result.

        Returns: dict with failures and specific improvement instructions
        """
        if result.passed:
            return {"status": "passed", "feedback": []}

        feedback = []
        for check in result.checks:
            if not check["passed"]:
                instruction = self._revision_instruction(check)
                feedback.append({
                    "rule": check["rule"],
                    "dimension": check["dimension"],
                    "severity": check["severity"],
                    "issue": check["message"],
                    "instruction": instruction,
                })

        return {
            "status": "needs_revision",
            "revision_number": result.revision_count + 1,
            "max_revisions": MAX_REVISIONS,
            "critical_issues": result.critical_failures,
            "minor_issues": result.minor_failures,
            "feedback": feedback,
        }

    def _revision_instruction(self, check):
        """Generate specific revision instruction for a failed check."""
        instructions = {
            "not_empty": "Regenerate the output — current output is empty",
            "min_length": "Expand the output with more detail and analysis",
            "max_length": "Condense the output — remove redundancy and focus on key points",
            "has_structure": "Add markdown headings (## Section Name) to organize the output",
            "required_sections": f"Add the missing sections: {check.get('message', '')}",
            "must_contain": "Ensure the output contains the required elements",
            "no_placeholder": "Replace all placeholder text with actual content",
            "no_truncation": "Complete the output — it appears to be cut off",
            "no_error_markers": "Remove LLM error responses and regenerate the content",
            "no_repetition": "Remove repeated paragraphs and ensure unique content throughout",
        }
        return instructions.get(check["rule"], f"Fix: {check['message']}")

    def _log_and_track(self, result):
        """Log gate result and update stats."""
        GATE_DIR.mkdir(parents=True, exist_ok=True)
        with open(GATE_LOG_PATH, "a") as f:
            f.write(json.dumps(result.to_dict()) + "\n")

        self.stats.record(result)

        # Log to MA-4 for blocked/escalated
        if result.verdict in ("blocked", "escalated"):
            self._log_to_decisions(result)

    def _log_escalation(self, result):
        """Log escalation when max revisions reached."""
        try:
            from scripts.decision_log import DecisionLog
            dl = DecisionLog()
            title = f"Quality gate escalation: {result.skill_id or result.output_type}"
            desc = (
                f"Output failed quality gate after {result.revision_count} revisions\n"
                f"Agent: {result.agent_id}\n"
                f"Score: {result.score:.0%}\n"
                f"Critical failures: {result.critical_failures}\n"
                f"Requires executive review\n"
            )
            dec_id, _ = dl.propose("executive_operator", title, desc,
                                    reversibility="reversible", confidence=0.9)
            dl.decide(dec_id, "Escalated for manual review", desc[:100],
                     decided_by="executive_operator")
        except Exception:
            pass

    def _log_to_decisions(self, result):
        """Log gate results to MA-4."""
        try:
            from scripts.decision_log import DecisionLog
            dl = DecisionLog()
            title = f"Quality gate {result.verdict}: {result.output_type}"
            failed_rules = [c["rule"] for c in result.checks if not c["passed"]]
            desc = (
                f"Agent: {result.agent_id}\n"
                f"Score: {result.score:.0%}\n"
                f"Failed: {failed_rules}\n"
                f"Revision: {result.revision_count}/{MAX_REVISIONS}\n"
            )
            dec_id, _ = dl.propose("executive_operator", title, desc,
                                    reversibility="reversible", confidence=0.8)
            dl.decide(dec_id, f"Gate: {result.verdict}", f"Score: {result.score:.0%}",
                     decided_by="executive_operator")
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════════════════════
# GATE STATISTICS
# ═══════════════════════════════════════════════════════════════════════════════

class GateStats:
    """Tracks quality gate statistics."""

    def __init__(self):
        self.data = {
            "total_checks": 0,
            "total_passed": 0,
            "total_blocked": 0,
            "total_escalated": 0,
            "pass_rate": 0.0,
            "by_agent": {},
            "by_skill": {},
            "by_type": {},
            "by_rule": {},
            "avg_score": 0.0,
            "score_sum": 0.0,
        }
        self._load()

    def _load(self):
        GATE_DIR.mkdir(parents=True, exist_ok=True)
        if GATE_STATS_PATH.exists():
            try:
                with open(GATE_STATS_PATH) as f:
                    self.data = json.load(f)
            except (json.JSONDecodeError, IOError):
                pass

    def _save(self):
        GATE_DIR.mkdir(parents=True, exist_ok=True)
        with open(GATE_STATS_PATH, "w") as f:
            json.dump(self.data, f, indent=2)

    def record(self, result):
        """Record a gate result."""
        self.data["total_checks"] += 1
        self.data["score_sum"] += result.score

        if result.verdict == "passed":
            self.data["total_passed"] += 1
        elif result.verdict == "blocked":
            self.data["total_blocked"] += 1
        elif result.verdict == "escalated":
            self.data["total_escalated"] += 1

        total = self.data["total_checks"]
        self.data["pass_rate"] = round(self.data["total_passed"] / total, 3) if total > 0 else 0
        self.data["avg_score"] = round(self.data["score_sum"] / total, 3) if total > 0 else 0

        # By agent
        agent = result.agent_id
        if agent not in self.data["by_agent"]:
            self.data["by_agent"][agent] = {"total": 0, "passed": 0, "blocked": 0}
        self.data["by_agent"][agent]["total"] += 1
        if result.passed:
            self.data["by_agent"][agent]["passed"] += 1
        else:
            self.data["by_agent"][agent]["blocked"] += 1

        # By skill
        skill = result.skill_id or "unknown"
        if skill not in self.data["by_skill"]:
            self.data["by_skill"][skill] = {"total": 0, "passed": 0, "blocked": 0}
        self.data["by_skill"][skill]["total"] += 1
        if result.passed:
            self.data["by_skill"][skill]["passed"] += 1
        else:
            self.data["by_skill"][skill]["blocked"] += 1

        # By output type
        otype = result.output_type
        if otype not in self.data["by_type"]:
            self.data["by_type"][otype] = {"total": 0, "passed": 0, "blocked": 0}
        self.data["by_type"][otype]["total"] += 1
        if result.passed:
            self.data["by_type"][otype]["passed"] += 1
        else:
            self.data["by_type"][otype]["blocked"] += 1

        # By failed rule
        for check in result.checks:
            if not check["passed"]:
                rule = check["rule"]
                if rule not in self.data["by_rule"]:
                    self.data["by_rule"][rule] = 0
                self.data["by_rule"][rule] += 1

        self._save()

    def summary(self):
        """Print gate statistics."""
        d = self.data
        print(f"  Total checks: {d['total_checks']}")
        print(f"  Passed: {d['total_passed']} ({d['pass_rate']:.0%})")
        print(f"  Blocked: {d['total_blocked']}")
        print(f"  Escalated: {d['total_escalated']}")
        print(f"  Avg score: {d['avg_score']:.0%}")

        if d.get("by_rule"):
            print(f"\n  Top failure rules:")
            sorted_rules = sorted(d["by_rule"].items(), key=lambda x: -x[1])
            for rule, count in sorted_rules[:5]:
                print(f"    {rule}: {count}x")

        if d.get("by_agent"):
            print(f"\n  By agent:")
            for agent, stats in sorted(d["by_agent"].items()):
                rate = stats["passed"] / stats["total"] if stats["total"] > 0 else 0
                print(f"    {agent}: {stats['total']} checks, {rate:.0%} pass rate")


# ═══════════════════════════════════════════════════════════════════════════════
# TESTS
# ═══════════════════════════════════════════════════════════════════════════════

def run_tests():
    print("=" * 60)
    print("  MA-15 Output Quality Gate Tests")
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

    gate = QualityGate()

    # Test 1: Rules defined
    test("Default rules defined", len(DEFAULT_RULES) >= 7)

    # Test 2: Output types defined
    test("Output type rules defined", len(OUTPUT_TYPE_RULES) >= 7)

    # Test 3: Good output passes
    good_output = """## Background

This is a comprehensive market research report on AI meeting assistants.
The market has grown significantly over the past three years driven by remote work.
Current market size is estimated at $2.5 billion with 25% year-over-year growth.
Key players include Otter.ai, Fireflies, and Microsoft Teams built-in features.

## Key Findings

Several key trends have emerged from our analysis of the competitive landscape.
Enterprise adoption is accelerating with remote work becoming a permanent fixture.
SMB segment is underserved with most solutions targeting enterprise price points.
AI transcription accuracy has reached 95%+ making real-time notes viable.
Integration with existing workflow tools is the top requested feature.

## Recommendations

Based on our findings, we recommend focusing on the SMB segment first.
The enterprise market requires significant compliance investment that delays launch.
A freemium model with usage-based pricing would capture the underserved SMB market.
Prioritize integrations with Slack, Notion, and Asana for maximum adoption.
"""
    result = gate.validate(good_output, "strategy_lead", "research", "e12-market-research-analyst")
    test("Good research output passes", result.passed, f"verdict={result.verdict}, score={result.score}")

    # Test 4: Empty output blocked
    result2 = gate.validate("", "strategy_lead", "research")
    test("Empty output blocked", not result2.passed and result2.verdict == "blocked")

    # Test 5: Too short output blocked
    result3 = gate.validate("Short text here.", "strategy_lead", "research")
    test("Too short output blocked", not result3.passed)

    # Test 6: Placeholder text blocked
    placeholder_output = """## Analysis
This section covers [INSERT YOUR ANALYSIS HERE] and provides insights.
The market is valued at [TODO] billion dollars.
"""
    result4 = gate.validate(placeholder_output, "strategy_lead", "analysis")
    test("Placeholder text blocked", not result4.passed)
    has_placeholder_check = any(c["rule"] == "no_placeholder" and not c["passed"] for c in result4.checks)
    test("Placeholder rule triggered", has_placeholder_check)

    # Test 7: Truncated output blocked
    truncated = "A" * 500 + "\n\nThe analysis shows promising results and continued..."
    result5 = gate.validate(truncated, "strategy_lead", "general")
    trunc_check = any(c["rule"] == "no_truncation" and not c["passed"] for c in result5.checks)
    test("Truncation detected", trunc_check)

    # Test 8: LLM error markers blocked
    error_output = "A" * 300 + "\n\nI apologize, but I cannot complete this analysis. As an AI, I don't have access to real-time data."
    result6 = gate.validate(error_output, "strategy_lead", "general")
    error_check = any(c["rule"] == "no_error_markers" and not c["passed"] for c in result6.checks)
    test("LLM error markers blocked", error_check)

    # Test 9: Missing required sections
    no_sections = "A" * 600 + "\n\nSome general text without proper sections or structure."
    result7 = gate.validate(no_sections, "strategy_lead", "research")
    section_check = any(c["rule"] == "required_sections" and not c["passed"] for c in result7.checks)
    test("Missing required sections caught", section_check)

    # Test 10: Repetitive content detected
    repeated = ("## Section\n\n" + "This is the same paragraph repeated. " * 10 + "\n\n") * 5
    result8 = gate.validate(repeated, "strategy_lead", "general")
    rep_check = any(c["rule"] == "no_repetition" and not c["passed"] for c in result8.checks)
    test("Repetition detected", rep_check)

    # Test 11: Score calculation
    test("Score is 0.0-1.0", 0.0 <= result.score <= 1.0, f"score={result.score}")

    # Test 12: Critical vs minor severity
    test("Critical failures block",
         result2.critical_failures > 0 and not result2.passed)

    # Test 13: Revision feedback
    feedback = gate.get_revision_feedback(result4)
    test("Revision feedback generated",
         feedback["status"] == "needs_revision" and len(feedback["feedback"]) > 0)

    # Test 14: Revision feedback has instructions
    has_instructions = all("instruction" in f for f in feedback["feedback"])
    test("Feedback has specific instructions", has_instructions)

    # Test 15: Escalation after max revisions
    bad_but_not_empty = "Short bad output that will fail min_length check for research type."
    result9 = gate.validate(bad_but_not_empty, "strategy_lead", "research",
                              revision_count=MAX_REVISIONS)
    test("Escalation after max revisions", result9.verdict == "escalated",
         f"verdict={result9.verdict}")

    # Test 16: Custom rules
    def check_has_numbers(content):
        has = bool(re.search(r'\d+', content))
        return has, "" if has else "No numbers found in output"

    result10 = gate.validate("No numbers in this text at all just words and more words " * 10,
                               "strategy_lead", "general",
                               custom_rules={"has_numbers": check_has_numbers})
    custom_failed = any(c["rule"] == "has_numbers" and not c["passed"] for c in result10.checks)
    test("Custom rule applied", custom_failed)

    # Test 17: Code output type
    code_output = """## Implementation

```python
import os

def process_data(input_path):
    with open(input_path) as f:
        data = f.read()
    return data
```

This function handles file processing with proper error handling.
""" + "A" * 200
    result11 = gate.validate(code_output, "engineering_lead", "code", "b05-feature-impl-writer")
    test("Code output validated", result11.passed or result11.minor_failures == 0,
         f"verdict={result11.verdict}")

    # Test 18: Batch validation
    batch = [
        {"content": good_output, "agent_id": "strategy_lead", "output_type": "research"},
        {"content": "", "agent_id": "engineering_lead", "output_type": "code"},
    ]
    batch_results = gate.validate_batch(batch)
    test("Batch: 2 results", len(batch_results) == 2)
    test("Batch: first passes, second fails",
         batch_results[0].passed and not batch_results[1].passed)

    # Test 20: Stats tracking
    stats = gate.stats
    test("Stats: total tracked", stats.data["total_checks"] > 0)
    test("Stats: pass rate calculated", 0.0 <= stats.data["pass_rate"] <= 1.0)

    # Test 22: Stats by agent
    test("Stats: by agent tracked", len(stats.data["by_agent"]) > 0)

    # Test 23: Stats by rule
    test("Stats: by failed rule tracked", len(stats.data["by_rule"]) > 0)

    # Test 24: GateResult to_dict
    result_dict = result.to_dict()
    test("GateResult serializable",
         all(k in result_dict for k in ["id", "passed", "verdict", "score", "checks"]))

    # Test 25: Passed output has no critical failures
    test("Passed output: 0 critical failures", result.critical_failures == 0)

    # Test 26: Product spec type
    spec_output = """## Overview

AI-powered meeting assistant for remote teams that automatically transcribes,
summarizes, and extracts action items from video calls. The product targets
SMB companies with 10-500 employees who use Zoom, Google Meet, or Teams.

## Requirements

The following requirements define the MVP scope for initial launch:
1. Real-time transcription with 95%+ accuracy across English accents
2. Automatic action item extraction with assignee detection
3. Post-meeting summary generation within 60 seconds of call end
4. Integration with Slack for summary delivery and action item tracking
5. Speaker identification and attribution for multi-party calls

## Scope

MVP includes core transcription, summary, and action item features.
Advanced analytics, sentiment analysis, and custom vocabulary deferred to v2.
Enterprise SSO and compliance features planned for v3.

## Timeline

90-day development cycle with weekly milestones and bi-weekly demos.
Phase 1 (Days 1-30): Core transcription engine and API
Phase 2 (Days 31-60): Summary generation and action items
Phase 3 (Days 61-90): Slack integration, testing, and launch prep
"""
    result12 = gate.validate(spec_output, "product_architect", "product_spec")
    test("Product spec passes with required sections", result12.passed,
         f"verdict={result12.verdict}, failures={[c['rule'] for c in result12.checks if not c['passed']]}")

    # Test 27: Gate result includes all dimensions
    dimensions = set(c["dimension"] for c in result.checks)
    test("Multiple dimensions checked", len(dimensions) >= 3, str(dimensions))

    # Test 28: Stats persists
    test("Stats saved to disk", GATE_STATS_PATH.exists())

    print(f"\n  Results: {tp}/{tt} passed")
    return tp == tt


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="NemoClaw Output Quality Gate")
    parser.add_argument("--test", action="store_true", help="Run all tests")
    parser.add_argument("--rules", action="store_true", help="Show all rules")
    parser.add_argument("--stats", action="store_true", help="Show gate statistics")
    parser.add_argument("--history", action="store_true", help="Show recent gate results")
    parser.add_argument("--check", metavar="FILE", help="Check a file through the gate")
    parser.add_argument("--type", default="general", help="Output type for --check")
    args = parser.parse_args()

    if args.test:
        success = run_tests()
        sys.exit(0 if success else 1)

    elif args.rules:
        print(f"  Default Rules ({len(DEFAULT_RULES)}):")
        for name, rule in DEFAULT_RULES.items():
            sev = "🛑 CRITICAL" if rule["severity"] == "critical" else "⚠️ MINOR"
            print(f"    [{sev}] {name}: {rule['description']}")
        print(f"\n  Output Types ({len(OUTPUT_TYPE_RULES)}):")
        for otype, config in OUTPUT_TYPE_RULES.items():
            sections = config.get("required_sections", [])
            min_len = config.get("min_length", "default")
            print(f"    {otype}: min_length={min_len}, sections={sections or 'none'}")

    elif args.stats:
        gate = QualityGate()
        gate.stats.summary()

    elif args.history:
        if GATE_LOG_PATH.exists():
            with open(GATE_LOG_PATH) as f:
                for line in f.readlines()[-20:]:
                    try:
                        r = json.loads(line.strip())
                        icon = "✅" if r.get("passed") else "🛑"
                        print(f"  {icon} [{r.get('timestamp', '?')[:19]}] {r.get('verdict')}: "
                              f"{r.get('output_type')} by {r.get('agent_id')} "
                              f"(score={r.get('score', 0):.0%})")
                    except json.JSONDecodeError:
                        continue
        else:
            print("  No gate history yet.")

    elif args.check:
        if not os.path.exists(args.check):
            print(f"  File not found: {args.check}")
            sys.exit(1)
        with open(args.check) as f:
            content = f.read()
        gate = QualityGate()
        result = gate.validate(content, "manual_check", args.type)
        icon = "✅" if result.passed else "🛑"
        print(f"  {icon} Verdict: {result.verdict} (score: {result.score:.0%})")
        for check in result.checks:
            ci = "✅" if check["passed"] else ("🛑" if check["severity"] == "critical" else "⚠️")
            print(f"    {ci} [{check['dimension']}] {check['rule']}: {check.get('message', 'OK')}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()

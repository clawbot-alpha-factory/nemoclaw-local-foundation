#!/usr/bin/env python3
"""
NemoClaw CI Policy Check — Deterministic compliance verification.
Runs locally (make ci-check) and in GitHub Actions CI.

Checks:
  1. L-003: Zero hardcoded model names in skills
  2. API keys: Zero direct access in skills (must use lib.routing)
  3. Schema: All skill.yaml have schema_version: 2
  4. Quality: All skill.yaml have quality_gate min_quality_score >= 9.0
  5. Critic: All skill.yaml have critic_loop enabled
  6. Syntax: Zero syntax errors in all .py files

Output: JSON summary + human-readable report
Exit: 0 if all pass, 1 if any fail
"""

import ast
import glob
import json
import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
EXCLUDE_DIRS = {".venv313", "tools/fish-speech", "tools/capcut-api", ".cc2-backup", "node_modules", ".next"}

# Known exceptions (files that legitimately contain model names)
L003_EXCEPTIONS = {
    "scripts/validate.py",
    "scripts/new-skill.py",
    "scripts/context_manager.py",
    "scripts/fix-l003.py",
}


def check_l003():
    """L-003: No hardcoded model names in skill run.py files."""
    pattern = re.compile(r"(gpt-4o|gpt-5\.4|claude-3-5|claude-sonnet-4|claude-haiku-4|claude-opus-4|gemini-2)")
    violations = []
    for f in sorted(glob.glob(str(REPO / "skills/*/run.py"))):
        content = open(f).read()
        if pattern.search(content):
            violations.append(f)
    return {"name": "L-003 (no hardcoded models)", "passed": len(violations) == 0,
            "violations": violations, "count": len(violations)}


def check_api_keys():
    """No direct API key access in skills (must use lib.routing)."""
    pattern = re.compile(r"(ANTHROPIC_API_KEY|OPENAI_API_KEY|GOOGLE_API_KEY)")
    violations = []
    for f in sorted(glob.glob(str(REPO / "skills/*/run.py"))):
        content = open(f).read()
        if pattern.search(content):
            violations.append(f)
    return {"name": "API key routing", "passed": len(violations) == 0,
            "violations": violations, "count": len(violations)}


def check_schema_version():
    """All skill.yaml have schema_version: 2."""
    violations = []
    try:
        import yaml
    except ImportError:
        return {"name": "Schema version", "passed": False, "violations": ["pyyaml not installed"], "count": 1}

    for f in sorted(glob.glob(str(REPO / "skills/*/skill.yaml"))):
        d = yaml.safe_load(open(f))
        if d.get("schema_version") != 2:
            violations.append(f"{f} (schema_version={d.get('schema_version')})")
    return {"name": "Schema version = 2", "passed": len(violations) == 0,
            "violations": violations, "count": len(violations)}


def check_quality_gate():
    """All skill.yaml have quality_gate with min_quality_score >= 9.0."""
    violations = []
    try:
        import yaml
    except ImportError:
        return {"name": "Quality gate", "passed": False, "violations": ["pyyaml not installed"], "count": 1}

    for f in sorted(glob.glob(str(REPO / "skills/*/skill.yaml"))):
        d = yaml.safe_load(open(f))
        qg = d.get("quality_gate", {})
        mqs = qg.get("min_quality_score", 0) if isinstance(qg, dict) else 0
        if float(mqs) < 9.0:
            violations.append(f"{f} (min_quality_score={mqs})")
    return {"name": "Quality gate >= 9.0", "passed": len(violations) == 0,
            "violations": violations, "count": len(violations)}


def check_critic_loop():
    """All skill.yaml have critic_loop enabled."""
    violations = []
    try:
        import yaml
    except ImportError:
        return {"name": "Critic loop", "passed": False, "violations": ["pyyaml not installed"], "count": 1}

    for f in sorted(glob.glob(str(REPO / "skills/*/skill.yaml"))):
        d = yaml.safe_load(open(f))
        cl = d.get("critic_loop", {})
        enabled = cl.get("enabled", False) if isinstance(cl, dict) else False
        if not enabled:
            violations.append(f)
    return {"name": "Critic loop enabled", "passed": len(violations) == 0,
            "violations": violations, "count": len(violations)}


def check_syntax():
    """Zero syntax errors across all .py files."""
    violations = []
    for root, dirs, files in os.walk(REPO):
        dirs[:] = [d for d in dirs if not any(ex in os.path.join(root, d) for ex in EXCLUDE_DIRS)]
        for f in files:
            if not f.endswith(".py"):
                continue
            path = os.path.join(root, f)
            try:
                ast.parse(open(path).read())
            except SyntaxError as e:
                violations.append(f"{path}:{e.lineno} — {e.msg}")
    return {"name": "Syntax (all .py files)", "passed": len(violations) == 0,
            "violations": violations, "count": len(violations)}


def main():
    checks = [
        check_l003(),
        check_api_keys(),
        check_schema_version(),
        check_quality_gate(),
        check_critic_loop(),
        check_syntax(),
    ]

    all_passed = all(c["passed"] for c in checks)

    # Human-readable output
    print("=" * 60)
    print("  NemoClaw CI Policy Check")
    print("=" * 60)
    for c in checks:
        icon = "PASS" if c["passed"] else "FAIL"
        print(f"  [{icon}] {c['name']}" + (f" ({c['count']} violations)" if not c["passed"] else ""))
        if not c["passed"]:
            for v in c["violations"][:5]:
                print(f"         {v}")
            if len(c["violations"]) > 5:
                print(f"         ... and {len(c['violations']) - 5} more")
    print("=" * 60)
    print(f"  Result: {'ALL PASSED' if all_passed else 'FAILED'}")
    print("=" * 60)

    # JSON output for CI parsing
    result = {
        "passed": all_passed,
        "checks": [{k: v for k, v in c.items() if k != "violations"} for c in checks],
        "total_checks": len(checks),
        "passed_checks": sum(1 for c in checks if c["passed"]),
    }
    print(f"\n{json.dumps(result)}")

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()

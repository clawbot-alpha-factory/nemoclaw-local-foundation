#!/usr/bin/env python3
"""
NemoClaw Regression Test Suite v2.0
Python-native runner — no shell escaping issues.

Usage:
  python3 scripts/test-all.py [--dry-run] [--skill SKILL_ID]
"""

import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_BASE = Path.home() / "nemoclaw-local-foundation"
SKILLS_DIR = REPO_BASE / "skills"
RUNNER = SKILLS_DIR / "skill-runner.py"
PYTHON = REPO_BASE / ".venv312" / "bin" / "python3"
CHECKPOINT_DB = Path.home() / ".nemoclaw" / "checkpoints" / "langgraph.db"

SKIP_DIRS = {"__pycache__", "graph-validation"}


def run_skill(skill_id: str, test_input_path: Path) -> tuple:
    """Run a skill with its test input. Returns (success, elapsed, error_msg)."""
    with open(test_input_path) as f:
        data = json.load(f)

    inputs = data.get("inputs", {})

    # Build command args
    cmd = [str(PYTHON), str(RUNNER), "--skill", skill_id]
    for key, value in inputs.items():
        cmd.extend(["--input", key, str(value)])

    # Delete checkpoint DB to prevent stale cache loops
    if CHECKPOINT_DB.exists():
        CHECKPOINT_DB.unlink()

    start = time.time()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,
            cwd=str(REPO_BASE),
        )
        elapsed = int(time.time() - start)
        output = result.stdout + result.stderr

        if "Skill complete" in output:
            return True, elapsed, None
        else:
            # Extract error
            error = ""
            for line in output.split("\n"):
                if '"error"' in line:
                    error = line.strip()
                    break
            if not error and result.returncode != 0:
                error = output.strip().split("\n")[-1][:200]
            return False, elapsed, error or "Unknown failure"

    except subprocess.TimeoutExpired:
        elapsed = int(time.time() - start)
        return False, elapsed, "TIMEOUT (300s)"
    except Exception as e:
        elapsed = int(time.time() - start)
        return False, elapsed, str(e)[:200]


def main():
    dry_run = "--dry-run" in sys.argv
    single_skill = None
    if "--skill" in sys.argv:
        idx = sys.argv.index("--skill")
        if idx + 1 < len(sys.argv):
            single_skill = sys.argv[idx + 1]

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print("=" * 50)
    print(f"  NemoClaw Regression Test Suite v2.0")
    print(f"  {now}")
    print("=" * 50)
    print()

    # Backup checkpoint DB
    if CHECKPOINT_DB.exists() and not dry_run:
        backup = Path(str(CHECKPOINT_DB) + ".pre-regression")
        shutil.copy2(CHECKPOINT_DB, backup)
        print("  [backup] Checkpoint DB saved to .pre-regression")
        print()

    passed = 0
    failed = 0
    skipped = 0
    results = []

    skill_dirs = sorted(SKILLS_DIR.iterdir())
    for skill_dir in skill_dirs:
        if not skill_dir.is_dir():
            continue
        skill_id = skill_dir.name
        if skill_id in SKIP_DIRS:
            continue
        if single_skill and skill_id != single_skill:
            continue

        test_input = skill_dir / "test-input.json"
        if not test_input.exists():
            print(f"  ⏭  {skill_id} — no test-input.json (SKIP)")
            skipped += 1
            results.append(("SKIP", skill_id, 0, "no test-input.json"))
            continue

        if dry_run:
            print(f"  🔍 {skill_id} — would run (DRY RUN)")
            continue

        print(f"  🔄 {skill_id}...", end="", flush=True)

        success, elapsed, error = run_skill(skill_id, test_input)

        if success:
            print(f" ✅ PASS ({elapsed}s)")
            passed += 1
            results.append(("PASS", skill_id, elapsed, None))
        else:
            print(f" ❌ FAIL ({elapsed}s)")
            if error:
                # Truncate error for display
                short_error = error[:120]
                print(f"    {short_error}")
            failed += 1
            results.append(("FAIL", skill_id, elapsed, error))

    # Restore checkpoint DB
    if not dry_run:
        backup = Path(str(CHECKPOINT_DB) + ".pre-regression")
        if backup.exists():
            shutil.copy2(backup, CHECKPOINT_DB)
            print()
            print("  [restore] Checkpoint DB restored from .pre-regression")

    print()
    print("=" * 50)
    print(f"  Results: {passed} passed  {failed} failed  {skipped} skipped")
    print("=" * 50)

    if results:
        print()
        print("  Detail:")
        for status, sid, elapsed, error in results:
            if status == "PASS":
                print(f"    ✅ {sid} ({elapsed}s)")
            elif status == "FAIL":
                err_short = f" — {error[:80]}" if error else ""
                print(f"    ❌ {sid} ({elapsed}s){err_short}")
            else:
                print(f"    ⏭  {sid}")

    # Write results JSON for automation
    results_path = REPO_BASE / "scripts" / "regression-results.json"
    with open(results_path, "w") as f:
        json.dump({
            "timestamp": now,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "detail": [
                {"status": s, "skill": sid, "elapsed": e, "error": err}
                for s, sid, e, err in results
            ],
        }, f, indent=2)

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
NemoClaw Content Factory Runner — Daily autonomous content production.
Produces 10+ content pieces across 12 social accounts daily.

Usage:
    python3 scripts/content_factory_runner.py --date today
    python3 scripts/content_factory_runner.py --date 2026-04-02 --dry-run
    python3 scripts/content_factory_runner.py --phase strategy
    python3 scripts/content_factory_runner.py --test  # verify pipeline works
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

CONFIG_DIR = REPO / "config" / "content-factory"
ASSETS_DIR = REPO / "assets" / "content-factory"
SKILL_RUNNER = REPO / "skills" / "skill-runner.py"

PHASES = ["strategy", "plan", "script", "compose", "publish", "analyze"]

PHASE_SKILLS = {
    "strategy": [
        ("cnt-07-content-performance-analyzer", {"content_metrics": "last_7_days", "period": "weekly"}),
        ("cnt-10-viral-pattern-analyzer", {"platform_data": "multi_platform", "niche": "ai_automation"}),
    ],
    "plan": [
        ("cnt-06-content-calendar-builder", {"business_context": "nemoclaw_agents", "channels": "instagram,tiktok,youtube,linkedin,x"}),
    ],
    "script": [
        ("cnt-01-viral-hook-generator", {"topic": "ai_automation", "platform": "tiktok"}),
        ("cnt-02-instagram-reel-script-writer", {"topic": "ai_automation", "cta_goal": "follow"}),
        ("cnt-03-tiktok-content-engine", {"niche": "ai_automation", "batch_size": "3"}),
        ("cnt-05-youtube-script-writer", {"video_topic": "ai_automation", "video_length": "short"}),
        ("cnt-11-agent-self-promo-generator", {"agent_id": "social_media_lead", "performance_data": "weekly_stats"}),
    ],
    "compose": [
        ("cnt-12-video-composer", {"script_text": "from_workspace", "agent_id": "social_media_lead", "platform": "tiktok"}),
        ("cnt-13-thumbnail-generator", {"title": "from_workspace", "agent_id": "social_media_lead", "platform": "youtube"}),
        ("cnt-14-caption-generator", {"audio_path": "from_workspace", "style": "bold_centered"}),
    ],
    "publish": [
        ("cnt-08-cross-channel-distributor", {"content_piece": "from_workspace", "channels": "all_active"}),
        ("cnt-09-social-posting-executor", {"post_content": "from_workspace", "platform": "scheduled"}),
    ],
    "analyze": [
        ("cnt-07-content-performance-analyzer", {"content_metrics": "today", "period": "daily"}),
    ],
}


def load_config(name: str) -> dict:
    """Load a YAML config from the content-factory config directory."""
    try:
        import yaml
    except ImportError:
        # Fallback: return empty dict if PyYAML not available
        return {}
    path = CONFIG_DIR / name
    if not path.exists():
        print(f"  [WARN] Config not found: {path}")
        return {}
    with open(path) as f:
        return yaml.safe_load(f) or {}


def resolve_date(date_str: str) -> str:
    """Resolve date string to YYYY-MM-DD format."""
    if date_str == "today":
        return date.today().isoformat()
    # Validate format
    datetime.strptime(date_str, "%Y-%m-%d")
    return date_str


def ensure_workspace(run_date: str) -> dict:
    """Create workspace directories for the day's run."""
    dirs = {}
    for subdir in ["scripts", "videos", "thumbnails", "captions", "images", "reports"]:
        d = ASSETS_DIR / subdir / run_date if subdir != "reports" else ASSETS_DIR / subdir
        d.mkdir(parents=True, exist_ok=True)
        dirs[subdir] = str(d)
    return dirs


def run_skill(skill_id: str, inputs: dict, dry_run: bool = False) -> dict:
    """Invoke a skill via skill-runner.py subprocess."""
    cmd = [sys.executable, str(SKILL_RUNNER), "--skill", skill_id]
    for k, v in inputs.items():
        cmd.extend(["--input", k, str(v)])

    print(f"    -> {skill_id} ", end="", flush=True)

    if dry_run:
        print("[DRY-RUN] skipped")
        return {"status": "dry_run", "skill": skill_id}

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=300, cwd=str(REPO)
        )
        if result.returncode == 0:
            print("[OK]")
            return {"status": "success", "skill": skill_id, "stdout": result.stdout[-500:]}
        else:
            print(f"[FAIL] rc={result.returncode}")
            return {"status": "failed", "skill": skill_id, "stderr": result.stderr[-500:]}
    except subprocess.TimeoutExpired:
        print("[TIMEOUT]")
        return {"status": "timeout", "skill": skill_id}
    except Exception as e:
        print(f"[ERROR] {e}")
        return {"status": "error", "skill": skill_id, "error": str(e)}


def run_phase(phase: str, run_date: str, dry_run: bool = False) -> list:
    """Execute all skills in a phase, with retry on failure."""
    print(f"\n  === Phase: {phase.upper()} ===")
    skills = PHASE_SKILLS.get(phase, [])
    results = []

    for skill_id, base_inputs in skills:
        inputs = {**base_inputs, "date": run_date}
        result = run_skill(skill_id, inputs, dry_run=dry_run)

        # Retry once on failure
        if result["status"] == "failed":
            print(f"    -> Retrying {skill_id}...")
            result = run_skill(skill_id, inputs, dry_run=dry_run)

        results.append(result)

    succeeded = sum(1 for r in results if r["status"] in ("success", "dry_run"))
    print(f"  Phase {phase}: {succeeded}/{len(results)} skills succeeded")
    return results


def write_report(run_date: str, all_results: dict, elapsed: float, dry_run: bool):
    """Write daily report JSON."""
    report_path = ASSETS_DIR / "reports" / f"{run_date}.json"
    report = {
        "date": run_date,
        "dry_run": dry_run,
        "elapsed_seconds": round(elapsed, 1),
        "timestamp": datetime.now().isoformat(),
        "phases": {},
        "summary": {"total_skills": 0, "succeeded": 0, "failed": 0},
    }
    for phase, results in all_results.items():
        report["phases"][phase] = results
        report["summary"]["total_skills"] += len(results)
        report["summary"]["succeeded"] += sum(1 for r in results if r["status"] in ("success", "dry_run"))
        report["summary"]["failed"] += sum(1 for r in results if r["status"] not in ("success", "dry_run"))

    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\n  Report written: {report_path}")
    return report


def run_test():
    """Minimal end-to-end test: one script skill -> verify output."""
    print("\n[TEST MODE] Running minimal pipeline test...")
    run_date = date.today().isoformat()
    ensure_workspace(run_date)

    result = run_skill(
        "cnt-01-viral-hook-generator",
        {"topic": "ai_automation", "platform": "tiktok", "date": run_date},
        dry_run=False,
    )

    if result["status"] == "success":
        print("\n  [PASS] Content Factory pipeline test passed")
        return 0
    else:
        print(f"\n  [FAIL] Pipeline test failed: {result.get('stderr', result.get('error', 'unknown'))}")
        return 1


def main():
    parser = argparse.ArgumentParser(description="NemoClaw Content Factory Runner")
    parser.add_argument("--date", default="today", help="Run date (YYYY-MM-DD or 'today')")
    parser.add_argument("--dry-run", action="store_true", help="Run all phases without publishing")
    parser.add_argument("--phase", choices=PHASES, help="Run a single phase only")
    parser.add_argument("--test", action="store_true", help="Run minimal end-to-end test")
    args = parser.parse_args()

    if args.test:
        sys.exit(run_test())

    run_date = resolve_date(args.date)
    print(f"Content Factory Runner — {run_date} {'[DRY-RUN]' if args.dry_run else ''}")

    # Load configs
    pipeline_cfg = load_config("pipeline-config.yaml")
    accounts_cfg = load_config("accounts-config.yaml")
    presets_cfg = load_config("platform-presets.yaml")
    print(f"  Loaded configs: pipeline={bool(pipeline_cfg)}, accounts={bool(accounts_cfg)}, presets={bool(presets_cfg)}")

    # Prepare workspace
    workspace = ensure_workspace(run_date)
    print(f"  Workspace: {ASSETS_DIR}")

    # Determine phases to run
    phases_to_run = [args.phase] if args.phase else PHASES
    if args.dry_run and "publish" in phases_to_run:
        print("  [DRY-RUN] Publish phase will be skipped")
        phases_to_run = [p for p in phases_to_run if p != "publish"]

    # Execute phases
    start = time.time()
    all_results = {}
    for phase in phases_to_run:
        all_results[phase] = run_phase(phase, run_date, dry_run=args.dry_run)

    elapsed = time.time() - start

    # Write report
    report = write_report(run_date, all_results, elapsed, args.dry_run)

    # Summary
    s = report["summary"]
    print(f"\n  DONE: {s['succeeded']}/{s['total_skills']} skills succeeded in {elapsed:.0f}s")
    if s["failed"] > 0:
        print(f"  WARNING: {s['failed']} skills failed — check report for details")
        sys.exit(1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
NemoClaw Avatar Pose Pipeline — Fully autonomous 20-pose generation for all 11 agents.

Phases:
  0. Extract character sheets (GPT-4o vision)
  1. Generate poses (GPT-Image edit with reference anchoring)
  2. Quality gate (CLIP + structural checks)
  3. Retry failed QA (escalating prompts)
  4. Summary report

Usage:
    python3 scripts/avatar_pose_pipeline.py                    # full run, all 11 agents
    python3 scripts/avatar_pose_pipeline.py --agent tariq      # single agent
    python3 scripts/avatar_pose_pipeline.py --dry-run          # show plan without generating
    python3 scripts/avatar_pose_pipeline.py --resume           # resume interrupted run
    python3 scripts/avatar_pose_pipeline.py --phase 2          # run specific phase only
"""

import json, os, sys, time
from pathlib import Path
from datetime import datetime, timezone

REPO = Path(os.path.expanduser("~/nemoclaw-local-foundation"))
sys.path.insert(0, str(REPO / "scripts"))

from avatar_character_sheet import extract_all as extract_sheets, SHEETS_DIR, AGENTS
from avatar_pose_generator import (generate_agent_poses, retry_failed, _load_metadata,
                                    _save_metadata, POSES_DIR, METADATA_FILE)
from avatar_quality_gate import score_image as qa_score_image
import avatar_quality_gate as qa_module

AVATARS_DIR = REPO / "assets" / "avatars"
POSE_DEFS = REPO / "config" / "avatars" / "pose_definitions.json"
ENV_FILE = REPO / "config" / ".env"


def _load_env():
    env = {}
    if not ENV_FILE.exists():
        return env
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


def preflight_check(agents: list[str]) -> tuple[bool, list[str]]:
    """Validate everything needed before running."""
    issues = []

    env = _load_env()
    if not (env.get("OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")):
        issues.append("OPENAI_API_KEY not found in config/.env or environment")

    if not POSE_DEFS.exists():
        issues.append(f"Pose definitions not found: {POSE_DEFS}")
    else:
        poses = json.loads(POSE_DEFS.read_text())
        if len(poses.get("poses", [])) != 20:
            issues.append(f"Expected 20 pose definitions, found {len(poses.get('poses', []))}")

    for agent_id in agents:
        avatar = AVATARS_DIR / f"{agent_id}.png"
        if not avatar.exists():
            issues.append(f"Missing avatar: {avatar}")

    # Check disk space (~150MB needed for 220 images)
    try:
        import shutil
        total, used, free = shutil.disk_usage(str(REPO))
        if free < 200_000_000:  # 200MB
            issues.append(f"Low disk space: {free // 1_000_000}MB free, need ~200MB")
    except Exception:
        pass

    # Check openai package
    try:
        import openai
    except ImportError:
        issues.append("openai package not installed")

    return len(issues) == 0, issues


def phase_0_character_sheets(agents: list[str]) -> bool:
    """Phase 0: Extract character descriptions."""
    print(f"\n{'=' * 60}")
    print(f"  Phase 0: Character Sheet Extraction ({len(agents)} agents)")
    print(f"{'=' * 60}\n")

    result = extract_sheets(agents)
    total = len(result.get("extracted", [])) + len(result.get("skipped", []))
    print(f"\n  ✅ {total}/{len(agents)} character sheets ready")
    return result.get("success", False)


def phase_1_generation(agents: list[str], api_key: str, metadata: dict) -> dict:
    """Phase 1: Generate all poses."""
    print(f"\n{'=' * 60}")
    print(f"  Phase 1: Pose Generation ({len(agents)} agents x 20 poses)")
    print(f"{'=' * 60}\n")

    totals = {"generated": 0, "skipped": 0, "failed": 0, "cost_usd": 0.0}

    for agent_id in agents:
        print(f"\n  🎨 {agent_id}")
        result = generate_agent_poses(agent_id, api_key, metadata=metadata)
        for k in totals:
            totals[k] += result.get(k, 0)
        print(f"    → Generated: {result['generated']}, Skipped: {result['skipped']}, "
              f"Failed: {result['failed']}, Cost: ${result['cost_usd']:.3f}")

    print(f"\n  Phase 1 complete: {totals['generated']} generated, "
          f"{totals['skipped']} skipped, ${totals['cost_usd']:.2f} spent")
    return totals


def phase_2_quality_gate(agents: list[str], metadata: dict) -> dict:
    """Phase 2: Run CLIP + structural QA on all generated images."""
    print(f"\n{'=' * 60}")
    print(f"  Phase 2: Quality Gate (CLIP + structural)")
    print(f"{'=' * 60}\n")

    totals = {"scored": 0, "passed": 0, "failed": 0, "clip_unavailable": False}

    for agent_id in agents:
        ref_path = str(AVATARS_DIR / f"{agent_id}.png")
        sheet_path = SHEETS_DIR / f"{agent_id}.json"
        bg_hex = None
        if sheet_path.exists():
            sheet = json.loads(sheet_path.read_text())
            bg_hex = sheet.get("background", {}).get("color_hex_estimate")

        agent_meta = metadata.get("agents", {}).get(agent_id, {})
        agent_passed = 0
        agent_total = 0

        for pose_key, pose_info in agent_meta.get("poses", {}).items():
            img_path = pose_info.get("image_path")
            if not img_path or not os.path.exists(img_path):
                continue
            if pose_info.get("passed") is True and pose_info.get("qa_score") is not None:
                totals["passed"] += 1
                totals["scored"] += 1
                agent_passed += 1
                agent_total += 1
                continue

            score = qa_score_image(ref_path, img_path, bg_hex)
            pose_info["qa_score"] = score["composite_score"]
            pose_info["clip_similarity"] = score.get("clip_similarity")
            pose_info["passed"] = score["passed"]

            if not score.get("clip_available"):
                totals["clip_unavailable"] = True

            totals["scored"] += 1
            agent_total += 1
            if score["passed"]:
                totals["passed"] += 1
                metadata["total_passed"] += 1
                agent_passed += 1

        if agent_total > 0:
            print(f"  {agent_id}: {agent_passed}/{agent_total} passed")

    _save_metadata(metadata)
    totals["failed"] = totals["scored"] - totals["passed"]
    fail_rate = totals["failed"] / max(1, totals["scored"]) * 100

    print(f"\n  Phase 2 complete: {totals['passed']}/{totals['scored']} passed "
          f"({fail_rate:.0f}% fail rate)")
    if totals["clip_unavailable"]:
        print("  ⚠️  CLIP not available — using structural checks only (install open-clip-torch for better QA)")
    return totals


def phase_3_retries(agents: list[str], api_key: str, metadata: dict) -> dict:
    """Phase 3: Retry failed QA with escalating prompts."""
    # Count how many need retrying
    needs_retry = 0
    for agent_id in agents:
        agent_meta = metadata.get("agents", {}).get(agent_id, {})
        for pose_key, pose_info in agent_meta.get("poses", {}).items():
            if not pose_info.get("passed") and pose_info.get("retry_level", 0) < 3:
                needs_retry += 1

    if needs_retry == 0:
        print(f"\n  Phase 3: No retries needed ✅")
        return {"retried": 0, "passed": 0, "exhausted": 0, "cost_usd": 0.0}

    print(f"\n{'=' * 60}")
    print(f"  Phase 3: Retry Failed QA ({needs_retry} images)")
    print(f"{'=' * 60}\n")

    totals = {"retried": 0, "passed": 0, "exhausted": 0, "cost_usd": 0.0}

    for agent_id in agents:
        result = retry_failed(agent_id, api_key, metadata, qa_module=qa_module)
        for k in totals:
            totals[k] += result.get(k, 0)

    print(f"\n  Phase 3 complete: {totals['retried']} retried, {totals['passed']} passed, "
          f"{totals['exhausted']} exhausted, ${totals['cost_usd']:.2f}")
    return totals


def phase_4_report(agents: list[str], metadata: dict):
    """Phase 4: Print and save final summary report."""
    print(f"\n{'=' * 60}")
    print(f"  FINAL REPORT")
    print(f"{'=' * 60}\n")

    total_images = 0
    total_passed = 0
    total_failed = 0
    total_exhausted = 0

    for agent_id in agents:
        agent_meta = metadata.get("agents", {}).get(agent_id, {})
        poses = agent_meta.get("poses", {})
        passed = sum(1 for p in poses.values() if p.get("passed"))
        failed = sum(1 for p in poses.values() if p.get("passed") is False)
        pending = sum(1 for p in poses.values() if p.get("passed") is None)
        avg_score = 0.0
        scored = [p.get("qa_score", 0) for p in poses.values() if p.get("qa_score") is not None]
        if scored:
            avg_score = sum(scored) / len(scored)

        status = "✅" if passed == 20 else "⚠️" if passed >= 15 else "❌"
        print(f"  {status} {agent_id:>8}: {passed}/20 passed | "
              f"avg score: {avg_score:.3f} | cost: ${agent_meta.get('cost_usd', 0):.2f}")

        total_images += len(poses)
        total_passed += passed
        total_failed += failed

    print(f"\n  {'─' * 50}")
    print(f"  Total images:    {total_images}")
    print(f"  Passed QA:       {total_passed}")
    print(f"  Failed QA:       {total_failed}")
    print(f"  Total cost:      ${metadata.get('total_cost_usd', 0):.2f}")
    print(f"  Output dir:      {POSES_DIR}")
    print(f"  Metadata:        {METADATA_FILE}")

    # Save completion timestamp
    metadata["completed_at"] = datetime.now(timezone.utc).isoformat()
    _save_metadata(metadata)


def dry_run(agents: list[str]):
    """Show what would be generated without actually doing it."""
    poses = json.loads(POSE_DEFS.read_text())["poses"]
    total = len(agents) * len(poses)
    est_cost = total * 0.019 * 1.2  # 20% retry buffer

    print(f"\n{'=' * 60}")
    print(f"  DRY RUN — Avatar Pose Pipeline")
    print(f"{'=' * 60}\n")
    print(f"  Agents:           {len(agents)}")
    print(f"  Poses per agent:  {len(poses)}")
    print(f"  Total images:     {total}")
    print(f"  Est. cost:        ${est_cost:.2f}")
    print(f"  Est. time:        ~{total * 2 // 60 + 5} minutes")
    print(f"\n  Agents: {', '.join(agents)}")
    print(f"\n  Poses:")
    for p in poses:
        print(f"    {p['id']:2d}. {p['name']:<30} ({p['framing']}, {p['difficulty']})")

    # Check existing sheets
    existing_sheets = sum(1 for a in agents if (SHEETS_DIR / f"{a}.json").exists())
    print(f"\n  Character sheets: {existing_sheets}/{len(agents)} extracted")

    # Check existing poses
    metadata = _load_metadata()
    existing = 0
    for a in agents:
        agent_meta = metadata.get("agents", {}).get(a, {})
        existing += sum(1 for p in agent_meta.get("poses", {}).values() if p.get("passed"))
    print(f"  Existing passed:  {existing}/{total}")
    print(f"  Remaining:        {total - existing}")


def main():
    import argparse
    p = argparse.ArgumentParser(description="NemoClaw Avatar Pose Pipeline")
    p.add_argument("--agent", help="Single agent ID (default: all 11)")
    p.add_argument("--dry-run", action="store_true", help="Show plan without generating")
    p.add_argument("--resume", action="store_true", help="Resume interrupted run")
    p.add_argument("--phase", type=int, choices=[0, 1, 2, 3], help="Run specific phase only")
    p.add_argument("--skip-qa", action="store_true", help="Skip quality gate (faster, no CLIP needed)")
    args = p.parse_args()

    agents = [args.agent] if args.agent else AGENTS
    start_time = time.time()

    if args.dry_run:
        dry_run(agents)
        return

    # Preflight
    print(f"\n{'=' * 60}")
    print(f"  NemoClaw Avatar Pose Pipeline")
    print(f"  {len(agents)} agents x 20 poses = {len(agents) * 20} images")
    print(f"{'=' * 60}")

    ok, issues = preflight_check(agents)
    if not ok:
        print(f"\n  ❌ Preflight failed:")
        for issue in issues:
            print(f"    • {issue}")
        sys.exit(1)
    print(f"\n  ✅ Preflight passed")

    env = _load_env()
    api_key = env.get("OPENAI_API_KEY", "") or os.environ.get("OPENAI_API_KEY", "")
    metadata = _load_metadata()

    # Run phases
    run_all = args.phase is None

    if run_all or args.phase == 0:
        phase_0_character_sheets(agents)

    if run_all or args.phase == 1:
        phase_1_generation(agents, api_key, metadata)

    if not args.skip_qa and (run_all or args.phase == 2):
        phase_2_quality_gate(agents, metadata)

    if not args.skip_qa and (run_all or args.phase == 3):
        phase_3_retries(agents, api_key, metadata)

    # Report
    if run_all:
        phase_4_report(agents, metadata)

    elapsed = time.time() - start_time
    print(f"\n  ⏱️  Total time: {elapsed / 60:.1f} minutes")
    print(f"  💰 Total cost: ${metadata.get('total_cost_usd', 0):.2f}")


if __name__ == "__main__":
    main()

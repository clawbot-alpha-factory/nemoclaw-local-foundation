#!/usr/bin/env python3
"""
ZARA'S HEYGEN POSE UPLOADER
============================
Uploads generated avatar poses to HeyGen as photo avatars.
Each pose becomes a separate talking_photo that can be used in video generation.

Usage:
    python3 scripts/avatar_heygen_uploader.py --agent tariq         # upload all Tariq poses
    python3 scripts/avatar_heygen_uploader.py --agent tariq --dry-run
    python3 scripts/avatar_heygen_uploader.py                       # all agents
"""

import json, os, sys, time, logging, requests
from pathlib import Path
from datetime import datetime, timezone

REPO = Path(__file__).resolve().parent.parent
logging.basicConfig(level=logging.INFO, format="%(asctime)s [ZARA-UPLOAD] %(message)s")
log = logging.getLogger("zara-upload")

POSES_DIR = REPO / "assets" / "avatars" / "poses"
METADATA_FILE = POSES_DIR / "metadata.json"
AVATAR_IDS_FILE = REPO / "config" / "content-factory" / "heygen-avatar-ids.json"
ENV_FILE = REPO / "config" / ".env"
LOG_DIR = Path.home() / ".nemoclaw" / "integrations"
ACTION_LOG = LOG_DIR / "avatar-pose-actions.jsonl"

HEYGEN_API_BASE = "https://api.heygen.com"
HEYGEN_UPLOAD_BASE = "https://upload.heygen.com"
UPLOAD_DELAY = 2.0  # seconds between uploads (rate limit safety)

AGENTS = ["tariq", "nadia", "khalid", "layla", "omar", "yasmin",
          "faisal", "hassan", "rania", "amira", "zara"]


def _load_key(name):
    if not ENV_FILE.exists():
        return ""
    for ln in ENV_FILE.read_text().splitlines():
        if ln.startswith(f"{name}="):
            return ln.strip().split("=", 1)[1]
    return ""


def _log_action(action, params, success, error=None):
    entry = {"timestamp": datetime.now(timezone.utc).isoformat(), "service": "avatar_pose",
             "phase": "heygen_upload", "action": action, "params": params, "success": success}
    if error:
        entry["error"] = str(error)[:200]
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with open(ACTION_LOG, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass


def upload_photo_avatar(image_path: str, api_key: str, name: str = None) -> tuple[bool, str]:
    """Upload a single image to HeyGen as a talking photo avatar.
    Uses POST /v1/talking_photo (the correct endpoint for photo uploads).
    Returns (success, talking_photo_id_or_error)."""
    headers = {"X-Api-Key": api_key}

    try:
        # HeyGen expects raw binary body with Content-Type header, NOT multipart form
        headers["Content-Type"] = "image/png"
        with open(image_path, "rb") as f:
            image_data = f.read()

        r = requests.post(f"{HEYGEN_UPLOAD_BASE}/v1/talking_photo",
                        headers=headers, data=image_data, timeout=120)

        resp = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}

        if r.status_code == 200 and resp.get("data"):
            data = resp["data"]
            avatar_id = data.get("talking_photo_id") or data.get("id") or data.get("avatar_id")
            if avatar_id:
                return True, avatar_id
            return True, json.dumps(data)[:100]
        elif r.status_code == 200:
            # Success but unexpected response shape
            return False, f"200 but no data: {r.text[:200]}"
        else:
            error_msg = resp.get("error", {}).get("message", "") or resp.get("message", "") or r.text[:200]
            return False, f"HTTP {r.status_code}: {error_msg}"

    except requests.exceptions.Timeout:
        return False, "Request timed out (120s)"
    except Exception as e:
        return False, str(e)[:200]


def upload_agent_poses(agent_id: str, api_key: str, dry_run: bool = False) -> dict:
    """Upload all QA-passed poses for a single agent to HeyGen."""
    # Load metadata
    if not METADATA_FILE.exists():
        return {"success": False, "error": "No metadata.json — run avatar_pose_pipeline.py first"}

    metadata = json.loads(METADATA_FILE.read_text())
    agent_meta = metadata.get("agents", {}).get(agent_id, {})
    poses = agent_meta.get("poses", {})

    if not poses:
        return {"success": False, "error": f"No poses found for {agent_id}"}

    # Load existing avatar IDs
    avatar_ids = json.loads(AVATAR_IDS_FILE.read_text()) if AVATAR_IDS_FILE.exists() else {}
    # Ensure poses structure exists
    if "avatar_poses" not in avatar_ids:
        avatar_ids["avatar_poses"] = {}
    if agent_id not in avatar_ids["avatar_poses"]:
        avatar_ids["avatar_poses"][agent_id] = {}

    results = {"uploaded": 0, "skipped": 0, "failed": 0, "errors": []}
    start_time = time.time()

    passed_poses = {k: v for k, v in poses.items() if v.get("passed")}
    log.info(f"  {agent_id}: {len(passed_poses)} poses passed QA, uploading to HeyGen...")

    for pose_key, pose_info in sorted(passed_poses.items()):
        img_path = pose_info.get("image_path")
        if not img_path or not os.path.exists(img_path):
            results["failed"] += 1
            results["errors"].append(f"{pose_key}: image not found at {img_path}")
            continue

        # Skip already uploaded
        if avatar_ids["avatar_poses"][agent_id].get(pose_key):
            results["skipped"] += 1
            log.info(f"    ⏭️  {pose_key} — already uploaded")
            continue

        display_name = f"nemoclaw_{agent_id}_{pose_key}"

        if dry_run:
            results["uploaded"] += 1
            log.info(f"    🔍 {pose_key} — would upload {Path(img_path).name} as '{display_name}'")
            continue

        log.info(f"    📤 {pose_key}...", )
        ok, result = upload_photo_avatar(img_path, api_key, name=display_name)

        if ok:
            results["uploaded"] += 1
            avatar_ids["avatar_poses"][agent_id][pose_key] = result
            pose_info["heygen_avatar_id"] = result
            log.info(f"       ✅ avatar_id: {result}")
            _log_action("upload_pose", {"agent": agent_id, "pose": pose_key, "avatar_id": result}, True)
        else:
            results["failed"] += 1
            results["errors"].append(f"{pose_key}: {result}")
            log.error(f"       ❌ {result}")
            _log_action("upload_pose", {"agent": agent_id, "pose": pose_key}, False, error=result)

        time.sleep(UPLOAD_DELAY)

    elapsed = time.time() - start_time

    # Save updated avatar IDs
    if not dry_run:
        AVATAR_IDS_FILE.write_text(json.dumps(avatar_ids, indent=2))
        # Update metadata too
        tmp = METADATA_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(metadata, indent=2))
        tmp.rename(METADATA_FILE)

    results["elapsed_seconds"] = round(elapsed, 1)
    results["success"] = results["failed"] == 0
    return results


def main():
    import argparse
    p = argparse.ArgumentParser(description="Zara's HeyGen Pose Uploader")
    p.add_argument("--agent", help="Single agent ID (default: all)")
    p.add_argument("--dry-run", action="store_true", help="Show what would be uploaded")
    args = p.parse_args()

    api_key = _load_key("HEYGEN_API_KEY")
    if not api_key and not args.dry_run:
        log.error("❌ HEYGEN_API_KEY not found in config/.env")
        sys.exit(1)

    agents = [args.agent] if args.agent else AGENTS

    log.info(f"\n{'=' * 60}")
    log.info(f"  ZARA — HeyGen Pose Upload {'(DRY RUN)' if args.dry_run else ''}")
    log.info(f"  Agents: {', '.join(agents)}")
    log.info(f"{'=' * 60}\n")

    total = {"uploaded": 0, "skipped": 0, "failed": 0}

    for agent_id in agents:
        result = upload_agent_poses(agent_id, api_key, dry_run=args.dry_run)
        if not result.get("success", True) and "error" in result:
            log.error(f"  {agent_id}: {result['error']}")
            continue
        for k in total:
            total[k] += result.get(k, 0)
        log.info(f"  {agent_id}: uploaded={result['uploaded']}, skipped={result['skipped']}, "
                 f"failed={result['failed']}, time={result.get('elapsed_seconds', 0)}s\n")

    log.info(f"  {'─' * 50}")
    log.info(f"  Total uploaded: {total['uploaded']}")
    log.info(f"  Total skipped:  {total['skipped']}")
    log.info(f"  Total failed:   {total['failed']}")


if __name__ == "__main__":
    main()

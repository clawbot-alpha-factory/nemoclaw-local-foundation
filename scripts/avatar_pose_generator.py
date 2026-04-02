#!/usr/bin/env python3
"""
Phase 1 + 3: Generate avatar poses using OpenAI GPT-Image with reference image anchoring.
Includes retry logic with prompt reinforcement for failed QA.

    python3 scripts/avatar_pose_generator.py --agent tariq --pose 1
    python3 scripts/avatar_pose_generator.py --agent tariq  # all 20 poses
"""

import json, os, sys, time, base64, tempfile, shutil
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

REPO = Path(os.path.expanduser("~/nemoclaw-local-foundation"))
AVATARS_DIR = REPO / "assets" / "avatars"
POSES_DIR = REPO / "assets" / "avatars" / "poses"
SHEETS_DIR = REPO / "config" / "avatars" / "character_sheets"
POSE_DEFS = REPO / "config" / "avatars" / "pose_definitions.json"
ENV_FILE = REPO / "config" / ".env"
LOG_DIR = Path.home() / ".nemoclaw" / "integrations"
ACTION_LOG = LOG_DIR / "avatar-pose-actions.jsonl"
METADATA_FILE = POSES_DIR / "metadata.json"

COST_PER_IMAGE_MEDIUM = 0.019
COST_PER_IMAGE_HIGH = 0.042
RATE_LIMIT_DELAY = 2.0  # seconds between requests
MAX_RETRIES = 3

AGENTS = ["tariq", "nadia", "khalid", "layla", "omar", "yasmin",
          "faisal", "hassan", "rania", "amira", "zara"]


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


def _log(action, params, success, error=None):
    entry = {"timestamp": datetime.now(timezone.utc).isoformat(), "service": "avatar_pose",
             "phase": "generation", "action": action, "params": params, "success": success}
    if error:
        entry["error"] = str(error)[:200]
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with open(ACTION_LOG, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass


def _load_metadata() -> dict:
    if METADATA_FILE.exists():
        return json.loads(METADATA_FILE.read_text())
    return {"version": "1.0", "started_at": datetime.now(timezone.utc).isoformat(),
            "agents": {}, "total_cost_usd": 0.0, "total_generated": 0, "total_passed": 0}


def _save_metadata(meta: dict):
    METADATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = METADATA_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(meta, indent=2))
    tmp.rename(METADATA_FILE)


def _build_prompt(character_sheet: dict, pose_def: dict, retry_level: int = 0) -> str:
    """Construct generation prompt from character sheet + pose definition."""
    anchor = character_sheet.get("prompt_anchor", "")
    art = character_sheet.get("art_style", {})
    bg = character_sheet.get("background", {})
    bg_color = bg.get("color_hex_estimate", "#333333")
    pose_text = pose_def["prompt"]

    base = (
        f"A {art.get('type', 'cartoon')} character illustration with "
        f"{art.get('line_weight', 'bold black outlines')} and {art.get('shading', 'flat color shading')}. "
        f"{anchor} "
        f"POSE: {pose_text}. "
        f"Solid {bg_color} background. "
        f"The character must wear the EXACT same outfit, accessories, and colors as in the reference image. "
        f"Same art style, same line weight, same color palette. "
        f"No text, no watermarks, no logos. Clean 1024x1024 illustration."
    )

    if retry_level >= 1:
        base += (" CRITICAL: The character must be IDENTICAL to the reference image. "
                 "Same face shape, same skin tone, same hair, same clothes, same accessories. "
                 "Only the body pose changes.")
    if retry_level >= 2:
        base += " Use high fidelity. Prioritize character identity over pose accuracy."

    return base


def generate_single_pose(agent_id: str, pose_def: dict, character_sheet: dict,
                          api_key: str, quality: str = "medium",
                          retry_level: int = 0) -> tuple[bool, dict | str]:
    """Generate a single pose image. Returns (success, result_dict_or_error)."""
    avatar_path = AVATARS_DIR / f"{agent_id}.png"
    if not avatar_path.exists():
        return False, f"Avatar not found: {avatar_path}"

    try:
        import openai
        client = openai.OpenAI(api_key=api_key)
    except ImportError:
        return False, "openai package not installed"

    prompt = _build_prompt(character_sheet, pose_def, retry_level)
    pose_name = pose_def["name"]
    pose_id = pose_def["id"]

    # Output path
    agent_dir = POSES_DIR / agent_id
    agent_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{pose_id:02d}_{pose_name}.png"
    out_path = agent_dir / filename

    try:
        # Read reference image
        img_b64 = base64.b64encode(avatar_path.read_bytes()).decode()

        # Use images.edit with reference image for character anchoring
        resp = client.images.edit(
            model="gpt-image-1",
            image=open(avatar_path, "rb"),
            prompt=prompt,
            n=1,
            size="1024x1024",
            quality=quality
        )

        img_data = resp.data[0]
        cost = COST_PER_IMAGE_HIGH if quality == "high" else COST_PER_IMAGE_MEDIUM

        # Write atomically
        tmp_path = out_path.with_suffix(".tmp.png")
        if hasattr(img_data, "b64_json") and img_data.b64_json:
            tmp_path.write_bytes(base64.b64decode(img_data.b64_json))
        elif hasattr(img_data, "url") and img_data.url:
            import requests
            r = requests.get(img_data.url, timeout=60)
            tmp_path.write_bytes(r.content)
        else:
            return False, "No image data in response"

        tmp_path.rename(out_path)

        _log("generate_pose", {"agent": agent_id, "pose": pose_name,
                                "retry": retry_level, "quality": quality,
                                "cost_usd": cost}, True)

        return True, {
            "image_path": str(out_path),
            "cost_usd": cost,
            "quality": quality,
            "retry_level": retry_level,
            "prompt_length": len(prompt)
        }

    except Exception as e:
        _log("generate_pose", {"agent": agent_id, "pose": pose_name,
                                "retry": retry_level}, False, error=e)
        return False, str(e)


def generate_agent_poses(agent_id: str, api_key: str, pose_ids: list[int] = None,
                          metadata: dict = None) -> dict:
    """Generate all poses for a single agent. Returns summary."""
    # Load character sheet
    sheet_path = SHEETS_DIR / f"{agent_id}.json"
    if not sheet_path.exists():
        return {"success": False, "error": f"No character sheet for {agent_id}. Run avatar_character_sheet.py first."}

    character_sheet = json.loads(sheet_path.read_text())
    pose_defs = json.loads(POSE_DEFS.read_text())["poses"]

    if pose_ids:
        pose_defs = [p for p in pose_defs if p["id"] in pose_ids]

    if metadata is None:
        metadata = _load_metadata()

    agent_meta = metadata.setdefault("agents", {}).setdefault(agent_id, {"poses": {}, "cost_usd": 0.0})
    results = {"generated": 0, "skipped": 0, "failed": 0, "cost_usd": 0.0}

    for pose_def in pose_defs:
        pose_name = pose_def["name"]
        pose_key = f"{pose_def['id']:02d}_{pose_name}"

        # Skip already completed
        existing = agent_meta["poses"].get(pose_key, {})
        if existing.get("passed"):
            results["skipped"] += 1
            continue

        print(f"    📸 {pose_key}...", end=" ", flush=True)
        ok, data = generate_single_pose(agent_id, pose_def, character_sheet, api_key)

        if ok:
            results["generated"] += 1
            results["cost_usd"] += data["cost_usd"]
            agent_meta["poses"][pose_key] = {
                "image_path": data["image_path"],
                "cost_usd": data["cost_usd"],
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "retry_level": 0,
                "qa_score": None,
                "passed": None  # set by quality gate
            }
            metadata["total_cost_usd"] += data["cost_usd"]
            metadata["total_generated"] += 1
            _save_metadata(metadata)
            print(f"✅ (${data['cost_usd']:.3f})")
        else:
            results["failed"] += 1
            agent_meta["poses"][pose_key] = {
                "error": data, "generated_at": datetime.now(timezone.utc).isoformat(),
                "passed": False
            }
            _save_metadata(metadata)
            print(f"❌ {str(data)[:60]}")

        time.sleep(RATE_LIMIT_DELAY)

    agent_meta["cost_usd"] += results["cost_usd"]
    _save_metadata(metadata)
    return results


def retry_failed(agent_id: str, api_key: str, metadata: dict,
                  qa_module=None) -> dict:
    """Retry poses that failed QA. Up to MAX_RETRIES attempts with escalating prompts."""
    sheet_path = SHEETS_DIR / f"{agent_id}.json"
    if not sheet_path.exists():
        return {"retried": 0}

    character_sheet = json.loads(sheet_path.read_text())
    pose_defs = {p["name"]: p for p in json.loads(POSE_DEFS.read_text())["poses"]}
    agent_meta = metadata.get("agents", {}).get(agent_id, {})
    ref_path = str(AVATARS_DIR / f"{agent_id}.png")
    bg_hex = character_sheet.get("background", {}).get("color_hex_estimate")

    results = {"retried": 0, "passed": 0, "exhausted": 0, "cost_usd": 0.0}

    for pose_key, pose_info in agent_meta.get("poses", {}).items():
        if pose_info.get("passed"):
            continue
        if pose_info.get("retry_level", 0) >= MAX_RETRIES:
            results["exhausted"] += 1
            continue

        # Parse pose name from key
        parts = pose_key.split("_", 1)
        if len(parts) < 2:
            continue
        pose_name = parts[1]
        pose_def = pose_defs.get(pose_name)
        if not pose_def:
            continue

        retry_level = pose_info.get("retry_level", 0) + 1
        quality = "high" if retry_level >= 2 else "medium"

        print(f"    🔄 {agent_id}/{pose_key} retry {retry_level}...", end=" ", flush=True)
        ok, data = generate_single_pose(agent_id, pose_def, character_sheet,
                                         api_key, quality=quality, retry_level=retry_level)

        if ok:
            results["retried"] += 1
            results["cost_usd"] += data["cost_usd"]
            pose_info["image_path"] = data["image_path"]
            pose_info["cost_usd"] = pose_info.get("cost_usd", 0) + data["cost_usd"]
            pose_info["retry_level"] = retry_level
            pose_info["generated_at"] = datetime.now(timezone.utc).isoformat()
            metadata["total_cost_usd"] += data["cost_usd"]

            # Re-run QA if module available
            if qa_module and os.path.exists(data["image_path"]):
                score = qa_module.score_image(ref_path, data["image_path"], bg_hex)
                pose_info["qa_score"] = score["composite_score"]
                pose_info["clip_similarity"] = score["clip_similarity"]
                pose_info["passed"] = score["passed"]
                if score["passed"]:
                    results["passed"] += 1
                    metadata["total_passed"] += 1
                    print(f"✅ score={score['composite_score']:.3f}")
                else:
                    print(f"⚠️  score={score['composite_score']:.3f}")
            else:
                pose_info["passed"] = None
                print("✅ (no QA)")
        else:
            pose_info["retry_level"] = retry_level
            print(f"❌ {str(data)[:60]}")

        _save_metadata(metadata)
        time.sleep(RATE_LIMIT_DELAY)

    return results


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Generate avatar poses")
    p.add_argument("--agent", help="Single agent ID")
    p.add_argument("--pose", type=int, help="Single pose ID (1-20)")
    args = p.parse_args()

    env = _load_env()
    api_key = env.get("OPENAI_API_KEY", "") or os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        print("❌ No OPENAI_API_KEY found"); sys.exit(1)

    agents = [args.agent] if args.agent else AGENTS
    pose_ids = [args.pose] if args.pose else None
    metadata = _load_metadata()

    for agent_id in agents:
        print(f"\n  🎨 {agent_id}")
        result = generate_agent_poses(agent_id, api_key, pose_ids, metadata)
        print(f"    Generated: {result['generated']}, Skipped: {result['skipped']}, "
              f"Failed: {result['failed']}, Cost: ${result['cost_usd']:.3f}")

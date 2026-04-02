#!/usr/bin/env python3
"""
Phase 0: Extract structured character descriptions from avatar images using GPT-4o vision.
Saves JSON character sheets for deterministic prompt construction in pose generation.

    python3 scripts/avatar_character_sheet.py
    python3 scripts/avatar_character_sheet.py --agent tariq
"""

import json, os, sys, base64
from pathlib import Path
from datetime import datetime, timezone

REPO = Path(os.path.expanduser("~/nemoclaw-local-foundation"))
AVATARS_DIR = REPO / "assets" / "avatars"
SHEETS_DIR = REPO / "config" / "avatars" / "character_sheets"
ENV_FILE = REPO / "config" / ".env"
LOG_DIR = Path.home() / ".nemoclaw" / "integrations"
ACTION_LOG = LOG_DIR / "avatar-pose-actions.jsonl"

AGENTS = ["tariq", "nadia", "khalid", "layla", "omar", "yasmin",
          "faisal", "hassan", "rania", "amira", "zara"]

EXTRACTION_PROMPT = """Analyze this cartoon character avatar image and extract a precise structured description.
Return ONLY valid JSON with these exact fields:

{
  "agent_id": "<name>",
  "art_style": {
    "type": "cartoon/animated",
    "line_weight": "bold black outlines or thin lines",
    "shading": "flat color or gradient",
    "skin_color_style": "describe exact skin color (e.g. Simpsons yellow, natural tan, etc.)"
  },
  "face": {
    "skin_tone": "exact color description",
    "head_shape": "round/oval/angular",
    "hair_style": "description",
    "hair_color": "color",
    "eyes": "description including glasses if any",
    "facial_expression": "default expression",
    "distinguishing_features": "any unique facial features"
  },
  "outfit": {
    "top": "exact description of jacket/blazer/shirt with colors",
    "shirt": "undershirt or collar details",
    "tie_or_neckwear": "tie, scarf, or neckwear details with color/pattern, or null",
    "accessories": [
      "list each accessory: pocket square pattern and color, lapel pin type, glasses, earrings, etc."
    ]
  },
  "body": {
    "build": "slim/average/stocky",
    "posture": "description of current pose"
  },
  "held_items": ["list any items the character is holding, or empty array"],
  "background": {
    "color_hex_estimate": "#hexcode",
    "type": "solid color"
  },
  "prompt_anchor": "A single paragraph describing this exact character for image generation, focusing on outfit and identity markers. Be extremely specific about colors and patterns."
}

Be extremely precise about colors, patterns, and small details. These descriptions will be used to regenerate this exact character in different poses."""


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
             "phase": "character_sheet", "action": action, "params": params, "success": success}
    if error:
        entry["error"] = str(error)[:200]
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with open(ACTION_LOG, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass


def extract_character_sheet(agent_id: str, api_key: str) -> tuple[bool, dict | str]:
    """Extract character description from avatar image using GPT-4o vision."""
    avatar_path = AVATARS_DIR / f"{agent_id}.png"
    if not avatar_path.exists():
        return False, f"Avatar not found: {avatar_path}"

    try:
        import openai
        client = openai.OpenAI(api_key=api_key)
    except ImportError:
        return False, "openai package not installed"

    img_b64 = base64.b64encode(avatar_path.read_bytes()).decode()

    try:
        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": EXTRACTION_PROMPT},
                    {"type": "image_url", "image_url": {
                        "url": f"data:image/png;base64,{img_b64}", "detail": "high"
                    }}
                ]
            }],
            max_tokens=2000,
            temperature=0.1
        )
        raw = resp.choices[0].message.content.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

        sheet = json.loads(raw)
        sheet["agent_id"] = agent_id
        sheet["extracted_at"] = datetime.now(timezone.utc).isoformat()
        sheet["source_image"] = str(avatar_path)

        cost = 0.01  # approximate GPT-4o vision cost
        _log("extract", {"agent": agent_id, "cost_usd": cost}, True)
        return True, sheet

    except json.JSONDecodeError as e:
        _log("extract", {"agent": agent_id}, False, error=f"JSON parse: {e}")
        return False, f"Failed to parse GPT-4o response as JSON: {e}\nRaw: {raw[:300]}"
    except Exception as e:
        _log("extract", {"agent": agent_id}, False, error=e)
        return False, str(e)


def extract_all(agents: list[str] = None, api_key: str = None) -> dict:
    """Extract character sheets for all agents. Returns summary."""
    agents = agents or AGENTS
    env = _load_env()
    api_key = api_key or env.get("OPENAI_API_KEY", "") or os.environ.get("OPENAI_API_KEY", "")

    if not api_key:
        return {"success": False, "error": "No OPENAI_API_KEY found"}

    SHEETS_DIR.mkdir(parents=True, exist_ok=True)
    results = {"success": True, "extracted": [], "failed": [], "skipped": []}

    for agent_id in agents:
        sheet_path = SHEETS_DIR / f"{agent_id}.json"
        if sheet_path.exists():
            results["skipped"].append(agent_id)
            print(f"  ⏭️  {agent_id} — already extracted")
            continue

        print(f"  🔍 {agent_id} — extracting character sheet...", end=" ", flush=True)
        ok, data = extract_character_sheet(agent_id, api_key)

        if ok:
            sheet_path.write_text(json.dumps(data, indent=2))
            results["extracted"].append(agent_id)
            print("✅")
        else:
            results["failed"].append({"agent": agent_id, "error": data})
            print(f"❌ {data[:80]}")

    total = len(results["extracted"]) + len(results["skipped"])
    results["success"] = total == len(agents)
    return results


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Extract character sheets from avatar images")
    p.add_argument("--agent", help="Single agent ID to extract")
    p.add_argument("--force", action="store_true", help="Re-extract even if sheet exists")
    args = p.parse_args()

    agents = [args.agent] if args.agent else AGENTS
    if args.force:
        for a in agents:
            sheet = SHEETS_DIR / f"{a}.json"
            if sheet.exists():
                sheet.unlink()

    print(f"\n{'=' * 50}")
    print(f"  Character Sheet Extraction — {len(agents)} agents")
    print(f"{'=' * 50}\n")

    result = extract_all(agents)

    print(f"\n  Extracted: {len(result['extracted'])}")
    print(f"  Skipped:   {len(result['skipped'])}")
    print(f"  Failed:    {len(result['failed'])}")
    print(f"  {'✅ All done' if result['success'] else '❌ Some failed'}")

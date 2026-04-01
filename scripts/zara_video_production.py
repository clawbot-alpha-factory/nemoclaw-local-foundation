#!/usr/bin/env python3
"""
ZARA'S VIDEO PRODUCTION PIPELINE
=================================
social_media_lead (Zara) — Creative Director & Executor

Zara handles EVERYTHING autonomously:
  Phase 1: Creative research (viral patterns + hooks)
  Phase 2: Script generation (one per agent, character voice)
  Phase 3: HeyGen API video production (animated talking avatars)
  Phase 4: Status tracking + download

Usage:
    .venv313/bin/python3 scripts/zara_video_production.py --all
    .venv313/bin/python3 scripts/zara_video_production.py --phase scripts
    .venv313/bin/python3 scripts/zara_video_production.py --phase heygen
    .venv313/bin/python3 scripts/zara_video_production.py --phase download
"""

import argparse, json, os, sys, time, subprocess, logging, requests
from pathlib import Path
from datetime import datetime, timezone

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [ZARA] %(message)s")
log = logging.getLogger("zara")

PYTHON = str(REPO / ".venv313" / "bin" / "python3")
OUTPUT_DIR = REPO / "assets" / "content-factory" / "videos" / "intros"
SCRIPTS_DIR = REPO / "assets" / "content-factory" / "scripts" / "intros"

def _load_key(name):
    with open(REPO / "config/.env") as f:
        for ln in f:
            if ln.startswith(f"{name}="): return ln.strip().split("=", 1)[1]
    return ""

# ═══════════════════════════════════════════════════════════════
# ZARA'S AGENT ROSTER — Character + Voice + Avatar mapping
# ═══════════════════════════════════════════════════════════════

# Voice assignments: picked to match each character's energy
# Male voices for male agents, female for female
AGENTS = {
    "tariq":  {"name": "Tariq",  "title": "CEO",   "character": "Homer Simpson",  "gender": "male",   "voice_name": "Marco",  "color": "#2C5F2D", "energy": "warm authoritative bumbling genius"},
    "nadia":  {"name": "Nadia",  "title": "CSO",   "character": "Velma Dinkley",  "gender": "female", "voice_name": "Amy",    "color": "#97233F", "energy": "analytical detective eureka"},
    "khalid": {"name": "Khalid", "title": "COO",   "character": "Dexter Morgan",  "gender": "male",   "voice_name": "Ray",    "color": "#1B1B1B", "energy": "calm intense methodical"},
    "layla":  {"name": "Layla",  "title": "CPO",   "character": "Sandy Cheeks",   "gender": "female", "voice_name": "Amy",    "color": "#D4A017", "energy": "energetic inventor"},
    "omar":   {"name": "Omar",   "title": "CRO",   "character": "Stewie Griffin",  "gender": "male",   "voice_name": "Mike",   "color": "#8B0000", "energy": "scheming ambitious mastermind"},
    "yasmin": {"name": "Yasmin", "title": "CCO",   "character": "Brian Griffin",   "gender": "female", "voice_name": "Amy",    "color": "#4B0082", "energy": "literary pretentious talented"},
    "faisal": {"name": "Faisal", "title": "CTO",   "character": "Dexter Lab",      "gender": "male",   "voice_name": "Marco",  "color": "#0047AB", "energy": "focused genius"},
    "hassan": {"name": "Hassan", "title": "VP Sales","character": "SpongeBob",      "gender": "male",   "voice_name": "Mike",   "color": "#FFD700", "energy": "maximum enthusiasm"},
    "rania":  {"name": "Rania",  "title": "VP Mktg","character": "Daria",           "gender": "female", "voice_name": "Amy",    "color": "#006B3C", "energy": "deadpan sarcastic"},
    "amira":  {"name": "Amira",  "title": "VP CS",  "character": "Dee Dee",         "gender": "female", "voice_name": "Amy",    "color": "#FF69B4", "energy": "bubbly enthusiastic"},
    "zara":   {"name": "Zara",   "title": "VP Social","character": "Rachel Green",  "gender": "female", "voice_name": "Amy",    "color": "#E91E63", "energy": "dramatic trendy storytelling"},
}


def _get_voice_id(voice_name, gender):
    """Find a HeyGen voice ID matching the name and gender."""
    key = _load_key("HEYGEN_API_KEY")
    r = requests.get("https://api.heygen.com/v2/voices", headers={"X-Api-Key": key})
    voices = r.json().get("data", {}).get("voices", [])
    # Match by name
    for v in voices:
        if v.get("name", "").lower().startswith(voice_name.lower()) and v.get("language", "").startswith("en"):
            return v["voice_id"]
    # Fallback: first English voice of matching gender
    for v in voices:
        if v.get("gender") == gender and v.get("language", "").startswith("en"):
            return v["voice_id"]
    return voices[0]["voice_id"] if voices else None


def _get_avatar_id(gender):
    """Get a suitable HeyGen stock avatar for this agent."""
    key = _load_key("HEYGEN_API_KEY")
    r = requests.get("https://api.heygen.com/v2/avatars", headers={"X-Api-Key": key})
    avatars = r.json().get("data", {}).get("avatars", [])
    # Find avatars matching gender
    matches = [a for a in avatars if a.get("gender") == gender]
    if not matches:
        matches = avatars
    # Pick one that's not premium
    for a in matches:
        if not a.get("premium"):
            return a["avatar_id"]
    return matches[0]["avatar_id"] if matches else None


# ═══════════════════════════════════════════════════════════════
# PHASE 1: CREATIVE RESEARCH
# ═══════════════════════════════════════════════════════════════

def phase_research():
    log.info("═══ PHASE 1: CREATIVE RESEARCH ═══")
    log.info("Oh my God, I need to study what's trending before I write ANYTHING. — Zara")

    ckpt = Path.home() / ".nemoclaw" / "checkpoints" / "langgraph.db"
    ckpt.unlink(missing_ok=True)

    subprocess.run([PYTHON, str(REPO / "skills/cnt-10-viral-pattern-analyzer/run.py"),
        "--force", "--input", "platform_data", "TikTok Instagram AI startup character reveals",
        "--input", "niche", "AI company with cartoon agents building to 1M ARR"],
        capture_output=True, cwd=str(REPO))

    ckpt.unlink(missing_ok=True)

    subprocess.run([PYTHON, str(REPO / "skills/cnt-01-viral-hook-generator/run.py"),
        "--force", "--input", "topic", "11 AI cartoon agents introducing themselves first time on social media",
        "--input", "platform", "tiktok"],
        capture_output=True, cwd=str(REPO))

    log.info("Research done. Strategy: Character-first, hook in 2 seconds, personality over info.")


# ═══════════════════════════════════════════════════════════════
# PHASE 2: SCRIPT GENERATION
# ═══════════════════════════════════════════════════════════════

def phase_scripts():
    log.info("═══ PHASE 2: WRITING SCRIPTS ═══")
    log.info("Every script needs to be FIRE. Character voice, viral hook, CTA. — Zara")

    SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)

    for agent_id, agent in AGENTS.items():
        log.info(f"  Writing {agent['name']}'s intro...")

        ckpt = Path.home() / ".nemoclaw" / "checkpoints" / "langgraph.db"
        ckpt.unlink(missing_ok=True)

        topic = (
            f"Write the VOICEOVER SCRIPT ONLY (no visual directions, no brackets, no stage cues) "
            f"for a 30-45 second TikTok intro video. Character: {agent['name']}, "
            f"the {agent['title']} at NemoClaw AI. Personality inspired by {agent['character']} — "
            f"{agent['energy']}. This is their FIRST public appearance. "
            f"80-120 words. Must include: attention-grabbing hook in first sentence, "
            f"who they are in character voice, what they do at NemoClaw, their main goal, "
            f"and end with Follow NemoClaw. Output ONLY the spoken words. Nothing else."
        )

        subprocess.run([PYTHON, str(REPO / "skills/cnt-02-instagram-reel-script-writer/run.py"),
            "--force", "--input", "topic", topic,
            "--input", "cta_goal", "follow NemoClaw to watch 11 AI agents build a million dollar business"],
            capture_output=True, cwd=str(REPO))

        outputs = sorted((REPO / "skills/cnt-02-instagram-reel-script-writer/outputs").glob("*.md"),
                         key=lambda p: p.stat().st_mtime, reverse=True)
        if outputs:
            import shutil
            shutil.copy2(outputs[0], SCRIPTS_DIR / f"{agent_id}_script.md")
            log.info(f"    ✓ {agent['name']}: Script saved")
        else:
            log.warning(f"    ✗ {agent['name']}: FAILED")

    count = len(list(SCRIPTS_DIR.glob("*.md")))
    log.info(f"Scripts complete: {count}/11")


def _extract_voiceover(script_path):
    """Extract JUST the spoken words from Zara's script."""
    import re
    text = script_path.read_text()
    # Remove all markdown/formatting
    text = re.sub(r'#.*?\n', '', text)
    text = re.sub(r'\*\*.*?\*\*', '', text)
    text = re.sub(r'\*.*?\*', '', text)
    text = re.sub(r'\[.*?\]', '', text)
    text = re.sub(r'---+', '', text)
    text = re.sub(r'TEXT OVERLAY:.*?\n', '', text, flags=re.IGNORECASE)
    text = re.sub(r'VISUAL:.*?\n', '', text, flags=re.IGNORECASE)
    text = re.sub(r'SOUND:.*?\n', '', text, flags=re.IGNORECASE)
    text = re.sub(r'CUT TO:.*?\n', '', text, flags=re.IGNORECASE)
    text = re.sub(r'SCENE \d.*?\n', '', text, flags=re.IGNORECASE)
    # Extract quoted speech
    quotes = re.findall(r'"([^"]{10,})"', text)
    if quotes and len(" ".join(quotes)) > 80:
        return " ".join(quotes)[:600]
    # Fallback: clean everything
    text = re.sub(r'\n+', ' ', text).strip()
    sentences = [s.strip() for s in re.split(r'[.!?]', text) if len(s.strip()) > 10]
    return '. '.join(sentences[:10])[:600]


# ═══════════════════════════════════════════════════════════════
# PHASE 3: HEYGEN VIDEO GENERATION
# ═══════════════════════════════════════════════════════════════

def phase_heygen(agent_ids=None, limit=None):
    log.info("═══ PHASE 3: HEYGEN VIDEO PRODUCTION ═══")
    log.info("Time to make my agents STARS! Each one gets their own animated video. — Zara")

    key = _load_key("HEYGEN_API_KEY")
    if not key:
        log.error("No HEYGEN_API_KEY in config/.env")
        return False

    headers = {"X-Api-Key": key, "Content-Type": "application/json"}
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Load OUR avatar and voice mapping — NOT stock
    mapping_path = REPO / "config/content-factory/heygen-avatar-ids.json"
    if mapping_path.exists():
        mapping = json.load(open(mapping_path))
        our_avatars = mapping.get("avatars", {})
        our_voices = mapping.get("voices", {})
    else:
        log.error("No avatar mapping found at config/content-factory/heygen-avatar-ids.json")
        return False

    # Fallback voice for agents without cloned voice (Khalid, Faisal, Amira)
    fallback_male_voice = None
    fallback_female_voice = None

    video_ids = {}
    agents_to_do = {k: v for k, v in AGENTS.items() if agent_ids is None or k in agent_ids}

    if limit:
        agents_to_do = dict(list(agents_to_do.items())[:limit])
        log.info(f"  Limited to {limit} videos: {list(agents_to_do.keys())}")

    for agent_id, agent in agents_to_do.items():
        script_path = SCRIPTS_DIR / f"{agent_id}_script.md"
        if not script_path.exists():
            log.warning(f"  {agent['name']}: No script, skipping")
            continue

        voiceover = _extract_voiceover(script_path)
        if len(voiceover) < 50:
            log.warning(f"  {agent['name']}: Script too short ({len(voiceover)} chars)")
            continue

        # Use OUR avatar — the one we uploaded to HeyGen
        avatar_id = our_avatars.get(agent_id)
        if not avatar_id:
            log.error(f"  {agent['name']}: No avatar ID in mapping! Upload avatar to HeyGen first.")
            continue

        # Use OUR cloned voice — fall back to HeyGen stock only if not cloned
        voice_id = our_voices.get(agent_id)
        if not voice_id:
            if not fallback_male_voice or not fallback_female_voice:
                r = requests.get("https://api.heygen.com/v2/voices", headers={"X-Api-Key": key})
                for v in r.json().get("data", {}).get("voices", []):
                    if v.get("language", "").startswith("en"):
                        if v.get("gender") == "male" and not fallback_male_voice:
                            fallback_male_voice = v["voice_id"]
                        elif v.get("gender") == "female" and not fallback_female_voice:
                            fallback_female_voice = v["voice_id"]
            voice_id = fallback_male_voice if agent["gender"] == "male" else fallback_female_voice
            log.warning(f"  {agent['name']}: Using fallback voice (clone missing in HeyGen)")

        log.info(f"  {agent['name']}: Generating video")
        log.info(f"    Avatar: OUR character {avatar_id[:16]}...")
        log.info(f"    Voice: {'OUR clone' if our_voices.get(agent_id) else 'fallback'} {voice_id[:16]}...")
        log.info(f"    Script: {voiceover[:80]}...")

        payload = {
            "title": f"NemoClaw - {agent['name']} ({agent['title']}) Intro",
            "video_inputs": [{
                "character": {
                    "type": "talking_photo",
                    "talking_photo_id": avatar_id,
                    "talking_style": "expressive",
                    "expression": "default"
                },
                "voice": {
                    "type": "text",
                    "voice_id": voice_id,
                    "input_text": voiceover,
                    "speed": 1.0
                },
                "background": {
                    "type": "color",
                    "value": agent["color"]
                }
            }],
            "dimension": {"width": 1080, "height": 1920}
        }

        r = requests.post("https://api.heygen.com/v2/video/generate",
                         headers=headers, json=payload)

        if r.status_code == 200:
            vid = r.json().get("data", {}).get("video_id")
            video_ids[agent_id] = vid
            log.info(f"    ✓ Video queued: {vid}")
        else:
            log.error(f"    ✗ FAILED: {r.status_code} — {r.text[:150]}")

    # Save video IDs for download phase
    ids_path = OUTPUT_DIR / "video_ids.json"
    json.dump(video_ids, open(ids_path, "w"), indent=2)
    log.info(f"\n  Videos queued: {len(video_ids)}/11")
    log.info(f"  Video IDs saved to: {ids_path}")
    log.info("  Run --phase download after ~2-5 minutes to fetch completed videos.")
    return True


# ═══════════════════════════════════════════════════════════════
# PHASE 4: DOWNLOAD COMPLETED VIDEOS
# ═══════════════════════════════════════════════════════════════

def phase_download():
    log.info("═══ PHASE 4: DOWNLOADING VIDEOS ═══")

    key = _load_key("HEYGEN_API_KEY")
    ids_path = OUTPUT_DIR / "video_ids.json"

    if not ids_path.exists():
        log.error("No video_ids.json found. Run --phase heygen first.")
        return False

    video_ids = json.load(open(ids_path))
    log.info(f"Checking {len(video_ids)} videos...")

    downloaded = 0
    for agent_id, vid in video_ids.items():
        r = requests.get(f"https://api.heygen.com/v1/video_status.get?video_id={vid}",
                        headers={"X-Api-Key": key})
        data = r.json().get("data", {})
        status = data.get("status", "unknown")
        url = data.get("video_url")

        if status == "completed" and url:
            log.info(f"  {agent_id}: Downloading...")
            video_data = requests.get(url).content
            output = OUTPUT_DIR / f"{agent_id}_intro.mp4"
            output.write_bytes(video_data)
            log.info(f"    ✓ Saved: {output} ({len(video_data)//1024}KB)")
            downloaded += 1
        elif status == "processing":
            log.info(f"  {agent_id}: Still processing... (try again in a minute)")
        elif status == "failed":
            log.error(f"  {agent_id}: FAILED — {data.get('error', 'unknown error')}")
        else:
            log.info(f"  {agent_id}: Status = {status}")

    log.info(f"\nDownloaded: {downloaded}/{len(video_ids)}")
    if downloaded < len(video_ids):
        log.info("Some videos still processing. Run --phase download again shortly.")
    return True


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Zara's Video Production")
    parser.add_argument("--all", action="store_true", help="Run phases 1-3")
    parser.add_argument("--phase", choices=["research", "scripts", "heygen", "download"])
    parser.add_argument("--limit", type=int, help="Limit number of videos to generate")
    parser.add_argument("--agents", nargs="+", help="Specific agent IDs to process")
    args = parser.parse_args()

    log.info("═══════════════════════════════════════════════════")
    log.info("  ZARA (social_media_lead) — Autonomous Video Production")
    log.info("  'Every agent is about to become a STAR.' — Zara")
    log.info("═══════════════════════════════════════════════════")

    if args.phase == "research" or args.all:
        phase_research()
    if args.phase == "scripts" or args.all:
        phase_scripts()
    if args.phase == "heygen" or args.all:
        phase_heygen(agent_ids=args.agents, limit=args.limit)
    if args.phase == "download":
        phase_download()

    scripts = len(list(SCRIPTS_DIR.glob("*.md"))) if SCRIPTS_DIR.exists() else 0
    videos = len(list(OUTPUT_DIR.glob("*.mp4"))) if OUTPUT_DIR.exists() else 0
    log.info(f"\n  Scripts: {scripts} | Videos: {videos}")


if __name__ == "__main__":
    main()

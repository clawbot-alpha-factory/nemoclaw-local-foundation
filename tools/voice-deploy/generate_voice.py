#!/usr/bin/env python3
"""
NemoClaw Voice Generator — Generate agent voiceovers for content production.

Uses fish-speech API (either local GPU or Vast.ai remote) to generate
voiceovers in each agent's character style.

Usage:
    # Generate a single voiceover
    python3 tools/voice-deploy/generate_voice.py \
        --agent hassan \
        --text "I'm ready! Pipeline is at 48K!" \
        --output assets/voices/content/hassan_promo_01.wav

    # Generate voiceovers for all agents (weekly self-promo batch)
    python3 tools/voice-deploy/generate_voice.py --batch weekly_promo

    # Use remote Vast.ai GPU
    python3 tools/voice-deploy/generate_voice.py \
        --agent tariq --text "System audit complete." \
        --api-url http://VAST_IP:8763
"""

import argparse
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
REFS_DIR = REPO / "assets" / "voices" / "references"
OUTPUT_DIR = REPO / "assets" / "voices" / "generated"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_API_URL = "http://127.0.0.1:8763"

# Agent personality lines for batch generation
WEEKLY_PROMO_LINES = {
    "tariq": "This week at NemoClaw, all systems are running green. Eleven agents, zero excuses. We're on track for our revenue targets and I couldn't be more... well, I made some surprisingly brilliant decisions. As usual.",
    "nadia": "Jinkies! My research this week uncovered three new market segments we weren't even looking at. The data doesn't lie — segment B has two point three X better unit economics. I've already briefed the team.",
    "khalid": "Operations report. Workflow completion: ninety-seven point three percent. I found and eliminated three bottlenecks. The system is now four seconds faster per cycle. Tonight, I optimize further.",
    "layla": "Y'all, I shipped two new API endpoints, refactored the authentication layer, and wrote a complete architecture spec. All before lunch. This system is getting stronger every week.",
    "omar": "Revenue update. Monthly recurring revenue is climbing. Three new deals in the pipeline. My pricing experiments are yielding beautiful data. World domination through monetization continues as planned.",
    "yasmin": "This week I crafted twelve pieces of content across four platforms. Brand voice consistency: ninety-four percent. Every word serves the narrative. Every narrative serves the mission.",
    "faisal": "Code deployed. Zero bugs. Build time: forty-seven seconds. I also automated three manual processes and my CI pipeline caught two potential regressions before they hit production. You're welcome.",
    "hassan": "I'm ready! I'm READY! Booked twelve meetings this week! Response rate is up twenty-three percent! The pipeline is beautiful and growing! Every lead gets my absolute best effort!",
    "rania": "Campaign performance report. Killed two underperformers. Scaled one winner to three X budget. Return on ad spend: four point two. Total leads generated: fifty-three. I don't do sentiment. I do results.",
    "amira": "Client health update! Four clients in green zone, one moved from yellow to green after my proactive outreach. Zero churn. One upsell closed. NPS score: nine point two. Everyone is happy!",
    "zara": "Oh my GOD you guys. This week's content calendar was fire. Three reels went semi-viral. Hassan's deal close got the best behind-the-scenes footage. I documented everything. The NemoClaw story continues.",
}


def generate_voice(agent_id, text, api_url=DEFAULT_API_URL, output_path=None):
    """Generate a voiceover for an agent using fish-speech API."""
    import requests

    ref_file = list(REFS_DIR.glob(f"{agent_id}/*reference*.wav"))
    if not ref_file:
        print(f"  WARNING: No reference audio for {agent_id}")
        ref_path = None
    else:
        ref_path = f"/app/references/{agent_id}_reference.wav"

    payload = {"text": text, "format": "wav"}
    if ref_path:
        payload["reference_audio"] = ref_path

    if output_path is None:
        output_path = OUTPUT_DIR / f"{agent_id}_latest.wav"

    try:
        resp = requests.post(
            f"{api_url}/v1/tts",
            json=payload,
            timeout=120,
        )
        if resp.status_code == 200 and len(resp.content) > 1000:
            Path(output_path).write_bytes(resp.content)
            print(f"  {agent_id}: OK ({len(resp.content)} bytes) -> {output_path}")
            return True
        else:
            print(f"  {agent_id}: FAIL (HTTP {resp.status_code})")
            return False
    except Exception as e:
        print(f"  {agent_id}: ERROR ({e})")
        return False


def batch_generate(batch_name, api_url=DEFAULT_API_URL):
    """Generate voiceovers for all agents in a named batch."""
    if batch_name == "weekly_promo":
        lines = WEEKLY_PROMO_LINES
    else:
        print(f"Unknown batch: {batch_name}")
        return

    print(f"Generating batch: {batch_name} ({len(lines)} agents)")
    success = 0
    for agent_id, text in lines.items():
        output = OUTPUT_DIR / f"{agent_id}_{batch_name}.wav"
        if generate_voice(agent_id, text, api_url, output):
            success += 1

    print(f"\nBatch complete: {success}/{len(lines)} generated")


def main():
    parser = argparse.ArgumentParser(description="NemoClaw Voice Generator")
    parser.add_argument("--agent", help="Agent ID (e.g., tariq, hassan)")
    parser.add_argument("--text", help="Text to speak")
    parser.add_argument("--output", help="Output WAV path")
    parser.add_argument("--batch", help="Batch name (e.g., weekly_promo)")
    parser.add_argument("--api-url", default=DEFAULT_API_URL, help="Fish-speech API URL")
    args = parser.parse_args()

    if args.batch:
        batch_generate(args.batch, args.api_url)
    elif args.agent and args.text:
        generate_voice(args.agent, args.text, args.api_url, args.output)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
NemoClaw Content Factory — End-to-End Test
Generates a single content piece through the full pipeline and verifies output.

Usage:
    python3 scripts/test-content-factory.py              # full test (uses APIs)
    python3 scripts/test-content-factory.py --free-only  # local-only, no API spend
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

ASSETS = REPO / "assets" / "content-factory"
SKILL_RUNNER = REPO / "skills" / "skill-runner.py"
VOICES_DIR = REPO / "assets" / "voices" / "generated"
TEST_DATE = date.today().isoformat()


def ensure_dirs():
    """Create workspace directories for test run."""
    for sub in ["scripts", "videos", "captions", "thumbnails", "images"]:
        (ASSETS / sub / TEST_DATE).mkdir(parents=True, exist_ok=True)
    (ASSETS / "reports").mkdir(parents=True, exist_ok=True)


def run_skill(skill_id: str, inputs: dict, label: str) -> dict:
    """Run a skill and return result dict."""
    cmd = [sys.executable, str(SKILL_RUNNER), "--skill", skill_id]
    for k, v in inputs.items():
        cmd.extend(["--input", k, str(v)])
    print(f"  [{label}] Running {skill_id}...", end=" ", flush=True)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=180, cwd=str(REPO))
        ok = r.returncode == 0
        print("OK" if ok else f"FAIL (rc={r.returncode})")
        return {"ok": ok, "stdout": r.stdout[-300:], "stderr": r.stderr[-300:]}
    except Exception as e:
        print(f"ERROR: {e}")
        return {"ok": False, "error": str(e)}


def create_test_srt(output_path: Path):
    """Write a minimal test SRT file for free-only mode."""
    srt = (
        "1\n00:00:00,000 --> 00:00:03,000\n"
        "This is a test caption for the content factory.\n\n"
        "2\n00:00:03,000 --> 00:00:06,000\n"
        "NemoClaw agents produce content autonomously.\n\n"
        "3\n00:00:06,000 --> 00:00:09,000\n"
        "End-to-end pipeline verification complete.\n"
    )
    output_path.write_text(srt)
    return output_path


def create_solid_png(output_path: Path, width: int = 1080, height: int = 1920):
    """Create a solid-color PNG for free-only mode (no API call)."""
    try:
        import struct, zlib
        # Minimal PNG: solid dark blue
        raw = b""
        for _ in range(height):
            raw += b"\x00" + (b"\x1a\x1a\x3d") * width  # filter byte + RGB
        compressed = zlib.compress(raw)

        def chunk(ctype, data):
            c = ctype + data
            return len(data).to_bytes(4, "big") + c + zlib.crc32(c).to_bytes(4, "big", signed=False if zlib.crc32(c) >= 0 else True)

        ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
        png = b"\x89PNG\r\n\x1a\n"
        png += chunk(b"IHDR", ihdr)
        png += chunk(b"IDAT", compressed)
        png += chunk(b"IEND", b"")
        output_path.write_bytes(png)
    except Exception:
        # Fallback: write a tiny placeholder
        output_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
    return output_path


def find_test_voice() -> Path | None:
    """Find an existing voice WAV for testing."""
    if VOICES_DIR.exists():
        for f in VOICES_DIR.iterdir():
            if f.suffix == ".wav" and f.stat().st_size > 1000:
                return f
    return None


def test_full_pipeline():
    """Full pipeline test using API calls."""
    results = {}
    costs = 0.0

    # Step 1: Generate a script
    r = run_skill("cnt-01-viral-hook-generator", {"topic": "ai_automation", "platform": "tiktok"}, "SCRIPT")
    results["script"] = r

    # Step 2: Check for voice file
    voice = find_test_voice()
    if voice:
        print(f"  [VOICE] Using existing: {voice.name}")
        results["voice"] = {"ok": True, "path": str(voice)}
    else:
        print("  [VOICE] No voice file found — skipping voiceover steps")
        results["voice"] = {"ok": False, "error": "no_voice_file"}

    # Step 3: Video composition (if script succeeded)
    if r["ok"]:
        r2 = run_skill("cnt-12-video-composer", {
            "script_text": "AI agents are changing everything. Here is why you need one.",
            "agent_id": "social_media_lead",
            "platform": "tiktok",
        }, "COMPOSE")
        results["compose"] = r2
    else:
        print("  [COMPOSE] Skipped — script generation failed")
        results["compose"] = {"ok": False, "error": "skipped"}

    return results


def test_free_pipeline():
    """Free-only pipeline: no API calls, uses local components only."""
    results = {}

    # Step 1: Use a hardcoded sample script
    sample_script = (
        "Hook: Did you know AI agents can create content while you sleep?\n"
        "Body: NemoClaw runs 7 autonomous agents that produce, edit, and publish content.\n"
        "CTA: Follow for more AI automation secrets."
    )
    script_path = ASSETS / "scripts" / TEST_DATE / "test-script.txt"
    script_path.write_text(sample_script)
    print(f"  [SCRIPT] Wrote sample script: {script_path.name}")
    results["script"] = {"ok": True, "path": str(script_path)}

    # Step 2: Use existing voice or skip
    voice = find_test_voice()
    if voice:
        print(f"  [VOICE] Using existing: {voice.name}")
        results["voice"] = {"ok": True, "path": str(voice)}
    else:
        print("  [VOICE] No voice file found — using silent placeholder")
        results["voice"] = {"ok": False, "note": "no_voice_available"}

    # Step 3: Create test images (solid PNGs)
    img_dir = ASSETS / "images" / TEST_DATE
    for i in range(3):
        create_solid_png(img_dir / f"test-frame-{i}.png")
    print(f"  [IMAGES] Created 3 solid PNG frames")
    results["images"] = {"ok": True, "count": 3}

    # Step 4: Create test captions (SRT)
    srt_path = ASSETS / "captions" / TEST_DATE / "test-captions.srt"
    create_test_srt(srt_path)
    print(f"  [CAPTIONS] Wrote test SRT: {srt_path.name}")
    results["captions"] = {"ok": True, "path": str(srt_path)}

    # Step 5: Attempt video composition with local-only inputs
    r = run_skill("cnt-12-video-composer", {
        "script_text": sample_script,
        "agent_id": "social_media_lead",
        "platform": "tiktok",
    }, "COMPOSE")
    results["compose"] = r

    return results


def verify_outputs(results: dict) -> bool:
    """Check that expected outputs exist."""
    passed = True
    video_dir = ASSETS / "videos" / TEST_DATE
    if video_dir.exists():
        videos = list(video_dir.glob("*.mp4"))
        if videos:
            for v in videos:
                size = v.stat().st_size
                if size > 10240:
                    print(f"  [VERIFY] Video OK: {v.name} ({size:,} bytes)")
                else:
                    print(f"  [VERIFY] Video too small: {v.name} ({size:,} bytes)")
                    passed = False
        else:
            print("  [VERIFY] No MP4 files found in video output directory")
            passed = False
    else:
        print("  [VERIFY] Video output directory does not exist")
        passed = False

    # Check at least script output exists
    script_dir = ASSETS / "scripts" / TEST_DATE
    if script_dir.exists() and any(script_dir.iterdir()):
        print(f"  [VERIFY] Script outputs present")
    else:
        print(f"  [VERIFY] No script outputs found")

    return passed


def main():
    parser = argparse.ArgumentParser(description="Content Factory E2E Test")
    parser.add_argument("--free-only", action="store_true", help="Skip API calls, use local-only components")
    args = parser.parse_args()

    print(f"Content Factory E2E Test — {TEST_DATE}")
    print(f"  Mode: {'FREE-ONLY (no API spend)' if args.free_only else 'FULL (may incur API costs)'}")

    ensure_dirs()
    start = time.time()

    if args.free_only:
        results = test_free_pipeline()
    else:
        results = test_full_pipeline()

    elapsed = time.time() - start

    # Verify
    video_ok = verify_outputs(results)

    # Report
    report = {
        "date": TEST_DATE,
        "mode": "free_only" if args.free_only else "full",
        "elapsed_seconds": round(elapsed, 1),
        "results": {k: {"ok": v.get("ok", False)} for k, v in results.items()},
        "video_verified": video_ok,
    }
    report_path = ASSETS / "reports" / f"test-{TEST_DATE}.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)

    # Summary
    ok_count = sum(1 for v in results.values() if v.get("ok"))
    total = len(results)
    status = "PASS" if ok_count == total and video_ok else "PARTIAL" if ok_count > 0 else "FAIL"

    print(f"\n  Result: {status} — {ok_count}/{total} steps OK, video={'verified' if video_ok else 'missing'}")
    print(f"  Elapsed: {elapsed:.1f}s")
    print(f"  Report: {report_path}")
    sys.exit(0 if status == "PASS" else 1)


if __name__ == "__main__":
    main()

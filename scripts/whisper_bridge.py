#!/usr/bin/env python3
"""
NemoClaw Whisper Bridge — Audio transcription via OpenAI Whisper API.
Converts audio files to text + SRT subtitles with word-level timestamps.
Cost: $0.006/minute of audio.

    python3 scripts/whisper_bridge.py --test
"""

import json, os, sys, time, hashlib, base64
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

REPO = os.path.expanduser("~/nemoclaw-local-foundation")
ENV_FILE = os.path.join(REPO, "config/.env")
LOG_DIR = Path.home() / ".nemoclaw" / "integrations"
ACTION_LOG = LOG_DIR / "whisper-actions.jsonl"
COST_PER_MINUTE = 0.006


def _load_env():
    env = {}
    if not os.path.exists(ENV_FILE):
        return env
    with open(ENV_FILE) as f:
        for line in f:
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


def _format_srt_time(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _segments_to_srt(segments):
    lines = []
    for i, seg in enumerate(segments, 1):
        start = _format_srt_time(seg["start"])
        end = _format_srt_time(seg["end"])
        lines.append(f"{i}\n{start} --> {end}\n{seg['text'].strip()}\n")
    return "\n".join(lines)


class WhisperClient:
    def __init__(self, api_key: Optional[str] = None):
        env = _load_env()
        self.api_key = api_key or env.get("OPENAI_API_KEY", "") or os.environ.get("OPENAI_API_KEY", "")
        self.client = None
        LOG_DIR.mkdir(parents=True, exist_ok=True)

    def _log(self, action, params, success, error=None):
        entry = {"timestamp": datetime.now(timezone.utc).isoformat(), "service": "whisper",
                 "action": action, "params": params, "success": success}
        if error:
            entry["error"] = str(error)[:200]
        try:
            with open(ACTION_LOG, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass

    def _get_client(self):
        if self.client is None:
            try:
                import openai
                self.client = openai.OpenAI(api_key=self.api_key)
            except ImportError:
                return None
        return self.client

    def transcribe(self, audio_path, language="en"):
        try:
            client = self._get_client()
            if client is None:
                return (False, "openai package not installed")
            if not os.path.exists(audio_path):
                return (False, f"Audio file not found: {audio_path}")
            with open(audio_path, "rb") as f:
                resp = client.audio.transcriptions.create(
                    model="whisper-1", file=f, response_format="verbose_json",
                    language=language, timestamp_granularities=["word", "segment"])
            segments = [{"start": s.start, "end": s.end, "text": s.text} for s in (resp.segments or [])]
            words = [{"word": w.word, "start": w.start, "end": w.end} for w in (resp.words or [])]
            duration = segments[-1]["end"] if segments else 0.0
            cost = (duration / 60) * COST_PER_MINUTE
            srt = _segments_to_srt(segments)
            result = {"text": resp.text, "segments": segments, "words": words,
                      "srt": srt, "duration_seconds": round(duration, 2), "cost_usd": round(cost, 4)}
            self._log("transcribe", {"audio_path": str(audio_path), "language": language}, True)
            return (True, result)
        except Exception as e:
            self._log("transcribe", {"audio_path": str(audio_path)}, False, error=e)
            return (False, str(e))

    def transcribe_to_srt(self, audio_path, output_srt_path):
        ok, result = self.transcribe(audio_path)
        if not ok:
            return (False, result)
        try:
            Path(output_srt_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_srt_path, "w") as f:
                f.write(result["srt"])
            self._log("transcribe_to_srt", {"output": str(output_srt_path)}, True)
            return (True, {"srt_path": str(output_srt_path), "duration_seconds": result["duration_seconds"],
                           "cost_usd": result["cost_usd"]})
        except Exception as e:
            self._log("transcribe_to_srt", {}, False, error=e)
            return (False, str(e))


def _run_tests():
    from unittest.mock import patch, MagicMock
    passed = total = 0

    def test(name, fn):
        nonlocal passed, total; total += 1
        try: fn(); passed += 1; print(f"  ✅ {name}")
        except Exception as e: print(f"  ❌ {name}: {e}")

    print("=" * 60); print("  Whisper Bridge Tests"); print("=" * 60)

    def t1(): c = WhisperClient(api_key="tok"); assert c.api_key == "tok"
    test("Constructor loads key", t1)

    def t2():
        assert _format_srt_time(3661.5) == "01:01:01,500"
    test("SRT time formatting", t2)

    def t3():
        segs = [{"start": 0.0, "end": 1.5, "text": "Hello"}, {"start": 1.5, "end": 3.0, "text": "World"}]
        srt = _segments_to_srt(segs); assert "1\n00:00:00,000 --> 00:00:01,500" in srt
    test("Segments to SRT", t3)

    def t4():
        c = WhisperClient(api_key="tok")
        ok, err = c.transcribe("/nonexistent/audio.wav"); assert not ok
    test("File not found", t4)

    def t5():
        c = WhisperClient(api_key="tok")
        seg = MagicMock(); seg.start = 0.0; seg.end = 2.0; seg.text = "Hello world"
        word = MagicMock(); word.word = "Hello"; word.start = 0.0; word.end = 1.0
        resp = MagicMock(); resp.text = "Hello world"; resp.segments = [seg]; resp.words = [word]
        with patch.object(c, "_get_client") as mc:
            mc.return_value.audio.transcriptions.create.return_value = resp
            with patch("builtins.open", MagicMock()):
                with patch("os.path.exists", return_value=True):
                    ok, r = c.transcribe("test.wav")
                    assert ok; assert r["text"] == "Hello world"
                    assert r["duration_seconds"] == 2.0
                    assert r["cost_usd"] == round(2.0 / 60 * 0.006, 4)
    test("Transcribe success", t5)

    def t6():
        c = WhisperClient(api_key="tok")
        c._log("test", {}, True); assert ACTION_LOG.exists()
    test("Action log", t6)

    def t7():
        cost = (120 / 60) * COST_PER_MINUTE; assert cost == 0.012
    test("Cost calculation", t7)

    print(f"\n  {'=' * 50}"); print(f"  Whisper Bridge: {'PASS' if passed == total else 'FAIL'}")
    print(f"  Passed: {passed}/{total}"); print(f"  {'=' * 50}")
    return passed == total


if __name__ == "__main__":
    import argparse
    if "--test" in sys.argv:
        sys.exit(0 if _run_tests() else 1)
    p = argparse.ArgumentParser(description="NemoClaw Whisper Bridge")
    p.add_argument("--audio", help="Path to audio file")
    p.add_argument("--output", help="Output SRT path")
    p.add_argument("--language", default="en")
    p.add_argument("--test", action="store_true")
    args = p.parse_args()
    if args.audio:
        c = WhisperClient()
        if args.output:
            ok, r = c.transcribe_to_srt(args.audio, args.output)
        else:
            ok, r = c.transcribe(args.audio, language=args.language)
        print(f"{'✅' if ok else '❌'} {json.dumps(r, indent=2) if ok else r}")
    else:
        p.print_help()

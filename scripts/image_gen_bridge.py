#!/usr/bin/env python3
"""
NemoClaw Image Generation Bridge — GPT Image 1 for content visuals.
Generates images, thumbnails, and composites with agent avatars.
Cost: $0.005/image (Mini quality).

    python3 scripts/image_gen_bridge.py --test
"""

import json, os, sys, time, hashlib, base64
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List

REPO = os.path.expanduser("~/nemoclaw-local-foundation")
ENV_FILE = os.path.join(REPO, "config/.env")
LOG_DIR = Path.home() / ".nemoclaw" / "integrations"
ACTION_LOG = LOG_DIR / "image-gen-actions.jsonl"
IMAGES_DIR = os.path.join(REPO, "assets/content-factory/images")
AVATARS_DIR = os.path.join(REPO, "assets/avatars")
COST_PER_IMAGE = 0.005
PLATFORM_SIZES = {"tiktok": (1080, 1920), "youtube": (1280, 720), "instagram": (1080, 1080),
                  "twitter": (1200, 675), "linkedin": (1200, 627)}


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


class ImageGenClient:
    def __init__(self, api_key: Optional[str] = None):
        env = _load_env()
        self.api_key = api_key or env.get("OPENAI_API_KEY", "") or os.environ.get("OPENAI_API_KEY", "")
        self.client = None
        LOG_DIR.mkdir(parents=True, exist_ok=True)

    def _log(self, action, params, success, error=None):
        entry = {"timestamp": datetime.now(timezone.utc).isoformat(), "service": "image_gen",
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

    def generate(self, prompt, size="1024x1024", quality="low"):
        try:
            client = self._get_client()
            if client is None:
                return (False, "openai package not installed")
            resp = client.images.generate(model="gpt-image-1", prompt=prompt, n=1,
                                          size=size, quality=quality)
            img_data = resp.data[0]
            date_dir = datetime.now().strftime("%Y-%m-%d")
            out_dir = os.path.join(IMAGES_DIR, date_dir)
            os.makedirs(out_dir, exist_ok=True)
            img_hash = hashlib.md5(prompt.encode()).hexdigest()[:12]
            img_path = os.path.join(out_dir, f"{img_hash}.png")
            if hasattr(img_data, "b64_json") and img_data.b64_json:
                with open(img_path, "wb") as f:
                    f.write(base64.b64decode(img_data.b64_json))
            elif hasattr(img_data, "url") and img_data.url:
                import requests
                r = requests.get(img_data.url, timeout=60)
                with open(img_path, "wb") as f:
                    f.write(r.content)
            self._log("generate", {"prompt_len": len(prompt), "size": size, "quality": quality,
                                    "cost_usd": COST_PER_IMAGE}, True)
            return (True, {"image_path": img_path, "cost_usd": COST_PER_IMAGE})
        except Exception as e:
            self._log("generate", {"prompt_len": len(prompt)}, False, error=e)
            return (False, str(e))

    def generate_thumbnail(self, title, agent_id, platform="tiktok"):
        try:
            width, height = PLATFORM_SIZES.get(platform, (1080, 1920))
            bg_prompt = (f"Vibrant professional thumbnail background for '{title}', "
                         f"modern digital style, no text, {width}x{height}")
            ok, result = self.generate(bg_prompt, size="1024x1024", quality="low")
            if not ok:
                return (False, result)
            bg_path = result["image_path"]
            try:
                from PIL import Image, ImageDraw, ImageFont
                bg = Image.open(bg_path).resize((width, height))
                avatar_path = os.path.join(AVATARS_DIR, f"{agent_id}.png")
                if os.path.exists(avatar_path):
                    avatar = Image.open(avatar_path).resize((int(width * 0.25), int(width * 0.25)))
                    margin = int(width * 0.05)
                    bg.paste(avatar, (margin, margin), avatar if avatar.mode == "RGBA" else None)
                draw = ImageDraw.Draw(bg)
                try:
                    font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", int(width * 0.06))
                except Exception:
                    font = ImageFont.load_default()
                text_y = int(height * 0.7)
                draw.text((int(width * 0.05), text_y), title, fill="white", font=font,
                          stroke_width=3, stroke_fill="black")
                date_dir = datetime.now().strftime("%Y-%m-%d")
                out_dir = os.path.join(IMAGES_DIR, date_dir)
                os.makedirs(out_dir, exist_ok=True)
                thumb_hash = hashlib.md5(f"{title}{agent_id}{platform}".encode()).hexdigest()[:12]
                thumb_path = os.path.join(out_dir, f"thumb_{thumb_hash}.png")
                bg.save(thumb_path)
                self._log("generate_thumbnail", {"title": title, "agent": agent_id,
                                                  "platform": platform}, True)
                return (True, {"thumbnail_path": thumb_path, "cost_usd": COST_PER_IMAGE})
            except ImportError:
                self._log("generate_thumbnail", {"title": title}, True)
                return (True, {"thumbnail_path": bg_path, "cost_usd": COST_PER_IMAGE,
                               "note": "Pillow not installed, returning raw background"})
        except Exception as e:
            self._log("generate_thumbnail", {"title": title}, False, error=e)
            return (False, str(e))

    def generate_batch(self, prompts):
        results = []
        for prompt in prompts:
            ok, r = self.generate(prompt)
            results.append({"prompt": prompt[:50], "success": ok, "result": r})
        total_cost = sum(COST_PER_IMAGE for r in results if r["success"])
        self._log("generate_batch", {"count": len(prompts), "cost_usd": total_cost}, True)
        return (True, {"images": results, "total_cost_usd": total_cost})


def _run_tests():
    from unittest.mock import patch, MagicMock
    passed = total = 0

    def test(name, fn):
        nonlocal passed, total; total += 1
        try: fn(); passed += 1; print(f"  ✅ {name}")
        except Exception as e: print(f"  ❌ {name}: {e}")

    print("=" * 60); print("  Image Generation Bridge Tests"); print("=" * 60)

    def t1(): c = ImageGenClient(api_key="tok"); assert c.api_key == "tok"
    test("Constructor loads key", t1)

    def t2(): assert PLATFORM_SIZES["tiktok"] == (1080, 1920)
    test("Platform sizes", t2)

    def t3():
        c = ImageGenClient(api_key="tok")
        img = MagicMock(); img.b64_json = base64.b64encode(b"\x89PNG\r\n").decode(); img.url = None
        resp = MagicMock(); resp.data = [img]
        with patch.object(c, "_get_client") as mc:
            mc.return_value.images.generate.return_value = resp
            ok, r = c.generate("test prompt")
            assert ok; assert "image_path" in r; assert r["cost_usd"] == 0.005
    test("Generate image", t3)

    def t4():
        c = ImageGenClient(api_key="tok")
        ok, r = c.generate_batch([]); assert ok; assert r["total_cost_usd"] == 0
    test("Batch empty", t4)

    def t5():
        c = ImageGenClient(api_key="tok")
        with patch.object(c, "generate", return_value=(True, {"image_path": "/tmp/bg.png", "cost_usd": 0.005})):
            with patch.dict("sys.modules", {"PIL": None, "PIL.Image": None}):
                ok, r = c.generate_thumbnail("Test Title", "hassan", "tiktok")
                assert ok
    test("Generate thumbnail (no Pillow fallback)", t5)

    def t6():
        c = ImageGenClient(api_key="tok")
        c._log("test", {}, True); assert ACTION_LOG.exists()
    test("Action log", t6)

    def t7():
        c = ImageGenClient(api_key="tok")
        with patch.object(c, "generate", side_effect=[(True, {"image_path": f"/tmp/{i}.png", "cost_usd": 0.005}) for i in range(3)]):
            ok, r = c.generate_batch(["a", "b", "c"])
            assert ok; assert r["total_cost_usd"] == 0.015
    test("Batch generate", t7)

    def t8():
        c = ImageGenClient(api_key="tok")
        with patch.object(c, "_get_client", return_value=None): ok, r = c.generate("test"); assert not ok
    test("No openai package", t8)

    print(f"\n  {'=' * 50}"); print(f"  Image Generation Bridge: {'PASS' if passed == total else 'FAIL'}")
    print(f"  Passed: {passed}/{total}"); print(f"  {'=' * 50}")
    return passed == total


if __name__ == "__main__":
    import argparse
    if "--test" in sys.argv:
        sys.exit(0 if _run_tests() else 1)
    p = argparse.ArgumentParser(description="NemoClaw Image Generation Bridge")
    p.add_argument("--prompt", help="Image generation prompt")
    p.add_argument("--output", help="Output image path")
    p.add_argument("--size", default="1024x1024")
    p.add_argument("--quality", default="low", choices=["low", "medium", "high"])
    p.add_argument("--thumbnail", action="store_true", help="Generate thumbnail")
    p.add_argument("--title", help="Thumbnail title text")
    p.add_argument("--agent", default="hassan", help="Agent ID for avatar")
    p.add_argument("--platform", default="tiktok")
    p.add_argument("--test", action="store_true")
    args = p.parse_args()
    c = ImageGenClient()
    if args.thumbnail and args.title:
        ok, r = c.generate_thumbnail(args.title, args.agent, args.platform)
        print(f"{'✅' if ok else '❌'} {json.dumps(r, indent=2) if isinstance(r, dict) else r}")
    elif args.prompt:
        ok, r = c.generate(args.prompt, size=args.size, quality=args.quality)
        if ok and args.output:
            import shutil; shutil.copy(r["image_path"], args.output); r["output"] = args.output
        print(f"{'✅' if ok else '❌'} {json.dumps(r, indent=2) if isinstance(r, dict) else r}")
    else:
        p.print_help()

#!/usr/bin/env python3
"""
NemoClaw Social Publishing Bridge — Multi-backend social media publishing.
Supports PinchTab (free, browser), Zernio API, and direct platform APIs.

    python3 scripts/social_publish_bridge.py --test
"""

import json, os, sys, time, uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List

REPO = os.path.expanduser("~/nemoclaw-local-foundation")
ENV_FILE = os.path.join(REPO, "config/.env")
ACCOUNTS_CONFIG = os.path.join(REPO, "config/content-factory/accounts-config.yaml")
LOG_DIR = Path.home() / ".nemoclaw" / "integrations"
ACTION_LOG = LOG_DIR / "social-publish-actions.jsonl"


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


class SocialPublisher:
    SUPPORTED_BACKENDS = ["pinchtab", "zernio", "youtube", "tiktok"]

    def __init__(self, backend: str = "pinchtab"):
        self.env = _load_env()
        self.backend = backend
        self.zernio_key = self.env.get("ZERNIO_API_KEY", "") or os.environ.get("ZERNIO_API_KEY", "")
        self.pinchtab_url = self.env.get("PINCHTAB_URL", "http://localhost:9867")
        self.yt_client_id = self.env.get("YOUTUBE_CLIENT_ID", "") or os.environ.get("YOUTUBE_CLIENT_ID", "")
        self.yt_client_secret = self.env.get("YOUTUBE_CLIENT_SECRET", "") or os.environ.get("YOUTUBE_CLIENT_SECRET", "")
        self.yt_api_key = self.env.get("YOUTUBE_API_KEY", "") or os.environ.get("YOUTUBE_API_KEY", "")
        self.tiktok_client_key = self.env.get("TIKTOK_CLIENT_KEY", "") or os.environ.get("TIKTOK_CLIENT_KEY", "")
        self.tiktok_client_secret = self.env.get("TIKTOK_CLIENT_SECRET", "") or os.environ.get("TIKTOK_CLIENT_SECRET", "")
        self.timeout = 30
        LOG_DIR.mkdir(parents=True, exist_ok=True)

    def _log(self, action, params, success, error=None):
        entry = {"timestamp": datetime.now(timezone.utc).isoformat(), "service": "social_publish",
                 "action": action, "params": params, "success": success, "backend": self.backend}
        if error:
            entry["error"] = str(error)[:200]
        try:
            with open(ACTION_LOG, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass

    def _post_pinchtab(self, platforms, text, media_paths=None, account_id="nemoclaw_company"):
        try:
            import requests
            payload = {"action": "social_post", "platforms": platforms, "text": text,
                       "account_id": account_id}
            if media_paths:
                payload["media_paths"] = media_paths
            r = requests.post(f"{self.pinchtab_url}/api/social/post", json=payload, timeout=self.timeout)
            if r.status_code >= 400:
                return (False, f"HTTP {r.status_code}: {r.text[:300]}")
            return (True, r.json())
        except ImportError:
            return (False, "requests package not installed")
        except Exception as e:
            return (False, str(e))

    def _post_zernio(self, platforms, text, media_paths=None, schedule_date=None):
        try:
            import requests
            payload = {"platforms": platforms, "content": text}
            if media_paths:
                payload["media"] = media_paths
            if schedule_date:
                payload["scheduled_at"] = schedule_date
            headers = {"Authorization": f"Bearer {self.zernio_key}", "Content-Type": "application/json"}
            r = requests.post("https://api.zernio.com/v1/posts", json=payload,
                              headers=headers, timeout=self.timeout)
            if r.status_code >= 400:
                return (False, f"HTTP {r.status_code}: {r.text[:300]}")
            return (True, r.json())
        except ImportError:
            return (False, "requests package not installed")
        except Exception as e:
            return (False, str(e))

    def _post_youtube(self, text, media_paths=None, title=None, privacy="private", category_id="22"):
        """Upload a video to YouTube via Data API v3 (resumable upload).
        Requires OAuth 2.0 token stored at ~/.nemoclaw/youtube_token.json.
        """
        try:
            import requests
            if not media_paths or not media_paths[0]:
                return (False, "YouTube upload requires a video file path in media_paths")
            video_path = media_paths[0]
            if not os.path.exists(video_path):
                return (False, f"Video file not found: {video_path}")
            token_path = Path.home() / ".nemoclaw" / "youtube_token.json"
            if not token_path.exists():
                return (False, "OAuth token not found at ~/.nemoclaw/youtube_token.json — run OAuth flow first")
            with open(token_path) as f:
                token_data = json.load(f)
            access_token = token_data.get("access_token", "")
            if not access_token:
                return (False, "No access_token in youtube_token.json")
            video_title = title or text[:100] or "NemoClaw Upload"
            metadata = {
                "snippet": {"title": video_title, "description": text, "categoryId": category_id},
                "status": {"privacyStatus": privacy}
            }
            headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
            init_resp = requests.post(
                "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
                json=metadata, headers=headers, timeout=self.timeout
            )
            if init_resp.status_code not in (200, 308):
                return (False, f"YouTube init upload failed: HTTP {init_resp.status_code}: {init_resp.text[:300]}")
            upload_url = init_resp.headers.get("Location")
            if not upload_url:
                return (False, "No upload URL returned from YouTube")
            with open(video_path, "rb") as vf:
                upload_resp = requests.put(
                    upload_url, data=vf,
                    headers={"Content-Type": "video/*"},
                    timeout=600
                )
            if upload_resp.status_code >= 400:
                return (False, f"YouTube upload failed: HTTP {upload_resp.status_code}: {upload_resp.text[:300]}")
            return (True, upload_resp.json())
        except ImportError:
            return (False, "requests package not installed")
        except Exception as e:
            return (False, str(e))

    def _post_tiktok(self, text, media_paths=None):
        """Post a video to TikTok via Content Posting API (direct post).
        Requires OAuth access token stored at ~/.nemoclaw/tiktok_token.json.
        """
        try:
            import requests
            if not media_paths or not media_paths[0]:
                return (False, "TikTok posting requires a video file path in media_paths")
            video_path = media_paths[0]
            if not os.path.exists(video_path):
                return (False, f"Video file not found: {video_path}")
            if not self.tiktok_client_key or self.tiktok_client_key.startswith("PENDING"):
                return (False, "TikTok client key not configured — register app at developers.tiktok.com")
            token_path = Path.home() / ".nemoclaw" / "tiktok_token.json"
            if not token_path.exists():
                return (False, "OAuth token not found at ~/.nemoclaw/tiktok_token.json — run OAuth flow first")
            with open(token_path) as f:
                token_data = json.load(f)
            access_token = token_data.get("access_token", "")
            if not access_token:
                return (False, "No access_token in tiktok_token.json")
            # Step 1: Init upload
            file_size = os.path.getsize(video_path)
            init_payload = {
                "post_info": {"title": text[:150], "privacy_level": "SELF_ONLY"},
                "source_info": {"source": "FILE_UPLOAD", "video_size": file_size, "chunk_size": file_size}
            }
            headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
            init_resp = requests.post(
                "https://open.tiktokapis.com/v2/post/publish/inbox/video/init/",
                json=init_payload, headers=headers, timeout=self.timeout
            )
            if init_resp.status_code >= 400:
                return (False, f"TikTok init failed: HTTP {init_resp.status_code}: {init_resp.text[:300]}")
            init_data = init_resp.json().get("data", {})
            upload_url = init_data.get("upload_url")
            if not upload_url:
                return (False, "No upload_url returned from TikTok init")
            # Step 2: Upload video
            with open(video_path, "rb") as vf:
                upload_headers = {
                    "Content-Type": "video/mp4",
                    "Content-Range": f"bytes 0-{file_size - 1}/{file_size}"
                }
                upload_resp = requests.put(upload_url, data=vf, headers=upload_headers, timeout=600)
            if upload_resp.status_code >= 400:
                return (False, f"TikTok upload failed: HTTP {upload_resp.status_code}: {upload_resp.text[:300]}")
            return (True, {"publish_id": init_data.get("publish_id", "unknown"), "status": "uploaded"})
        except ImportError:
            return (False, "requests package not installed")
        except Exception as e:
            return (False, str(e))

    def post(self, platforms, text, media_paths=None, schedule_date=None, account_id="nemoclaw_company"):
        if isinstance(platforms, str):
            platforms = [platforms]
        if self.backend == "pinchtab":
            ok, r = self._post_pinchtab(platforms, text, media_paths, account_id)
        elif self.backend == "zernio":
            ok, r = self._post_zernio(platforms, text, media_paths, schedule_date)
        elif self.backend == "youtube":
            ok, r = self._post_youtube(text, media_paths)
        elif self.backend == "tiktok":
            ok, r = self._post_tiktok(text, media_paths)
        else:
            ok, r = (False, f"Unknown backend: {self.backend}")
        result = {"post_id": str(uuid.uuid4())[:8], "platforms_posted": platforms,
                  "status": "posted" if ok else "failed", "urls": r if ok else []}
        self._log("post", {"platforms": platforms, "text_len": len(text)}, ok, error=r if not ok else None)
        return (ok, result)

    def upload_media(self, file_path):
        try:
            if not os.path.exists(file_path):
                return (False, f"File not found: {file_path}")
            self._log("upload_media", {"file": str(file_path)}, True)
            return (True, {"media_id": str(uuid.uuid4())[:8], "path": str(file_path)})
        except Exception as e:
            self._log("upload_media", {}, False, error=e)
            return (False, str(e))

    def get_analytics(self, platform, period="7d"):
        try:
            import requests
            if self.backend == "zernio":
                headers = {"Authorization": f"Bearer {self.zernio_key}"}
                r = requests.get(f"https://api.zernio.com/v1/analytics/{platform}",
                                 params={"period": period}, headers=headers, timeout=self.timeout)
                if r.status_code >= 400:
                    return (False, f"HTTP {r.status_code}: {r.text[:300]}")
                self._log("get_analytics", {"platform": platform, "period": period}, True)
                return (True, r.json())
            return (False, f"Analytics not supported for backend: {self.backend}")
        except ImportError:
            return (False, "requests package not installed")
        except Exception as e:
            self._log("get_analytics", {}, False, error=e)
            return (False, str(e))

    def list_accounts(self):
        try:
            if not os.path.exists(ACCOUNTS_CONFIG):
                return (False, f"Config not found: {ACCOUNTS_CONFIG}")
            try:
                import yaml
                with open(ACCOUNTS_CONFIG) as f:
                    data = yaml.safe_load(f)
                self._log("list_accounts", {}, True)
                return (True, data)
            except ImportError:
                with open(ACCOUNTS_CONFIG) as f:
                    content = f.read()
                self._log("list_accounts", {}, True)
                return (True, {"raw": content})
        except Exception as e:
            self._log("list_accounts", {}, False, error=e)
            return (False, str(e))


def _run_tests():
    from unittest.mock import patch, MagicMock
    passed = total = 0

    def test(name, fn):
        nonlocal passed, total; total += 1
        try: fn(); passed += 1; print(f"  ✅ {name}")
        except Exception as e: print(f"  ❌ {name}: {e}")

    print("=" * 60); print("  Social Publishing Bridge Tests"); print("=" * 60)

    def mr(s=200, d=None):
        r = MagicMock(); r.status_code = s; r.json.return_value = d or {}; r.text = json.dumps(d) if d else ""; return r

    def t1(): p = SocialPublisher(backend="pinchtab"); assert p.backend == "pinchtab"
    test("Constructor default backend", t1)

    def t2(): p = SocialPublisher(backend="zernio"); assert p.backend == "zernio"
    test("Constructor zernio backend", t2)

    def t3():
        p = SocialPublisher(backend="pinchtab")
        with patch("requests.post", return_value=mr(200, {"id": "p1"})): ok, r = p.post(["tiktok"], "Test post"); assert ok
    test("Post via PinchTab", t3)

    def t4():
        p = SocialPublisher(backend="zernio"); p.zernio_key = "tok"
        with patch("requests.post", return_value=mr(200, {"id": "p1"})): ok, r = p.post(["twitter"], "Test"); assert ok
    test("Post via Zernio", t4)

    def t5():
        p = SocialPublisher(); ok, r = p.post("tiktok", "Test")
        assert isinstance(r, dict); assert "platforms_posted" in r
    test("String platform auto-wrap", t5)

    def t6():
        p = SocialPublisher(); ok, r = p.upload_media("/nonexistent/file.mp4"); assert not ok
    test("Upload media file not found", t6)

    def t7():
        p = SocialPublisher(backend="unknown"); ok, r = p.post(["x"], "test"); assert not ok
    test("Unknown backend", t7)

    def t8():
        p = SocialPublisher(backend="pinchtab")
        with patch("requests.post", return_value=mr(500, {"error": "fail"})): ok, r = p.post(["ig"], "test"); assert not ok
    test("HTTP error", t8)

    def t9():
        p = SocialPublisher()
        p._log("test", {}, True); assert ACTION_LOG.exists()
    test("Action log", t9)

    def t10():
        p = SocialPublisher(); ok, r = p.list_accounts()
        # ok depends on whether config exists, just check it returns a tuple
        assert isinstance(ok, bool)
    test("List accounts returns tuple", t10)

    def t11():
        p = SocialPublisher(backend="youtube")
        ok, r = p.post(["youtube"], "Test video", media_paths=None)
        assert not ok  # No media_paths → should fail
    test("YouTube requires media_paths", t11)

    def t12():
        p = SocialPublisher(backend="youtube")
        ok, r = p.post(["youtube"], "Test video", media_paths=["/nonexistent/video.mp4"])
        assert not ok  # File not found → should fail
    test("YouTube file not found", t12)

    def t13():
        p = SocialPublisher(backend="tiktok")
        ok, r = p.post(["tiktok"], "Test video", media_paths=None)
        assert not ok  # No media_paths → should fail
    test("TikTok requires media_paths", t13)

    def t14():
        p = SocialPublisher(backend="tiktok")
        ok, r = p.post(["tiktok"], "Test video", media_paths=["/nonexistent/video.mp4"])
        assert not ok  # File not found → should fail
    test("TikTok file not found", t14)

    def t15():
        assert "youtube" in SocialPublisher.SUPPORTED_BACKENDS
        assert "tiktok" in SocialPublisher.SUPPORTED_BACKENDS
    test("Supported backends include youtube and tiktok", t15)

    print(f"\n  {'=' * 50}"); print(f"  Social Publishing Bridge: {'PASS' if passed == total else 'FAIL'}")
    print(f"  Passed: {passed}/{total}"); print(f"  {'=' * 50}")
    return passed == total


if __name__ == "__main__":
    import argparse
    if "--test" in sys.argv:
        sys.exit(0 if _run_tests() else 1)
    p = argparse.ArgumentParser(description="NemoClaw Social Publishing Bridge")
    p.add_argument("--post", action="store_true", help="Publish a post")
    p.add_argument("--platform", default="tiktok")
    p.add_argument("--text", default="")
    p.add_argument("--media", help="Media file path")
    p.add_argument("--backend", default="pinchtab", choices=["pinchtab", "zernio", "youtube", "tiktok"])
    p.add_argument("--test", action="store_true")
    args = p.parse_args()
    if args.post:
        pub = SocialPublisher(backend=args.backend)
        media = [args.media] if args.media else None
        ok, r = pub.post([args.platform], args.text, media_paths=media)
        print(f"{'✅' if ok else '❌'} {json.dumps(r, indent=2)}")
    else:
        p.print_help()

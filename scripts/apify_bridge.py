#!/usr/bin/env python3
"""
NemoClaw Apify Bridge — Social media scraping via Apify actors.

Provides unified interface to Apify's actor ecosystem for:
- TikTok profile/hashtag scraping
- Instagram profile/post/comment scraping
- LinkedIn post scraping
- Twitter/X search scraping
- Generic web scraping

All agents have full access (autonomy mode 2026-04-02).

Usage:
    from scripts.apify_bridge import ApifyBridge
    bridge = ApifyBridge()
    results = bridge.scrape_tiktok_profile("@username", max_posts=50)
    comments = bridge.scrape_comments("https://tiktok.com/...", max_comments=200)
"""

import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Optional

# Resolve config
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

logger = logging.getLogger("nemoclaw.apify")

# Pre-configured Apify actor IDs (community + official)
ACTORS = {
    "tiktok_scraper": "clockworks/free-tiktok-scraper",
    "tiktok_comments": "clockworks/tiktok-comments-scraper",
    "tiktok_hashtag": "clockworks/tiktok-hashtag-scraper",
    "instagram_scraper": "apify/instagram-scraper",
    "instagram_comments": "apify/instagram-comment-scraper",
    "instagram_hashtag": "apify/instagram-hashtag-scraper",
    "linkedin_scraper": "anchor/linkedin-post-scraper",
    "twitter_scraper": "quacker/twitter-scraper",
    "web_scraper": "apify/web-scraper",
}


class ApifyBridge:
    """Unified Apify scraping interface for NemoClaw agents."""

    def __init__(self, api_token: Optional[str] = None):
        self.api_token = api_token or self._load_token()
        self.base_url = "https://api.apify.com/v2"
        self._session = None

    def _load_token(self) -> str:
        """Load Apify API token from config/.env or environment."""
        # Check environment first
        token = os.environ.get("APIFY_API_TOKEN", "")
        if token:
            return token

        # Load from config/.env
        env_file = REPO / "config" / ".env"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                if line.startswith("APIFY_API_TOKEN="):
                    return line.split("=", 1)[1].strip()
        return ""

    @property
    def is_available(self) -> bool:
        return bool(self.api_token)

    def _get_session(self):
        if self._session is None:
            import httpx
            self._session = httpx.Client(
                base_url=self.base_url,
                headers={"Authorization": f"Bearer {self.api_token}"},
                timeout=60.0,
            )
        return self._session

    def _run_actor(self, actor_id: str, input_data: dict, timeout_secs: int = 300) -> list:
        """Run an Apify actor and wait for results."""
        if not self.is_available:
            logger.warning("Apify token not configured — cannot run actors")
            return []

        client = self._get_session()

        # Start actor run
        try:
            resp = client.post(
                f"/acts/{actor_id}/runs",
                json=input_data,
                params={"waitForFinish": min(timeout_secs, 300)},
            )
            resp.raise_for_status()
            run_data = resp.json().get("data", {})
            run_id = run_data.get("id")
            status = run_data.get("status")

            if not run_id:
                logger.error(f"Apify actor {actor_id} failed to start")
                return []

            # If not finished yet, poll
            if status not in ("SUCCEEDED", "FAILED", "ABORTED"):
                run_data = self._poll_run(run_id, timeout_secs)
                status = run_data.get("status")

            if status != "SUCCEEDED":
                logger.warning(f"Apify run {run_id} ended with status: {status}")
                return []

            # Get dataset items
            dataset_id = run_data.get("defaultDatasetId")
            if not dataset_id:
                return []

            items_resp = client.get(f"/datasets/{dataset_id}/items")
            items_resp.raise_for_status()
            return items_resp.json()

        except Exception as e:
            logger.error(f"Apify actor {actor_id} error: {e}")
            return []

    def _poll_run(self, run_id: str, timeout_secs: int) -> dict:
        """Poll a run until completion."""
        client = self._get_session()
        deadline = time.time() + timeout_secs
        while time.time() < deadline:
            try:
                resp = client.get(f"/actor-runs/{run_id}")
                resp.raise_for_status()
                data = resp.json().get("data", {})
                if data.get("status") in ("SUCCEEDED", "FAILED", "ABORTED"):
                    return data
            except Exception:
                pass
            time.sleep(5)
        return {"status": "TIMEOUT"}

    # ── High-level scraping methods ──────────────────────────────────

    def scrape_tiktok_profile(self, username: str, max_posts: int = 50) -> list:
        """Scrape TikTok profile posts."""
        return self._run_actor(ACTORS["tiktok_scraper"], {
            "profiles": [username.lstrip("@")],
            "resultsPerPage": max_posts,
            "shouldDownloadVideos": False,
        })

    def scrape_tiktok_hashtag(self, hashtag: str, max_posts: int = 100) -> list:
        """Scrape TikTok posts by hashtag."""
        return self._run_actor(ACTORS["tiktok_hashtag"], {
            "hashtags": [hashtag.lstrip("#")],
            "resultsPerPage": max_posts,
        })

    def scrape_tiktok_comments(self, video_url: str, max_comments: int = 200) -> list:
        """Scrape comments from a TikTok video."""
        return self._run_actor(ACTORS["tiktok_comments"], {
            "postURLs": [video_url],
            "maxComments": max_comments,
        })

    def scrape_instagram_profile(self, username: str, max_posts: int = 50) -> list:
        """Scrape Instagram profile posts."""
        return self._run_actor(ACTORS["instagram_scraper"], {
            "directUrls": [f"https://www.instagram.com/{username.lstrip('@')}/"],
            "resultsLimit": max_posts,
            "resultsType": "posts",
        })

    def scrape_instagram_comments(self, post_url: str, max_comments: int = 200) -> list:
        """Scrape comments from an Instagram post."""
        return self._run_actor(ACTORS["instagram_comments"], {
            "directUrls": [post_url],
            "resultsLimit": max_comments,
        })

    def scrape_instagram_hashtag(self, hashtag: str, max_posts: int = 100) -> list:
        """Scrape Instagram posts by hashtag."""
        return self._run_actor(ACTORS["instagram_hashtag"], {
            "hashtags": [hashtag.lstrip("#")],
            "resultsLimit": max_posts,
        })

    def scrape_linkedin_posts(self, profile_url: str, max_posts: int = 30) -> list:
        """Scrape LinkedIn profile posts."""
        return self._run_actor(ACTORS["linkedin_scraper"], {
            "profileUrls": [profile_url],
            "maxPosts": max_posts,
        })

    def scrape_twitter_search(self, query: str, max_tweets: int = 100) -> list:
        """Scrape tweets matching a search query."""
        return self._run_actor(ACTORS["twitter_scraper"], {
            "searchTerms": [query],
            "maxTweets": max_tweets,
        })

    def scrape_comments(self, url: str, max_comments: int = 200) -> list:
        """Auto-detect platform and scrape comments."""
        if "tiktok.com" in url:
            return self.scrape_tiktok_comments(url, max_comments)
        elif "instagram.com" in url:
            return self.scrape_instagram_comments(url, max_comments)
        else:
            logger.warning(f"Unsupported platform for comment scraping: {url}")
            return []

    def scrape_web(self, urls: list, max_pages: int = 10) -> list:
        """Generic web scraping."""
        return self._run_actor(ACTORS["web_scraper"], {
            "startUrls": [{"url": u} for u in urls],
            "maxPagesPerCrawl": max_pages,
        })

    # ── Analytics helpers ────────────────────────────────────────────

    def analyze_comments(self, comments: list) -> dict:
        """Basic comment analytics — sentiment distribution, top themes, engagement."""
        if not comments:
            return {"total": 0, "themes": [], "avg_likes": 0}

        total = len(comments)
        likes = [c.get("likes", c.get("diggCount", 0)) or 0 for c in comments]
        avg_likes = sum(likes) / total if total else 0

        # Extract text
        texts = [c.get("text", c.get("comment", "")) for c in comments]
        word_freq = {}
        for text in texts:
            for word in text.lower().split():
                if len(word) > 4:
                    word_freq[word] = word_freq.get(word, 0) + 1

        top_words = sorted(word_freq.items(), key=lambda x: -x[1])[:20]

        return {
            "total": total,
            "avg_likes": round(avg_likes, 1),
            "top_words": top_words,
            "sample_comments": texts[:10],
        }

    def health_check(self) -> dict:
        """Check Apify API connectivity."""
        if not self.is_available:
            return {"status": "unavailable", "reason": "No APIFY_API_TOKEN"}
        try:
            client = self._get_session()
            resp = client.get("/users/me")
            resp.raise_for_status()
            user = resp.json().get("data", {})
            return {
                "status": "healthy",
                "username": user.get("username"),
                "plan": user.get("plan", {}).get("id"),
                "usage_usd": user.get("plan", {}).get("monthlyUsageUsd"),
            }
        except Exception as e:
            return {"status": "error", "reason": str(e)}


# ── CLI for testing ──────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Apify Bridge CLI")
    parser.add_argument("--test", action="store_true", help="Run health check")
    parser.add_argument("--tiktok", help="Scrape TikTok profile")
    parser.add_argument("--instagram", help="Scrape Instagram profile")
    parser.add_argument("--comments", help="Scrape comments from URL")
    parser.add_argument("--max", type=int, default=20, help="Max results")
    args = parser.parse_args()

    bridge = ApifyBridge()

    if args.test:
        result = bridge.health_check()
        print(json.dumps(result, indent=2))
    elif args.tiktok:
        results = bridge.scrape_tiktok_profile(args.tiktok, args.max)
        print(f"Got {len(results)} posts")
        print(json.dumps(results[:3], indent=2, default=str))
    elif args.instagram:
        results = bridge.scrape_instagram_profile(args.instagram, args.max)
        print(f"Got {len(results)} posts")
        print(json.dumps(results[:3], indent=2, default=str))
    elif args.comments:
        results = bridge.scrape_comments(args.comments, args.max)
        analytics = bridge.analyze_comments(results)
        print(json.dumps(analytics, indent=2, default=str))
    else:
        parser.print_help()

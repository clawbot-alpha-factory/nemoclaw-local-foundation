#!/usr/bin/env python3
"""
NemoClaw Content Analytics Collector — Pull engagement data nightly.
Collects performance metrics from published content and feeds insights
into the next day's strategy phase.

Usage:
    python3 scripts/content_analytics_collector.py --date today
    python3 scripts/content_analytics_collector.py --date 2026-04-02
    python3 scripts/content_analytics_collector.py --test
"""

import argparse
import json
import os
import sys
import time
from datetime import date, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

ASSETS = REPO / "assets" / "content-factory"
ANALYTICS_DIR = ASSETS / "analytics"
REPORTS_DIR = ASSETS / "reports"


def resolve_date(date_str: str) -> str:
    if date_str == "today":
        return date.today().isoformat()
    datetime.strptime(date_str, "%Y-%m-%d")
    return date_str


def load_published_content(run_date: str) -> list:
    """Load today's published content records from reports."""
    report_path = REPORTS_DIR / f"{run_date}.json"
    if report_path.exists():
        with open(report_path) as f:
            report = json.load(f)
        return report.get("phases", {}).get("publish", [])
    return []


def collect_platform_metrics(run_date: str) -> dict:
    """Collect engagement metrics from each platform.

    In production this calls social_publish_bridge APIs.
    Currently returns structure with placeholder data that the
    strategy phase can consume.
    """
    platforms = ["instagram", "tiktok", "youtube", "linkedin", "x",
                 "facebook", "threads", "pinterest", "snapchat",
                 "reddit", "medium", "substack"]
    metrics = {}
    for platform in platforms:
        # Check for existing analytics data from bridge
        bridge_file = ANALYTICS_DIR / f"{platform}-{run_date}.json"
        if bridge_file.exists():
            with open(bridge_file) as f:
                metrics[platform] = json.load(f)
        else:
            metrics[platform] = {
                "platform": platform,
                "date": run_date,
                "posts_published": 0,
                "impressions": 0,
                "engagements": 0,
                "engagement_rate": 0.0,
                "followers_gained": 0,
                "top_post": None,
                "source": "no_data",
            }
    return metrics


def calculate_insights(metrics: dict, run_date: str) -> dict:
    """Derive actionable insights from collected metrics."""
    # Top performing platform by engagement rate
    active = {k: v for k, v in metrics.items() if v.get("engagements", 0) > 0}

    top_platform = None
    best_engagement = 0.0
    for name, data in active.items():
        rate = data.get("engagement_rate", 0.0)
        if rate > best_engagement:
            best_engagement = rate
            top_platform = name

    # Best posting time (from top posts)
    best_times = []
    for data in active.values():
        top = data.get("top_post")
        if top and "posted_at" in top:
            best_times.append(top["posted_at"])

    # Total engagement across all platforms
    total_impressions = sum(v.get("impressions", 0) for v in metrics.values())
    total_engagements = sum(v.get("engagements", 0) for v in metrics.values())
    total_followers = sum(v.get("followers_gained", 0) for v in metrics.values())
    overall_rate = (total_engagements / total_impressions * 100) if total_impressions > 0 else 0.0

    return {
        "date": run_date,
        "top_platform": top_platform,
        "best_engagement_rate": best_engagement,
        "best_posting_times": best_times[:5],
        "total_impressions": total_impressions,
        "total_engagements": total_engagements,
        "total_followers_gained": total_followers,
        "overall_engagement_rate": round(overall_rate, 2),
        "active_platforms": len(active),
        "trends": {
            "growing": [k for k, v in active.items() if v.get("followers_gained", 0) > 0],
            "declining": [],  # Would compare with previous day
        },
        "recommendations": [],
    }


def write_analytics(run_date: str, metrics: dict, insights: dict):
    """Write analytics output for strategy phase consumption."""
    ANALYTICS_DIR.mkdir(parents=True, exist_ok=True)

    output = {
        "date": run_date,
        "collected_at": datetime.now().isoformat(),
        "platform_metrics": metrics,
        "insights": insights,
    }
    output_path = ANALYTICS_DIR / f"{run_date}.json"
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)
    return output_path


def run_test():
    """Test mode: verify collection pipeline with synthetic data."""
    print("[TEST] Running analytics collector test...")
    run_date = date.today().isoformat()

    metrics = collect_platform_metrics(run_date)
    insights = calculate_insights(metrics, run_date)
    path = write_analytics(run_date, metrics, insights)

    if path.exists() and path.stat().st_size > 100:
        print(f"  [PASS] Analytics written: {path} ({path.stat().st_size:,} bytes)")
        return 0
    else:
        print("  [FAIL] Analytics file not written or empty")
        return 1


def main():
    parser = argparse.ArgumentParser(description="Content Analytics Collector")
    parser.add_argument("--date", default="today", help="Collection date (YYYY-MM-DD or 'today')")
    parser.add_argument("--test", action="store_true", help="Run test mode")
    args = parser.parse_args()

    if args.test:
        sys.exit(run_test())

    run_date = resolve_date(args.date)
    print(f"Content Analytics Collector — {run_date}")

    start = time.time()

    # Collect metrics
    print("  Collecting platform metrics...")
    metrics = collect_platform_metrics(run_date)
    active = sum(1 for v in metrics.values() if v.get("source") != "no_data")
    print(f"  Collected from {active}/{len(metrics)} platforms")

    # Calculate insights
    print("  Calculating insights...")
    insights = calculate_insights(metrics, run_date)

    # Write output
    path = write_analytics(run_date, metrics, insights)
    elapsed = time.time() - start

    print(f"\n  Analytics written: {path}")
    print(f"  Top platform: {insights['top_platform'] or 'N/A'}")
    print(f"  Overall engagement: {insights['overall_engagement_rate']}%")
    print(f"  Elapsed: {elapsed:.1f}s")


if __name__ == "__main__":
    main()

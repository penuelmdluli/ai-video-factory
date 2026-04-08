"""
Genesis Content Engine — Main Runner

Orchestrates the full daily pipeline:
  1. Fetch trends (4 brands)
  2. Generate scripts (Claude API)
  3. Generate videos (Genesis Studio API)
  4. Apply watermarks (FFmpeg)
  5. Post to Facebook
  6. Post to TikTok
  7. Post to YouTube
  8. Pull analytics

Usage:
    python -m genesis.run                    # Full pipeline
    python -m genesis.run --phase trends     # Just fetch trends
    python -m genesis.run --phase scripts    # Just generate scripts
    python -m genesis.run --phase videos     # Just generate videos
    python -m genesis.run --phase watermark  # Just watermark
    python -m genesis.run --phase post       # Just post (all platforms)
    python -m genesis.run --phase analytics  # Just pull analytics
    python -m genesis.run --status           # Show today's pipeline status
"""
import asyncio
import argparse
import sys
import time
from datetime import datetime

from genesis.genesis_config import BRANDS
from genesis.db import (
    get_today_trends, get_today_videos, get_today_pipeline_log,
    get_unposted_videos, get_top_trend, log_pipeline,
)


async def run_trends():
    """Phase 1: Fetch trends."""
    from genesis.trend_fetcher import fetch_all_trends
    return await fetch_all_trends()


def run_scripts(trends: dict = None):
    """Phase 2: Generate scripts."""
    from genesis.script_generator import generate_all_scripts

    if not trends:
        # Load from DB
        trends = {}
        for brand in BRANDS:
            trend = get_top_trend(brand)
            if trend:
                trends[brand] = trend

    return generate_all_scripts(trends)


async def run_videos(scripts: dict = None):
    """Phase 3: Generate videos."""
    from genesis.video_generator import generate_all_videos
    from genesis.db import get_latest_script

    if not scripts:
        # Load latest scripts from DB
        scripts = {}
        for brand in BRANDS:
            script = get_latest_script(brand)
            if script:
                scripts[brand] = script
        if not scripts:
            print("  No scripts found in DB. Run scripts phase first.")
            return {}

    return await generate_all_videos(scripts)


def run_watermark(videos: dict = None):
    """Phase 4: Apply watermarks."""
    from genesis.watermark import apply_all_watermarks
    from genesis.db import get_videos_by_status

    if not videos:
        # Load raw-ready videos from DB
        raw_videos = get_videos_by_status("raw_ready")
        if not raw_videos:
            print("  ℹ️  No videos ready for watermarking")
            return {}
        videos = {}
        for v in raw_videos:
            if v["brand"] not in videos:
                videos[v["brand"]] = {
                    "video_id": v["id"],
                    "video_path": v["raw_video_path"],
                    "branded_path": None,
                    "script_data": {},
                }

    return apply_all_watermarks(videos)


async def run_post(branded_videos: dict = None):
    """Phase 5-7: Post to all platforms."""
    from genesis.poster_facebook import post_to_facebook
    from genesis.poster_tiktok import post_to_tiktok
    from genesis.poster_youtube import post_to_youtube
    from genesis.db import get_unposted_videos as get_unposted

    if not branded_videos:
        # Load from DB
        unposted = get_unposted()
        if not unposted:
            print("  ℹ️  No branded videos ready for posting")
            return {}
        branded_videos = {}
        for v in unposted:
            if v["brand"] not in branded_videos:
                branded_videos[v["brand"]] = {
                    "video_id": v["id"],
                    "video_path": v.get("raw_video_path", ""),
                    "branded_path": v.get("branded_video_path", ""),
                    "script_data": {
                        "hook_line": v.get("hook_line", ""),
                        "caption": v.get("caption", ""),
                        "script": v.get("script", ""),
                    },
                }

    print("\n📤 PHASE 5-7: Posting to All Platforms...")

    results = {}
    for brand, video_data in branded_videos.items():
        if not video_data:
            continue

        brand_name = BRANDS[brand]["name"]
        print(f"\n  🔹 {brand_name}:")

        brand_results = {}

        # Facebook
        fb = await post_to_facebook(brand, video_data)
        if fb:
            brand_results["facebook"] = fb
            print(f"    ✅ Facebook: Posted")
        else:
            print(f"    ❌ Facebook: Failed")

        # TikTok
        tt = await post_to_tiktok(brand, video_data)
        if tt:
            brand_results["tiktok"] = tt
            print(f"    ✅ TikTok: Posted")
        else:
            print(f"    ❌ TikTok: Failed")

        # YouTube
        yt = post_to_youtube(brand, video_data)
        if yt:
            brand_results["youtube"] = yt
            print(f"    ✅ YouTube: {yt.get('url', 'Posted')}")
        else:
            print(f"    ❌ YouTube: Failed")

        results[brand] = brand_results

    return results


async def run_analytics():
    """Phase 8: Pull analytics."""
    from genesis.analytics import pull_all_analytics
    await pull_all_analytics()


def show_status():
    """Show today's pipeline status."""
    print("\n" + "=" * 60)
    print("  GENESIS CONTENT ENGINE — Pipeline Status")
    print(f"  Date: {datetime.now().strftime('%Y-%m-%d %H:%M SAST')}")
    print("=" * 60)

    # Trends
    trends = get_today_trends()
    print(f"\n🔍 Trends: {len(trends)} fetched")
    for t in trends[:8]:
        used = "✅" if t["used"] else "⬜"
        print(f"  {used} [{t['brand']}] {t['headline'][:60]} (score: {t['score']:.1f})")

    # Videos
    videos = get_today_videos()
    print(f"\n🎬 Videos: {len(videos)} generated")
    for v in videos:
        status_icon = {"pending": "⏳", "generating": "🔄", "raw_ready": "📦", "branded": "✅", "failed": "❌"}.get(v["status"], "❓")
        print(f"  {status_icon} [{v['brand']}] {v['status']} — {(v.get('hook_line') or '')[:50]}")

    # Pipeline log
    log = get_today_pipeline_log()
    print(f"\n📋 Pipeline Log: {len(log)} entries")
    for entry in log[-15:]:
        icon = "✅" if entry["status"] == "success" else "❌"
        dur = f" ({entry['duration_seconds']:.1f}s)" if entry["duration_seconds"] else ""
        print(f"  {icon} [{entry['phase']}] {entry.get('brand', 'all')}: {entry['message'][:60]}{dur}")

    print("\n" + "=" * 60)


async def run_full_pipeline():
    """Run the complete pipeline end-to-end."""
    print("\n" + "=" * 60)
    print("  ⚡ GENESIS CONTENT ENGINE — Full Pipeline")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S SAST')}")
    print("=" * 60)

    overall_start = time.time()

    # Phase 1: Trends
    trends = await run_trends()

    # Phase 2: Scripts
    scripts = run_scripts(trends)

    # Phase 3: Videos
    videos = await run_videos(scripts)

    # Phase 4: Watermark
    branded = run_watermark(videos)

    # Phase 5-7: Post
    posts = await run_post(branded)

    # Summary
    total_time = time.time() - overall_start

    print("\n" + "=" * 60)
    print("  ⚡ PIPELINE COMPLETE")
    print(f"  Duration: {total_time:.0f}s ({total_time/60:.1f} min)")
    print(f"  Trends: {sum(1 for v in trends.values() if v)}/4")
    print(f"  Scripts: {sum(1 for v in scripts.values() if v)}/4")
    print(f"  Videos: {sum(1 for v in videos.values() if v)}/4")
    print(f"  Branded: {sum(1 for v in branded.values() if v)}/4")

    posted_count = sum(
        sum(1 for p in brand_posts.values() if p)
        for brand_posts in posts.values()
    ) if posts else 0
    print(f"  Posts: {posted_count} across all platforms")
    print("=" * 60)

    log_pipeline("full_pipeline", "all", "success",
                 f"Complete: {posted_count} posts in {total_time:.0f}s", total_time)


def main():
    parser = argparse.ArgumentParser(description="Genesis Content Engine")
    parser.add_argument("--phase", choices=["trends", "scripts", "videos", "watermark", "post", "analytics"],
                        help="Run a specific phase only")
    parser.add_argument("--status", action="store_true", help="Show pipeline status")
    parser.add_argument("--brand", choices=list(BRANDS.keys()), help="Run for a specific brand only")

    args = parser.parse_args()

    if args.status:
        show_status()
        return

    if args.phase:
        if args.phase == "trends":
            asyncio.run(run_trends())
        elif args.phase == "scripts":
            run_scripts()
        elif args.phase == "videos":
            asyncio.run(run_videos())
        elif args.phase == "watermark":
            run_watermark()
        elif args.phase == "post":
            asyncio.run(run_post())
        elif args.phase == "analytics":
            asyncio.run(run_analytics())
    else:
        asyncio.run(run_full_pipeline())


if __name__ == "__main__":
    main()

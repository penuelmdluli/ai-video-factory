"""
Genesis Content Engine — Two-Batch Daily Scheduler

Runs the content pipeline twice daily:
  MORNING BATCH (9 AM SAST post time):
    07:00 — Fetch trends + generate scripts
    07:15 — Generate Brain Studio videos
    07:45 — Apply watermarks
    09:00 — Post all 4 brands to Facebook

  EVENING BATCH (6 PM SAST post time):
    14:00 — Fetch trends + generate scripts
    14:15 — Generate Brain Studio videos
    14:45 — Apply watermarks
    18:00 — Post all 4 brands to Facebook

  ANALYTICS:
    00:00 — Pull daily performance metrics

Total: 8 posts/day (2 per brand across 4 brands)
"""
import asyncio
import time
import sys
from datetime import datetime

from genesis.genesis_config import BRANDS, SCHEDULE
from genesis.db import log_pipeline


def _parse_cron(cron_str: str) -> tuple:
    """Parse simple 'minute hour * * *' cron to (hour, minute)."""
    parts = cron_str.strip().split()
    return int(parts[1]), int(parts[0])


async def run_batch(batch_name: str):
    """Run a full batch: trends → scripts → videos → watermark."""
    print(f"\n{'='*60}")
    print(f"  GENESIS CONTENT ENGINE — {batch_name.upper()} BATCH")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S SAST')}")
    print(f"{'='*60}")

    batch_start = time.time()

    try:
        # Phase 1: Trends
        print(f"\n--- {batch_name.upper()} PHASE 1: TRENDS ---")
        from genesis.trend_fetcher import fetch_all_trends
        trends = await fetch_all_trends()
        print(f"Trends: {len(trends)}/4")

        # Phase 2: Scripts
        print(f"\n--- {batch_name.upper()} PHASE 2: SCRIPTS ---")
        from genesis.script_generator import generate_all_scripts
        scripts = generate_all_scripts(trends)
        print(f"Scripts: {len(scripts)}/4")

        # Phase 3: Videos
        print(f"\n--- {batch_name.upper()} PHASE 3: VIDEOS ---")
        from genesis.video_generator import generate_all_videos
        videos = await generate_all_videos(scripts)
        video_count = sum(1 for v in videos.values() if v)
        print(f"Videos: {video_count}/4")

        # Phase 4: Watermark
        print(f"\n--- {batch_name.upper()} PHASE 4: WATERMARK ---")
        from genesis.watermark import apply_all_watermarks
        branded = apply_all_watermarks(videos)
        branded_count = sum(1 for v in branded.values() if v)
        print(f"Branded: {branded_count}/4")

        duration = time.time() - batch_start
        log_pipeline(f"{batch_name}_batch", "all", "success",
                     f"Batch complete: {video_count} videos, {branded_count} branded in {duration:.0f}s", duration)

        print(f"\n{batch_name.upper()} BATCH COMPLETE — {branded_count}/4 videos ready for posting")

    except Exception as e:
        duration = time.time() - batch_start
        log_pipeline(f"{batch_name}_batch", "all", "failed", str(e), duration)
        print(f"\n{batch_name.upper()} BATCH FAILED: {e}")


async def run_post_all():
    """Post all branded videos ready in the DB to Facebook."""
    print(f"\n--- POSTING ALL BRANDS ---")
    from genesis.poster_facebook import post_to_facebook
    from genesis.db import get_unposted_videos

    unposted = get_unposted_videos()
    if not unposted:
        print("  No branded videos ready for posting")
        return

    posted = 0
    for v in unposted:
        brand = v["brand"]
        video_data = {
            "video_id": v["id"],
            "video_path": v.get("raw_video_path", ""),
            "branded_path": v.get("branded_video_path", ""),
            "script_data": {
                "hook_line": v.get("hook_line", ""),
                "caption": v.get("caption", ""),
            },
        }

        if not video_data["branded_path"]:
            print(f"  SKIP {BRANDS.get(brand, {}).get('name', brand)}: No branded video")
            continue

        result = await post_to_facebook(brand, video_data)
        if result:
            posted += 1
            print(f"  OK {BRANDS[brand]['name']}: FB post {result['platform_post_id']}")
        else:
            print(f"  FAIL {BRANDS[brand]['name']}")

    print(f"  Posted: {posted} videos to Facebook")
    log_pipeline("post_all", "all", "success", f"Posted {posted} videos")


async def run_analytics():
    """Pull analytics for all posted content."""
    print(f"\n--- ANALYTICS ---")
    from genesis.analytics import pull_all_analytics
    await pull_all_analytics()


def run_scheduler():
    """Simple sleep-loop scheduler. Checks every 60 seconds."""
    print("\n" + "=" * 60)
    print("  GENESIS CONTENT ENGINE — Scheduler Started")
    print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S SAST')}")
    print("=" * 60)
    print("\n  Schedule (SAST):")
    print("  MORNING:")
    print("    07:00 — Fetch trends + scripts")
    print("    07:15 — Generate Brain Studio videos")
    print("    07:45 — Apply watermarks")
    print("    09:00 — Post all 4 brands")
    print("  EVENING:")
    print("    14:00 — Fetch trends + scripts")
    print("    14:15 — Generate Brain Studio videos")
    print("    14:45 — Apply watermarks")
    print("    18:00 — Post all 4 brands")
    print("  ANALYTICS:")
    print("    00:00 — Pull daily metrics")
    print("\n  Total: 8 posts/day (2 per brand)")
    print("\nWaiting for next scheduled task...\n")

    executed_today = set()

    while True:
        now = datetime.utcnow()
        today_key = now.strftime("%Y-%m-%d")
        current_hm = now.strftime("%H:%M")

        for task_name, cron_str in SCHEDULE.items():
            hour, minute = _parse_cron(cron_str)
            task_hm = f"{hour:02d}:{minute:02d}"
            task_key = f"{today_key}_{task_name}"

            if current_hm == task_hm and task_key not in executed_today:
                executed_today.add(task_key)

                try:
                    if task_name in ("morning_trends", "evening_trends"):
                        # Trends + scripts phase
                        batch = "morning" if "morning" in task_name else "evening"
                        print(f"\n[{datetime.now().strftime('%H:%M')}] {batch.upper()} — Fetching trends + scripts...")
                        from genesis.trend_fetcher import fetch_all_trends
                        from genesis.script_generator import generate_all_scripts
                        trends = asyncio.run(fetch_all_trends())
                        generate_all_scripts(trends)

                    elif task_name in ("morning_videos", "evening_videos"):
                        # Video generation phase
                        batch = "morning" if "morning" in task_name else "evening"
                        print(f"\n[{datetime.now().strftime('%H:%M')}] {batch.upper()} — Generating Brain Studio videos...")
                        from genesis.video_generator import generate_all_videos
                        from genesis.db import get_latest_script
                        scripts = {}
                        for brand in BRANDS:
                            script = get_latest_script(brand)
                            if script:
                                scripts[brand] = script
                        asyncio.run(generate_all_videos(scripts))

                    elif task_name in ("morning_watermark", "evening_watermark"):
                        # Watermark phase
                        batch = "morning" if "morning" in task_name else "evening"
                        print(f"\n[{datetime.now().strftime('%H:%M')}] {batch.upper()} — Applying watermarks...")
                        from genesis.watermark import apply_all_watermarks
                        from genesis.db import get_videos_by_status
                        raw_videos = get_videos_by_status("raw_ready")
                        if raw_videos:
                            videos = {}
                            for v in raw_videos:
                                if v["brand"] not in videos:
                                    videos[v["brand"]] = {
                                        "video_id": v["id"],
                                        "video_path": v["raw_video_path"],
                                    }
                            apply_all_watermarks(videos)
                        else:
                            print("  No videos ready for watermarking")

                    elif task_name in ("morning_post", "evening_post"):
                        # Post all brands
                        batch = "morning" if "morning" in task_name else "evening"
                        print(f"\n[{datetime.now().strftime('%H:%M')}] {batch.upper()} — Posting to Facebook...")
                        asyncio.run(run_post_all())

                    elif task_name == "analytics":
                        print(f"\n[{datetime.now().strftime('%H:%M')}] Pulling analytics...")
                        asyncio.run(run_analytics())

                except Exception as e:
                    print(f"  Scheduler error ({task_name}): {e}")
                    log_pipeline("scheduler", "all", "failed", f"{task_name}: {e}")

        # Reset executed set at midnight UTC
        if now.hour == 0 and now.minute == 0:
            executed_today.clear()

        time.sleep(60)  # Check every minute


if __name__ == "__main__":
    if "--once" in sys.argv:
        print("Running full pipeline once (morning batch)...")
        asyncio.run(run_batch("morning"))
    elif "--post" in sys.argv:
        print("Posting all ready videos...")
        asyncio.run(run_post_all())
    else:
        run_scheduler()

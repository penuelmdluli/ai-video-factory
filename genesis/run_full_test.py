"""Full pipeline test — runs all phases with flushed output."""
import sys
import os
sys.stdout = open(sys.stdout.fileno(), mode='w', buffering=1, encoding='utf-8', errors='replace')
sys.stderr = open(sys.stderr.fileno(), mode='w', buffering=1, encoding='utf-8', errors='replace')

# Ensure dotenv loaded
from dotenv import load_dotenv
load_dotenv(override=True)

import asyncio
import time
from genesis.genesis_config import BRANDS
from genesis.db import get_latest_script

async def main():
    overall_start = time.time()
    print("=" * 60)
    print("  GENESIS CONTENT ENGINE — Full Pipeline Test")
    print("=" * 60)

    # Phase 1: Trends
    print("\n--- PHASE 1: TRENDS ---")
    from genesis.trend_fetcher import fetch_all_trends
    trends = await fetch_all_trends()
    print(f"Trends: {len(trends)}/4")

    # Phase 2: Scripts
    print("\n--- PHASE 2: SCRIPTS ---")
    from genesis.script_generator import generate_all_scripts
    scripts = generate_all_scripts(trends)
    print(f"Scripts: {len(scripts)}/4")

    # Phase 3: Videos (Brain Studio)
    print("\n--- PHASE 3: VIDEOS (Brain Studio) ---")
    from genesis.video_generator import generate_all_videos
    videos = await generate_all_videos(scripts)
    print(f"Videos: {sum(1 for v in videos.values() if v)}/4")

    # Phase 4: Watermarks
    print("\n--- PHASE 4: WATERMARKS ---")
    from genesis.watermark import apply_all_watermarks
    branded = apply_all_watermarks(videos)
    print(f"Branded: {sum(1 for v in branded.values() if v)}/4")

    # Phase 5: Post to Facebook
    print("\n--- PHASE 5: FACEBOOK POSTING ---")
    from genesis.poster_facebook import post_to_facebook
    posts = {}
    for brand, video_data in branded.items():
        if not video_data:
            continue
        print(f"  Posting {BRANDS[brand]['name']}...")
        result = await post_to_facebook(brand, video_data)
        if result:
            posts[brand] = result
            print(f"  OK {BRANDS[brand]['name']}: FB post {result['platform_post_id']}")
        else:
            print(f"  FAIL {BRANDS[brand]['name']}")

    total = time.time() - overall_start
    print("\n" + "=" * 60)
    print(f"  PIPELINE COMPLETE in {total:.0f}s ({total/60:.1f} min)")
    print(f"  Trends: {len(trends)}/4")
    print(f"  Scripts: {len(scripts)}/4")
    print(f"  Videos: {sum(1 for v in videos.values() if v)}/4")
    print(f"  Branded: {sum(1 for v in branded.values() if v)}/4")
    print(f"  FB Posts: {len(posts)}/4")
    print("=" * 60)

asyncio.run(main())

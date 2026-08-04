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


def _notify(text):
    """Best-effort Telegram alert; never breaks the pipeline if unavailable."""
    try:
        from remote_control import notify
        notify(text)
    except Exception as e:
        print(f"[notify] skipped: {e}")


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

    # Phase 5: Post to ALL platforms (Facebook + YouTube + TikTok)
    print("\n--- PHASE 5: MULTI-PLATFORM POSTING ---")
    from genesis.poster_facebook import post_to_facebook
    from genesis.poster_youtube import post_to_youtube
    from genesis.poster_tiktok import post_to_tiktok

    fb_count = 0
    yt_count = 0
    tt_count = 0

    for brand, video_data in branded.items():
        if not video_data:
            continue
        brand_name = BRANDS[brand]['name']
        print(f"\n  {brand_name}:")

        # Facebook
        fb = await post_to_facebook(brand, video_data)
        if fb:
            fb_count += 1
            print(f"    FB: Posted ({fb['platform_post_id']})")
        else:
            print(f"    FB: Failed")

        # YouTube Shorts
        yt = post_to_youtube(brand, video_data)
        if yt:
            yt_count += 1
            print(f"    YT: Posted ({yt.get('url', yt['platform_post_id'])})")
        else:
            print(f"    YT: Failed/Skipped")

        # TikTok
        tt = await post_to_tiktok(brand, video_data)
        if tt:
            tt_count += 1
            print(f"    TT: Posted ({tt['platform_post_id']})")
        else:
            print(f"    TT: Failed/Skipped")

    total = time.time() - overall_start
    trends_n = len(trends)
    scripts_n = len(scripts)
    videos_n = sum(1 for v in videos.values() if v)
    branded_count = sum(1 for v in branded.values() if v)
    total_posts = fb_count + yt_count + tt_count

    print("\n" + "=" * 60)
    print(f"  PIPELINE COMPLETE in {total:.0f}s ({total/60:.1f} min)")
    print(f"  Trends: {trends_n}/4")
    print(f"  Scripts: {scripts_n}/4")
    print(f"  Videos: {videos_n}/4")
    print(f"  Branded: {branded_count}/4")
    print(f"  Facebook: {fb_count}/{branded_count}")
    print(f"  YouTube:  {yt_count}/{branded_count}")
    print(f"  TikTok:   {tt_count}/{branded_count}")
    print(f"  Total Posts: {total_posts}")
    print("=" * 60)

    # ── Fail-loud: a run that posts nothing must NOT report success ──
    # Previously the job exited 0 even with 0 posts, so months of silent
    # zero-post days looked green. Pinpoint the earliest broken stage,
    # alert via Telegram, and exit non-zero so the run goes red.
    if total_posts == 0:
        if scripts_n == 0:
            reason = "script generation failed — check ANTHROPIC_API_KEY credits/billing"
        elif videos_n == 0:
            reason = "video generation failed — check Genesis Studio / Vercel deployment"
        elif branded_count == 0:
            reason = "watermarking failed — no branded videos produced"
        else:
            reason = "posting failed — videos were ready but no platform accepted them"

        alert = (
            "🔴 Genesis pipeline posted 0 videos\n"
            f"Reason: {reason}\n"
            f"Trends {trends_n}/4 · Scripts {scripts_n}/4 · "
            f"Videos {videos_n}/4 · Branded {branded_count}/4 · Posts 0"
        )
        print(f"\n[ALERT] {alert}")
        _notify(alert)
        return 1

    _notify(
        f"✅ Genesis pipeline posted {total_posts} video(s) — "
        f"FB {fb_count} · YT {yt_count} · TT {tt_count} (branded {branded_count}/4)."
    )
    return 0


_exit_code = asyncio.run(main())
sys.exit(_exit_code)

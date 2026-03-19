"""
Batch Build + Upload to TikTok & Facebook (hourly intervals)

Builds short-form videos for all 6 niches, then uploads each to
TikTok + Facebook Reels with 1-hour gaps between niches.

Phase 1: BUILD all 6 videos (back to back)
Phase 2: UPLOAD one niche per hour to TikTok + Facebook

Usage:
    python batch_tiktok_facebook.py              # Build + upload all 6
    python batch_tiktok_facebook.py --build      # Build only (no upload)
    python batch_tiktok_facebook.py --upload     # Upload pre-built only
    python batch_tiktok_facebook.py --interval 30  # 30-min intervals instead of 60
"""
import asyncio
import argparse
import json
import sys
import os
import io
from datetime import datetime, timedelta
from pathlib import Path

# UTF-8 output for Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(__file__))

from config import NICHES, OUTPUT_DIR


NICHE_ORDER = [
    "blissful_moments",   # 58K followers — highest reach first
    "ai_trading",         # 29K followers
    "tech_news",          # 10K followers
    "ai_money",           # 4K followers
    "health_wellness",    # 912 followers
    "motivation",         # 176 followers
]


async def build_all_videos() -> list[dict]:
    """Phase 1: Build baby podcast videos for all 6 niches."""
    from main import create_video

    print(f"\n{'#'*60}")
    print(f"# PHASE 1: BUILDING 6 BABY PODCAST VIDEOS")
    print(f"# Format: Baby Avatars (SPARKY vs NOVA)")
    print(f"# {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'#'*60}\n")

    built = []
    for i, niche in enumerate(NICHE_ORDER):
        niche_name = NICHES[niche]["name"]
        print(f"\n[{i+1}/6] Building: {niche_name} (Baby Podcast)")
        print(f"{'─'*50}")

        try:
            result = await create_video(niche, "podcast", dry_run=False, build_only=True)
            if result["status"] == "built":
                print(f"[OK] Built: {result['title'][:60]}")
                print(f"     Duration: {result['duration']:.0f}s | Path: {result['video_path']}")
                built.append({
                    "niche": niche,
                    "title": result["title"],
                    "manifest_path": result["manifest_path"],
                    "video_path": result["video_path"],
                })
            else:
                print(f"[FAIL] {result.get('error', 'unknown')}")
        except Exception as e:
            print(f"[ERROR] {niche}: {e}")

        await asyncio.sleep(5)

    print(f"\n{'='*60}")
    print(f"BUILD COMPLETE: {len(built)}/6 baby podcast videos ready")
    print(f"{'='*60}\n")

    return built


async def upload_with_intervals(interval_minutes: int = 60):
    """
    Phase 2: Upload pre-built videos to TikTok + Facebook
    with intervals between each niche.
    """
    from modules.uploader_tiktok import upload_to_tiktok
    from modules.uploader_facebook import upload_to_facebook

    # Find all unuploaded manifests
    manifests = []
    for niche in NICHE_ORDER:
        # Find latest manifest for this niche (podcast format = baby avatars)
        niche_dirs = sorted(
            OUTPUT_DIR.glob(f"{niche}_podcast_*"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for d in niche_dirs:
            manifest_path = d / "upload_manifest.json"
            if manifest_path.exists():
                try:
                    data = json.loads(manifest_path.read_text())
                    # Check if not yet uploaded to TikTok/Facebook
                    if not data.get("tiktok_fb_uploaded"):
                        video_path = Path(data["video_path"])
                        if video_path.exists():
                            manifests.append((niche, manifest_path, data))
                            break
                except Exception:
                    continue

    if not manifests:
        print("[UPLOAD] No pre-built short videos found for TikTok/Facebook upload")
        return

    total = len(manifests)
    print(f"\n{'#'*60}")
    print(f"# PHASE 2: UPLOADING TO TIKTOK + FACEBOOK")
    print(f"# Videos: {total} | Interval: {interval_minutes} min")
    print(f"# {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'#'*60}\n")

    # Show upload schedule
    now = datetime.now()
    for i, (niche, _, data) in enumerate(manifests):
        upload_time = now + timedelta(minutes=i * interval_minutes)
        niche_name = NICHES[niche]["name"]
        print(f"  {upload_time.strftime('%H:%M')} — {niche_name}: {data['title'][:50]}...")
    print()

    for i, (niche, manifest_path, data) in enumerate(manifests):
        niche_name = NICHES[niche]["name"]
        video_path = data["video_path"]
        title = data["title"]
        description = data.get("description", "")
        caption = data.get("caption", title)
        tags = data.get("tags", NICHES[niche].get("hashtags", []))
        thumb_path = data.get("thumb_path", "")

        print(f"\n[{i+1}/{total}] Uploading: {niche_name}")
        print(f"  Title: {title[:60]}")
        print(f"  Time: {datetime.now().strftime('%H:%M:%S')}")
        print(f"{'─'*50}")

        uploads = []

        # TikTok
        try:
            print(f"  [TikTok] Uploading...")
            tt_result = await upload_to_tiktok(
                video_path=video_path,
                description=caption,
                hashtags=tags,
            )
            status = tt_result.get("status", "unknown")
            print(f"  [TikTok] {status}")
            uploads.append(("tiktok", tt_result))
        except Exception as e:
            print(f"  [TikTok] FAILED: {e}")
            uploads.append(("tiktok", {"status": "failed", "error": str(e)}))

        # Facebook Reels
        try:
            print(f"  [Facebook] Uploading Reel...")
            fb_result = await upload_to_facebook(
                video_path=video_path,
                title=title,
                description=description,
                niche=niche,
                hashtags=tags,
                is_reel=True,
                thumbnail_path=thumb_path if Path(thumb_path).exists() else None,
            )
            status = fb_result.get("status", "unknown")
            print(f"  [Facebook] {status}")
            uploads.append(("facebook", fb_result))
        except Exception as e:
            print(f"  [Facebook] FAILED: {e}")
            uploads.append(("facebook", {"status": "failed", "error": str(e)}))

        # Mark manifest
        data["tiktok_fb_uploaded"] = True
        data["tiktok_fb_uploaded_at"] = datetime.now().isoformat()
        data["tiktok_fb_results"] = [
            {"platform": p, "status": r.get("status")} for p, r in uploads
        ]
        manifest_path.write_text(json.dumps(data, indent=2))

        ok_platforms = [p for p, r in uploads if r.get("status") == "uploaded"]
        print(f"  Uploaded to: {', '.join(ok_platforms) or 'none'}")

        # Wait before next niche (skip wait after last one)
        if i < total - 1:
            next_time = datetime.now() + timedelta(minutes=interval_minutes)
            print(f"\n  Waiting {interval_minutes} min until next upload ({next_time.strftime('%H:%M')})...")
            await asyncio.sleep(interval_minutes * 60)

    print(f"\n{'='*60}")
    print(f"ALL UPLOADS COMPLETE — {datetime.now().strftime('%H:%M:%S')}")
    print(f"{'='*60}\n")


async def run_full(interval_minutes: int = 60):
    """Build all videos, then upload with intervals."""
    await build_all_videos()
    await upload_with_intervals(interval_minutes)


def main():
    parser = argparse.ArgumentParser(description="Batch TikTok + Facebook Upload")
    parser.add_argument("--build", action="store_true", help="Build phase only")
    parser.add_argument("--upload", action="store_true", help="Upload phase only")
    parser.add_argument("--interval", type=int, default=60, help="Minutes between uploads (default: 60)")
    args = parser.parse_args()

    if args.build:
        asyncio.run(build_all_videos())
    elif args.upload:
        asyncio.run(upload_with_intervals(args.interval))
    else:
        asyncio.run(run_full(args.interval))


if __name__ == "__main__":
    main()

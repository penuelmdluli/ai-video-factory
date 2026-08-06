"""
Viral Shorts Pipeline — New Main Orchestrator for 10-30 Second Content.

Replaces the old long-form pipeline with a shorts-first strategy.
Every video is rendered separately per platform (no cross-posting).

Pipeline:
1. Pick trending topic (with trend data + performance feedback)
2. Generate viral script (Hook → Escalation → Payoff, 10-30 sec)
3. Create voiceover (Kokoro primary → ElevenLabs → edge-tts)
4. Generate AI visuals (clip library → Kling 3.0 → local AI → stock)
5. Get background music (cache → local MusicGen → Suno API)
6. Generate captions (word-level, karaoke-style)
7. Assemble video (cinema-grade, viral-optimized)
8. Render per platform (separate files for YT/TT/IG/FB)
9. Upload to all platforms
10. Log analytics

Usage:
    python shorts_pipeline.py                          # All niches
    python shorts_pipeline.py --niche tech_news        # Single niche
    python shorts_pipeline.py --niche tech_news --count 5  # 5 videos
    python shorts_pipeline.py --dry-run                # Build only, no upload
    python shorts_pipeline.py --stats                  # Show clip library stats
    python shorts_pipeline.py --budget 5.0             # Set API budget ($)
"""
import matplotlib
matplotlib.use("Agg")

import asyncio
import argparse
import json
import os
import shutil
import traceback
from datetime import datetime
from pathlib import Path

from config import (
    NICHES, SCHEDULE, OUTPUT_DIR,
    SHORTS_MAX_DURATION, SHORTS_MIN_DURATION,
    SHORTS_PLATFORMS, VIRAL_SHORTS_NICHES,
    AI_VIDEO_BUDGET_PER_SESSION,
)


def _safe(text: str) -> str:
    """Strip non-ASCII for safe Windows console printing."""
    return text.encode("ascii", errors="ignore").decode("ascii")


async def create_viral_short(
    niche: str,
    dry_run: bool = False,
    duration_target: int = 20,
    budget_limit: float = 0.50,
) -> dict:
    """
    Run the full viral shorts pipeline for a single video.

    Args:
        niche: Niche key (tech_news, health_wellness, etc.)
        dry_run: If True, generate video but don't upload
        duration_target: Target duration in seconds (10-30)
        budget_limit: Max API spend for this video

    Returns:
        Result dict with status, paths, and upload info
    """
    from modules.topic_generator import pick_topic
    from modules.script_writer import generate_viral_short_script, get_full_narration
    from modules.voice_generator import generate_voice
    from modules.visual_fetcher import fetch_visuals_for_viral_shorts
    from modules.caption_generator import generate_captions
    from modules.video_assembler import assemble_viral_short, render_for_all_platforms
    from modules.thumbnail_maker import generate_thumbnail_from_script
    from modules.logger import log_video

    niche_config = NICHES[niche]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    work_dir = OUTPUT_DIR / f"viral_{niche}_{timestamp}"
    work_dir.mkdir(parents=True, exist_ok=True)

    result = {
        "niche": niche,
        "format": "viral_short",
        "status": "started",
        "timestamp": timestamp,
        "work_dir": str(work_dir),
    }

    try:
        # ── 1. Pick Trending Topic ───────────────────────────
        print(f"\n{'='*60}")
        print(f"[Pipeline] VIRAL SHORT: {niche_config['name']}")
        print(f"{'='*60}")

        topic_data = await pick_topic(niche)
        topic = topic_data["topic"] if isinstance(topic_data, dict) else str(topic_data)
        result["topic"] = topic
        result["viral_score"] = topic_data.get("viral_score") if isinstance(topic_data, dict) else None
        print(f"[Pipeline] Topic: {_safe(topic)}")

        # ── 2. Generate Viral Script ─────────────────────────
        script = await generate_viral_short_script(
            topic=topic,
            niche=niche,
            duration_target=duration_target,
        )
        if not script:
            raise RuntimeError("Script generation failed for all models")

        result["title"] = script.get("title", topic)
        print(f"[Pipeline] Script: {_safe(script.get('title', '')[:60])}")
        print(f"[Pipeline] Scenes: {len(script.get('scenes', []))}, Target: {duration_target}s")

        # Save script
        with open(work_dir / "script.json", "w", encoding="utf-8") as f:
            json.dump(script, f, indent=2, ensure_ascii=False)

        # ── 3. Generate Voiceover ────────────────────────────
        narration = get_full_narration(script)

        voice_result = await generate_voice(
            text=narration,
            output_dir=work_dir,
            filename_base="voiceover",
            format_type="short",
            niche=niche,
            scenes=script.get("scenes"),
        )
        if not voice_result:
            raise RuntimeError("Voice generation failed")

        voice_path = Path(voice_result.get("audio_path", work_dir / "voiceover.mp3"))
        srt_path = Path(voice_result.get("subtitle_path", work_dir / "voiceover.srt"))
        if not voice_path.exists():
            raise RuntimeError(f"Voice file not found: {voice_path}")

        result["voice_path"] = str(voice_path)
        print(f"[Pipeline] Voice: {voice_path.name} ({voice_result.get('engine', 'unknown')})")

        # ── 4. Generate AI Visuals ───────────────────────────
        scenes_for_visuals = [
            {
                "scene_number": s["scene_number"],
                "visual_description": s.get("visual_description", ""),
                "narration": s.get("narration", ""),
                "duration_seconds": s.get("duration_seconds", 4),
            }
            for s in script["scenes"]
        ]

        visuals = await fetch_visuals_for_viral_shorts(
            scenes=scenes_for_visuals,
            output_dir=work_dir / "visuals",
            niche=niche,
            aspect_ratio="9:16",
        )

        # Merge visual paths back into scenes
        visual_map = {v["scene_number"]: v for v in visuals}
        for scene in script["scenes"]:
            vis = visual_map.get(scene["scene_number"], {})
            scene["local_path"] = vis.get("local_path")
            scene["type"] = vis.get("type", "placeholder")
            scene["duration"] = scene.get("duration_seconds", 4)

        ai_count = sum(1 for v in visuals if v.get("type") in ("ai_video", "ai_image"))
        lib_count = sum(1 for v in visuals if v.get("source") == "library")
        print(f"[Pipeline] Visuals: {len(visuals)} ({ai_count} AI, {lib_count} from library)")

        # ── 5. Get Background Music ──────────────────────────
        music_path = None
        try:
            from modules.ai_music_api import get_background_music
            music_path = await get_background_music(
                niche=niche,
                mood="default",
                duration=duration_target,
                output_path=str(work_dir / "music.mp3"),
            )
            if music_path:
                print(f"[Pipeline] Music: {Path(music_path).name}")
        except ImportError:
            print("[Pipeline] AI Music API not available, trying legacy...")
        except Exception as e:
            print(f"[Pipeline] Music generation failed: {e}")

        if not music_path:
            # Skip legacy MusicGen fallback — GPU hangs on it
            # Videos work fine without background music (YouTube Shorts strips it anyway)
            print("[Pipeline] No background music (GPU busy) — continuing without")

        # ── 6. Generate Captions ─────────────────────────────
        captions = []
        try:
            captions = await generate_captions(
                audio_path=str(voice_path),
                vtt_path=str(srt_path) if srt_path.exists() else None,
                output_dir=work_dir,
            )
            print(f"[Pipeline] Captions: {len(captions)} phrases")
        except Exception as e:
            print(f"[Pipeline] Caption generation failed: {e}")

        # ── 7. Render Per Platform ───────────────────────────
        platform_results = await render_for_all_platforms(
            scenes=script["scenes"],
            audio_path=str(voice_path),
            captions=captions,
            output_dir=work_dir,
            music_path=music_path,
            niche=niche,
            title=script.get("title", ""),
        )

        result["platform_videos"] = platform_results
        print(f"[Pipeline] Rendered {len(platform_results)} platform versions")

        # ── 8. Generate Thumbnail ────────────────────────────
        try:
            thumb_path = work_dir / "thumbnail.jpg"
            generate_thumbnail_from_script(
                script=script,
                output_path=str(thumb_path),
                niche=niche,
            )
            result["thumbnail_path"] = str(thumb_path)
        except Exception as e:
            print(f"[Pipeline] Thumbnail failed: {e}")

        # ── 9. Upload to All Platforms ───────────────────────
        if not dry_run:
            upload_results = await _upload_to_all_platforms(
                script=script,
                platform_videos=platform_results,
                niche=niche,
                thumbnail_path=result.get("thumbnail_path"),
            )
            result["uploads"] = upload_results
        else:
            print("[Pipeline] DRY RUN — skipping uploads")
            result["uploads"] = {"status": "dry_run"}

        # ── 10. Log Analytics ────────────────────────────────
        try:
            log_video(result)
        except Exception:
            pass

        result["status"] = "success"
        print(f"\n[Pipeline] SUCCESS: {_safe(result.get('title', ''))[:60]}")

    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
        print(f"\n[Pipeline] FAILED: {e}")
        traceback.print_exc()

    return result


async def _upload_to_all_platforms(
    script: dict,
    platform_videos: list[dict],
    niche: str,
    thumbnail_path: str | None = None,
) -> dict:
    """Upload to all platforms using platform-specific video files."""
    from config import ENABLE_AI_DISCLOSURE, AI_DISCLOSURE_HASHTAG

    uploads = {}
    title = script.get("title", "")
    caption = script.get("caption", "")
    description = script.get("description", caption)

    # Add AI disclosure hashtag (EU AI Act compliance)
    if ENABLE_AI_DISCLOSURE and AI_DISCLOSURE_HASHTAG not in caption:
        caption = f"{caption} {AI_DISCLOSURE_HASHTAG}"
        description = f"{description} {AI_DISCLOSURE_HASHTAG}"

    for pv in platform_videos:
        platform = pv.get("platform", "")
        video_path = pv.get("video_path", "")

        if not video_path or not Path(video_path).exists():
            continue

        try:
            if platform == "youtube_shorts":
                from modules.uploader_youtube import upload_to_youtube
                yt_result = await upload_to_youtube(
                    video_path=video_path,
                    title=title,
                    description=description,
                    tags=script.get("tags", []),
                    niche=niche,
                    is_short=True,
                    thumbnail_path=thumbnail_path,
                )
                uploads["youtube"] = yt_result
                print(f"[Upload] YouTube Shorts: {yt_result.get('status', 'unknown')}")

            elif platform == "tiktok":
                from modules.uploader_tiktok import upload_to_tiktok
                tt_result = await upload_to_tiktok(
                    video_path=video_path,
                    title=title,
                    description=caption,
                    niche=niche,
                )
                uploads["tiktok"] = tt_result
                print(f"[Upload] TikTok: {tt_result.get('status', 'unknown')}")

            elif platform == "instagram_reels":
                from modules.uploader_instagram import upload_to_instagram_local
                ig_result = await upload_to_instagram_local(
                    video_path=video_path,
                    caption=caption,
                    niche=niche,
                )
                uploads["instagram"] = ig_result
                print(f"[Upload] Instagram: {ig_result.get('status', 'unknown')}")

            elif platform == "facebook_reels":
                from modules.uploader_facebook import upload_to_facebook
                fb_result = await upload_to_facebook(
                    video_path=video_path,
                    title=title,
                    description=caption,
                    niche=niche,
                    is_reel=True,
                )
                uploads["facebook"] = fb_result
                print(f"[Upload] Facebook: {fb_result.get('status', 'unknown')}")

        except Exception as e:
            uploads[platform] = {"status": "error", "error": str(e)}
            print(f"[Upload] {platform} failed: {e}")

    return uploads


async def run_all_niches(
    dry_run: bool = False,
    niches: list[str] | None = None,
    count_override: int | None = None,
    budget_limit: float = 0.50,
):
    """Run the viral shorts pipeline for all configured niches."""
    target_niches = niches or VIRAL_SHORTS_NICHES
    total_videos = 0
    total_success = 0
    total_errors = 0

    print(f"\n{'#'*60}")
    print(f"# VIRAL SHORTS PIPELINE — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"# Niches: {len(target_niches)} | Budget: ${budget_limit}/session")
    print(f"{'#'*60}\n")

    # Show clip library stats if available
    try:
        from modules.clip_library import get_stats
        stats = get_stats()
        print(f"[Library] {stats['total_clips']} clips cached, "
              f"{stats['total_reuses']} reuses, "
              f"~${stats.get('estimated_savings', 0):.0f} saved")
    except Exception:
        pass

    for niche in target_niches:
        if niche not in NICHES:
            print(f"[Pipeline] Unknown niche: {niche}, skipping")
            continue

        schedule = SCHEDULE.get(niche, {})
        count = count_override or schedule.get("viral_shorts", 3)

        # Vary duration for diversity (research says mix of 15s, 20s, 25s works best)
        durations = [15, 20, 25, 20, 15]  # Rotation pattern

        for i in range(count):
            total_videos += 1
            duration = durations[i % len(durations)]

            try:
                result = await create_viral_short(
                    niche=niche,
                    dry_run=dry_run,
                    duration_target=duration,
                    budget_limit=budget_limit,
                )

                if result.get("status") == "success":
                    total_success += 1
                else:
                    total_errors += 1

            except Exception as e:
                total_errors += 1
                print(f"[Pipeline] {niche} video {i+1} failed: {e}")

            # Brief pause between videos to avoid rate limits
            if i < count - 1:
                await asyncio.sleep(5)

    # Summary
    print(f"\n{'='*60}")
    print(f"PIPELINE COMPLETE")
    print(f"  Total: {total_videos} | Success: {total_success} | Errors: {total_errors}")

    # Updated library stats
    try:
        from modules.clip_library import get_stats
        stats = get_stats()
        print(f"  Clip Library: {stats['total_clips']} clips, ~${stats.get('estimated_savings', 0):.0f} saved total")
    except Exception:
        pass

    print(f"{'='*60}\n")


def show_stats():
    """Show clip library and pipeline statistics."""
    print("\n=== CLIP LIBRARY STATS ===\n")
    try:
        from modules.clip_library import get_stats
        stats = get_stats()
        print(f"Total clips:      {stats['total_clips']}")
        print(f"Total reuses:     {stats['total_reuses']}")
        print(f"Reuse rate:       {stats.get('reuse_rate', 0):.1%}")
        print(f"Est. savings:     ${stats.get('estimated_savings', 0):.2f}")
        print(f"\nClips per niche:")
        for niche, count in stats.get("clips_per_niche", {}).items():
            print(f"  {niche}: {count}")
    except Exception as e:
        print(f"Clip library not available: {e}")

    print("\n=== MUSIC CACHE STATS ===\n")
    try:
        from modules.ai_music_api import get_cache_stats
        stats = get_cache_stats()
        print(f"Total tracks:     {stats.get('total_tracks', 0)}")
        print(f"Disk usage:       {stats.get('disk_usage_mb', 0):.1f} MB")
    except Exception as e:
        print(f"Music cache not available: {e}")


def main():
    parser = argparse.ArgumentParser(description="Viral Shorts Pipeline — 10-30 sec AI video content")
    parser.add_argument("--niche", type=str, help="Run specific niche only")
    parser.add_argument("--count", type=int, help="Videos per niche (overrides schedule)")
    parser.add_argument("--dry-run", action="store_true", help="Build only, no upload")
    parser.add_argument("--budget", type=float, default=AI_VIDEO_BUDGET_PER_SESSION, help="API budget ($)")
    parser.add_argument("--stats", action="store_true", help="Show clip library stats")
    parser.add_argument("--duration", type=int, default=20, help="Target duration (seconds)")

    args = parser.parse_args()

    if args.stats:
        show_stats()
        return

    niches = [args.niche] if args.niche else None

    asyncio.run(run_all_niches(
        dry_run=args.dry_run,
        niches=niches,
        count_override=args.count,
        budget_limit=args.budget,
    ))


if __name__ == "__main__":
    main()

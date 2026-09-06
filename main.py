"""
AI Video Factory — Main Orchestrator (Shorts Only)

Runs the complete automated pipeline:
1. Select A/B test variants
2. Pick trending topic (with real trend data + performance feedback)
3. Generate viral script (with hook/title style from A/B tests)
4. Create voiceover (ElevenLabs or edge-tts)
5. Fetch visuals (Pexels stock + AI images)
6. Generate captions
7. Assemble video (with hook overlay, pattern interrupts, safe zones)
8. Create thumbnail
9. Upload to YouTube, TikTok, Instagram, Twitter, Facebook
10. Post first comments (engagement seeding)
11. Record multi-platform analytics
12. Clean up temp files

Usage:
    python main.py                     # Run all niches
    python main.py --niche ai_money    # Run specific niche
    python main.py --format short      # Run only short-form
    python main.py --dry-run           # Generate but don't upload
    python main.py --health            # Run health check
    python main.py --update-metrics    # Refresh performance data (all platforms)
    python main.py --ab-summary        # Show A/B test results
    python main.py --trends            # Show current trending topics
"""
import matplotlib
matplotlib.use("Agg")  # Non-interactive backend — MUST be before any matplotlib import to prevent tkinter crash

import asyncio
import argparse
import json
import os
import shutil
import traceback
from datetime import datetime, timedelta
from pathlib import Path

from config import NICHES, SCHEDULE, OUTPUT_DIR, OPENAI_API_KEY, GEMINI_API_KEY


def _safe(text: str) -> str:
    """Strip non-ASCII chars (emoji) for safe Windows console printing."""
    return text.encode("ascii", errors="ignore").decode("ascii")


def _pick_best_frame(video_file, out_path, duration):
    """Grab the most eye-catching frame for a thumbnail: sample several timestamps
    and keep the sharpest, best-exposed one (avoids washed-out / dark frames)."""
    import subprocess
    import numpy as np
    from PIL import Image
    out_path = str(out_path)
    dur = max(float(duration or 10), 2.0)
    tmp = str(Path(out_path).with_name("_frmscan.jpg"))
    best_score = -1.0
    for f in (0.12, 0.22, 0.33, 0.45, 0.58, 0.70, 0.82):
        try:
            subprocess.run(["ffmpeg", "-y", "-ss", str(round(dur * f, 2)),
                            "-i", str(video_file), "-frames:v", "1", "-q:v", "2", tmp],
                           capture_output=True, timeout=15)
            if not Path(tmp).exists():
                continue
            g = np.asarray(Image.open(tmp).convert("L"), dtype=np.float32)
            mean = float(g.mean())
            expo = 0.4 if (mean < 42 or mean > 212) else 1.0     # penalise dark/blown
            detail = g.std() + (abs(np.diff(g, axis=1)).mean()
                                + abs(np.diff(g, axis=0)).mean()) * 6.0
            score = detail * expo
            if score > best_score:
                best_score = score
                Image.open(tmp).save(out_path, quality=92)
        except Exception:
            continue
    try:
        Path(tmp).unlink()
    except Exception:
        pass
    return out_path if Path(out_path).exists() else None


def _pick_clean_cover(visuals, out_path):
    """Best CAPTION-FREE frame from the raw scene clips/images — captured DURING the
    build, before captions + the LIVE pill get baked in — so covers/thumbnails don't
    show duplicated text. Returns the saved path or None."""
    import numpy as np
    from PIL import Image
    out_path = str(out_path)
    paths = [v.get("local_path") for v in (visuals or []) if v.get("local_path")]
    if not paths:
        return None
    # Prefer content scenes over the (often generic) opening hook.
    ordered = (paths[1:] + paths[:1]) if len(paths) > 1 else paths
    best = -1.0
    for p in ordered[:8]:
        try:
            pth = Path(p)
            if not pth.exists():
                continue
            if pth.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
                im = Image.open(p).convert("RGB")
            else:
                from moviepy import VideoFileClip
                with VideoFileClip(p) as c:
                    t = min(max(c.duration - 0.1, 0), c.duration * 0.5)
                    im = Image.fromarray(c.get_frame(t)).convert("RGB")
            g = np.asarray(im.convert("L"), dtype=np.float32)
            mean = float(g.mean())
            expo = 0.4 if (mean < 42 or mean > 212) else 1.0
            score = (g.std() + (abs(np.diff(g, axis=1)).mean()
                                + abs(np.diff(g, axis=0)).mean()) * 6.0) * expo
            if score > best:
                best = score
                im.save(out_path, quality=92)
        except Exception:
            continue
    return out_path if Path(out_path).exists() else None


async def create_video(
    niche: str,
    format_type: str = "short",
    dry_run: bool = False,
    build_only: bool = False,
    tiktok_schedule_time: datetime | None = None,
) -> dict:
    """
    Run the full pipeline for a single video.

    Args:
        niche: Niche key (ai_trading, ai_money, tech_news)
        format_type: "short" — shorts only pipeline (30s viral videos)
        dry_run: If True, generate video but don't upload
        tiktok_schedule_time: If set, schedule TikTok post for this time

    Returns:
        Result dict with status and upload info
    """
    # Force short format — shorts only pipeline
    format_type = "short"

    # Locked page (e.g. blissful_moments = SAGA OF THE NORTH): its own poster owns
    # it, so don't even build here.
    from config import page_locked, LOCKED_PAGES
    if page_locked(niche):
        print(f"[SKIP] {niche}: page locked to {LOCKED_PAGES[niche]} — not building/posting")
        return {"niche": niche, "format": format_type, "status": "skipped",
                "error": f"page locked to {LOCKED_PAGES[niche]}"}

    from modules.topic_generator import pick_topic
    from modules.script_writer import generate_script, get_full_narration, get_scene_visuals
    from modules.voice_generator import generate_voice
    from modules.visual_fetcher import fetch_visuals_for_scenes
    from modules.chart_generator import generate_charts_for_niche
    from modules.caption_generator import generate_captions
    from modules.video_assembler import assemble_video
    from modules.thumbnail_maker import generate_thumbnail_from_script
    from modules.uploader_youtube import upload_to_youtube, upload_to_deep_chill
    from modules.uploader_tiktok import upload_to_tiktok
    from modules.uploader_twitter import upload_to_twitter
    from modules.uploader_facebook import upload_to_facebook
    from modules.uploader_instagram import upload_to_instagram_local
    from modules.logger import log_video

    niche_config = NICHES[niche]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    work_dir = OUTPUT_DIR / f"{niche}_{format_type}_{timestamp}"
    work_dir.mkdir(parents=True, exist_ok=True)

    uploads = []
    ab_experiment_id = None
    ab_variants = {}

    try:
        # ── Step 0: Select A/B Test Variants ──────────────────
        try:
            from modules.ab_testing import select_variants, record_experiment
            ab_variants = select_variants(niche)
            print(f"[A/B] Variants: {ab_variants}")
        except Exception:
            ab_variants = {}

        # ── Step 1: Pick Topic ─────────────────────────────────
        print(f"\n{'='*60}")
        print(f"[Pipeline] {niche_config['name']} | {format_type} | {timestamp}")
        print(f"{'='*60}")

        topic_data = await pick_topic(niche, ab_variants=ab_variants)
        topic = topic_data["topic"]
        print(f"[1/10] Topic: {_safe(topic)} (source: {topic_data['source']})")

        # ── Step 2: Generate Script ────────────────────────────
        script = await generate_script(topic, niche, format_type)
        title = script.get("title", topic)
        description = script.get("description", "")
        # Fallback: auto-generate description from title + scenes if empty
        if not description or len(description.strip()) < 20:
            # Use whole sentences — slicing each narration at a fixed width cut
            # words in half ("...bill doubled. Yo Here's what's...").
            scene_texts = " ".join(
                s.get("narration", "").strip() for s in script.get("scenes", [])[:3]
            )
            description = f"{title}. {scene_texts}".strip()
            if len(description) > 500:
                description = description[:497].rsplit(" ", 1)[0].rstrip(",;:") + "..."
            print(f"[2/10] Auto-generated description (script had none)")
        # Always use niche-configured hashtags as base, then append AI-generated ones
        niche_tags = niche_config.get("hashtags", [])
        ai_tags = script.get("tags", [])
        # Deduplicate: niche tags first, then AI tags that aren't duplicates
        seen = {t.lower().lstrip("#") for t in niche_tags}
        extra_tags = [t for t in ai_tags if t.lower().lstrip("#") not in seen]
        tags = niche_tags + extra_tags[:5]  # Cap AI extras at 5
        print(f"[2/10] Script: {_safe(title[:60])}... ({len(script['scenes'])} scenes)")

        # ── Step 2.5: Get Dynamic Hashtags ─────────────────────
        optimized_hashtags = niche_config["hashtags"]  # Default static
        comment_hashtags = []
        try:
            from modules.hashtag_optimizer import get_optimized_hashtags, get_first_comment_hashtags

            # Get trending hashtags from real data
            trending_tags = []
            try:
                from modules.trend_detector import get_trending_hashtags
                trending_tags = await get_trending_hashtags(niche)
            except Exception:
                pass

            # Get topic keywords for relevant hashtags
            topic_keywords = [w for w in topic.split() if len(w) > 3][:5]

            # Optimize hashtags per platform
            platform = "tiktok" if format_type == "short" else "youtube"
            optimized_hashtags = get_optimized_hashtags(
                niche=niche,
                platform=platform,
                trending_hashtags=trending_tags,
                topic_keywords=topic_keywords,
            )

            # Get extra hashtags for first comment
            comment_hashtags = get_first_comment_hashtags(
                niche=niche,
                platform=platform,
                main_hashtags=optimized_hashtags,
            )

            print(f"[2.5/10] Hashtags: {len(optimized_hashtags)} optimized + {len(comment_hashtags)} for comment")
        except Exception as e:
            print(f"[2.5/10] Hashtags: using defaults ({e})")

        # Record A/B experiment
        if ab_variants:
            try:
                ab_experiment_id = record_experiment(
                    niche=niche,
                    variants=ab_variants,
                    topic=topic,
                    title=title,
                )
            except Exception:
                pass

        # ── Step 3: Generate Voiceover ─────────────────────────
        narration = get_full_narration(script)
        voice_result = await generate_voice(
            text=narration,
            output_dir=work_dir,
            filename_base="voiceover",
            format_type=format_type,
            niche=niche,
            scenes=script.get("scenes"),
        )
        print(f"[3/10] Voice: {voice_result['engine']} ({voice_result['word_count']} words)")

        # ── Step 4: Fetch Visuals ──────────────────────────────
        scene_visuals = get_scene_visuals(script)
        orientation = "portrait"  # Always portrait for shorts (9:16)

        visuals = await fetch_visuals_for_scenes(
            scene_visuals,
            work_dir / "visuals",
            niche_queries=niche_config.get("pexels_queries"),
            orientation=orientation,
            niche=niche,
        )
        ai_image_count = sum(1 for v in visuals if v.get("type") == "ai_image")

        # Generate trading charts if applicable
        chart_paths = []
        if niche_config.get("generate_charts"):
            chart_paths = await generate_charts_for_niche(
                niche_config["chart_symbols"],
                work_dir / "charts",
            )
            for i, chart in enumerate(chart_paths):
                if i < len(visuals):
                    replace_idx = min(i * 3, len(visuals) - 1)
                    visuals[replace_idx]["local_path"] = chart
                    visuals[replace_idx]["type"] = "photo"

        print(f"[4/10] Visuals: {len(visuals)} scenes + {len(chart_paths)} charts + {ai_image_count} AI images")

        # ── Step 4.1: Convert AI images to video clips (SVD-XT) ──
        # Second SVD entry point. visual_fetcher has its own, and gating only that
        # one still left this running ~47s/step x 15 steps x 6 scenes (~1 hour).
        if os.getenv("FORCE_STILLS_ONLY", "").lower() in ("true", "1", "yes"):
            print("[4.1/10] stills-only: skipping SVD-XT — Ken Burns on stills")
            ai_image_count = 0
        if ai_image_count > 0:
            try:
                from modules.ai_video_generator import convert_images_to_videos
                visuals = await convert_images_to_videos(visuals, work_dir / "svd_clips", niche=niche)
                svd_count = sum(1 for v in visuals if v.get("type") == "ai_video")
                if svd_count > 0:
                    print(f"[4.1/10] AI Video: {svd_count}/{ai_image_count} images converted to video (SVD-XT)")
                else:
                    print(f"[4.1/10] AI Video: SVD disabled or failed, using Ken Burns for all scenes")
            except Exception as e:
                print(f"[4.1/10] AI Video: SVD error ({str(e)[:80]}), using Ken Burns fallback")

        # Capture a clean, caption-free cover frame NOW (scene clips still on disk,
        # captions/LIVE pill not yet baked) for a duplicate-free thumbnail + reel cover.
        clean_cover_path = None
        try:
            clean_cover_path = _pick_clean_cover(visuals, work_dir / "cover_source.jpg")
        except Exception as _e:
            print(f"[4.1/10] Clean cover capture skipped: {_e}")

        # ── Step 5: Generate Captions ──────────────────────────
        caption_result = await generate_captions(
            audio_path=voice_result["audio_path"],
            vtt_path=voice_result.get("subtitle_path"),
            output_dir=work_dir,
        )
        print(f"[5/10] Captions: {caption_result['phrase_count']} phrases ({caption_result['source']})")

        # ── Step 4.5: Generate Avatar PiP ──────────────────────
        avatar_pip_path = None
        try:
            from modules.avatar_generator import generate_full_avatar
            avatar_pip_path = await generate_full_avatar(
                voice_result=voice_result,
                work_dir=work_dir,
                niche=niche,
            )
            if avatar_pip_path:
                print(f"[4.5/10] Avatar: PiP generated (full duration)")
            else:
                print("[4.5/10] Avatar: skipped (not configured or failed)")
        except Exception as e:
            print(f"[4.5/10] Avatar skipped: {e}")

        # ── Step 5.5: Generate Sound Effects ───────────────────
        sfx_placements = []
        try:
            from modules.sfx_manager import generate_scene_sfx
            for i, v in enumerate(visuals):
                if i < len(script["scenes"]):
                    v["narration"] = script["scenes"][i].get("narration", "")
                    v["sfx_hint"] = script["scenes"][i].get("sfx_hint", "")
                    v["niche"] = niche
            sfx_placements = await generate_scene_sfx(visuals)
            if sfx_placements:
                print(f"[5.5/10] SFX: {len(sfx_placements)} sound effects placed")
        except Exception as e:
            print(f"[5.5/10] SFX skipped: {e}")

        # ── Step 6: Assemble Video ─────────────────────────────
        video_format = "youtube_shorts"  # Always shorts
        video_path = work_dir / f"final_{format_type}.mp4"

        assembly_result = await assemble_video(
            scenes=visuals,
            audio_path=voice_result["audio_path"],
            captions=caption_result["segments"],
            output_path=video_path,
            format_type=video_format,
            sfx_placements=sfx_placements,
            avatar_pip_path=avatar_pip_path,
            niche=niche,
            title=title,  # For hook overlay in first 3 seconds
        )
        print(f"[6/10] Video: {assembly_result['duration']:.0f}s, {assembly_result['file_size_mb']:.1f}MB")

        # ── Step 7: Generate Thumbnail ─────────────────────────
        thumb_path = work_dir / "thumbnail.jpg"
        bg_chart = chart_paths[0] if chart_paths else None

        # Prefer the clean, caption-free scene frame captured earlier; fall back to a
        # frame from the finished video only if that's unavailable.
        frame_path = None
        clean_source = bool(clean_cover_path and Path(clean_cover_path).exists())
        if not bg_chart:
            if clean_source:
                frame_path = clean_cover_path
            elif assembly_result.get("output_path"):
                frame_path = _pick_best_frame(
                    assembly_result["output_path"], work_dir / "thumb_frame.jpg",
                    assembly_result.get("duration", 10))
            if frame_path:
                bg_chart = frame_path

        thumbnail_layout = ab_variants.get("thumbnail_layout")
        generate_thumbnail_from_script(
            script, thumb_path,
            chart_image=bg_chart,
            layout=thumbnail_layout,
        )
        print(f"[7/10] Thumbnail: {thumb_path.name} (layout: {thumbnail_layout or 'random'})")

        # Portrait 9:16 cover for the Reel/Short (correct shape for FB/IG). Add the LIVE
        # badge ONLY when the source is the clean scene frame (news niche) — a finished-
        # video fallback frame already carries the baked pill, so we'd double it.
        reel_cover_path = None
        if frame_path and format_type == "short":
            try:
                from modules.thumbnail_maker import generate_reel_cover
                from config import NICHES as _NICHES
                thumb_hook = script.get("thumbnail_text") or title
                reel_cover_path = str(work_dir / "reel_cover.jpg")
                add_live = clean_source and bool(_NICHES.get(niche, {}).get("topic_focus"))
                generate_reel_cover(
                    title_text=thumb_hook, background_image=frame_path, niche=niche,
                    live_badge=add_live,
                    output_path=reel_cover_path)
            except Exception as _e:
                print(f"[7/10] Reel cover skipped: {_e}")
                reel_cover_path = None

        # ── Save Upload Manifest (for deferred upload) ────────
        manifest = {
            "niche": niche,
            "format_type": format_type,
            "title": title,
            "description": description,
            "tags": optimized_hashtags,
            "video_path": str(video_path),
            "thumb_path": str(thumb_path),
            "reel_cover_path": reel_cover_path,  # portrait 9:16 cover for FB/IG reels
            "srt_path": voice_result.get("subtitle_path"),
            "caption": script.get("caption", title),
            "is_short": format_type == "short",
            "built_at": datetime.now().isoformat(),
            "uploaded": False,
            "comment_hashtags": comment_hashtags,
            "ab_experiment_id": ab_experiment_id,
            "topic": topic,
            "duration": assembly_result["duration"],
        }
        manifest_path = work_dir / "upload_manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2),
                                 encoding="utf-8")

        if build_only:
            print(f"[BUILD COMPLETE] Video ready for deferred upload: {video_path.name}")
            log_video(
                niche=niche,
                topic=topic,
                format_type=format_type,
                script_title=title,
                video_path=str(video_path),
                uploads=[{"platform": "pending", "status": "built"}],
                duration=assembly_result["duration"],
            )
            return {
                "status": "built",
                "niche": niche,
                "format": format_type,
                "title": title,
                "video_path": str(video_path),
                "duration": assembly_result["duration"],
                "manifest_path": str(manifest_path),
            }

        # ── Step 8: Upload ─────────────────────────────────────
        if dry_run:
            print("[8/10] Dry run - skipping uploads")
            uploads = [{"platform": "dry_run", "status": "skipped"}]
        else:
            print("[8/10] Uploading to platforms...")

            srt_path = voice_result.get("subtitle_path")

            # YouTube (always pass thumbnail — works for shorts too).
            # Guard: only post if this niche has its OWN channel token — otherwise the
            # uploader falls back to the default channel and misposts (e.g. sa_pulse
            # has a FB page but no YouTube channel yet → FB/blog only).
            is_short = format_type == "short"
            if not (Path("tokens") / f"youtube_token_{niche}.json").exists():
                print(f"[YouTube] No channel token for '{niche}' — skipping YouTube (posts to FB/blog only)")
                yt_result = {"platform": "youtube", "status": "skipped", "error": "no dedicated channel token"}
            else:
                yt_result = await upload_to_youtube(
                    video_path=str(video_path),
                    title=title,
                    description=description,
                    tags=optimized_hashtags,
                    niche=niche,
                    thumbnail_path=str(thumb_path) if thumb_path.exists() else None,
                    is_short=is_short,
                    srt_path=srt_path,
                )
            uploads.append(yt_result)

            # Deep Chill secondary channel (all niches)
            dc_result = await upload_to_deep_chill(
                video_path=str(video_path),
                title=title,
                description=description,
                tags=optimized_hashtags,
                niche=niche,
                thumbnail_path=str(thumb_path) if thumb_path.exists() else None,
                is_short=is_short,
                srt_path=srt_path,
            )
            uploads.append(dc_result)

            # TikTok (all formats)
            try:
                from modules.hashtag_optimizer import get_optimized_hashtags as _get_tt_tags
                tt_hashtags = _get_tt_tags(niche=niche, platform="tiktok")
            except Exception:
                tt_hashtags = niche_config["hashtags"]

            tt_result = await upload_to_tiktok(
                video_path=str(video_path),
                description=script.get("caption", title),
                hashtags=tt_hashtags,
                schedule_time=tiktok_schedule_time,
                niche=niche,
            )
            uploads.append(tt_result)

            # Twitter (short-form only)
            if format_type == "short":
                tw_result = await upload_to_twitter(
                    video_path=str(video_path),
                    text=title[:200],
                    hashtags=optimized_hashtags[:3],
                )
                uploads.append(tw_result)

            # Facebook
            try:
                from modules.hashtag_optimizer import get_optimized_hashtags as _get_fb_tags
                fb_hashtags = _get_fb_tags(niche=niche, platform="facebook")
            except Exception:
                fb_hashtags = niche_config["hashtags"]

            # Syndication: shorts -> Reel; LONG-FORM -> 16:9 for Facebook's
            # in-stream (higher-CPM, CMP-paying) tier. Reframe long-form to 16:9
            # if it isn't already, so it lands in the paying format. Never
            # double-posts the same clip (avoids Meta's duplicate/unoriginal flag).
            fb_video_path = str(video_path)
            if not is_short:
                try:
                    from modules.reframe import reframe as _reframe
                    from pathlib import Path as _P
                    _wide = _P(str(video_path)).with_name(_P(str(video_path)).stem + "_fb16x9.mp4")
                    fb_video_path = _reframe(str(video_path), "16x9", str(_wide))
                except Exception as _e:
                    print(f"[Syndicate] 16:9 reframe skipped, posting original: {_e}")

            # Reels want a PORTRAIT cover; 16:9 videos use the landscape thumbnail.
            fb_cover = (reel_cover_path if (is_short and reel_cover_path
                                            and Path(reel_cover_path).exists())
                        else (str(thumb_path) if thumb_path.exists() else None))
            fb_result = await upload_to_facebook(
                video_path=fb_video_path,
                title=title,
                description=description,
                niche=niche,
                hashtags=fb_hashtags,
                is_reel=is_short,
                thumbnail_path=fb_cover,
            )
            uploads.append(fb_result)

            # Instagram (short-form — with cloud storage!)
            if format_type == "short":
                try:
                    from modules.cloud_storage import upload_to_cloud, is_cloud_storage_configured
                    if is_cloud_storage_configured():
                        ig_result = await upload_to_instagram_local(
                            video_path=str(video_path),
                            caption=script.get("caption", title),
                            hashtags=optimized_hashtags,
                            upload_to_cloud_fn=upload_to_cloud,
                        )
                    else:
                        ig_result = await upload_to_instagram_local(
                            video_path=str(video_path),
                            caption=script.get("caption", title),
                            hashtags=optimized_hashtags,
                        )
                except Exception as e:
                    ig_result = {"platform": "instagram", "status": "failed", "error": str(e)}
                uploads.append(ig_result)

            uploaded_platforms = [u["platform"] for u in uploads if u.get("status") == "uploaded"]
            print(f"[8/10] Uploaded to: {', '.join(uploaded_platforms) or 'none'}")

            # ── Step 9: Post First Comments ────────────────────
            try:
                from modules.engagement_booster import post_first_comments
                comment_results = await post_first_comments(
                    uploads=uploads,
                    niche=niche,
                    extra_hashtags=comment_hashtags,
                )
                comments_posted = sum(1 for c in comment_results if c.get("status") == "posted")
                print(f"[9/10] First comments: {comments_posted} posted")
            except Exception as e:
                print(f"[9/10] First comments skipped: {e}")

            # ── Step 10: Record Multi-Platform Analytics ───────
            try:
                from modules.performance_tracker import record_video_performance

                for upload in uploads:
                    if upload.get("status") != "uploaded":
                        continue

                    record_video_performance(
                        niche=niche,
                        topic=topic,
                        title=title,
                        post_id=upload.get("post_id"),
                        video_id=upload.get("video_id"),
                        platform=upload.get("platform", "unknown"),
                        hashtags=optimized_hashtags,
                        ab_experiment_id=ab_experiment_id,
                    )
                print(f"[10/10] Analytics: {len(uploaded_platforms)} platforms tracked")
            except Exception as e:
                print(f"[10/10] Analytics failed: {e}")

            # Clean up cloud storage temp files
            try:
                from modules.cloud_storage import cleanup_old_uploads
                await cleanup_old_uploads(max_age_hours=1)
            except Exception:
                pass

        # ── Log Result ─────────────────────────────────────────
        log_video(
            niche=niche,
            topic=topic,
            format_type=format_type,
            script_title=title,
            video_path=str(video_path),
            uploads=uploads,
            duration=assembly_result["duration"],
        )

        # Cleanup work directory (keep only final video + thumbnail)
        for subdir in ["visuals", "charts", "ai_images"]:
            subdir_path = work_dir / subdir
            if subdir_path.exists():
                shutil.rmtree(subdir_path)

        return {
            "status": "success",
            "niche": niche,
            "format": format_type,
            "title": title,
            "video_path": str(video_path),
            "duration": assembly_result["duration"],
            "uploads": uploads,
            "ab_variants": ab_variants,
        }

    except Exception as e:
        error_msg = f"{type(e).__name__}: {e}"
        print(f"\n[Pipeline] FAILED: {error_msg}")
        traceback.print_exc()

        log_video(
            niche=niche,
            topic=topic_data.get("topic", "unknown") if 'topic_data' in locals() else "unknown",
            format_type=format_type,
            script_title=title if 'title' in locals() else "unknown",
            video_path=None,
            uploads=uploads,
            error=error_msg,
        )

        return {
            "status": "error",
            "niche": niche,
            "format": format_type,
            "error": error_msg,
        }


async def upload_prebuilt_videos(
    niche_filter: str | None = None,
    format_filter: str | None = None,
    most_recent_only: bool = False,
) -> list[dict]:
    """
    Find and upload all pre-built videos that haven't been uploaded yet.

    Scans output/ for upload_manifest.json files where uploaded=False.
    Used by the scheduler's upload phase (2 hours after build phase).

    most_recent_only=True posts only the SINGLE newest un-posted video per
    (niche, format) instead of every same-day build — so a run never fires
    multiple videos to the same page back-to-back. Older same-day builds are
    left un-posted (they become stale after today and are skipped).
    """
    from modules.uploader_youtube import upload_to_youtube, upload_to_deep_chill
    from modules.uploader_tiktok import upload_to_tiktok
    from modules.uploader_twitter import upload_to_twitter
    from modules.uploader_facebook import upload_to_facebook
    from modules.uploader_instagram import upload_to_instagram_local
    from modules.logger import log_video

    results = []
    manifests = sorted(OUTPUT_DIR.glob("*/upload_manifest.json"))
    today = datetime.now().strftime("%Y-%m-%d")

    # most-recent-only: pre-scan to find the newest eligible manifest per
    # (niche, format) so we skip older same-day builds in the loop below.
    keep_paths = None
    if most_recent_only:
        latest: dict[tuple, tuple] = {}
        for mp in manifests:
            try:
                m = json.loads(mp.read_text(encoding="utf-8"))
            except Exception:
                continue
            ba = m.get("built_at", "")
            n, f = m.get("niche"), m.get("format_type")
            if m.get("uploaded") or not ba.startswith(today) or n not in NICHES:
                continue
            if (niche_filter and n != niche_filter) or (format_filter and f != format_filter):
                continue
            key = (n, f)
            if key not in latest or ba > latest[key][0]:
                latest[key] = (ba, mp)
        keep_paths = {mp for _, mp in latest.values()}
        print(f"[most-recent-only] posting {len(keep_paths)} video(s): "
              f"newest un-posted per niche/format only")

    for manifest_path in manifests:
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            continue

        if manifest.get("uploaded"):
            continue

        # Only upload videos built TODAY — prevents duplicate posting of old videos
        built_at = manifest.get("built_at", "")
        if not built_at.startswith(today):
            print(f"[SKIP] {manifest.get('niche', '?')}: Built on {built_at[:10]}, not today — skipping stale manifest")
            continue

        niche = manifest["niche"]
        format_type = manifest["format_type"]
        if niche not in NICHES:
            print(f"[SKIP] {niche}/{format_type}: Niche removed from pipeline")
            continue
        from config import page_locked
        if page_locked(niche):
            print(f"[SKIP] {niche}/{format_type}: page locked to its own poster (see LOCKED_PAGES)")
            continue
        if niche_filter and niche != niche_filter:
            continue
        if format_filter and format_type != format_filter:
            continue
        if keep_paths is not None and manifest_path not in keep_paths:
            print(f"[SKIP] {niche}/{format_type}: older same-day build (most-recent-only)")
            continue

        video_path = Path(manifest["video_path"])
        if not video_path.exists():
            print(f"[SKIP] {niche}/{format_type}: Video file missing")
            continue

        title = manifest["title"]
        description = manifest["description"]
        tags = manifest.get("tags", [])
        thumb_path = Path(manifest.get("thumb_path", ""))
        srt_path = manifest.get("srt_path")
        caption = manifest.get("caption", title)
        is_short = manifest.get("is_short", False)
        comment_hashtags = manifest.get("comment_hashtags", [])

        niche_config = NICHES.get(niche, {})
        uploads = []

        print(f"\n[UPLOAD] {niche}/{format_type}: {_safe(title[:60])}...")

        # YouTube — skip if this niche has no dedicated channel token (avoids
        # falling back to the default channel and misposting).
        if not (Path("tokens") / f"youtube_token_{niche}.json").exists():
            print(f"[YouTube] No channel token for '{niche}' — skipping YouTube (posts to FB/blog only)")
            yt_result = {"platform": "youtube", "status": "skipped", "error": "no dedicated channel token"}
        else:
            yt_result = await upload_to_youtube(
                video_path=str(video_path),
                title=title,
                description=description,
                tags=tags,
                niche=niche,
                thumbnail_path=str(thumb_path) if thumb_path.exists() else None,
                is_short=is_short,
                srt_path=srt_path,
            )
        uploads.append(yt_result)

        # Deep Chill secondary channel
        dc_result = await upload_to_deep_chill(
            video_path=str(video_path),
            title=title,
            description=description,
            tags=tags,
            niche=niche,
            thumbnail_path=str(thumb_path) if thumb_path.exists() else None,
            is_short=is_short,
            srt_path=srt_path,
        )
        uploads.append(dc_result)

        # TikTok (all formats)
        try:
            tt_result = await upload_to_tiktok(
                video_path=str(video_path),
                description=caption,
                hashtags=tags,
                niche=niche,
            )
            uploads.append(tt_result)
        except Exception:
            pass

        # Twitter (short-form only)
        if is_short:
            try:
                tw_result = await upload_to_twitter(
                    video_path=str(video_path),
                    text=title[:200],
                    hashtags=tags[:3],
                )
                uploads.append(tw_result)
            except Exception:
                pass

        # Facebook — reels need the PORTRAIT cover, not the 16:9 thumbnail.
        _rc = manifest.get("reel_cover_path")
        if is_short and _rc and Path(_rc).exists():
            fb_cover = _rc
        elif thumb_path.exists():
            fb_cover = str(thumb_path)
        else:
            fb_cover = None
        try:
            fb_result = await upload_to_facebook(
                video_path=str(video_path),
                title=title,
                description=description,
                niche=niche,
                hashtags=tags,
                is_reel=is_short,
                thumbnail_path=fb_cover,
            )
            uploads.append(fb_result)
        except Exception:
            pass

        # Instagram (short-form)
        if is_short:
            try:
                from modules.cloud_storage import upload_to_cloud, is_cloud_storage_configured
                if is_cloud_storage_configured():
                    ig_result = await upload_to_instagram_local(
                        video_path=str(video_path),
                        caption=caption,
                        hashtags=tags,
                        upload_to_cloud_fn=upload_to_cloud,
                    )
                else:
                    ig_result = await upload_to_instagram_local(
                        video_path=str(video_path),
                        caption=caption,
                        hashtags=tags,
                    )
                uploads.append(ig_result)
            except Exception:
                pass

        uploaded_platforms = [u["platform"] for u in uploads if u.get("status") == "uploaded"]
        print(f"  Uploaded to: {', '.join(uploaded_platforms) or 'none'}")

        # First comments
        try:
            from modules.engagement_booster import post_first_comments
            await post_first_comments(
                uploads=uploads,
                niche=niche,
                extra_hashtags=comment_hashtags,
            )
        except Exception:
            pass

        # Analytics
        try:
            from modules.performance_tracker import record_video_performance
            for upload in uploads:
                if upload.get("status") != "uploaded":
                    continue
                record_video_performance(
                    niche=niche,
                    topic=manifest.get("topic", ""),
                    title=title,
                    post_id=upload.get("post_id"),
                    video_id=upload.get("video_id"),
                    platform=upload.get("platform", "unknown"),
                    hashtags=tags,
                )
        except Exception:
            pass

        # Mark manifest as uploaded
        manifest["uploaded"] = True
        manifest["uploaded_at"] = datetime.now().isoformat()
        manifest["upload_results"] = [
            {"platform": u.get("platform"), "status": u.get("status")}
            for u in uploads
        ]
        manifest_path.write_text(json.dumps(manifest, indent=2),
                                 encoding="utf-8")

        results.append({
            "niche": niche,
            "format": format_type,
            "title": title,
            "uploads": uploads,
            "status": "uploaded" if uploaded_platforms else "failed",
        })

    if not results:
        print("[UPLOAD] No pre-built videos pending upload")

    return results


async def run_daily_pipeline(
    niches: list[str] | None = None,
    formats: list[str] | None = None,
    dry_run: bool = False,
    build_only: bool = False,
):
    """
    Run the full daily video creation pipeline.

    TikTok staggered scheduling: the first video posts immediately,
    subsequent videos are scheduled 2 hours apart for better algorithm reach.
    """
    if niches is None:
        niches = list(NICHES.keys())
    if formats is None:
        formats = ["short"]  # Shorts only pipeline

    tiktok_stagger_hours = 2.0

    print(f"\n{'#'*60}")
    print(f"# AI Video Factory v2 — Trending Edition")
    print(f"# Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"# Niches: {', '.join(niches)}")
    print(f"# Formats: {', '.join(formats)}")
    print(f"# Dry Run: {dry_run}")
    print(f"# Build Only: {build_only}")
    print(f"# TikTok: 1st posts NOW, rest scheduled {tiktok_stagger_hours}h apart")
    print(f"{'#'*60}\n")

    results = []
    tiktok_video_index = 0  # Tracks which TikTok video we're on

    for niche in niches:
        schedule = SCHEDULE.get(niche, {"short": 2})

        for fmt in formats:
            count = schedule.get("short", schedule.get("shorts", 2))
            for i in range(count):
                print(f"\n--- {niche} | {fmt} | Video {i+1}/{count} ---")

                # Calculate TikTok schedule time
                # First video (index 0) → None (posts immediately)
                # Subsequent → staggered 2h apart from now
                if tiktok_video_index == 0 or dry_run:
                    tt_schedule = None
                else:
                    tt_schedule = datetime.now() + timedelta(
                        hours=tiktok_stagger_hours * tiktok_video_index
                    )

                result = await create_video(niche, fmt, dry_run, build_only, tt_schedule)
                results.append(result)
                tiktok_video_index += 1

                if not dry_run:
                    await asyncio.sleep(5)

    successes = sum(1 for r in results if r["status"] == "success")
    failures = sum(1 for r in results if r["status"] == "error")

    print(f"\n{'='*60}")
    print(f"DAILY RUN COMPLETE")
    print(f"  Total: {len(results)} videos")
    print(f"  Success: {successes}")
    print(f"  Failed: {failures}")
    print(f"{'='*60}\n")

    return results


def main():
    parser = argparse.ArgumentParser(description="AI Video Factory v2")
    parser.add_argument("--niche", choices=list(NICHES.keys()), help="Run specific niche only")
    parser.add_argument("--format", choices=["short"], default="short", help="Video format (shorts only)")
    parser.add_argument("--dry-run", action="store_true", help="Generate videos but don't upload")
    parser.add_argument("--stats", action="store_true", help="Show statistics")
    parser.add_argument("--health", action="store_true", help="Run health check on all services")
    parser.add_argument("--update-metrics", action="store_true", help="Update performance metrics (all platforms)")
    parser.add_argument("--ab-summary", action="store_true", help="Show A/B test results")
    parser.add_argument("--trends", action="store_true", help="Show current trending topics (all 5 sources)")
    parser.add_argument("--trend-health", action="store_true", help="Show trend source health status")
    parser.add_argument("--viral-check", type=str, metavar="TOPIC", help="Check viral score for a topic string")
    parser.add_argument("--niche-heat", action="store_true", help="Show niche trend heat rankings")
    parser.add_argument("--build-only", action="store_true", help="Build videos without uploading (for scheduled deferred upload)")
    parser.add_argument("--upload-prebuilt", action="store_true", help="Upload pre-built videos from previous build phase")
    parser.add_argument("--most-recent-only", action="store_true", help="With --upload-prebuilt: post only the newest un-posted video per niche/format (no back-to-back posts)")
    parser.add_argument("--engagement", action="store_true", help="Run one round of engagement posts to all FB pages")
    args = parser.parse_args()

    if args.update_metrics:
        from modules.performance_tracker import update_all_metrics, get_performance_summary
        asyncio.run(update_all_metrics())
        summary = get_performance_summary()
        print(f"\n--- Performance Summary (Multi-Platform) ---")
        print(f"  Tracked: {summary['total_tracked']} videos")
        print(f"  By platform: {summary.get('by_platform', {})}")
        for niche, score in summary.get("niche_scores", {}).items():
            print(f"  {niche}: avg score {score}")
        return

    if args.ab_summary:
        from modules.ab_testing import get_experiment_summary
        for niche in NICHES:
            summary = get_experiment_summary(niche)
            print(f"\n--- A/B Test: {NICHES[niche]['name']} ---")
            print(f"  Experiments: {summary['total_experiments']} ({summary['scored_experiments']} scored)")
            winners = summary.get("winning_variants", {})
            for dim, variant in winners.items():
                print(f"  Winner [{dim}]: {variant}")
        return

    if args.trends:
        async def show_trends():
            from modules.trend_detector import get_trending_topics
            target_niches = [args.niche] if args.niche else list(NICHES.keys())
            for niche in target_niches:
                data = await get_trending_topics(niche)
                print(f"\n--- {NICHES[niche]['name']} ---")
                print(f"  Active sources: {', '.join(data.get('active_sources', []))}")
                print(f"  Total trends: {data['source_count']}")
                for kw in data["top_keywords"][:8]:
                    print(f"  -> {kw}")
        asyncio.run(show_trends())
        return

    if args.trend_health:
        from modules.trend_detector import get_health_status
        status = get_health_status()
        print(f"\n{'='*55}")
        print(f"  Trend Source Health Status")
        print(f"{'='*55}")
        for source, info in status.items():
            h = "OK" if info["healthy"] else "STALE"
            b = " BACKOFF" if info["backed_off"] else ""
            err = f" | Last error: {info['last_error'][:50]}" if info["last_error"] else ""
            print(f"  {source:<16} [{h}{b}] failures: {info['consecutive_failures']} | results: {info['last_result_count']}{err}")
        print(f"{'='*55}\n")
        return

    if args.viral_check:
        async def check_viral():
            from modules.viral_scorer import validate_topic
            niche = args.niche or "tech_news"
            print(f"\nChecking viral score for: {args.viral_check}")
            print(f"Niche: {niche}")
            result = await validate_topic(args.viral_check, niche)
            print(f"\n  Viral Score: {result['viral_score']}/100 ({result['recommendation']})")
            print(f"  Passes threshold ({VIRAL_SCORE_THRESHOLD}): {result['passes_threshold']}")
            print(f"  Components:")
            for k, v in result["components"].items():
                print(f"    {k}: {v}")
        from config import VIRAL_SCORE_THRESHOLD
        asyncio.run(check_viral())
        return

    if args.niche_heat:
        from modules.niche_prioritizer import show_niche_heat
        asyncio.run(show_niche_heat())
        return

    if args.health:
        from modules.retry import PipelineHealthCheck
        checker = PipelineHealthCheck()
        asyncio.run(checker.run_all())
        return

    if args.stats:
        from modules.logger import get_daily_summary, get_total_stats
        daily = get_daily_summary()
        total = get_total_stats()
        print(f"\n--- Today ({daily['date']}) ---")
        print(f"  Videos: {daily['total_videos']} (OK: {daily['successful']}, Fail: {daily['failed']})")
        print(f"  Uploads: {daily['platforms_uploaded']}")
        print(f"\n--- All Time ---")
        print(f"  Videos: {total['total_videos']} (OK: {total['successful']}, Fail: {total['failed']})")
        print(f"  Uploads: {total['total_uploads']}")
        print(f"  By niche: {total['by_niche']}")
        return

    if args.engagement:
        async def run_eng():
            from modules.engagement_poster import run_engagement_round
            niches = [args.niche] if args.niche else None
            return await run_engagement_round(niches=niches, dry_run=args.dry_run)
        asyncio.run(run_eng())
        return

    if args.upload_prebuilt:
        niche_f = args.niche if args.niche else None
        format_f = args.format if args.format else None
        asyncio.run(upload_prebuilt_videos(niche_f, format_f, most_recent_only=args.most_recent_only))
        return

    niches = [args.niche] if args.niche else None
    formats = [args.format] if args.format else None
    build_only = args.build_only

    asyncio.run(run_daily_pipeline(niches, formats, args.dry_run, build_only))


if __name__ == "__main__":
    main()

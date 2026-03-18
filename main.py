"""
AI Video Factory — Main Orchestrator (v3 — Podcast Edition)

Runs the complete automated pipeline:
1. Select A/B test variants
2. Pick trending topic (with real trend data + performance feedback)
3. Generate viral script (with hook/title style from A/B tests)
4. Create voiceover (ElevenLabs for YouTube, edge-tts for shorts)
5. Fetch visuals (Pexels stock + AI images + trading charts)
6. Generate captions
7. Assemble video (with hook overlay, pattern interrupts, safe zones)
8. Create thumbnail
9. Upload to YouTube, TikTok, Instagram, Twitter, Facebook
10. Post first comments (engagement seeding)
11. Record multi-platform analytics
12. Clean up temp files

New in v3 — Baby Podcast Format:
- Two-character split-screen debate videos (SPARKY vs NOVA)
- Emotion-tagged dialogue with voice parameter control
- 4 character styles: baby, robot, cartoon, realistic
- Per-niche podcast topic banks
- Dual-voice generation with distinct character voices
- Split-screen video with active-speaker highlighting
- Section titles (THE TWIST, ROUND 1, CLIFFHANGER)
- Viral optimization: hooks, quotable moments, cliffhangers

Usage:
    python main.py                     # Run all niches, all formats
    python main.py --niche ai_trading  # Run specific niche
    python main.py --format short      # Run only short-form
    python main.py --format podcast    # Run only podcast format
    python main.py --dry-run           # Generate but don't upload
    python main.py --health            # Run health check
    python main.py --update-metrics    # Refresh performance data (all platforms)
    python main.py --ab-summary        # Show A/B test results
    python main.py --trends            # Show current trending topics
"""
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


async def create_video(
    niche: str,
    format_type: str = "long",
    dry_run: bool = False,
    build_only: bool = False,
    tiktok_schedule_time: datetime | None = None,
) -> dict:
    """
    Run the full pipeline for a single video.

    Args:
        niche: Niche key (ai_trading, ai_money, tech_news)
        format_type: "long" for YouTube, "short" for Shorts/TikTok/Reels, "podcast" for split-screen debate
        dry_run: If True, generate video but don't upload
        tiktok_schedule_time: If set, schedule TikTok post for this time

    Returns:
        Result dict with status and upload info
    """
    # Route podcast format to dedicated pipeline
    if format_type == "podcast":
        return await create_podcast_video(niche, dry_run, build_only, tiktok_schedule_time)

    # Route news anchor format to dedicated pipeline
    if niche == "daily_breakdown" or format_type == "news_anchor":
        return await create_news_anchor_video(niche or "daily_breakdown", dry_run, build_only, tiktok_schedule_time)

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
        tags = script.get("tags", [])
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

            # Optimize hashtags per platform (use TikTok set as base for short, YT for long)
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
        orientation = "landscape" if format_type == "long" else "portrait"

        visuals = await fetch_visuals_for_scenes(
            scene_visuals,
            work_dir / "visuals",
            niche_queries=niche_config.get("pexels_queries"),
            orientation=orientation,
        )

        # Generate AI images for weak scenes
        ai_image_count = 0
        from modules.ai_images import generate_image
        has_free_ai = bool(GEMINI_API_KEY) or bool(os.getenv("CF_ACCOUNT_ID") and os.getenv("CF_API_TOKEN"))

        if has_free_ai or OPENAI_API_KEY:
            weak_scenes = [
                v for v in visuals
                if v.get("type") in ("placeholder", "photo") or v.get("local_path") is None
            ]
            for v in weak_scenes:
                sn = v["scene_number"]
                desc = ""
                for sv in scene_visuals:
                    if sv.get("scene_number") == sn:
                        desc = sv.get("visual", sv.get("visual_description", ""))
                        break
                if not desc:
                    continue
                ai_path = work_dir / "ai_images" / f"ai_scene_{sn:02d}.png"
                result = await generate_image(desc, ai_path, niche=niche, orientation=orientation)
                if result:
                    v["local_path"] = result
                    v["type"] = "photo"
                    ai_image_count += 1

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
        video_format = "youtube_long" if format_type == "long" else "youtube_shorts"
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

        # If no chart, extract a visually interesting frame from the video
        if not bg_chart and assembly_result.get("output_path"):
            try:
                import subprocess
                video_file = assembly_result["output_path"]
                duration = assembly_result.get("duration", 10)
                # Grab frame at ~25% (past intro, usually a good visual)
                grab_time = min(max(duration * 0.25, 2), duration - 1)
                frame_path = str(work_dir / "thumb_frame.jpg")
                subprocess.run([
                    "ffmpeg", "-y", "-ss", str(grab_time),
                    "-i", str(video_file), "-frames:v", "1",
                    "-q:v", "2", frame_path,
                ], capture_output=True, timeout=15)
                if Path(frame_path).exists():
                    bg_chart = frame_path
            except Exception:
                pass

        thumbnail_layout = ab_variants.get("thumbnail_layout")
        generate_thumbnail_from_script(
            script, thumb_path,
            chart_image=bg_chart,
            layout=thumbnail_layout,
        )
        print(f"[7/10] Thumbnail: {thumb_path.name} (layout: {thumbnail_layout or 'random'})")

        # ── Save Upload Manifest (for deferred upload) ────────
        manifest = {
            "niche": niche,
            "format_type": format_type,
            "title": title,
            "description": description,
            "tags": optimized_hashtags,
            "video_path": str(video_path),
            "thumb_path": str(thumb_path),
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
        manifest_path.write_text(json.dumps(manifest, indent=2))

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

            # YouTube (always pass thumbnail — works for shorts too)
            is_short = format_type == "short"
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

            fb_result = await upload_to_facebook(
                video_path=str(video_path),
                title=title,
                description=description,
                niche=niche,
                hashtags=fb_hashtags,
                is_reel=is_short,
                thumbnail_path=str(thumb_path) if thumb_path.exists() else None,
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


async def create_news_anchor_video(
    niche: str = "daily_breakdown",
    dry_run: bool = False,
    build_only: bool = False,
    tiktok_schedule_time: datetime | None = None,
) -> dict:
    """
    Create a news anchor analysis video (The Daily Breakdown).

    REVERSED pipeline: scrape news → fetch clips → write script around clips.
    """
    from modules.news_scraper import select_news_stories
    from modules.script_writer import generate_news_anchor_script, get_full_narration
    from modules.voice_generator import generate_voice
    from modules.visual_fetcher import search_pexels_videos, search_pexels_photos, search_pixabay_videos, search_pixabay_photos
    from modules.caption_generator import generate_captions
    from modules.video_assembler import assemble_news_anchor_video
    from modules.thumbnail_maker import generate_thumbnail
    from modules.ai_images import generate_image

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    niche_config = NICHES.get(niche, NICHES["daily_breakdown"])
    work_dir = OUTPUT_DIR / f"{niche}_news_anchor_{timestamp}"
    work_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"[NewsAnchor] {niche_config['name']} | {timestamp}")
    print(f"{'='*60}")

    try:
        # ── Step 1: Scrape trending news ──
        print("[1/8] Scraping trending news headlines...")
        news_stories = await select_news_stories(
            regions=["iran", "south_africa", "world", "africa", "conflict"],
            max_stories=3,
        )
        if not news_stories:
            raise RuntimeError("No news stories found")
        print(f"[1/8] News: {len(news_stories)} stories selected")

        # ── Step 2: Fetch real footage + AI images for each story ──
        print("[2/8] Fetching real footage & generating AI visuals...")
        clips_dir = work_dir / "clips"
        clips_dir.mkdir(exist_ok=True)
        ai_images_dir = work_dir / "ai_images"
        ai_images_dir.mkdir(exist_ok=True)
        news_clips = []
        import httpx

        for i, story in enumerate(news_stories):
            queries = story.get("suggested_pexels_queries", ["news broadcast"])
            headline = story.get("headline", "breaking news")
            story_clips_count = 0

            # ── A) Fetch MULTIPLE real video clips per story from Pexels + Pixabay ──
            for query in queries[:5]:  # Try up to 5 queries per story
                try:
                    # Search Pexels first (portrait preferred for shorts)
                    videos = search_pexels_videos(query, per_page=5, orientation="portrait", min_duration=5)
                    if not videos:
                        videos = search_pexels_videos(query, per_page=5, orientation="landscape", min_duration=5)

                    # Also search Pixabay for documentary-style footage
                    pixabay_vids = search_pixabay_videos(query, per_page=5, min_duration=5)
                    if pixabay_vids:
                        videos = (videos or []) + pixabay_vids

                    if videos:
                        for vid_idx, video in enumerate(videos[:2]):  # Up to 2 clips per query
                            try:
                                source = video.get("source", "pexels")
                                clip_path = clips_dir / f"clip_{i}_{story_clips_count}_{query.replace(' ', '_')[:15]}.mp4"
                                async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                                    resp = await client.get(video["url"])
                                    if resp.status_code == 200:
                                        clip_path.write_bytes(resp.content)
                                        news_clips.append({
                                            "path": str(clip_path),
                                            "query": query,
                                            "visual_description": f"{query} footage",
                                            "story_index": i,
                                            "duration": video.get("duration", 10),
                                            "type": "video",
                                            "source": source,
                                        })
                                        story_clips_count += 1
                                        print(f"  Story {i} clip {story_clips_count}: [{source}] {query} ({video.get('duration', '?')}s)")
                            except Exception:
                                continue
                except Exception as e:
                    print(f"  Story {i} query '{query}' failed: {e}")
                    continue

                if story_clips_count >= 4:  # 4 clips per story for maximum variety
                    break

            # ── B) Fetch real photos from Pexels + Pixabay ──
            if story_clips_count < 2:
                for query in queries[:3]:
                    try:
                        photos = search_pexels_photos(query, per_page=3, orientation="portrait")
                        if not photos:
                            photos = search_pexels_photos(query, per_page=3, orientation="landscape")
                        # Add Pixabay photos
                        pixabay_imgs = search_pixabay_photos(query, per_page=3, orientation="vertical")
                        if pixabay_imgs:
                            photos = (photos or []) + pixabay_imgs

                        if photos:
                            for photo in photos[:2]:
                                source = photo.get("source", "pexels")
                                photo_path = clips_dir / f"clip_{i}_{story_clips_count}_photo.jpg"
                                async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                                    resp = await client.get(photo["url"])
                                    if resp.status_code == 200:
                                        photo_path.write_bytes(resp.content)
                                        news_clips.append({
                                            "path": str(photo_path),
                                            "query": query,
                                            "visual_description": f"{query} photo",
                                            "story_index": i,
                                            "type": "photo",
                                            "source": source,
                                        })
                                        story_clips_count += 1
                                        print(f"  Story {i} photo {story_clips_count}: [{source}] {query}")
                                        if story_clips_count >= 3:
                                            break
                    except Exception:
                        continue

            # ── C) AI-generated images for stories with few visuals ──
            if story_clips_count < 2:
                print(f"  Story {i}: Generating AI images for '{headline[:40]}'...")
                ai_prompts = [
                    f"Breaking news scene: {headline}. Dramatic photojournalism.",
                    f"News report visual: {queries[0] if queries else headline}. Documentary style.",
                ]
                for ai_idx, ai_prompt in enumerate(ai_prompts):
                    if story_clips_count >= 3:
                        break
                    try:
                        ai_path = ai_images_dir / f"ai_story_{i}_{ai_idx}.png"
                        result = await generate_image(
                            ai_prompt, ai_path,
                            niche="daily_breakdown",
                            orientation="portrait",
                        )
                        if result:
                            news_clips.append({
                                "path": result,
                                "query": ai_prompt[:40],
                                "visual_description": ai_prompt,
                                "story_index": i,
                                "type": "ai_image",
                            })
                            story_clips_count += 1
                            print(f"  Story {i} AI image {ai_idx}: generated")
                    except Exception as e:
                        print(f"  Story {i} AI image failed: {e}")

            # ── D) Last resort: placeholder ──
            if story_clips_count == 0:
                news_clips.append({
                    "path": None,
                    "query": queries[0] if queries else "news",
                    "visual_description": f"news footage for: {headline[:40]}",
                    "story_index": i,
                    "type": "placeholder",
                })

        total_visuals = sum(1 for c in news_clips if c.get("path"))
        videos_count = sum(1 for c in news_clips if c.get("type") == "video")
        photos_count = sum(1 for c in news_clips if c.get("type") == "photo")
        ai_count = sum(1 for c in news_clips if c.get("type") == "ai_image")
        print(f"[2/8] Visuals: {total_visuals} total ({videos_count} videos, {photos_count} photos, {ai_count} AI images)")

        # ── Step 3: Generate script based on clips + stories ──
        print("[3/8] Generating news analysis script...")
        script = await generate_news_anchor_script(news_stories, news_clips, niche)
        if not script:
            raise RuntimeError("Failed to generate news anchor script")

        title = script.get("title", "Daily Breakdown")
        print(f"[3/8] Script: {_safe(title)[:60]} ({len(script.get('scenes', []))} scenes)")

        # ── Step 4: Generate AI images for scenes missing visuals ──
        print("[4/8] Filling visual gaps with AI-generated images...")
        scenes = script.get("scenes", [])
        ai_fill_count = 0
        for scene in scenes:
            clip_idx = scene.get("clip_index", 0)
            # Check if this scene has a valid clip
            has_clip = (clip_idx < len(news_clips) and
                        news_clips[clip_idx].get("path") and
                        Path(news_clips[clip_idx]["path"]).exists())
            if not has_clip:
                # Generate AI image for this scene
                visual_desc = scene.get("visual_description", scene.get("narration", "news scene")[:80])
                try:
                    ai_path = ai_images_dir / f"ai_scene_fill_{clip_idx}_{ai_fill_count}.png"
                    result = await generate_image(
                        f"News footage scene: {visual_desc}. Photojournalism, real-world, dramatic.",
                        ai_path,
                        niche="daily_breakdown",
                        orientation="portrait",
                    )
                    if result:
                        # Insert into news_clips at the right index
                        while len(news_clips) <= clip_idx:
                            news_clips.append({"path": None, "type": "placeholder"})
                        news_clips[clip_idx] = {
                            "path": result,
                            "visual_description": visual_desc,
                            "type": "ai_image",
                            "story_index": scene.get("story_index", 0),
                        }
                        ai_fill_count += 1
                        print(f"  Scene {scene.get('scene_number', '?')}: AI image generated")
                except Exception as e:
                    print(f"  Scene fill failed: {e}")
        print(f"[4/8] AI fill: {ai_fill_count} images generated for missing scenes")

        # ── Step 5: Generate voice narration ──
        print("[5/8] Generating voice narration...")
        narration = get_full_narration(script)
        voice_result = await generate_voice(
            text=narration,
            output_dir=work_dir,
            filename_base="narration",
            niche=niche,
        )
        audio_path = voice_result["audio_path"]
        print(f"[5/8] Voice: {voice_result.get('engine', 'unknown')} ({voice_result.get('duration_estimate', 0):.0f}s)")

        # ── Step 6: Generate captions ──
        print("[6/8] Generating captions...")
        captions_data = None
        srt_path = voice_result.get("subtitle_path")
        try:
            captions_result = await generate_captions(
                audio_path=audio_path,
                vtt_path=srt_path if srt_path and Path(srt_path).exists() else None,
                output_dir=work_dir,
                filename_base="captions",
            )
            if captions_result and captions_result.get("segments"):
                captions_data = captions_result["segments"]
                print(f"[6/8] Captions: {len(captions_data)} segments")
            else:
                print("[6/8] Captions: no segments generated")
        except Exception as e:
            print(f"[6/8] Captions: skipped ({e})")

        # ── Step 7: Assemble video (full-screen clips + voiceover) ──
        print("[7/8] Assembling premium news video...")
        video_path = work_dir / "final_news_anchor.mp4"
        video_result = await assemble_news_anchor_video(
            scenes=script.get("scenes", []),
            audio_path=audio_path,
            anchor_image=None,
            news_clips=news_clips,
            output_path=video_path,
            captions_data=captions_data,
            niche=niche,
            title=title,
            animated_avatar=None,
        )
        print(f"[7/8] Video: {video_result.get('file_size_mb', '?')}MB, {video_result.get('duration', '?')}s")

        # ── Step 8: Generate thumbnail ──
        print("[8/8] Generating thumbnail...")
        thumb_path = work_dir / "thumbnail.jpg"
        try:
            generate_thumbnail(
                title_text=script.get("thumbnail_text", title),
                output_path=str(thumb_path),
                niche=niche,
            )
            print(f"[8/8] Thumbnail: {thumb_path.name}")
        except Exception as e:
            print(f"[8/8] Thumbnail: skipped ({e})")
            thumb_path = None

        # ── Save manifest ──
        manifest = {
            "niche": niche,
            "format": "news_anchor",
            "title": title,
            "video_path": str(video_path),
            "thumbnail_path": str(thumb_path) if thumb_path else None,
            "script": script,
            "news_stories": [s.get("headline") for s in news_stories],
            "created_at": datetime.now().isoformat(),
            "uploaded": False,
        }
        manifest_path = work_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, default=str))

        if dry_run or build_only:
            print(f"\n[NewsAnchor] {'DRY RUN' if dry_run else 'BUILD ONLY'} — skipping upload")
            return {"status": "built", "niche": niche, "title": title, "video_path": str(video_path)}

        # ── Upload ──
        print("\n[NewsAnchor] Uploading to platforms...")
        uploads = []

        # YouTube Shorts
        try:
            from modules.uploader_youtube import upload_to_youtube
            yt_result = await upload_to_youtube(
                video_path=str(video_path),
                title=title[:100],
                description=script.get("caption", title),
                tags=script.get("tags", []) + niche_config.get("hashtags", []),
                category_id="25",  # News category
                is_short=True,
                niche=niche,
                thumbnail_path=str(thumb_path) if thumb_path and thumb_path.exists() else None,
            )
            uploads.append({"platform": "youtube", "status": "success", **yt_result})
        except Exception as e:
            print(f"[Upload] YouTube failed: {e}")
            uploads.append({"platform": "youtube", "status": "failed", "error": str(e)})

        # TikTok
        try:
            from modules.uploader_tiktok import upload_to_tiktok
            tt_result = await upload_to_tiktok(
                video_path=str(video_path),
                title=title[:100],
                tags=[h.replace("#", "") for h in niche_config.get("hashtags", [])[:5]],
                niche=niche,
                schedule_time=tiktok_schedule_time,
            )
            uploads.append({"platform": "tiktok", "status": "success", **tt_result})
        except Exception as e:
            print(f"[Upload] TikTok failed: {e}")
            uploads.append({"platform": "tiktok", "status": "failed", "error": str(e)})

        # Facebook Reels
        try:
            from modules.uploader_facebook import upload_to_facebook
            fb_result = await upload_to_facebook(
                video_path=str(video_path),
                title=title[:100],
                description=script.get("caption", title),
                niche=niche,
                is_reel=True,
            )
            uploads.append({"platform": "facebook", "status": "success", **fb_result})
        except Exception as e:
            print(f"[Upload] Facebook failed: {e}")
            uploads.append({"platform": "facebook", "status": "failed", "error": str(e)})

        # Update manifest
        manifest["uploaded"] = True
        manifest["uploaded_at"] = datetime.now().isoformat()
        manifest["upload_results"] = uploads
        manifest_path.write_text(json.dumps(manifest, indent=2, default=str))

        print(f"\n[NewsAnchor] COMPLETE: {_safe(title)}")
        return {
            "status": "uploaded",
            "niche": niche,
            "title": title,
            "video_path": str(video_path),
            "uploads": uploads,
        }

    except Exception as e:
        print(f"\n[NewsAnchor] FAILED: {e}")
        traceback.print_exc()
        return {"status": "failed", "niche": niche, "error": str(e)}


async def create_podcast_video(
    niche: str,
    dry_run: bool = False,
    build_only: bool = False,
    tiktok_schedule_time: datetime | None = None,
) -> dict:
    """
    Run the Baby Podcast pipeline — two-character split-screen debate video.

    Pipeline:
    1. Pick trending topic for debate
    2. Generate dual-character podcast script (SPARKY vs NOVA)
    3. Generate dual voices (premium ElevenLabs per-niche voice pairs)
    4. Generate/cache character images (baby/robot/cartoon/realistic in studio)
    5. Animate avatars via D-ID (talking heads — lip-synced to audio)
    6. Assemble split-screen video (studio bg, active-speaker glow, captions)
    7. Create thumbnail
    8. Upload to all platforms
    """
    from modules.podcast_generator import (
        generate_podcast_script,
        generate_character_images,
        NICHE_PODCAST_CONFIG,
    )
    from modules.voice_generator import generate_podcast_dual_voice
    from modules.video_assembler import assemble_podcast_video
    from modules.podcast_generator import generate_podcast_avatars
    from modules.thumbnail_maker import generate_thumbnail_from_script
    from modules.uploader_youtube import upload_to_youtube, upload_to_deep_chill
    from modules.uploader_tiktok import upload_to_tiktok
    from modules.uploader_twitter import upload_to_twitter
    from modules.uploader_facebook import upload_to_facebook
    from modules.uploader_instagram import upload_to_instagram_local
    from modules.logger import log_video

    niche_config = NICHES[niche]
    podcast_config = NICHE_PODCAST_CONFIG.get(niche, {})
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    work_dir = OUTPUT_DIR / f"{niche}_podcast_{timestamp}"
    work_dir.mkdir(parents=True, exist_ok=True)

    uploads = []
    topic = "unknown"
    title = "unknown"

    try:
        # ── Step 1: Pick Topic ────────────────────────────────
        print(f"\n{'='*60}")
        print(f"[Podcast] {niche_config['name']} | BABY PODCAST | {timestamp}")
        print(f"{'='*60}")

        # Try trending topics first, fall back to podcast topic bank
        try:
            from modules.topic_generator import pick_topic
            topic_data = await pick_topic(niche)
            topic = topic_data["topic"]
        except Exception:
            import random
            topics = podcast_config.get("topics", ["Will AI change everything?"])
            topic = random.choice(topics)

        print(f"[1/8] Topic: {_safe(topic)}")

        # ── Step 2: Generate Podcast Script ───────────────────
        character_style = podcast_config.get("default_style", "baby")
        script = await generate_podcast_script(
            topic=topic,
            niche=niche,
            duration=90,
            character_style=character_style,
        )
        if not script:
            raise RuntimeError("Failed to generate podcast script")

        title = script.get("title", topic)
        description = script.get("description", "")
        tags = script.get("tags", [])
        line_count = len(script.get("lines", []))
        print(f"[2/8] Script: {_safe(title[:60])}... ({line_count} lines, style: {character_style})")

        # ── Step 3: Generate Dual Voices ──────────────────────
        voice_result = await generate_podcast_dual_voice(
            script_data=script,
            output_dir=work_dir,
            niche=niche,
            use_elevenlabs=True,  # Premium ElevenLabs voices (falls back to edge-tts)
        )
        print(f"[3/8] Voices: {voice_result['engine']} ({voice_result['line_count']} lines, {voice_result['duration']:.0f}s)")

        # ── Step 4: Generate Character Images ─────────────────
        char_images = await generate_character_images(
            character_style=character_style,
            output_dir=work_dir / "characters",
            niche=niche,
        )
        print(f"[4/8] Characters: {character_style} style (SPARKY + NOVA)")

        # ── Step 5: Animate Avatars (D-ID → HeyGen → static) ──
        animated_avatars = None
        try:
            # Use per-character audio so each character only lip-syncs their own lines
            char_audio = voice_result.get("character_audio", {})
            if not char_audio:
                # Fallback: use combined audio for both (less accurate lip sync)
                char_audio = {
                    "sparky": voice_result["audio_path"],
                    "nova": voice_result["audio_path"],
                }
                print("[5/8] Using combined audio (per-character audio not available)")
            else:
                print("[5/8] Using per-character audio for accurate lip sync")
            animated_avatars = await generate_podcast_avatars(
                character_images=char_images,
                character_audio=char_audio,
                output_dir=work_dir / "avatars",
                niche=niche,
                line_timings=voice_result.get("line_timings", []),
            )
            if animated_avatars and animated_avatars.get("animated"):
                animated_count = sum(1 for k in ("sparky", "nova") if animated_avatars.get(k))
                print(f"[5/8] Avatars: {animated_count}/2 animated talking heads")
            else:
                print(f"[5/8] Avatars: No API credits — using static images with studio bg")
                animated_avatars = None
        except Exception as e:
            print(f"[5/8] Avatars: Failed ({e}) — using static images")
            animated_avatars = None

        # ── Step 6: Assemble Split-Screen Video ───────────────
        video_path = work_dir / "final_podcast.mp4"
        assembly_result = await assemble_podcast_video(
            line_timings=voice_result["line_timings"],
            audio_path=voice_result["audio_path"],
            character_images=char_images,
            output_path=video_path,
            format_type="podcast_short",
            niche=niche,
            title=title,
            script=script,
            animated_avatars=animated_avatars,
        )
        print(f"[6/8] Video: {assembly_result['duration']:.0f}s, {assembly_result['file_size_mb']:.1f}MB")

        # ── Step 7: Thumbnail ─────────────────────────────────
        thumb_path = work_dir / "thumbnail.jpg"
        # Create podcast-style thumbnail using script data
        podcast_thumb_script = {
            "title": title,
            "scenes": [{"visual_description": "split screen debate", "narration": topic}],
            "thumbnail_text": script.get("thumbnail_text", title[:30]),
            "niche": niche,
        }
        generate_thumbnail_from_script(podcast_thumb_script, thumb_path)
        print(f"[7/8] Thumbnail: {thumb_path.name}")

        # ── Save Upload Manifest (for deferred upload) ────────
        manifest = {
            "niche": niche,
            "format_type": "podcast",
            "title": title,
            "description": description,
            "tags": niche_config.get("hashtags", []),
            "video_path": str(video_path),
            "thumb_path": str(thumb_path),
            "srt_path": voice_result.get("subtitle_path"),
            "caption": script.get("caption", title),
            "is_short": True,
            "built_at": datetime.now().isoformat(),
            "uploaded": False,
            "topic": topic,
            "duration": assembly_result["duration"],
        }
        manifest_path = work_dir / "upload_manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2))

        if build_only:
            print(f"[BUILD COMPLETE] Podcast ready for deferred upload: {video_path.name}")
            log_video(
                niche=niche,
                topic=topic,
                format_type="podcast",
                script_title=title,
                video_path=str(video_path),
                uploads=[{"platform": "pending", "status": "built"}],
                duration=assembly_result["duration"],
            )
            return {
                "status": "built",
                "niche": niche,
                "format": "podcast",
                "title": title,
                "video_path": str(video_path),
                "duration": assembly_result["duration"],
                "manifest_path": str(manifest_path),
            }

        # ── Step 8: Upload ────────────────────────────────────
        if dry_run:
            print("[8/8] Dry run - skipping uploads")
            uploads = [{"platform": "dry_run", "status": "skipped"}]
        else:
            print("[8/8] Uploading podcast to platforms...")

            # YouTube Shorts
            yt_result = await upload_to_youtube(
                video_path=str(video_path),
                title=f"🔴🔵 {title}",
                description=description,
                tags=niche_config.get("hashtags", []),
                niche=niche,
                thumbnail_path=str(thumb_path) if thumb_path.exists() else None,
                is_short=True,
                srt_path=voice_result.get("subtitle_path"),
            )
            uploads.append(yt_result)

            # Deep Chill secondary channel
            dc_result = await upload_to_deep_chill(
                video_path=str(video_path),
                title=f"🔴🔵 {title}",
                description=description,
                tags=niche_config.get("hashtags", []),
                niche=niche,
                thumbnail_path=str(thumb_path) if thumb_path.exists() else None,
                is_short=True,
                srt_path=voice_result.get("subtitle_path"),
            )
            uploads.append(dc_result)

            # TikTok — staggered scheduling (first posts now, rest scheduled)
            try:
                tt_result = await upload_to_tiktok(
                    video_path=str(video_path),
                    description=script.get("caption", title),
                    hashtags=niche_config.get("hashtags", []),
                    schedule_time=tiktok_schedule_time,
                )
                uploads.append(tt_result)
            except Exception:
                pass

            # Facebook Reels
            try:
                fb_result = await upload_to_facebook(
                    video_path=str(video_path),
                    title=title,
                    description=description,
                    niche=niche,
                    hashtags=niche_config.get("hashtags", []),
                    is_reel=True,
                    thumbnail_path=str(thumb_path) if thumb_path.exists() else None,
                )
                uploads.append(fb_result)
            except Exception:
                pass

            # Instagram
            try:
                from modules.cloud_storage import upload_to_cloud, is_cloud_storage_configured
                if is_cloud_storage_configured():
                    ig_result = await upload_to_instagram_local(
                        video_path=str(video_path),
                        caption=script.get("caption", title),
                        hashtags=niche_config.get("hashtags", []),
                        upload_to_cloud_fn=upload_to_cloud,
                    )
                else:
                    ig_result = await upload_to_instagram_local(
                        video_path=str(video_path),
                        caption=script.get("caption", title),
                        hashtags=niche_config.get("hashtags", []),
                    )
                uploads.append(ig_result)
            except Exception:
                pass

            uploaded_platforms = [u["platform"] for u in uploads if u.get("status") == "uploaded"]
            print(f"[8/8] Uploaded to: {', '.join(uploaded_platforms) or 'none'}")

            # First comments
            try:
                from modules.engagement_booster import post_first_comments
                await post_first_comments(uploads=uploads, niche=niche)
            except Exception:
                pass

        # Log result
        log_video(
            niche=niche,
            topic=topic,
            format_type="podcast",
            script_title=title,
            video_path=str(video_path),
            uploads=uploads,
            duration=assembly_result["duration"],
        )

        # Cleanup
        for subdir in ["characters"]:
            p = work_dir / subdir
            if p.exists():
                import shutil
                shutil.rmtree(p)

        return {
            "status": "success",
            "niche": niche,
            "format": "podcast",
            "title": title,
            "video_path": str(video_path),
            "duration": assembly_result["duration"],
            "uploads": uploads,
            "character_style": character_style,
        }

    except Exception as e:
        error_msg = f"{type(e).__name__}: {e}"
        print(f"\n[Podcast] FAILED: {error_msg}")
        traceback.print_exc()

        log_video(
            niche=niche,
            topic=topic,
            format_type="podcast",
            script_title=title,
            video_path=None,
            uploads=uploads,
            error=error_msg,
        )

        return {
            "status": "error",
            "niche": niche,
            "format": "podcast",
            "error": error_msg,
        }


async def upload_prebuilt_videos(
    niche_filter: str | None = None,
    format_filter: str | None = None,
) -> list[dict]:
    """
    Find and upload all pre-built videos that haven't been uploaded yet.

    Scans output/ for upload_manifest.json files where uploaded=False.
    Used by the scheduler's upload phase (2 hours after build phase).
    """
    from modules.uploader_youtube import upload_to_youtube, upload_to_deep_chill
    from modules.uploader_tiktok import upload_to_tiktok
    from modules.uploader_twitter import upload_to_twitter
    from modules.uploader_facebook import upload_to_facebook
    from modules.uploader_instagram import upload_to_instagram_local
    from modules.logger import log_video

    results = []
    manifests = sorted(OUTPUT_DIR.glob("*/upload_manifest.json"))

    for manifest_path in manifests:
        try:
            manifest = json.loads(manifest_path.read_text())
        except Exception:
            continue

        if manifest.get("uploaded"):
            continue

        niche = manifest["niche"]
        format_type = manifest["format_type"]
        if niche_filter and niche != niche_filter:
            continue
        if format_filter and format_type != format_filter:
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

        # YouTube
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

        # Facebook
        try:
            fb_result = await upload_to_facebook(
                video_path=str(video_path),
                title=title,
                description=description,
                niche=niche,
                hashtags=tags,
                is_reel=is_short,
                thumbnail_path=str(thumb_path) if thumb_path.exists() else None,
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
        manifest_path.write_text(json.dumps(manifest, indent=2))

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
        formats = ["long", "short", "podcast", "news_anchor"]

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
        schedule = SCHEDULE.get(niche, {"long_form": 1, "shorts": 1})

        for fmt in formats:
            # daily_breakdown niche only runs news_anchor format; skip other formats
            if niche == "daily_breakdown" and fmt != "news_anchor":
                continue
            # Non-daily_breakdown niches skip news_anchor format
            if niche != "daily_breakdown" and fmt == "news_anchor":
                continue

            sched_key = {"long": "long_form", "short": "shorts", "podcast": "podcast", "news_anchor": "shorts"}.get(fmt, "shorts")
            count = schedule.get(sched_key, 1)
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
    parser.add_argument("--niche", choices=list(NICHES.keys()) + ["daily_breakdown"], help="Run specific niche only")
    parser.add_argument("--format", choices=["long", "short", "podcast", "news_anchor"], help="Run specific format only")
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

    if args.upload_prebuilt:
        niche_f = args.niche if args.niche else None
        format_f = args.format if args.format else None
        asyncio.run(upload_prebuilt_videos(niche_f, format_f))
        return

    niches = [args.niche] if args.niche else None
    formats = [args.format] if args.format else None
    build_only = args.build_only

    asyncio.run(run_daily_pipeline(niches, formats, args.dry_run, build_only))


if __name__ == "__main__":
    main()

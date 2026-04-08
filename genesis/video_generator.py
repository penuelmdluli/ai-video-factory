"""
Genesis Content Engine — Video Generator (Brain Studio)

Calls Genesis Studio Brain Studio internal API to generate full productions:
- Multi-shot scenes with AI video generation
- Voiceover (text-to-speech)
- Background music
- Captions burned in
- Full assembly pipeline

Uses /api/internal/brain with CRON_SECRET auth.
"""
import asyncio
import aiohttp
import time
import os
from pathlib import Path

from genesis.genesis_config import GENESIS_STUDIO_URL, BRANDS, OUTPUT_DIR
from genesis.db import save_video, update_video, log_pipeline

from dotenv import load_dotenv
load_dotenv(override=True)
CRON_SECRET = os.getenv("CRON_SECRET", "")


async def generate_video(brand: str, script_data: dict) -> dict | None:
    """Generate a full Brain Studio production for a brand."""
    start = time.time()

    script = script_data["script"]
    script_id = script_data["script_id"]
    hook_line = script_data.get("hook_line", "")

    # Create video record
    video_id = save_video(script_id, brand)

    api_url = f"{GENESIS_STUDIO_URL}/api/internal/brain"
    headers = {
        "Content-Type": "application/json",
        "x-cron-secret": CRON_SECRET,
    }

    try:
        async with aiohttp.ClientSession() as session:
            # ── Step 1: Plan the production ──────────────
            plan_payload = {
                "action": "plan",
                "concept": script,
                "targetDuration": 30,
                "style": "cinematic",
                "aspectRatio": "portrait",
                "voiceover": True,
                "voiceoverVoice": "voice-aria",
                "music": True,
                "captions": True,
                "soundEffects": False,
            }

            async with session.post(api_url, json=plan_payload, headers=headers, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    raise Exception(f"Plan failed ({resp.status}): {error_text[:300]}")

                plan_data = await resp.json()
                production_id = plan_data.get("productionId")
                if not production_id:
                    raise Exception(f"No productionId in plan response: {plan_data}")

            update_video(video_id, production_id=production_id, status="generating")
            est_time = plan_data.get("estimatedTime", 180)
            scene_count = len(plan_data.get("plan", {}).get("scenes", []))
            print(f"    Planned: {production_id} ({scene_count} scenes, ~{est_time}s)")

            # ── Step 2: Start production ─────────────────
            produce_payload = {
                "action": "produce",
                "productionId": production_id,
            }

            async with session.post(api_url, json=produce_payload, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    raise Exception(f"Produce failed ({resp.status}): {error_text[:300]}")

            print(f"    Production started: {production_id}")

            # ── Step 3: Poll for completion ──────────────
            status_payload = {
                "action": "status",
                "productionId": production_id,
            }

            max_polls = 80  # 80 * 15s = 20 minutes max
            last_status = ""
            last_progress = 0

            for attempt in range(max_polls):
                await asyncio.sleep(15)

                try:
                    async with session.post(api_url, json=status_payload, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                        if resp.status != 200:
                            continue

                        status_data = await resp.json()
                        status = status_data.get("status", "")
                        progress = status_data.get("progress", 0)
                        completed_scenes = status_data.get("completedScenes", 0)
                        total_scenes = status_data.get("totalScenes", 0)

                        # Log progress changes
                        if status != last_status or progress != last_progress:
                            scene_info = f" ({completed_scenes}/{total_scenes} scenes)" if total_scenes else ""
                            print(f"    [{brand}] {status} {progress}%{scene_info}")
                            last_status = status
                            last_progress = progress

                        if status == "completed":
                            output_urls = status_data.get("outputVideoUrls", {})
                            if not output_urls:
                                raise Exception("Completed but no outputVideoUrls")

                            # Extract the final assembled video URL
                            if isinstance(output_urls, dict):
                                # Prefer "final" key, fall back to first scene
                                final_path = output_urls.get("final", "")
                                if final_path and final_path.startswith("/api/"):
                                    # Relative API path — build full URL
                                    video_url = f"{GENESIS_STUDIO_URL}{final_path}"
                                elif final_path:
                                    video_url = final_path
                                else:
                                    # No final — use first scene
                                    scene_keys = sorted([k for k in output_urls if k.startswith("scene_")])
                                    video_url = output_urls[scene_keys[0]] if scene_keys else list(output_urls.values())[0]
                            elif isinstance(output_urls, list):
                                video_url = output_urls[0]
                            else:
                                video_url = output_urls

                            # Download video
                            video_filename = f"genesis_{brand}_{video_id}_raw.mp4"
                            video_path = OUTPUT_DIR / video_filename

                            # Pass CRON_SECRET for R2 videos served through /api/videos/
                            dl_headers = {"x-cron-secret": CRON_SECRET} if "/api/videos/" in video_url else {}
                            async with session.get(video_url, headers=dl_headers, timeout=aiohttp.ClientTimeout(total=120)) as dl_resp:
                                if dl_resp.status == 200:
                                    with open(video_path, "wb") as f:
                                        async for chunk in dl_resp.content.iter_chunked(8192):
                                            f.write(chunk)
                                else:
                                    raise Exception(f"Download failed: {dl_resp.status}")

                            update_video(video_id,
                                raw_video_url=video_url,
                                raw_video_path=str(video_path),
                                status="raw_ready"
                            )

                            duration = time.time() - start
                            size_mb = video_path.stat().st_size / (1024 * 1024) if video_path.exists() else 0
                            log_pipeline("video_generate", brand, "success",
                                        f"Brain Studio production complete: {video_path.name} ({size_mb:.1f} MB)", duration)

                            return {
                                "video_id": video_id,
                                "video_url": video_url,
                                "video_path": str(video_path),
                                "production_id": production_id,
                                "script_data": script_data,
                            }

                        elif status == "failed":
                            error = status_data.get("errorMessage", "Unknown error")
                            raise Exception(f"Production failed: {error}")

                except aiohttp.ClientError as ce:
                    if attempt % 4 == 0:
                        print(f"    [{brand}] Poll error (retrying): {ce}")
                    continue

            raise Exception("Timed out waiting for Brain Studio production (20 minutes)")

    except Exception as e:
        duration = time.time() - start
        update_video(video_id, status="failed", error_message=str(e))
        log_pipeline("video_generate", brand, "failed", str(e), duration)
        print(f"  FAIL {BRANDS[brand]['name']}: {e}")
        return None


async def generate_all_videos(scripts: dict) -> dict:
    """Generate Brain Studio productions for all brands."""
    print("\nPHASE 3: Generating Videos (Brain Studio)...")

    results = {}

    for brand, script_data in scripts.items():
        if not script_data:
            print(f"  SKIP {BRANDS[brand]['name']}: No script")
            continue

        print(f"\n  {BRANDS[brand]['name']}:")
        result = await generate_video(brand, script_data)
        results[brand] = result

        if result:
            print(f"  OK {BRANDS[brand]['name']}: Video ready")
        else:
            print(f"  FAIL {BRANDS[brand]['name']}: Production failed")

    return results


if __name__ == "__main__":
    import genesis
    test_script = {
        "script_id": 1,
        "script": "A dramatic financial news broadcast showing stock market charts surging upward, golden light reflecting off Wall Street buildings, traders celebrating as Bitcoin hits new all-time highs. The energy is electric, the market is alive.",
        "hook_line": "The market just did something unprecedented",
        "caption": "MARKET ALERT: The market just did something unprecedented\n\n#Finance #Crypto",
    }
    result = asyncio.run(generate_video("finance", test_script))
    if result:
        print(f"\nSUCCESS: {result['video_path']}")
    else:
        print("\nFAILED")

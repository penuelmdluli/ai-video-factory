"""
Genesis Content Engine — TikTok Poster (Official Content Posting API)

Posts branded videos to TikTok using the official Content Posting API.
No browser automation needed — works fully in the cloud.

Setup required:
1. Create app at https://developers.tiktok.com
2. Request video.publish and video.upload scopes
3. Complete app audit for public posting
4. Store user access token as TIKTOK_ACCESS_TOKEN env var
"""
import asyncio
import aiohttp
import json
import os
import time
import math
from pathlib import Path

from genesis.genesis_config import BRANDS
from genesis.db import save_post, update_post, log_pipeline


TIKTOK_API_BASE = "https://open.tiktokapis.com/v2"
TIKTOK_ACCESS_TOKEN = os.getenv("TIKTOK_ACCESS_TOKEN", "")

# Chunk size for file uploads (10 MB)
CHUNK_SIZE = 10 * 1024 * 1024


async def post_to_tiktok(brand: str, video_data: dict) -> dict | None:
    """Post a branded video to TikTok using the Content Posting API."""
    start = time.time()

    if not TIKTOK_ACCESS_TOKEN:
        log_pipeline("post_tiktok", brand, "skipped", "TIKTOK_ACCESS_TOKEN not set")
        print(f"    TikTok: Skipped (no access token)")
        return None

    video_path = Path(video_data.get("branded_path", ""))
    if not video_path.exists():
        log_pipeline("post_tiktok", brand, "failed", f"Video file not found: {video_path}")
        return None

    script_data = video_data.get("script_data", {})
    hook_line = script_data.get("hook_line", "")
    config = BRANDS[brand]
    hashtags = " ".join(config["hashtags"][:5])

    # TikTok caption: hook + hashtags (max 2200 chars)
    title = f"{hook_line[:150]} {hashtags}"[:2200]

    post_id = save_post(video_data["video_id"], brand, "tiktok", title)

    try:
        file_size = video_path.stat().st_size
        total_chunks = max(1, math.ceil(file_size / CHUNK_SIZE))

        headers = {
            "Authorization": f"Bearer {TIKTOK_ACCESS_TOKEN}",
            "Content-Type": "application/json; charset=UTF-8",
        }

        async with aiohttp.ClientSession() as session:
            # Step 1: Initialize upload
            init_payload = {
                "post_info": {
                    "title": title,
                    "privacy_level": "PUBLIC_TO_EVERYONE",
                    "disable_duet": False,
                    "disable_stitch": False,
                    "disable_comment": False,
                    "is_aigc": True,  # AI-generated content disclosure
                },
                "source_info": {
                    "source": "FILE_UPLOAD",
                    "video_size": file_size,
                    "chunk_size": min(CHUNK_SIZE, file_size),
                    "total_chunk_count": total_chunks,
                },
            }

            async with session.post(
                f"{TIKTOK_API_BASE}/post/publish/video/init/",
                headers=headers,
                json=init_payload,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                init_data = await resp.json()

                if resp.status != 200 or init_data.get("error", {}).get("code") != "ok":
                    error_msg = init_data.get("error", {}).get("message", str(init_data))
                    raise Exception(f"TikTok init failed: {error_msg}")

                publish_id = init_data["data"]["publish_id"]
                upload_url = init_data["data"]["upload_url"]

            # Step 2: Upload video in chunks
            with open(video_path, "rb") as f:
                for chunk_num in range(total_chunks):
                    chunk_data = f.read(CHUNK_SIZE)
                    chunk_start = chunk_num * CHUNK_SIZE
                    chunk_end = chunk_start + len(chunk_data) - 1

                    upload_headers = {
                        "Content-Type": "video/mp4",
                        "Content-Length": str(len(chunk_data)),
                        "Content-Range": f"bytes {chunk_start}-{chunk_end}/{file_size}",
                    }

                    async with session.put(
                        upload_url,
                        headers=upload_headers,
                        data=chunk_data,
                        timeout=aiohttp.ClientTimeout(total=120),
                    ) as upload_resp:
                        if upload_resp.status not in (200, 201, 206):
                            raise Exception(f"TikTok upload chunk {chunk_num} failed: {upload_resp.status}")

            # Step 3: Check publish status
            await asyncio.sleep(3)  # Give TikTok a moment to process

            status_payload = {"publish_id": publish_id}
            for _ in range(10):
                async with session.post(
                    f"{TIKTOK_API_BASE}/post/publish/status/fetch/",
                    headers=headers,
                    json=status_payload,
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as status_resp:
                    status_data = await status_resp.json()
                    pub_status = status_data.get("data", {}).get("status", "")

                    if pub_status == "PUBLISH_COMPLETE":
                        break
                    elif pub_status in ("FAILED", "PUBLISH_FAILED"):
                        fail_reason = status_data.get("data", {}).get("fail_reason", "Unknown")
                        raise Exception(f"TikTok publish failed: {fail_reason}")

                await asyncio.sleep(5)

        # Success
        update_post(post_id,
            platform_post_id=publish_id,
            status="posted",
            posted_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        )

        duration = time.time() - start
        log_pipeline("post_tiktok", brand, "success", f"Posted: {publish_id}", duration)

        return {
            "post_id": post_id,
            "platform_post_id": publish_id,
            "platform": "tiktok",
        }

    except Exception as e:
        duration = time.time() - start
        update_post(post_id, status="failed", error_message=str(e))
        log_pipeline("post_tiktok", brand, "failed", str(e), duration)
        print(f"    TikTok failed for {brand}: {e}")
        return None

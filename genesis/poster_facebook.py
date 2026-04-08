"""
Genesis Content Engine — Facebook Poster

Posts branded videos to Facebook Pages as Reels via Graph API.
Caption = hook line + niche hashtags. NO LINKS EVER.
"""
import asyncio
import aiohttp
import time
from pathlib import Path

from genesis.genesis_config import BRANDS
from genesis.db import save_post, update_post, log_pipeline


GRAPH_API_VERSION = "v19.0"
GRAPH_API_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"


async def post_to_facebook(brand: str, video_data: dict) -> dict | None:
    """Post a branded video to the brand's Facebook page as a Reel."""
    start = time.time()

    config = BRANDS[brand]
    fb = config["facebook"]
    page_id = fb["page_id"]
    access_token = fb["access_token"]

    if not page_id or not access_token:
        log_pipeline("post_facebook", brand, "failed", f"Facebook not configured for {brand}")
        return None

    video_path = Path(video_data.get("branded_path", ""))
    if not video_path.exists():
        log_pipeline("post_facebook", brand, "failed", f"Video file not found: {video_path}")
        return None

    caption = video_data.get("script_data", {}).get("caption", "")

    # Create post record
    post_id = save_post(video_data["video_id"], brand, "facebook", caption)

    try:
        # Use resumable upload for video
        # Step 1: Initialize upload
        async with aiohttp.ClientSession() as session:
            # For Reels, use the video upload endpoint
            init_url = f"{GRAPH_API_BASE}/{page_id}/videos"

            file_size = video_path.stat().st_size

            # Read file
            with open(video_path, "rb") as f:
                video_bytes = f.read()

            # Upload as multipart form
            form = aiohttp.FormData()
            form.add_field("source", video_bytes, filename=video_path.name, content_type="video/mp4")
            form.add_field("description", caption)
            form.add_field("access_token", access_token)

            async with session.post(init_url, data=form, timeout=aiohttp.ClientTimeout(total=300)) as resp:
                resp_data = await resp.json()

                if resp.status != 200:
                    error = resp_data.get("error", {}).get("message", str(resp_data))
                    raise Exception(f"Facebook API error: {error}")

                fb_post_id = resp_data.get("id") or resp_data.get("post_id")

        if not fb_post_id:
            raise Exception(f"No post ID returned: {resp_data}")

        # Update post record
        update_post(post_id,
            platform_post_id=fb_post_id,
            status="posted",
            posted_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        )

        duration = time.time() - start
        log_pipeline("post_facebook", brand, "success", f"Posted: {fb_post_id}", duration)

        return {
            "post_id": post_id,
            "platform_post_id": fb_post_id,
            "platform": "facebook",
        }

    except Exception as e:
        duration = time.time() - start
        update_post(post_id, status="failed", error_message=str(e))
        log_pipeline("post_facebook", brand, "failed", str(e), duration)
        print(f"  ❌ Facebook post failed for {brand}: {e}")
        return None

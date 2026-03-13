"""
Facebook Page Video Uploader — Posts Reels/Videos via Meta Graph API.

Uses resumable upload for videos. Supports posting to multiple pages.
Includes engagement CTAs tailored per niche for better reach.
Requires:
- Meta App (MOTIVATIONS, App ID: 591543017174198) in Live mode
- Page access tokens with pages_manage_posts, pages_read_engagement
"""
import os
import asyncio
import random
import requests
from pathlib import Path

from config import NICHES


# ── Engagement CTAs per niche ─────────────────────────────────
NICHE_ENGAGEMENT_CTAS = {
    "ai_trading": [
        "What's YOUR best AI trading strategy? Drop it below! 👇\n\n🚀 Try TradeRadar AI FREE → https://www.gettraderadar.com",
        "Are you using AI to trade? Comment YES or NO! 🤖\n\n📊 Get FREE AI stock analysis → https://www.gettraderadar.com",
        "What stock should AI analyze next? Comment below! 📈\n\n⚡ Try it FREE → https://www.gettraderadar.com",
        "Tag a friend who needs AI-powered trading insights! 🔥\n\n💡 FREE AI analysis → https://www.gettraderadar.com",
        "Save this for your next trading session! 💰\n\n🤖 TradeRadar AI — Free stock analysis → https://www.gettraderadar.com",
    ],
    "ai_money": [
        "What AI tool are YOU using to make money? Comment below! 💰\n\n📊 Try TradeRadar AI FREE → https://www.gettraderadar.com",
        "Would you try this? Drop a YES in the comments! 🚀\n\n🤖 FREE AI investing tool → https://www.gettraderadar.com",
        "Tag someone who needs this side hustle idea! 💡",
        "Share your AI income story in the comments! 🔥",
        "Save this — you'll want to try it later! ⭐",
    ],
    "tech_news": [
        "Is this exciting or scary? Share your thoughts below!",
        "What tech news surprised you the most this week?",
        "Tag a tech lover who needs to see this!",
        "Do you think AI will change this industry? Comment below!",
        "Save this to stay ahead of the tech curve!",
    ],
    "motivation": [
        "What's YOUR morning routine? Share below!",
        "Type 'I AM READY' if this motivated you!",
        "Tag someone who needs this motivation today!",
        "What's the ONE habit that changed your life? Comment!",
        "Save this for when you need a boost!",
    ],
    "health_wellness": [
        "Have you tried this? Share your experience below!",
        "What's YOUR go-to health tip? Comment!",
        "Tag someone who cares about their health!",
        "Save this for your wellness routine!",
        "What health topic should we cover next? Comment!",
    ],
    "blissful_moments": [
        "What brings YOU peace? Share in the comments!",
        "Tag someone who needs this positivity today!",
        "Type 'GRATEFUL' if this made you smile!",
        "Save this for a moment when you need calm!",
        "What's ONE thing you're thankful for today?",
    ],
}


def _build_engagement_description(description: str, niche: str) -> str:
    """Add engagement CTA + product promotion to the video description."""
    ctas = NICHE_ENGAGEMENT_CTAS.get(niche, NICHE_ENGAGEMENT_CTAS["motivation"])
    cta = random.choice(ctas)

    # Always include TradeRadar website in every video description
    product_line = ""
    if "gettraderadar.com" not in description and "gettraderadar.com" not in cta:
        product_line = "\n\n🌐 Visit us: https://www.gettraderadar.com"

    return f"{description}\n\n{cta}{product_line}"

# ── Configuration ──────────────────────────────────────────
GRAPH_API_VERSION = "v24.0"
GRAPH_API_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"

# Facebook App credentials (MOTIVATIONS app — Live mode)
FB_APP_ID = os.getenv("FB_APP_ID", "591543017174198")

# Page tokens: one per page we post to (long-lived page access tokens)
# Format in .env: FB_PAGE_TOKEN_ai_trading=<token>
# The page ID is also needed: FB_PAGE_ID_ai_trading=<page_id>
def _get_page_config(niche: str) -> dict:
    """Get Facebook page ID and token for a niche."""
    page_id = os.getenv(f"FB_PAGE_ID_{niche}", "")
    page_token = os.getenv(f"FB_PAGE_TOKEN_{niche}", "")
    return {"page_id": page_id, "page_token": page_token}


async def upload_to_facebook(
    video_path: str,
    title: str,
    description: str,
    niche: str = "ai_trading",
    hashtags: list[str] | None = None,
    is_reel: bool = False,
    thumbnail_path: str | None = None,
) -> dict:
    """
    Upload a video to a Facebook Page.

    For short-form content, uploads as a Reel.
    For long-form, uploads as a regular video post.

    Args:
        video_path: Local path to the MP4 file
        title: Video title
        description: Video description
        niche: Niche key to determine which page to post to
        hashtags: Optional hashtags to append
        is_reel: If True, upload as a Reel (short-form)
        thumbnail_path: Optional custom thumbnail image path

    Returns:
        dict with platform, status, post_id, etc.
    """
    config = _get_page_config(niche)
    page_id = config["page_id"]
    page_token = config["page_token"]

    if not page_id or not page_token:
        return {
            "platform": "facebook",
            "status": "skipped",
            "error": f"Facebook page not configured for niche '{niche}'. Set FB_PAGE_ID_{niche} and FB_PAGE_TOKEN_{niche}",
        }

    video_file = Path(video_path)
    if not video_file.exists():
        return {
            "platform": "facebook",
            "status": "failed",
            "error": f"Video file not found: {video_path}",
        }

    # Build description with engagement CTA and hashtags
    full_desc = _build_engagement_description(description, niche)
    if hashtags:
        tags = " ".join(h if h.startswith("#") else f"#{h}" for h in hashtags)
        full_desc = f"{full_desc}\n\n{tags}"

    try:
        if is_reel:
            result = await _upload_reel(page_id, page_token, video_file, title, full_desc)
        else:
            result = await _upload_video(page_id, page_token, video_file, title, full_desc)

        # Set custom thumbnail if available (for video posts — Reels auto-generate)
        if thumbnail_path and result.get("status") == "uploaded" and not is_reel:
            try:
                _set_video_thumbnail(result.get("post_id", ""), page_token, thumbnail_path)
            except Exception as te:
                print(f"[Facebook] Thumbnail set failed (non-critical): {te}")

        return result

    except Exception as e:
        print(f"[Facebook] Upload failed: {e}")
        return {
            "platform": "facebook",
            "status": "failed",
            "error": str(e),
        }


def _set_video_thumbnail(video_id: str, page_token: str, thumbnail_path: str):
    """Set a custom thumbnail on a Facebook video post."""
    if not video_id or not Path(thumbnail_path).exists():
        return

    # Upload thumbnail as a photo then set as video thumbnail
    with open(thumbnail_path, "rb") as f:
        resp = requests.post(
            f"{GRAPH_API_BASE}/{video_id}/thumbnails",
            files={"source": (Path(thumbnail_path).name, f, "image/jpeg")},
            data={
                "is_preferred": "true",
                "access_token": page_token,
            },
            timeout=30,
        )

    if resp.status_code == 200:
        print(f"[Facebook] Custom thumbnail set for video {video_id}")
    else:
        print(f"[Facebook] Thumbnail API: {resp.status_code} {resp.text[:200]}")


async def _upload_video(
    page_id: str,
    page_token: str,
    video_file: Path,
    title: str,
    description: str,
) -> dict:
    """
    Upload a video post to a Facebook Page (long-form).

    Uses chunked resumable upload to handle large files (>100MB).
    Facebook Graph API has a per-request size limit, so we split the file
    into chunks and upload each one sequentially with start_offset tracking.
    """
    file_size = video_file.stat().st_size
    api_url = f"{GRAPH_API_BASE}/{page_id}/videos"

    # Step 1: Initialize resumable upload
    init_resp = requests.post(
        api_url,
        data={
            "upload_phase": "start",
            "file_size": file_size,
            "access_token": page_token,
        },
        timeout=30,
    )
    init_resp.raise_for_status()
    init_data = init_resp.json()
    upload_session_id = init_data["upload_session_id"]
    start_offset = int(init_data.get("start_offset", 0))
    end_offset = int(init_data.get("end_offset", file_size))
    print(f"[Facebook] Upload session started: {upload_session_id[:20]}...")

    # Step 2: Upload in chunks (Facebook tells us the chunk boundaries)
    chunk_num = 0
    with open(video_file, "rb") as f:
        while start_offset < file_size:
            chunk_size = end_offset - start_offset
            f.seek(start_offset)
            chunk_data = f.read(chunk_size)
            chunk_num += 1

            transfer_resp = requests.post(
                api_url,
                data={
                    "upload_phase": "transfer",
                    "upload_session_id": upload_session_id,
                    "start_offset": start_offset,
                    "access_token": page_token,
                },
                files={"video_file_chunk": (video_file.name, chunk_data, "video/mp4")},
                timeout=300,
            )
            transfer_resp.raise_for_status()
            transfer_data = transfer_resp.json()

            # Facebook returns next chunk boundaries
            start_offset = int(transfer_data.get("start_offset", file_size))
            end_offset = int(transfer_data.get("end_offset", file_size))
            pct = min(100, int(start_offset / file_size * 100))
            print(f"[Facebook] Chunk {chunk_num} uploaded ({pct}%)")

    print(f"[Facebook] Video uploaded ({file_size / 1024 / 1024:.1f}MB) in {chunk_num} chunks")

    # Step 3: Finish upload and publish
    finish_resp = requests.post(
        api_url,
        data={
            "upload_phase": "finish",
            "upload_session_id": upload_session_id,
            "title": title[:255],
            "description": description[:8000],
            "access_token": page_token,
        },
        timeout=60,
    )
    finish_resp.raise_for_status()
    result = finish_resp.json()
    video_id = result.get("id") or result.get("video_id")

    print(f"[Facebook] Video published: {video_id}")
    return {
        "platform": "facebook",
        "status": "uploaded",
        "post_id": video_id,
        "page_id": page_id,
        "type": "video",
    }


async def _upload_reel(
    page_id: str,
    page_token: str,
    video_file: Path,
    title: str,
    description: str,
) -> dict:
    """Upload a Reel to a Facebook Page (short-form)."""
    # Step 1: Initialize Reel upload
    init_url = f"{GRAPH_API_BASE}/{page_id}/video_reels"
    init_resp = requests.post(
        init_url,
        data={
            "upload_phase": "start",
            "access_token": page_token,
        },
        timeout=30,
    )
    init_resp.raise_for_status()
    video_id = init_resp.json()["video_id"]
    print(f"[Facebook] Reel upload started: {video_id}")

    # Step 2: Upload file binary via rupload endpoint
    file_size = video_file.stat().st_size
    upload_url = f"https://rupload.facebook.com/video-upload/{GRAPH_API_VERSION}/{video_id}"
    with open(video_file, "rb") as f:
        upload_resp = requests.post(
            upload_url,
            headers={
                "Authorization": f"OAuth {page_token}",
                "offset": "0",
                "file_size": str(file_size),
            },
            data=f.read(),
            timeout=300,
        )
    upload_resp.raise_for_status()
    print(f"[Facebook] Reel uploaded ({file_size / 1024 / 1024:.1f}MB)")

    # Step 3: Publish the Reel
    publish_url = f"{GRAPH_API_BASE}/{page_id}/video_reels"
    publish_resp = requests.post(
        publish_url,
        data={
            "upload_phase": "finish",
            "video_id": video_id,
            "video_state": "PUBLISHED",
            "title": title[:255],
            "description": description[:8000],
            "access_token": page_token,
        },
        timeout=60,
    )
    if publish_resp.status_code != 200:
        print(f"[Facebook] Reel publish error: {publish_resp.status_code} {publish_resp.text[:300]}")
        # Fallback: try publishing as a regular video post instead
        fallback_resp = requests.post(
            f"{GRAPH_API_BASE}/{page_id}/videos",
            data={
                "file_url": f"https://graph.facebook.com/{video_id}",
                "title": title[:255],
                "description": description[:8000],
                "access_token": page_token,
            },
            timeout=30,
        )
        if fallback_resp.status_code == 200:
            result = fallback_resp.json()
            post_id = result.get("id") or video_id
            print(f"[Facebook] Published as video post (fallback): {post_id}")
            return {
                "platform": "facebook",
                "status": "uploaded",
                "post_id": post_id,
                "page_id": page_id,
                "type": "video",
            }
        publish_resp.raise_for_status()

    result = publish_resp.json()
    post_id = result.get("id") or result.get("post_id") or video_id

    print(f"[Facebook] Reel published: {post_id}")
    return {
        "platform": "facebook",
        "status": "uploaded",
        "post_id": post_id,
        "page_id": page_id,
        "type": "reel",
    }


async def upload_to_all_facebook_pages(
    video_path: str,
    title: str,
    description: str,
    niche: str,
    hashtags: list[str] | None = None,
    is_reel: bool = False,
) -> list[dict]:
    """Upload video to all configured Facebook pages for a niche."""
    results = []
    result = await upload_to_facebook(
        video_path=video_path,
        title=title,
        description=description,
        niche=niche,
        hashtags=hashtags,
        is_reel=is_reel,
    )
    results.append(result)
    return results

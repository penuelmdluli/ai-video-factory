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

from config import NICHES, get_website_url


# ── Engagement CTAs per niche ─────────────────────────────────
NICHE_ENGAGEMENT_CTAS = {
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
    "daily_breakdown": [
        "What's YOUR take on this story? Comment below!",
        "Did this surprise you? Share your thoughts!",
        "Tag someone who needs to see this breakdown!",
        "What topic should we break down next? Comment!",
        "Save this for your daily news update!",
    ],
    "shopmo_products": [
        "Have you tried this product? Drop a review below! 🛒\n\n🌐 Shop now: https://shopmoo.co.za",
        "Tag a friend who needs this deal! 🔥\n\n🛍️ Browse more: https://shopmoo.co.za",
        "Would you buy this? Comment YES or NO! 💰\n\n🌐 Visit ShopMO: https://shopmoo.co.za",
        "Save this for your next shopping spree! 🛒\n\n🛍️ ShopMO: https://shopmoo.co.za",
        "What product should we feature next? Comment below! 📦\n\n🌐 https://shopmoo.co.za",
    ],
    "limitless_you": [
        "AI says the #1 habit of high performers is ___. What do YOU think it is? Comment below!",
        "Type 'LIMITLESS' if you're ready for AI-powered growth!",
        "Tag someone who needs an AI coach in their life!",
        "Which area should AI analyze next? A) Morning routine B) Focus C) Habits — Comment!",
        "Save this — your AI coach just dropped knowledge!",
    ],
}


def _build_engagement_description(niche: str, description: str) -> str:
    """Pure content — no links, no affiliate promotions. Just the description."""
    return description

# ── Configuration ──────────────────────────────────────────
GRAPH_API_VERSION = "v24.0"
GRAPH_API_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"

# Facebook App credentials (MOTIVATIONS app — Live mode)
FB_APP_ID = os.getenv("FB_APP_ID", "591543017174198")

# Page tokens: one per page we post to (long-lived page access tokens)
# Format in .env: FB_PAGE_TOKEN_<niche>=<token>
# The page ID is also needed: FB_PAGE_ID_<niche>=<page_id>
def _get_page_config(niche: str) -> dict:
    """Get Facebook page ID and token for a niche."""
    page_id = os.getenv(f"FB_PAGE_ID_{niche}", "")
    page_token = os.getenv(f"FB_PAGE_TOKEN_{niche}", "")
    return {"page_id": page_id, "page_token": page_token}


async def upload_to_facebook(
    video_path: str,
    title: str,
    description: str,
    niche: str = "ai_money",
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
    # Locked page guard: blissful_moments is SAGA OF THE NORTH and only
    # post_next_viking.py may post there. Everything else is refused here.
    from config import page_locked, LOCKED_PAGES
    if page_locked(niche):
        print(f"[Facebook] BLOCKED: '{niche}' page is locked to {LOCKED_PAGES[niche]} — not posting")
        return {
            "platform": "facebook",
            "status": "skipped",
            "error": f"page '{niche}' locked to {LOCKED_PAGES[niche]}",
        }

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
    full_desc = _build_engagement_description(niche, description)
    if hashtags:
        tags = " ".join(h if h.startswith("#") else f"#{h}" for h in hashtags)
        full_desc = f"{full_desc}\n\n{tags}"

    # Reel format guard: reels MUST be vertical (9:16). Refuse a landscape file as a
    # reel (it either fails to publish or looks wrong) so the caller notices.
    if is_reel:
        try:
            from moviepy import VideoFileClip as _VFC
            with _VFC(str(video_file)) as _v:
                if _v.size[0] > _v.size[1]:
                    return {"platform": "facebook", "status": "failed",
                            "error": f"Reel must be vertical 9:16; got {_v.size[0]}x{_v.size[1]} (landscape). "
                                     "Pass the SHORT vertical clip, not the long-form."}
        except Exception:
            pass  # if probe fails, proceed and let Facebook validate

    try:
        if is_reel:
            result = await _upload_reel(page_id, page_token, video_file, title, full_desc, thumbnail_path)
        else:
            result = await _upload_video(page_id, page_token, video_file, title, full_desc)

        # Set custom cover/thumbnail (video posts here; Reels set it inside _upload_reel)
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
    session_video_id = init_data.get("video_id", "")   # the finish step only
    start_offset = int(init_data.get("start_offset", 0))  # returns success:true
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
    video_id = result.get("id") or result.get("video_id") or session_video_id

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
    thumbnail_path: str | None = None,
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
                "video_id": video_id,   # comments must target THIS id, not post_id
                "page_id": page_id,
                "type": "video",
            }
        publish_resp.raise_for_status()

    result = publish_resp.json()
    post_id = result.get("id") or result.get("post_id") or video_id

    print(f"[Facebook] Reel published: {post_id}")

    # Set our generated thumbnail as the Reel COVER (otherwise FB picks a random
    # frame). Reels accept a preferred thumbnail via the video_id/thumbnails edge.
    try:
        from config import SET_CUSTOM_THUMBNAIL as _SET_THUMB
    except Exception:
        _SET_THUMB = False
    if _SET_THUMB and thumbnail_path and Path(thumbnail_path).exists():
        try:
            with open(thumbnail_path, "rb") as f:
                cover_resp = requests.post(
                    f"{GRAPH_API_BASE}/{video_id}/thumbnails",
                    data={"is_preferred": "true", "access_token": page_token},
                    files={"source": (Path(thumbnail_path).name, f, "image/jpeg")},
                    timeout=60,
                )
            if cover_resp.status_code == 200:
                print(f"[Facebook] Reel cover set from {Path(thumbnail_path).name}")
            else:
                print(f"[Facebook] Reel cover not set ({cover_resp.status_code}): {cover_resp.text[:150]}")
        except Exception as ce:
            print(f"[Facebook] Reel cover error (non-critical): {ce}")

    return {
        "platform": "facebook",
        "status": "uploaded",
        "post_id": post_id,
        "video_id": video_id,   # comments must target THIS id — commenting on a
        "page_id": page_id,     # reel's post_id 400s ("singular statuses API")
        "type": "reel",
    }


async def upload_photo(image_path: str, caption: str, niche: str) -> dict:
    """
    Post a single photo to the page feed (lineup cards, result cards).
    Returns {"status": "uploaded", "photo_id", "post_id"} on success.
    """
    try:
        cfg = _get_page_config(niche)
    except Exception as e:
        return {"platform": "facebook", "status": "failed", "error": f"no page config: {e}"}
    p = Path(image_path)
    if not p.exists():
        return {"platform": "facebook", "status": "failed", "error": f"missing {image_path}"}
    try:
        with open(p, "rb") as f:
            resp = requests.post(
                f"{GRAPH_API_BASE}/{cfg['page_id']}/photos",
                data={"message": caption, "access_token": cfg["page_token"]},
                files={"source": (p.name, f, "image/png")},
                timeout=120,
            )
        if resp.status_code == 200:
            j = resp.json()
            print(f"[Facebook] Photo posted: {j.get('post_id') or j.get('id')}")
            return {"platform": "facebook", "status": "uploaded",
                    "photo_id": j.get("id"), "post_id": j.get("post_id") or j.get("id")}
        print(f"[Facebook] Photo failed ({resp.status_code}): {resp.text[:200]}")
        return {"platform": "facebook", "status": "failed", "error": resp.text[:200]}
    except Exception as e:
        return {"platform": "facebook", "status": "failed", "error": str(e)}


async def post_comment(object_id: str, message: str, niche: str) -> dict:
    """
    Comment on a page post/reel AS the page (first-comment engagement, link
    drops, etc.). object_id is the post_id/video_id returned by the uploaders.
    """
    try:
        cfg = _get_page_config(niche)
    except Exception as e:
        return {"status": "failed", "error": f"no page config: {e}"}
    try:
        resp = requests.post(
            f"{GRAPH_API_BASE}/{object_id}/comments",
            data={"message": message, "access_token": cfg["page_token"]},
            timeout=30,
        )
        if resp.status_code == 200:
            cid = resp.json().get("id", "")
            print(f"[Facebook] Comment posted: {cid}")
            return {"status": "posted", "comment_id": cid}
        print(f"[Facebook] Comment failed ({resp.status_code}): {resp.text[:200]}")
        return {"status": "failed", "error": resp.text[:200]}
    except Exception as e:
        print(f"[Facebook] Comment error: {e}")
        return {"status": "failed", "error": str(e)}


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

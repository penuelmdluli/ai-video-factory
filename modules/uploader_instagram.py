"""
Instagram Reels Uploader — Posts via Meta Graph API.

Requirements:
- Instagram Business Account connected to a Facebook Page
- Meta App with instagram_content_publish permission
- Long-lived access token
"""
import time
import requests

from config import INSTAGRAM_ACCESS_TOKEN, INSTAGRAM_USER_ID


GRAPH_API_BASE = "https://graph.facebook.com/v19.0"


async def upload_to_instagram(
    video_url: str,
    caption: str,
    hashtags: list[str] | None = None,
) -> dict:
    """
    Upload a Reel to Instagram via Graph API.

    IMPORTANT: video_url must be a publicly accessible direct URL to the video file.
    Use a hosting service (S3, Google Cloud Storage, etc.) to make the video accessible.

    Args:
        video_url: Public URL to the video file (must be direct link, no auth)
        caption: Reel caption
        hashtags: List of hashtags to append

    Returns:
        dict with platform, status, post_id, etc.
    """
    if not INSTAGRAM_ACCESS_TOKEN or not INSTAGRAM_USER_ID:
        return {
            "platform": "instagram",
            "status": "skipped",
            "error": "Instagram credentials not configured",
        }

    # Build caption with hashtags
    full_caption = caption
    if hashtags:
        tags = " ".join(h if h.startswith("#") else f"#{h}" for h in hashtags)
        full_caption = f"{caption}\n\n{tags}"
    full_caption = full_caption[:2200]  # IG caption limit

    try:
        # Step 1: Create media container
        create_url = f"{GRAPH_API_BASE}/{INSTAGRAM_USER_ID}/media"
        create_params = {
            "media_type": "REELS",
            "video_url": video_url,
            "caption": full_caption,
            "access_token": INSTAGRAM_ACCESS_TOKEN,
        }
        create_resp = requests.post(create_url, params=create_params, timeout=30)
        create_resp.raise_for_status()
        creation_id = create_resp.json()["id"]

        print(f"[Instagram] Media container created: {creation_id}")

        # Step 2: Wait for processing (poll status)
        status_url = f"{GRAPH_API_BASE}/{creation_id}"
        for attempt in range(30):  # Max 5 minutes (30 * 10s)
            time.sleep(10)
            status_resp = requests.get(
                status_url,
                params={
                    "fields": "status_code",
                    "access_token": INSTAGRAM_ACCESS_TOKEN,
                },
                timeout=15,
            )
            status_data = status_resp.json()
            status_code = status_data.get("status_code", "")

            if status_code == "FINISHED":
                break
            elif status_code == "ERROR":
                return {
                    "platform": "instagram",
                    "status": "failed",
                    "error": f"Media processing failed: {status_data}",
                }
            print(f"[Instagram] Processing... (attempt {attempt + 1}/30, status: {status_code})")
        else:
            return {
                "platform": "instagram",
                "status": "failed",
                "error": "Media processing timed out after 5 minutes",
            }

        # Step 3: Publish
        publish_url = f"{GRAPH_API_BASE}/{INSTAGRAM_USER_ID}/media_publish"
        publish_params = {
            "creation_id": creation_id,
            "access_token": INSTAGRAM_ACCESS_TOKEN,
        }
        publish_resp = requests.post(publish_url, params=publish_params, timeout=30)
        publish_resp.raise_for_status()
        post_id = publish_resp.json().get("id")

        print(f"[Instagram] Published Reel: {post_id}")

        return {
            "platform": "instagram",
            "status": "uploaded",
            "post_id": post_id,
        }

    except Exception as e:
        print(f"[Instagram] Upload failed: {e}")
        return {
            "platform": "instagram",
            "status": "failed",
            "error": str(e),
        }


async def upload_to_instagram_local(
    video_path: str,
    caption: str,
    hashtags: list[str] | None = None,
    upload_to_cloud_fn=None,
) -> dict:
    """
    Upload a local video to Instagram by first hosting it, then using Graph API.

    Args:
        video_path: Local path to video file
        caption: Reel caption
        hashtags: Hashtags list
        upload_to_cloud_fn: Async function(local_path) -> public_url
            Must upload the file and return a public URL

    Returns:
        Upload result dict
    """
    if upload_to_cloud_fn is None:
        return {
            "platform": "instagram",
            "status": "skipped",
            "error": "No cloud upload function provided. Instagram requires a public video URL.",
        }

    try:
        public_url = await upload_to_cloud_fn(video_path)
        return await upload_to_instagram(public_url, caption, hashtags)
    except Exception as e:
        return {
            "platform": "instagram",
            "status": "failed",
            "error": str(e),
        }

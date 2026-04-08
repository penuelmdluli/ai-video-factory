"""
Genesis Content Engine — YouTube Poster

Posts branded videos to YouTube as Shorts using existing OAuth tokens.
Title = hook line. Description = hashtags only. No links.
"""
import json
import time
from pathlib import Path

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

from genesis.genesis_config import BRANDS
from genesis.db import save_post, update_post, log_pipeline


YOUTUBE_SCOPES = [
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]


import os

# Maps brand niche_key to env var name for cloud token loading
_YT_TOKEN_ENV = {
    "tech_news": "YT_TOKEN_TECH_NEWS",
    "ai_money": "YT_TOKEN_AI_MONEY",
    "motivation": "YT_TOKEN_MOTIVATION",
    "blissful_moments": "YT_TOKEN_BLISSFUL_MOMENTS",
}


def _get_credentials(brand: str) -> Credentials | None:
    """Get YouTube credentials for a brand, refreshing if needed.

    Tries two methods:
    1. Token file on disk (local development)
    2. Environment variable with JSON token (cloud / GitHub Actions)
    """
    config = BRANDS[brand]
    niche_key = config.get("niche_key", brand)
    token_file = config["youtube"]["token_file"]

    creds = None

    # Method 1: Token file on disk
    if token_file.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(token_file), YOUTUBE_SCOPES)
        except Exception as e:
            print(f"  YouTube token file error for {brand}: {e}")

    # Method 2: Environment variable (cloud runs)
    if not creds:
        env_key = _YT_TOKEN_ENV.get(niche_key, "")
        token_json = os.getenv(env_key, "")
        if token_json:
            try:
                import json as _json
                token_data = _json.loads(token_json)
                creds = Credentials.from_authorized_user_info(token_data, YOUTUBE_SCOPES)
            except Exception as e:
                print(f"  YouTube env token error for {brand}: {e}")

    if not creds:
        print(f"  YouTube credentials not found for {brand}")
        return None

    try:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            # Save refreshed token back to file if possible
            if token_file.parent.exists():
                try:
                    with open(token_file, "w") as f:
                        f.write(creds.to_json())
                except Exception:
                    pass  # Can't save in cloud, that's fine

        if not creds.valid:
            return None

        return creds
    except Exception as e:
        print(f"  YouTube auth refresh error for {brand}: {e}")
        return None


def post_to_youtube(brand: str, video_data: dict) -> dict | None:
    """Post a branded video to YouTube as a Short."""
    start = time.time()

    creds = _get_credentials(brand)
    if not creds:
        log_pipeline("post_youtube", brand, "failed", "YouTube credentials not available")
        return None

    video_path = Path(video_data.get("branded_path", ""))
    if not video_path.exists():
        log_pipeline("post_youtube", brand, "failed", f"Video file not found: {video_path}")
        return None

    script_data = video_data.get("script_data", {})
    hook_line = script_data.get("hook_line", "")
    caption = script_data.get("caption", "")
    config = BRANDS[brand]

    # YouTube Short title: hook line + #Shorts
    title = f"{hook_line[:90]} #Shorts" if hook_line else f"{config['name']} #Shorts"

    # Description: hashtags only, no links
    description = " ".join(config["hashtags"])

    # Tags
    tags = [tag.replace("#", "") for tag in config["hashtags"]] + ["Shorts", "AI", "Genesis"]

    post_id = save_post(video_data["video_id"], brand, "youtube", title)

    try:
        youtube = build("youtube", "v3", credentials=creds)

        body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": tags,
                "categoryId": "24",  # Entertainment
            },
            "status": {
                "privacyStatus": "public",
                "selfDeclaredMadeForKids": False,
            },
        }

        media = MediaFileUpload(
            str(video_path),
            mimetype="video/mp4",
            resumable=True,
            chunksize=1024 * 1024 * 5,  # 5MB chunks
        )

        request = youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media,
        )

        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                progress = int(status.progress() * 100)
                if progress % 25 == 0:
                    print(f"    📤 YouTube upload {brand}: {progress}%")

        yt_video_id = response.get("id", "")

        if not yt_video_id:
            raise Exception(f"No video ID in YouTube response: {response}")

        update_post(post_id,
            platform_post_id=yt_video_id,
            status="posted",
            posted_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        )

        duration = time.time() - start
        log_pipeline("post_youtube", brand, "success", f"Posted: https://youtube.com/shorts/{yt_video_id}", duration)

        return {
            "post_id": post_id,
            "platform_post_id": yt_video_id,
            "platform": "youtube",
            "url": f"https://youtube.com/shorts/{yt_video_id}",
        }

    except Exception as e:
        duration = time.time() - start
        update_post(post_id, status="failed", error_message=str(e))
        log_pipeline("post_youtube", brand, "failed", str(e), duration)
        print(f"  ❌ YouTube post failed for {brand}: {e}")
        return None


async def post_all_youtube(videos: dict) -> dict:
    """Post all branded videos to YouTube."""
    results = {}
    for brand, video_data in videos.items():
        if not video_data:
            continue
        result = post_to_youtube(brand, video_data)
        results[brand] = result
    return results

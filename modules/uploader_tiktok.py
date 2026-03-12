"""
TikTok Uploader — Posts videos to TikTok via browser automation.

Uses tiktok-uploader (Selenium-based) since the official API is hard to get approved.
Requires browser cookies exported from an authenticated TikTok session.
"""
from pathlib import Path

from config import TOKENS_DIR

COOKIES_PATH = TOKENS_DIR / "tiktok_cookies.txt"


async def upload_to_tiktok(
    video_path: str,
    description: str,
    hashtags: list[str] | None = None,
    schedule: str | None = None,
) -> dict:
    """
    Upload a video to TikTok.

    Args:
        video_path: Path to the video file (9:16 vertical)
        description: Video caption
        hashtags: List of hashtags to append
        schedule: Optional schedule time (ISO format)

    Returns:
        dict with platform, status, etc.
    """
    if not COOKIES_PATH.exists():
        return {
            "platform": "tiktok",
            "status": "skipped",
            "error": f"Cookies not found at {COOKIES_PATH}. Export cookies from browser.",
        }

    try:
        from tiktok_uploader.upload import upload_video

        # Build description with hashtags
        full_description = description
        if hashtags:
            tags_str = " ".join(h if h.startswith("#") else f"#{h}" for h in hashtags)
            full_description = f"{description}\n\n{tags_str}"

        # Truncate to TikTok's limit (~2200 chars)
        full_description = full_description[:2200]

        upload_video(
            filename=video_path,
            description=full_description,
            cookies=str(COOKIES_PATH),
            headless=True,
        )

        print(f"[TikTok] Uploaded: {Path(video_path).name}")

        return {
            "platform": "tiktok",
            "status": "uploaded",
            "description": full_description[:100],
        }

    except Exception as e:
        print(f"[TikTok] Upload failed: {e}")
        return {
            "platform": "tiktok",
            "status": "failed",
            "error": str(e),
        }


async def upload_batch_to_tiktok(videos: list[dict]) -> list[dict]:
    """
    Upload multiple videos to TikTok.

    Args:
        videos: List of {path, description, hashtags}

    Returns:
        List of upload results
    """
    if not COOKIES_PATH.exists():
        return [{"platform": "tiktok", "status": "skipped", "error": "No cookies"}]

    try:
        from tiktok_uploader.upload import upload_videos

        upload_list = []
        for v in videos:
            desc = v["description"]
            if v.get("hashtags"):
                tags = " ".join(h if h.startswith("#") else f"#{h}" for h in v["hashtags"])
                desc = f"{desc}\n\n{tags}"

            entry = {"path": v["path"], "description": desc[:2200]}
            if v.get("schedule"):
                entry["schedule"] = v["schedule"]
            upload_list.append(entry)

        upload_videos(
            videos=upload_list,
            cookies=str(COOKIES_PATH),
            headless=True,
        )

        return [
            {"platform": "tiktok", "status": "uploaded", "path": v["path"]}
            for v in upload_list
        ]

    except Exception as e:
        print(f"[TikTok] Batch upload failed: {e}")
        return [{"platform": "tiktok", "status": "failed", "error": str(e)}]

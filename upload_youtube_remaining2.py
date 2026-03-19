"""Upload the 2 remaining videos (blissful_moments + motivation) that hit quota.
Run after YouTube API quota resets (midnight Pacific Time).

Usage: python upload_youtube_remaining2.py
"""
import asyncio
import sys
import os

os.environ["PYTHONIOENCODING"] = "utf-8"
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(__file__))

from pathlib import Path
from modules.uploader_youtube import upload_to_youtube

VIDEOS = {
    "blissful_moments": {
        "title": "This 6-Second Act Will Restore Your Faith in Humanity",
        "dir": "blissful_moments_podcast_20260311_162113",
        "description": (
            "A stranger did something in just 6 seconds that changed everything. "
            "Our baby podcasters share the most heartwarming stories that prove "
            "humanity is still beautiful.\n\n"
            "Subscribe for daily doses of positivity and inspiration!"
        ),
        "tags": [
            "BlissfulMoments", "Kindness", "Humanity", "Heartwarming", "Positivity",
            "GoodVibes", "FaithInHumanity", "Inspiration", "Wholesome", "FeelGood",
        ],
    },
    "motivation": {
        "title": "This 30-Day Productivity Hack Beats 5 AM Routines",
        "dir": "motivation_podcast_20260311_162112",
        "description": (
            "Forget waking up at 5 AM. This 30-day productivity experiment proved "
            "there is a way better approach to getting things done. Our baby "
            "motivators explain what actually works.\n\n"
            "Subscribe for daily motivation and mindset tips!"
        ),
        "tags": [
            "Motivation", "Mindset", "Success", "DailyMotivation", "Discipline",
            "GrindMode", "NeverGiveUp", "SuccessMindset", "SelfImprovement", "Hustle",
        ],
    },
}

OUTPUT_DIR = Path(__file__).parent / "output"


async def upload_remaining():
    for niche, info in VIDEOS.items():
        video_dir = OUTPUT_DIR / info["dir"]
        video_path = video_dir / "final_podcast.mp4"
        srt_path = video_dir / "podcast_captions.srt"
        thumb_path = video_dir / "thumbnail.jpg"

        if not video_path.exists():
            print(f"[SKIP] {niche}: Video not found")
            continue

        yt_title = f"\U0001f534\U0001f535 {info['title']}"
        if len(yt_title) > 93:
            yt_title = yt_title[:93]
        yt_title += " #Shorts"

        size_mb = video_path.stat().st_size / (1024 * 1024)
        print(f"[UPLOADING] {niche}: {info['title']} ({size_mb:.1f}MB)")

        result = await upload_to_youtube(
            video_path=str(video_path),
            title=yt_title,
            description=info["description"],
            tags=info["tags"],
            niche=niche,
            thumbnail_path=str(thumb_path) if thumb_path.exists() else None,
            is_short=True,
            srt_path=str(srt_path) if srt_path.exists() else None,
        )

        status = result.get("status", "unknown")
        url = result.get("url", result.get("error", ""))
        print(f"  [{status}] {url}\n")


if __name__ == "__main__":
    asyncio.run(upload_remaining())

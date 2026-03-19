"""Upload remaining YouTube videos (skip ai_trading + ai_money which are already done)."""
import asyncio
import sys
import os

os.environ["PYTHONIOENCODING"] = "utf-8"
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(__file__))

from pathlib import Path
from modules.uploader_youtube import upload_to_youtube

ALREADY_UPLOADED = {"ai_trading", "ai_money"}  # Already on YouTube

VIDEOS = {
    "tech_news": {
        "title": "New AI Can Replace 40% of Jobs (Companies Already Using It)",
        "dir": "tech_news_podcast_20260311_162112",
        "description": "OpenAI just dropped a new model that can handle 40 percent of all jobs and companies are already replacing workers with it. Our baby tech reporters have the full breakdown.\n\nSubscribe for daily AI and tech news updates!",
        "tags": ["AI", "TechNews", "ArtificialIntelligence", "Technology", "AINews", "Innovation", "FutureTech", "MachineLearning", "Tech", "AIUpdate"],
    },
    "health_wellness": {
        "title": "This Ancient Spice Is Better Than Most Painkillers",
        "dir": "health_wellness_podcast_20260311_162112",
        "description": "Turmeric might actually be more effective than prescription painkillers according to new studies. Our baby health experts break down the science and what you need to know.\n\nSubscribe for natural health tips and wellness secrets!",
        "tags": ["Health", "Wellness", "NaturalRemedies", "Turmeric", "Herbal", "HealthTips", "NaturalHealth", "HolisticHealth", "AntiInflammatory", "HealthyLiving"],
    },
    "blissful_moments": {
        "title": "This 6-Second Act Will Restore Your Faith in Humanity",
        "dir": "blissful_moments_podcast_20260311_162113",
        "description": "A stranger did something in just 6 seconds that changed everything. Our baby podcasters share the most heartwarming stories that prove humanity is still beautiful.\n\nSubscribe for daily doses of positivity and inspiration!",
        "tags": ["BlissfulMoments", "Kindness", "Humanity", "Heartwarming", "Positivity", "GoodVibes", "FaithInHumanity", "Inspiration", "Wholesome", "FeelGood"],
    },
    "motivation": {
        "title": "This 30-Day Productivity Hack Beats 5 AM Routines",
        "dir": "motivation_podcast_20260311_162112",
        "description": "Forget waking up at 5 AM. This 30-day productivity experiment proved there is a way better approach to getting things done. Our baby motivators explain what actually works.\n\nSubscribe for daily motivation and mindset tips!",
        "tags": ["Motivation", "Mindset", "Success", "DailyMotivation", "Discipline", "GrindMode", "NeverGiveUp", "SuccessMindset", "SelfImprovement", "Hustle"],
    },
}

OUTPUT_DIR = Path(__file__).parent / "output"


async def main():
    for niche, info in VIDEOS.items():
        if niche in ALREADY_UPLOADED:
            print(f"[SKIP] {niche}: Already uploaded")
            continue

        video_dir = OUTPUT_DIR / info["dir"]
        video_path = video_dir / "final_podcast.mp4"
        thumb_path = video_dir / "thumbnail.jpg"
        srt_path = video_dir / "podcast_captions.srt"

        if not video_path.exists():
            print(f"[SKIP] {niche}: Video not found")
            continue

        yt_title = f"\U0001f534\U0001f535 {info['title']}"
        if len(yt_title) > 93:
            yt_title = yt_title[:93]
        yt_title += " #Shorts"

        size_mb = video_path.stat().st_size / (1024 * 1024)
        print(f"[UPLOADING] {niche}: {info['title']} ({size_mb:.0f}MB)")
        sys.stdout.flush()

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

        status = result.get("status", "?")
        url = result.get("url", result.get("error", ""))
        print(f"  -> [{status}] {url}")
        sys.stdout.flush()

    print("\nDONE - All remaining YouTube uploads complete!")


asyncio.run(main())

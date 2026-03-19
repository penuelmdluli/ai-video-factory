"""
Batch YouTube Upload — Upload all 6 baby podcast videos as Shorts.
Run: python upload_youtube_batch.py
"""
import asyncio
import sys
import os

# Fix Windows encoding for emoji output
os.environ["PYTHONIOENCODING"] = "utf-8"
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(__file__))

from pathlib import Path
from modules.uploader_youtube import upload_to_youtube

# Production video data from 2026-03-11 pipeline run
VIDEOS = {
    "ai_trading": {
        "title": "AI Turned 10k into 13.8k in Weeks? (The Catch!)",
        "dir": "ai_trading_podcast_20260311_162112",
        "description": (
            "Two baby AI traders break down how artificial intelligence turned a "
            "10K portfolio into 13.8K - but there is a catch nobody talks about. "
            "Watch this before you trust any AI trading bot with your money.\n\n"
            "Subscribe for daily AI trading insights and market analysis!"
        ),
        "tags": [
            "AITrading", "StockMarket", "Crypto", "Trading", "DayTrading",
            "AI", "Finance", "Investing", "TradingBot", "Stocks", "TradeRadarAI",
        ],
    },
    "ai_money": {
        "title": "She Made $43K From AI Copywriting (Everyone Is Mad)",
        "dir": "ai_money_podcast_20260311_162112",
        "description": (
            "A 22-year-old made 43 thousand dollars using AI copywriting tools and "
            "the internet lost it. Our baby podcasters break down exactly how she "
            "did it and whether you can too.\n\n"
            "Subscribe for the best AI money-making strategies!"
        ),
        "tags": [
            "AI", "MakeMoneyOnline", "SideHustle", "PassiveIncome", "AITools",
            "Entrepreneur", "OnlineBusiness", "ChatGPT", "AISideHustle", "DigitalBusiness",
        ],
    },
    "tech_news": {
        "title": "New AI Can Replace 40% of Jobs (Companies Already Using It)",
        "dir": "tech_news_podcast_20260311_162112",
        "description": (
            "OpenAI just dropped a new model that can handle 40 percent of all jobs "
            "and companies are already replacing workers with it. Our baby tech "
            "reporters have the full breakdown.\n\n"
            "Subscribe for daily AI and tech news updates!"
        ),
        "tags": [
            "AI", "TechNews", "ArtificialIntelligence", "Technology", "AINews",
            "Innovation", "FutureTech", "MachineLearning", "Tech", "AIUpdate",
        ],
    },
    "health_wellness": {
        "title": "This Ancient Spice Is Better Than Most Painkillers",
        "dir": "health_wellness_podcast_20260311_162112",
        "description": (
            "Turmeric might actually be more effective than prescription painkillers "
            "according to new studies. Our baby health experts break down the science "
            "and what you need to know.\n\n"
            "Subscribe for natural health tips and wellness secrets!"
        ),
        "tags": [
            "Health", "Wellness", "NaturalRemedies", "Turmeric", "Herbal",
            "HealthTips", "NaturalHealth", "HolisticHealth", "AntiInflammatory", "HealthyLiving",
        ],
    },
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


async def upload_all():
    results = []
    success = 0
    failed = 0

    for niche, info in VIDEOS.items():
        video_dir = OUTPUT_DIR / info["dir"]
        video_path = video_dir / "final_podcast.mp4"
        thumb_path = video_dir / "thumbnail.jpg"
        srt_path = video_dir / "podcast_captions.srt"

        if not video_path.exists():
            print(f"[SKIP] {niche}: Video not found at {video_path}")
            failed += 1
            continue

        # YouTube title with emoji prefix + #Shorts tag
        yt_title = f"\U0001f534\U0001f535 {info['title']}"
        if len(yt_title) > 93:
            yt_title = yt_title[:93]
        yt_title += " #Shorts"

        size_mb = video_path.stat().st_size / (1024 * 1024)
        print(f"[UPLOADING] {niche}: {info['title']}")
        print(f"  Video: {size_mb:.1f}MB | SRT: {srt_path.exists()} | Thumb: {thumb_path.exists()}")

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
        print(f"  Result: [{status}] {url}")
        print()

        if status == "uploaded":
            success += 1
        else:
            failed += 1

        results.append((niche, result))

    print("\n" + "=" * 60)
    print("YOUTUBE UPLOAD SUMMARY")
    print("=" * 60)
    for niche, r in results:
        status = r.get("status", "?")
        url = r.get("url", r.get("error", ""))
        print(f"  {niche}: [{status}] {url}")
    print(f"\n  Success: {success} | Failed: {failed}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(upload_all())

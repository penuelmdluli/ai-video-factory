"""
Re-upload failed Facebook videos from today's pipeline run.
Usage: python reupload_facebook.py
"""
import asyncio
import sys
from pathlib import Path

# Videos that failed FB upload today (from the pipeline run)
VIDEOS_TO_UPLOAD = [
    {"niche": "ai_money", "video": "output/ai_money_short_20260309_205738/final_short.mp4", "title": "I Made $8,500 This Month Teaching AI to Local Businesses", "is_reel": True},
    {"niche": "tech_news", "video": "output/tech_news_short_20260309_210628/final_short.mp4", "title": "This Robot Just Changed Everything in 24 Hours", "is_reel": True},
    {"niche": "motivation", "video": "output/motivation_short_20260309_211736/final_short.mp4", "title": "The 5AM Millionaire Secret That Changed Everything", "is_reel": True},
    {"niche": "health_wellness", "video": "output/health_wellness_short_20260309_213013/final_short.mp4", "title": "Scientists Discovered the Perfect Sleep Formula", "is_reel": True},
    {"niche": "blissful_moments", "video": "output/blissful_moments_short_20260309_214138/final_short.mp4", "title": "5 Seconds to Peace: Find It Anywhere", "is_reel": True},
]


async def main():
    from modules.uploader_facebook import upload_to_facebook
    from config import NICHES

    for vid in VIDEOS_TO_UPLOAD:
        niche = vid["niche"]
        video_path = vid["video"]
        title = vid["title"]
        hashtags = NICHES[niche]["hashtags"]

        if not Path(video_path).exists():
            print(f"[SKIP] {niche}: video not found at {video_path}")
            continue

        print(f"\n[UPLOAD] {niche}: {title}")
        try:
            result = await upload_to_facebook(
                video_path=video_path,
                title=title,
                description=title,
                niche=niche,
                hashtags=hashtags,
                is_reel=vid["is_reel"],
            )
            if result.get("status") == "uploaded":
                print(f"[OK] {niche}: Posted to Facebook!")
            else:
                print(f"[FAIL] {niche}: {result}")
        except Exception as e:
            print(f"[ERROR] {niche}: {e}")

        await asyncio.sleep(5)

    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())

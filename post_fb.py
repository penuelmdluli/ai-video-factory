"""Publish the finished video to Tech Pulse Africa (tech_news page)."""
import asyncio
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\PenuelM\Documents\ai-video-factory")
sys.path.insert(0, str(ROOT))

from modules.uploader_facebook import upload_to_facebook

VIDEO = r"C:\Users\PenuelM\Desktop\AI_Videos\final_bestvoice_kokoro.mp4"
TITLE = "Red Sea Flashpoint — Naval Tensions Escalate"
DESC = (
    "\U0001F534 BREAKING: Tensions surge in the Red Sea as naval forces converge and global "
    "powers watch the world's oil shipping lanes. Analysts warn a single misstep could ignite "
    "a far wider conflict.\n\n"
    "\u26A0\uFE0F This report uses AI-generated visualizations for illustration."
)
HASHTAGS = ["RedSea", "BreakingNews", "Geopolitics", "WorldNews"]


async def main():
    print("Posting to Tech Pulse Africa (tech_news)...", flush=True)
    res = await upload_to_facebook(
        video_path=VIDEO,
        title=TITLE,
        description=DESC,
        niche="tech_news",
        hashtags=HASHTAGS,
        is_reel=False,
    )
    print("RESULT:", res, flush=True)


if __name__ == "__main__":
    asyncio.run(main())

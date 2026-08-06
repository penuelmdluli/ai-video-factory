"""Publish the vertical reel to Tech Pulse Africa as a REEL."""
import asyncio, sys
from pathlib import Path
ROOT = Path(r"C:\Users\PenuelM\Documents\ai-video-factory")
sys.path.insert(0, str(ROOT))
from modules.uploader_facebook import upload_to_facebook

VIDEO = r"C:\Users\PenuelM\Desktop\AI_Videos\reel_tensions.mp4"
TITLE = "Global Military Tensions Escalate"
DESC = (
    "\U0001F534 BREAKING: Military forces are mobilizing across multiple fronts as diplomatic tensions "
    "reach a breaking point. Analysts warn the days ahead could reshape the global balance of power. "
    "Governments urge calm \u2014 but the drums of conflict grow louder.\n\n"
    "\u26A0\uFE0F This report uses AI-generated visualizations for illustration."
)
HASHTAGS = ["BreakingNews", "Geopolitics", "WorldNews", "Military", "Reels"]


async def main():
    print("Posting REEL to Tech Pulse Africa...", flush=True)
    res = await upload_to_facebook(video_path=VIDEO, title=TITLE, description=DESC,
                                   niche="tech_news", hashtags=HASHTAGS, is_reel=True)
    print("RESULT:", res, flush=True)


asyncio.run(main())

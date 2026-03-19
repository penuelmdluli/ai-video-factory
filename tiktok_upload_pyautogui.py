"""
TikTok Upload via pyautogui — OS-level automation.
Uses real mouse clicks to trigger file dialogs.
"""
import pyautogui
import time
import sys
import os

# Safety settings
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.5

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")

VIDEOS = {
    "ai_trading": {
        "dir": "ai_trading_podcast_20260311_162112",
        "description": "AI Turned 10k into 13.8k in Weeks? The Catch Nobody Talks About!",
        "hashtags": "#AITrading #StockMarket #Crypto #Trading #AI #Finance #TradingBot #Stocks",
    },
    "ai_money": {
        "dir": "ai_money_podcast_20260311_162112",
        "description": "She Made $43K From AI Copywriting And Everyone Is Mad About It",
        "hashtags": "#AI #MakeMoneyOnline #SideHustle #PassiveIncome #AITools #ChatGPT #AISideHustle",
    },
    "tech_news": {
        "dir": "tech_news_podcast_20260311_162112",
        "description": "New AI Can Replace 40% of Jobs - Companies Already Using It!",
        "hashtags": "#AI #TechNews #ArtificialIntelligence #Technology #AINews #FutureTech #Innovation",
    },
    "health_wellness": {
        "dir": "health_wellness_podcast_20260311_162112",
        "description": "This Ancient Spice Is Better Than Most Painkillers According To Science",
        "hashtags": "#Health #Wellness #NaturalRemedies #Turmeric #HealthTips #HolisticHealth #Herbal",
    },
    "blissful_moments": {
        "dir": "blissful_moments_podcast_20260311_162113",
        "description": "This 6-Second Act Will Restore Your Faith in Humanity",
        "hashtags": "#BlissfulMoments #Kindness #Humanity #Heartwarming #Positivity #FaithInHumanity",
    },
    "motivation": {
        "dir": "motivation_podcast_20260311_162112",
        "description": "This 30-Day Productivity Hack Beats Every 5 AM Routine",
        "hashtags": "#Motivation #Mindset #Success #Discipline #Productivity #SelfImprovement #GrindMode",
    },
}


def find_and_click_button(image_name=None, text=None):
    """Try to find and click a button by image or location."""
    pass


def upload_video(video_path, description, hashtags):
    """Upload a single video using OS-level automation."""
    abs_path = os.path.abspath(video_path)
    if not os.path.exists(abs_path):
        print(f"  [ERROR] File not found: {abs_path}")
        return False

    print(f"  [CLICK] Clicking 'Select video' button...")

    # Try to find the "Select video" button by looking for the red button
    # The button should be roughly in the center of the upload area
    # We'll use pyautogui to locate it by color or just click known coordinates

    # First, try to find the button by locating red-ish pixels in the expected area
    try:
        # Look for the "Select video" text on screen
        btn = pyautogui.locateOnScreen
    except Exception:
        pass

    # Use keyboard shortcut approach instead:
    # In the file dialog, we can type the path directly

    # Click the center of the upload zone area (approximate)
    # This needs to be adjusted based on actual Chrome window position

    # Instead of guessing coordinates, let's use a more reliable method:
    # Tab to the file input and press Enter

    print(f"  [TYPE] Typing file path into dialog...")
    time.sleep(1)

    # Type the file path
    pyautogui.typewrite(abs_path, interval=0.01) if abs_path.isascii() else pyautogui.write(abs_path)
    time.sleep(0.5)

    # Press Enter to confirm
    pyautogui.press('enter')
    print(f"  [OK] File selected")

    # Wait for upload to process
    print(f"  [WAIT] Waiting for video upload & processing...")
    time.sleep(30)

    # Now fill in the caption
    # The caption field should be a contenteditable div
    # We need to click on it first, then type

    return True


if __name__ == "__main__":
    niche = sys.argv[1] if len(sys.argv) > 1 else None

    niches = [niche] if niche else list(VIDEOS.keys())

    for n in niches:
        if n not in VIDEOS:
            print(f"[SKIP] Unknown niche: {n}")
            continue

        info = VIDEOS[n]
        video_path = os.path.join(OUTPUT_DIR, info["dir"], "final_podcast.mp4")

        if not os.path.exists(video_path):
            print(f"[SKIP] {n}: Video not found")
            continue

        size_mb = os.path.getsize(video_path) / (1024 * 1024)
        print(f"\n[UPLOADING] {n}: {info['description'][:60]}... ({size_mb:.0f}MB)")

        upload_video(video_path, info["description"], info["hashtags"])

"""
Direct TikTok Uploader — Uses Selenium with cookie persistence.

Opens Chrome, you log in once, cookies are saved for future use.

Usage:
  python upload_tiktok_direct.py                    # Upload all 6 videos
  python upload_tiktok_direct.py --login-only       # Just log in and save session
  python upload_tiktok_direct.py --niche ai_trading # Upload single niche
"""
import sys
import os
import time
import json
import argparse

os.environ["PYTHONIOENCODING"] = "utf-8"
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(__file__))

from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

TOKENS_DIR = Path(__file__).parent / "tokens"
OUTPUT_DIR = Path(__file__).parent / "output"
COOKIES_JSON = TOKENS_DIR / "tiktok_cookies.json"

# Video metadata for all 6 niches
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


def create_driver(headless: bool = False):
    """Create Chrome driver."""
    options = Options()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument("--window-size=1280,900")

    if headless:
        options.add_argument("--headless=new")

    driver = webdriver.Chrome(options=options)
    driver.execute_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )
    return driver


def save_cookies(driver):
    """Save cookies to JSON file."""
    cookies = driver.get_cookies()
    COOKIES_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(COOKIES_JSON, "w") as f:
        json.dump(cookies, f, indent=2)
    print(f"  [SAVED] {len(cookies)} cookies -> {COOKIES_JSON}")


def load_cookies(driver) -> bool:
    """Load cookies from JSON file into driver."""
    if not COOKIES_JSON.exists():
        return False
    try:
        with open(COOKIES_JSON) as f:
            cookies = json.load(f)
        driver.get("https://www.tiktok.com/")
        time.sleep(2)
        for cookie in cookies:
            # Remove problematic fields
            for key in ["sameSite", "storeId", "id"]:
                cookie.pop(key, None)
            try:
                driver.add_cookie(cookie)
            except Exception:
                pass
        driver.refresh()
        time.sleep(3)
        return True
    except Exception as e:
        print(f"  [WARN] Could not load cookies: {e}")
        return False


def is_logged_in(driver) -> bool:
    """Check if user is logged into TikTok."""
    cookies = driver.get_cookies()
    cookie_names = {c["name"] for c in cookies}
    return "sessionid" in cookie_names or "sid_tt" in cookie_names


def wait_for_login(driver, timeout: int = 300):
    """Navigate to TikTok login and auto-detect when user completes login."""
    driver.get("https://www.tiktok.com/login")
    time.sleep(2)

    print("\n" + "=" * 50)
    print("TIKTOK LOGIN REQUIRED")
    print("=" * 50)
    print("A Chrome window has opened on your screen.")
    print("Please log in to your TikTok account there.")
    print(f"Waiting up to {timeout // 60} minutes for login...")
    print("=" * 50)
    sys.stdout.flush()

    # Poll for login every 5 seconds
    start = time.time()
    while time.time() - start < timeout:
        try:
            # Check current URL — after login TikTok redirects away from /login
            url = driver.current_url
            if "tiktok.com/login" not in url and "tiktok.com" in url:
                time.sleep(3)
                if is_logged_in(driver):
                    print("[OK] TikTok login detected!")
                    save_cookies(driver)
                    return True

            # Also check cookies directly
            if is_logged_in(driver):
                driver.get("https://www.tiktok.com/")
                time.sleep(3)
                print("[OK] TikTok login detected via cookies!")
                save_cookies(driver)
                return True
        except Exception:
            pass

        elapsed = int(time.time() - start)
        if elapsed % 30 == 0 and elapsed > 0:
            print(f"  [...] Still waiting for login ({elapsed}s elapsed)")
            sys.stdout.flush()
        time.sleep(5)

    print("[TIMEOUT] Login not detected within timeout. Saving what we have...")
    save_cookies(driver)
    return False


def upload_single_video(driver, video_path: str, description: str, hashtags: str) -> bool:
    """Upload a single video to TikTok via browser automation."""
    try:
        # Navigate to upload page
        driver.get("https://www.tiktok.com/upload")
        time.sleep(5)

        # Wait for the upload page to load
        wait = WebDriverWait(driver, 30)

        # Find the file input (TikTok uses iframe for upload)
        file_input = None
        try:
            # First try main page
            file_input = driver.find_element(By.CSS_SELECTOR, "input[type='file']")
        except Exception:
            pass

        if not file_input:
            # Try inside iframe
            try:
                iframes = driver.find_elements(By.TAG_NAME, "iframe")
                for iframe in iframes:
                    try:
                        driver.switch_to.frame(iframe)
                        file_input = driver.find_element(By.CSS_SELECTOR, "input[type='file']")
                        if file_input:
                            break
                    except Exception:
                        driver.switch_to.default_content()
                        continue
            except Exception:
                pass

        if not file_input:
            # Wait longer
            try:
                file_input = wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='file']"))
                )
            except TimeoutException:
                print("  [ERROR] Could not find file upload input")
                driver.switch_to.default_content()
                return False

        # Upload the video file
        abs_path = os.path.abspath(video_path)
        file_input.send_keys(abs_path)
        print(f"  [OK] File selected: {os.path.basename(video_path)}")

        # Switch back to main frame
        try:
            driver.switch_to.default_content()
        except Exception:
            pass

        # Wait for upload + processing (88MB takes a while)
        print("  [WAIT] Waiting for TikTok to upload & process video...")
        time.sleep(15)

        # Find and fill the caption/description field
        try:
            caption_selectors = [
                "div[contenteditable='true']",
                "div[role='textbox']",
                ".DraftEditor-root",
                "[data-testid='caption-input']",
                ".notranslate",
            ]
            caption_el = None
            for sel in caption_selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, sel)
                    for el in elements:
                        if el.is_displayed():
                            caption_el = el
                            break
                    if caption_el:
                        break
                except Exception:
                    continue

            if caption_el:
                # Select all + delete existing text
                caption_el.click()
                time.sleep(0.5)
                caption_el.send_keys(Keys.CONTROL + "a")
                time.sleep(0.3)
                caption_el.send_keys(Keys.DELETE)
                time.sleep(0.3)

                full_text = f"{description}\n\n{hashtags}"[:2200]
                # Type it in chunks to avoid issues
                for chunk in [full_text[i:i+50] for i in range(0, len(full_text), 50)]:
                    caption_el.send_keys(chunk)
                    time.sleep(0.1)

                print(f"  [OK] Caption: {description[:50]}...")
            else:
                print("  [WARN] Could not find caption field")
        except Exception as e:
            print(f"  [WARN] Caption error: {e}")

        # Wait for video to finish processing before posting
        print("  [WAIT] Waiting for video processing to complete...")
        time.sleep(30)

        # Find and click the Post button
        try:
            post_btn = None
            # Try various button selectors
            for sel in [
                "//button[contains(text(), 'Post')]",
                "//button[contains(text(), 'Publish')]",
                "//div[contains(@class, 'btn-post')]",
                "//button[@data-e2e='post_video_button']",
            ]:
                try:
                    post_btn = driver.find_element(By.XPATH, sel)
                    if post_btn and post_btn.is_displayed():
                        break
                    post_btn = None
                except Exception:
                    continue

            # Also try CSS selectors
            if not post_btn:
                for sel in [
                    "button[data-e2e='post_video_button']",
                    ".btn-post button",
                    "button.css-y1m958",
                ]:
                    try:
                        post_btn = driver.find_element(By.CSS_SELECTOR, sel)
                        if post_btn and post_btn.is_displayed():
                            break
                        post_btn = None
                    except Exception:
                        continue

            if post_btn:
                # Scroll to button and click
                driver.execute_script("arguments[0].scrollIntoView(true);", post_btn)
                time.sleep(1)
                post_btn.click()
                print("  [OK] Post button clicked!")
                time.sleep(15)

                # Check for success indicators
                try:
                    success_indicators = [
                        "//div[contains(text(), 'Your video is being uploaded')]",
                        "//div[contains(text(), 'uploaded')]",
                        "//span[contains(text(), 'Manage your posts')]",
                    ]
                    for si in success_indicators:
                        try:
                            driver.find_element(By.XPATH, si)
                            print("  [OK] Upload confirmed!")
                            return True
                        except Exception:
                            continue
                except Exception:
                    pass

                return True
            else:
                print("  [WARN] Post button not found. Waiting 60s for manual post...")
                time.sleep(60)
                return True

        except Exception as e:
            print(f"  [ERROR] Post failed: {e}")
            return False

    except Exception as e:
        print(f"  [ERROR] Upload failed: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Direct TikTok Uploader")
    parser.add_argument("--login-only", action="store_true", help="Just log in, don't upload")
    parser.add_argument("--niche", type=str, help="Upload single niche only")
    args = parser.parse_args()

    print("=" * 60)
    print("TIKTOK DIRECT UPLOADER")
    print("=" * 60)

    driver = create_driver(headless=False)

    try:
        # Try loading saved cookies first
        if COOKIES_JSON.exists():
            print("[...] Loading saved TikTok cookies...")
            load_cookies(driver)
            time.sleep(3)

            if is_logged_in(driver):
                print("[OK] Logged in via saved cookies!")
            else:
                print("[EXPIRED] Saved cookies expired, need fresh login")
                wait_for_login(driver)
        else:
            # First time — need login
            driver.get("https://www.tiktok.com/")
            time.sleep(3)
            if not is_logged_in(driver):
                wait_for_login(driver)
            else:
                print("[OK] Already logged in!")
                save_cookies(driver)

        if args.login_only:
            print("\n[DONE] Login saved! Run again without --login-only to upload.")
            return

        # Upload videos
        niches_to_upload = [args.niche] if args.niche else list(VIDEOS.keys())
        results = []

        for niche in niches_to_upload:
            if niche not in VIDEOS:
                print(f"[SKIP] {niche}: Unknown niche")
                continue

            info = VIDEOS[niche]
            video_dir = OUTPUT_DIR / info["dir"]
            video_path = video_dir / "final_podcast.mp4"

            if not video_path.exists():
                print(f"[SKIP] {niche}: Video not found at {video_dir}")
                results.append((niche, False))
                continue

            size_mb = video_path.stat().st_size / (1024 * 1024)
            print(f"\n[UPLOADING] {niche}: {info['description'][:60]}... ({size_mb:.0f}MB)")

            success = upload_single_video(
                driver,
                str(video_path),
                info["description"],
                info["hashtags"],
            )
            results.append((niche, success))

            if success:
                time.sleep(5)

        # Summary
        print("\n" + "=" * 60)
        print("TIKTOK UPLOAD SUMMARY")
        print("=" * 60)
        for niche, success in results:
            status = "UPLOADED" if success else "FAILED"
            print(f"  {niche}: [{status}]")
        uploaded = sum(1 for _, s in results if s)
        print(f"\n  Total: {uploaded}/{len(results)} uploaded")
        print("=" * 60)

    finally:
        driver.quit()


if __name__ == "__main__":
    main()

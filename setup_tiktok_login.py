"""
TikTok Login Helper — Opens a Selenium browser for you to log in.

This creates a persistent Chrome profile so you only need to log in ONCE.
The tiktok-uploader will reuse this profile for all future uploads.

Usage:
  python setup_tiktok_login.py          # Log in to TikTok
  python setup_tiktok_login.py --check  # Check if cookies are valid
"""
import os
import sys
import time
import json
import argparse
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from config import TOKENS_DIR

COOKIES_PATH = TOKENS_DIR / "tiktok_cookies.txt"
TIKTOK_PROFILE_DIR = TOKENS_DIR / "tiktok_chrome_profile"


def setup_selenium_driver(headless: bool = False):
    """Create a Selenium Chrome driver with persistent profile."""
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service

    options = Options()
    options.add_argument(f"--user-data-dir={TIKTOK_PROFILE_DIR}")
    options.add_argument("--profile-directory=Default")
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    if headless:
        options.add_argument("--headless=new")

    driver = webdriver.Chrome(options=options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver


def save_cookies_from_driver(driver) -> int:
    """Extract cookies from Selenium driver and save in Netscape format."""
    cookies = driver.get_cookies()
    tiktok_cookies = [c for c in cookies if "tiktok" in c.get("domain", "")]

    if not tiktok_cookies:
        print("[WARN] No TikTok cookies found in browser session")
        return 0

    COOKIES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(COOKIES_PATH, "w") as f:
        f.write("# Netscape HTTP Cookie File\n")
        f.write("# https://curl.haxx.se/rfc/cookie_spec.html\n")
        f.write("# Extracted from Selenium session\n\n")

        for c in tiktok_cookies:
            domain = c.get("domain", ".tiktok.com")
            include_sub = "TRUE" if domain.startswith(".") else "FALSE"
            path = c.get("path", "/")
            secure = "TRUE" if c.get("secure", False) else "FALSE"
            expiry = int(c.get("expiry", 0))
            name = c.get("name", "")
            value = c.get("value", "")
            f.write(f"{domain}\t{include_sub}\t{path}\t{secure}\t{expiry}\t{name}\t{value}\n")

    print(f"[OK] Saved {len(tiktok_cookies)} TikTok cookies to {COOKIES_PATH}")
    return len(tiktok_cookies)


def check_login_status(driver) -> bool:
    """Check if user is logged into TikTok by looking for session cookies."""
    cookies = driver.get_cookies()
    cookie_names = {c["name"] for c in cookies}
    auth_cookies = {"sessionid", "sid_tt", "uid_tt", "sessionid_ss"}
    found = auth_cookies & cookie_names
    return len(found) >= 2  # At least 2 auth cookies = logged in


def interactive_login():
    """Open browser for user to log in to TikTok."""
    print("=" * 60)
    print("TikTok Login Setup")
    print("=" * 60)
    print()
    print("A Chrome window will open. Please log in to TikTok.")
    print("Once logged in, press ENTER in this terminal to continue.")
    print()

    driver = setup_selenium_driver(headless=False)

    try:
        driver.get("https://www.tiktok.com/login")
        time.sleep(2)

        # Wait for user to log in
        print("[...] Waiting for you to log in to TikTok...")
        print("[...] Press ENTER when you're logged in and can see the TikTok feed.")
        input()

        # Navigate to main page to ensure all cookies are set
        driver.get("https://www.tiktok.com/")
        time.sleep(3)

        if check_login_status(driver):
            print("[OK] TikTok login detected!")
            count = save_cookies_from_driver(driver)
            if count > 0:
                print(f"\n[SUCCESS] TikTok is ready for uploads!")
                print(f"  Cookies saved to: {COOKIES_PATH}")
                print(f"  Profile saved to: {TIKTOK_PROFILE_DIR}")
                print(f"\n  The pipeline will automatically use these for TikTok uploads.")
            return True
        else:
            print("[ERROR] Login not detected. Please try again.")
            print("  Make sure you're fully logged in and can see your TikTok feed.")
            return False

    finally:
        driver.quit()


def check_cookies():
    """Check if existing cookies/profile are valid."""
    print("Checking TikTok login status...")

    if not TIKTOK_PROFILE_DIR.exists():
        print("[NO] TikTok profile not set up yet. Run: python setup_tiktok_login.py")
        return False

    try:
        driver = setup_selenium_driver(headless=True)
        driver.get("https://www.tiktok.com/")
        time.sleep(3)

        if check_login_status(driver):
            print("[OK] TikTok session is valid! Uploads will work.")
            # Refresh cookies file
            save_cookies_from_driver(driver)
            driver.quit()
            return True
        else:
            print("[EXPIRED] TikTok session expired. Run: python setup_tiktok_login.py")
            driver.quit()
            return False
    except Exception as e:
        print(f"[ERROR] {e}")
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TikTok Login Helper")
    parser.add_argument("--check", action="store_true", help="Check if cookies are valid")
    args = parser.parse_args()

    if args.check:
        check_cookies()
    else:
        interactive_login()

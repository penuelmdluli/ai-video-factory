"""
TikTok Cookie Extractor — Gets cookies from your Chrome browser.

Usage:
1. Make sure you're logged into TikTok in Chrome
2. Close Chrome completely
3. Run: python setup_tiktok_cookies.py

The script reads Chrome's cookie database and extracts TikTok cookies
to tokens/tiktok_cookies.txt in Netscape format.
"""
import os
import sys
import shutil
import sqlite3
import tempfile
from pathlib import Path
from datetime import datetime, timezone

# Chrome cookie database locations (Windows)
CHROME_COOKIE_PATHS = [
    Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/User Data/Default/Cookies",
    Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/User Data/Default/Network/Cookies",
    Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/User Data/Profile 1/Cookies",
    Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/User Data/Profile 1/Network/Cookies",
]

OUTPUT_PATH = Path(__file__).parent / "tokens" / "tiktok_cookies.txt"
TIKTOK_DOMAINS = [".tiktok.com", "tiktok.com", ".www.tiktok.com", "www.tiktok.com"]


def find_chrome_cookies():
    """Find Chrome's cookie database file."""
    for p in CHROME_COOKIE_PATHS:
        if p.exists():
            return p
    return None


def extract_tiktok_cookies():
    """Extract TikTok cookies from Chrome and save in Netscape format."""
    cookie_db = find_chrome_cookies()
    if not cookie_db:
        print("[ERROR] Chrome cookie database not found!")
        print("  Expected locations:")
        for p in CHROME_COOKIE_PATHS:
            print(f"    {p}")
        print("\n  Make sure Chrome is installed and you've visited TikTok at least once.")
        return False

    print(f"[INFO] Found Chrome cookies at: {cookie_db}")

    # Copy to temp file (Chrome locks the DB while running)
    tmp = Path(tempfile.gettempdir()) / "chrome_cookies_tmp.db"
    try:
        shutil.copy2(str(cookie_db), str(tmp))
    except PermissionError:
        print("[ERROR] Chrome is still running! Please close Chrome completely and try again.")
        return False

    try:
        conn = sqlite3.connect(str(tmp))
        cursor = conn.cursor()

        # Query TikTok cookies
        placeholders = ",".join(["?"] * len(TIKTOK_DOMAINS))
        query = f"""
            SELECT host_key, name, value, path, expires_utc, is_secure, is_httponly
            FROM cookies
            WHERE host_key IN ({placeholders})
            ORDER BY host_key, name
        """
        cursor.execute(query, TIKTOK_DOMAINS)
        cookies = cursor.fetchall()
        conn.close()

        if not cookies:
            print("[ERROR] No TikTok cookies found in Chrome!")
            print("  1. Open Chrome and go to https://www.tiktok.com")
            print("  2. Log in to your TikTok account")
            print("  3. Close Chrome completely")
            print("  4. Run this script again")
            return False

        # Write Netscape HTTP Cookie File format
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(OUTPUT_PATH, "w") as f:
            f.write("# Netscape HTTP Cookie File\n")
            f.write("# https://curl.haxx.se/rfc/cookie_spec.html\n")
            f.write("# This is a generated file! Do not edit.\n\n")

            for host, name, value, path, expires, secure, httponly in cookies:
                # Chrome stores expiry as microseconds since 1601-01-01
                # Convert to Unix epoch
                if expires > 0:
                    try:
                        unix_expires = int((expires / 1000000) - 11644473600)
                    except (ValueError, OverflowError):
                        unix_expires = 0
                else:
                    unix_expires = 0

                include_subdomains = "TRUE" if host.startswith(".") else "FALSE"
                secure_str = "TRUE" if secure else "FALSE"

                # Note: Chrome encrypts cookie values on Windows
                # The 'value' column may be empty if encrypted_value is used
                if not value:
                    continue  # Skip encrypted cookies we can't read

                f.write(f"{host}\t{include_subdomains}\t{path}\t{secure_str}\t{unix_expires}\t{name}\t{value}\n")

        cookie_count = sum(1 for _ in open(OUTPUT_PATH) if not _.startswith("#") and _.strip())
        print(f"\n[SUCCESS] Extracted {cookie_count} TikTok cookies!")
        print(f"  Saved to: {OUTPUT_PATH}")
        print(f"\n  You can now run the pipeline and TikTok uploads will work.")
        return True

    except Exception as e:
        print(f"[ERROR] Failed to extract cookies: {e}")
        return False
    finally:
        try:
            tmp.unlink()
        except Exception:
            pass


def manual_cookie_setup():
    """Fallback: guide user through manual cookie export."""
    print("\n" + "=" * 60)
    print("MANUAL TIKTOK COOKIE SETUP")
    print("=" * 60)
    print("""
If automatic extraction didn't work (Chrome encrypts cookies on Windows),
you can manually export cookies:

OPTION 1: Use 'EditThisCookie' Chrome Extension
  1. Install: https://chrome.google.com/webstore/detail/editthiscookie
  2. Go to https://www.tiktok.com and log in
  3. Click the EditThisCookie icon
  4. Click the export button (Netscape format)
  5. Save to: {output}

OPTION 2: Use 'Get cookies.txt LOCALLY' Chrome Extension
  1. Install from Chrome Web Store
  2. Go to https://www.tiktok.com and log in
  3. Click the extension icon
  4. Click 'Export' -> save as cookies.txt
  5. Copy to: {output}

OPTION 3: Use browser_cookie3 Python package
  pip install browser-cookie3
  Then run: python -c "
import browser_cookie3
cj = browser_cookie3.chrome(domain_name='.tiktok.com')
with open('{output}', 'w') as f:
    f.write('# Netscape HTTP Cookie File\\n')
    for c in cj:
        f.write(f'{{c.domain}}\\tTRUE\\t{{c.path}}\\t{{str(c.secure).upper()}}\\t{{c.expires or 0}}\\t{{c.name}}\\t{{c.value}}\\n')
"
""".format(output=OUTPUT_PATH))


if __name__ == "__main__":
    print("=" * 60)
    print("TikTok Cookie Extractor for AI Video Factory")
    print("=" * 60)
    print()

    success = extract_tiktok_cookies()

    if not success:
        # Try browser_cookie3 as fallback
        try:
            import browser_cookie3
            print("\n[INFO] Trying browser_cookie3 package...")
            cj = browser_cookie3.chrome(domain_name='.tiktok.com')
            cookies = list(cj)
            if cookies:
                OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
                with open(OUTPUT_PATH, "w") as f:
                    f.write("# Netscape HTTP Cookie File\n")
                    for c in cookies:
                        secure = "TRUE" if c.secure else "FALSE"
                        f.write(f"{c.domain}\tTRUE\t{c.path}\t{secure}\t{c.expires or 0}\t{c.name}\t{c.value}\n")
                print(f"\n[SUCCESS] Extracted {len(cookies)} cookies via browser_cookie3!")
                print(f"  Saved to: {OUTPUT_PATH}")
            else:
                print("[INFO] No TikTok cookies found. Please log in to TikTok first.")
                manual_cookie_setup()
        except ImportError:
            print("\n[INFO] Installing browser_cookie3...")
            os.system(f"{sys.executable} -m pip install browser-cookie3")
            manual_cookie_setup()
        except Exception as e:
            print(f"\n[INFO] browser_cookie3 failed: {e}")
            manual_cookie_setup()

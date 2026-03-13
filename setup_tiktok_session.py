"""
TikTok Session ID Setup — One-time setup to enable TikTok uploads.

This is the most reliable method. The session ID lasts weeks/months.

Usage:
    python setup_tiktok_session.py
"""
import os
import re
import sys
from pathlib import Path

ENV_FILE = Path(__file__).parent / ".env"


def get_current_session_id() -> str:
    """Read current TIKTOK_SESSION_ID from .env"""
    if not ENV_FILE.exists():
        return ""
    for line in ENV_FILE.read_text().splitlines():
        if line.startswith("TIKTOK_SESSION_ID="):
            return line.split("=", 1)[1].strip()
    return ""


def save_session_id(session_id: str):
    """Write TIKTOK_SESSION_ID to .env"""
    content = ENV_FILE.read_text() if ENV_FILE.exists() else ""
    lines = content.splitlines()

    # Replace existing or append
    found = False
    for i, line in enumerate(lines):
        if line.startswith("TIKTOK_SESSION_ID=") or line.strip() == "TIKTOK_SESSION_ID=":
            lines[i] = f"TIKTOK_SESSION_ID={session_id}"
            found = True
            break

    if not found:
        # Add under TikTok section comment if it exists
        for i, line in enumerate(lines):
            if "TikTok" in line and line.startswith("#"):
                lines.insert(i + 1, f"TIKTOK_SESSION_ID={session_id}")
                found = True
                break

    if not found:
        lines.append(f"\n# === TikTok ===")
        lines.append(f"TIKTOK_SESSION_ID={session_id}")

    ENV_FILE.write_text("\n".join(lines) + "\n")


def test_session_id(session_id: str) -> bool:
    """Quick test: verify sessionid format looks valid (32+ hex chars)."""
    return bool(re.match(r'^[a-f0-9]{32,}$', session_id, re.I))


def try_auto_extract() -> str:
    """Try to extract sessionid automatically via browser_cookie3."""
    try:
        import browser_cookie3
        print("[AUTO] Trying browser_cookie3 (Chrome)...")
        cj = browser_cookie3.chrome(domain_name='.tiktok.com')
        for cookie in cj:
            if cookie.name == 'sessionid' and cookie.value:
                print(f"[AUTO] Found sessionid via browser_cookie3!")
                return cookie.value
        print("[AUTO] sessionid not found via browser_cookie3")
    except ImportError:
        print("[AUTO] browser_cookie3 not installed. Trying pip install...")
        os.system(f"{sys.executable} -m pip install browser-cookie3 -q")
        try:
            import browser_cookie3
            cj = browser_cookie3.chrome(domain_name='.tiktok.com')
            for cookie in cj:
                if cookie.name == 'sessionid' and cookie.value:
                    return cookie.value
        except Exception:
            pass
    except Exception as e:
        print(f"[AUTO] browser_cookie3 error: {e}")
    return ""


def main():
    print("=" * 60)
    print("  TikTok Session ID Setup")
    print("=" * 60)

    current = get_current_session_id()
    if current:
        print(f"\nCurrent session ID: {current[:8]}...{current[-4:]} ({len(current)} chars)")
        print("TikTok uploads should already be working.\n")
        resp = input("Replace it with a new session ID? [y/N]: ").strip().lower()
        if resp != 'y':
            print("Keeping existing session ID. Done!")
            return

    # Try auto-extract first
    print("\n[1/2] Attempting automatic extraction from Chrome cookies...")
    auto_id = try_auto_extract()

    if auto_id:
        print(f"\n✓ Auto-extracted: {auto_id[:8]}...{auto_id[-4:]}")
        save_session_id(auto_id)
        print(f"✓ Saved to .env")
        print("\nTikTok uploads are now enabled!")
        return

    # Manual instructions
    print("\n[2/2] Auto-extraction failed. Manual setup required.")
    print("\n" + "-" * 60)
    print("HOW TO GET YOUR TIKTOK SESSION ID:")
    print("-" * 60)
    print("""
  1. Open Chrome and go to:  https://www.tiktok.com
  2. Log in with your TikTok account
  3. Press F12 to open Developer Tools
  4. Click the 'Application' tab (top menu)
  5. In the left sidebar: Storage → Cookies → https://www.tiktok.com
  6. Find the row where Name = 'sessionid'
  7. Click it and copy the entire Value (it's a long hex string)

  Example: a3f8c2d1e9b7...  (64+ characters)
""")
    print("─" * 60)

    while True:
        session_id = input("\nPaste your sessionid here (or 'skip' to cancel): ").strip()

        if session_id.lower() == 'skip':
            print("\nSkipped. TikTok uploads will remain disabled.")
            break

        if not session_id:
            print("Empty input, try again.")
            continue

        if not test_session_id(session_id):
            print(f"Warning: '{session_id[:20]}...' doesn't look like a valid sessionid.")
            print("Valid sessionids are 32+ hexadecimal characters.")
            confirm = input("Use it anyway? [y/N]: ").strip().lower()
            if confirm != 'y':
                continue

        save_session_id(session_id)
        print(f"\n✓ Session ID saved to .env ({len(session_id)} chars)")
        print("✓ TikTok uploads are now enabled!")
        print("\nTest it with:")
        print("  python main.py --niche ai_trading --format short --dry-run")
        break


if __name__ == "__main__":
    main()

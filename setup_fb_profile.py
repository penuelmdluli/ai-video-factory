"""
Facebook profile session setup — one-time, enables personal-timeline posting.

Companion to setup_tiktok_session.py. Prompts for the two cookies that
identify a Facebook session and writes them to .env:

    FB_PROFILE_C_USER   your numeric account id
    FB_PROFILE_XS       the session secret

The `xs` cookie is a live key to the account - it bypasses the password and,
in most configurations, two-factor as well. So it is read with getpass (it
does not echo to the terminal, and does not land in shell history), and it is
never printed back. Nobody but the account owner should ever handle it.

Where to find them:
    1. https://www.facebook.com in Chrome, logged in as yourself
    2. F12 -> Application -> Cookies -> https://www.facebook.com
    3. Copy the Value of `c_user`, then of `xs`

Paste `xs` EXACTLY as DevTools shows it - percent-escapes and all
(%3A where a colon would read). That is the raw form the browser sends; the
uploader passes it through unchanged, and decoding it produces a cookie
Facebook rejects.

Usage:
    python setup_fb_profile.py
"""
import getpass
import sys
from pathlib import Path

ENV_FILE = Path(__file__).parent / ".env"


def _set_key(lines: list, key: str, value: str) -> list:
    """Replace this key in place, or append it. Never duplicates a key -
    python-dotenv takes the LAST occurrence, so a stale duplicate above a
    fresh one is a silent, very confusing failure."""
    out, found = [], False
    for line in lines:
        if line.split("=", 1)[0].strip() == key:
            if not found:
                out.append(f"{key}={value}")
                found = True
            # any further copy of the key is dropped
            continue
        out.append(line)
    if not found:
        out.append(f"{key}={value}")
    return out


def main() -> int:
    print("Facebook profile session setup")
    print("-" * 60)
    print("F12 -> Application -> Cookies -> https://www.facebook.com")
    print()

    c_user = input("c_user (your numeric id): ").strip()
    if not c_user.isdigit():
        print(f"\n! '{c_user}' is not a numeric id - c_user is digits only.")
        return 1

    # getpass, not input: this value must not echo to the screen or be
    # recoverable from the terminal scrollback of a shared machine.
    xs = getpass.getpass("xs (hidden - paste and press Enter): ").strip()
    if len(xs) < 20:
        print("\n! that xs value looks too short to be real - nothing saved.")
        return 1
    if xs.startswith('"') or xs.startswith("'"):
        xs = xs.strip("\"'")
        print("  (stripped the surrounding quotes)")

    content = ENV_FILE.read_text(encoding="utf-8") if ENV_FILE.exists() else ""
    lines = content.splitlines()
    lines = _set_key(lines, "FB_PROFILE_C_USER", c_user)
    lines = _set_key(lines, "FB_PROFILE_XS", xs)
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print()
    print(f"Saved to {ENV_FILE}")
    print(f"  FB_PROFILE_C_USER = {c_user}")
    print(f"  FB_PROFILE_XS     = {'*' * 12} ({len(xs)} chars)")
    print()
    print("Now verify the session (composes nothing):")
    print("  py -X utf8 modules/uploader_fb_profile.py --check")
    return 0


if __name__ == "__main__":
    sys.exit(main())

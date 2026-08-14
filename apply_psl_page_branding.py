"""
Apply the Genesis News — PSL brand kit to the Facebook page.

Sets the page profile picture (new gold-on-black football badge) and the cover
photo, and updates the page description to the PSL about text.

Usage:
    python apply_psl_page_branding.py --dry-run   # show what would change
    python apply_psl_page_branding.py             # apply it
"""
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(override=True)

ROOT = Path(__file__).parent
BRAND = ROOT / "assets" / "youtube_branding"
GRAPH = "https://graph.facebook.com/v24.0"

PAGE_ID = os.getenv("FB_PAGE_ID_sa_pulse", "")
TOKEN = os.getenv("FB_PAGE_TOKEN_sa_pulse", "")

LOGO = BRAND / "logo_sa_pulse.png"
COVER = BRAND / "cover_sa_pulse.png"
ABOUT = BRAND / "about_sa_pulse.txt"


def _post(path, data=None, files=None):
    r = requests.post(f"{GRAPH}/{path}", data={**(data or {}), "access_token": TOKEN},
                      files=files, timeout=90)
    ok = r.status_code == 200
    print(f"  [{'OK ' if ok else 'ERR'}] {path} ({r.status_code}): {r.text[:220]}")
    return ok


def main():
    dry = "--dry-run" in sys.argv
    if not PAGE_ID or not TOKEN:
        print("FB_PAGE_ID_sa_pulse / FB_PAGE_TOKEN_sa_pulse not set — nothing to do")
        return
    for f in (LOGO, COVER, ABOUT):
        if not f.exists():
            print(f"missing {f} — run `python make_psl_brand.py` first")
            return

    info = requests.get(f"{GRAPH}/{PAGE_ID}", params={"fields": "name", "access_token": TOKEN},
                        timeout=30).json()
    print(f"Page: {info.get('name', '?')} ({PAGE_ID})")

    desc = ABOUT.read_text(encoding="utf-8").strip()
    if dry:
        print("DRY RUN — would set profile picture, cover photo and description:")
        print(f"  logo:  {LOGO}")
        print(f"  cover: {COVER}")
        print(f"  about: {desc[:120]}...")
        return

    print("Setting profile picture...")
    with open(LOGO, "rb") as f:
        _post(f"{PAGE_ID}/picture", files={"source": (LOGO.name, f, "image/png")})

    print("Uploading cover photo...")
    with open(COVER, "rb") as f:
        r = requests.post(f"{GRAPH}/{PAGE_ID}/photos",
                          data={"access_token": TOKEN, "published": "false"},
                          files={"source": (COVER.name, f, "image/png")}, timeout=90)
    print(f"  cover upload ({r.status_code}): {r.text[:220]}")
    if r.status_code == 200 and r.json().get("id"):
        _post(PAGE_ID, {"cover": r.json()["id"]})

    print("Updating description...")
    # `about` is the short blurb; `description` is the long one.
    _post(PAGE_ID, {"about": "Daily PSL news — Chiefs, Pirates & Sundowns ⚽",
                    "description": desc})
    print("Done.")


if __name__ == "__main__":
    main()

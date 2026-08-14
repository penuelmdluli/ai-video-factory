"""Apply our branded thumbnails to every Genesis News YouTube upload.

Run AFTER the channel is phone-verified (youtube.com/verify) — custom
thumbnails 403 until then.

    python fix_youtube_thumbnails.py
"""
import json
import sys
from pathlib import Path

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

ROOT = Path(__file__).parent

# video_id -> thumbnail image (our covers/cards for each upload)
THUMBS = {
    # long-form derby preview show (landscape title card)
    "JZhC8R-eb4Q": ROOT / "output/psl_show_20260814_215652/seg1.png",
    # shorts (portrait covers — YouTube crops Shorts thumbs itself, still worth setting)
    "StEjF6C0rrU": ROOT / "output/sa_pulse_short_20260814_212149/cover.png",
    "tIaxi8q8-NM": ROOT / "output/sa_pulse_short_20260814_204721/cover.png",
    "5HH2cmIJwPY": ROOT / "output/sa_pulse_short_20260814_194919/card_1.png",
}


def main():
    creds = Credentials.from_authorized_user_info(
        json.loads((ROOT / "tokens/youtube_token_sa_pulse.json").read_text()))
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    yt = build("youtube", "v3", credentials=creds)
    ok = 0
    for vid, img in THUMBS.items():
        if not img.exists():
            # fall back to whatever cover exists in that folder
            alt = list(img.parent.glob("cover.png")) or list(img.parent.glob("card_1.png"))
            if not alt:
                print(f"  {vid}: no image found ({img.name}) — skipped")
                continue
            img = alt[0]
        try:
            yt.thumbnails().set(videoId=vid,
                                media_body=MediaFileUpload(str(img))).execute()
            print(f"  {vid}: thumbnail set from {img.name}")
            ok += 1
        except Exception as e:
            msg = str(e)
            if "403" in msg:
                print(f"  {vid}: STILL 403 — channel not verified yet")
                sys.exit(1)
            print(f"  {vid}: failed ({msg[:120]})")
    print(f"DONE — {ok}/{len(THUMBS)} thumbnails applied")


if __name__ == "__main__":
    main()

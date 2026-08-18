"""
Rebrand the 'motivation' page/channel: Elevate You -> MZANSI CAREERS.
Sets Facebook page name, about/description, profile picture and cover, and
the YouTube channel title, description, keywords and banner.
"""
import asyncio
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent))

GRAPH = "https://graph.facebook.com/v24.0"
NICHE = "motivation"
LOGO = "assets/careers_brand/logo.png"
COVER = "assets/careers_brand/cover.png"

NAME = "Mzansi Careers"
ABOUT = "Verified SA jobs, learnerships, internships & bursaries."
DESCRIPTION = (
    "Mzansi Careers posts real, verified opportunities for South Africans — "
    "jobs, learnerships, internships and bursaries.\n\n"
    "How we work:\n"
    "• Every opportunity is checked on the employer's own careers portal or "
    "an official government circular before we post it.\n"
    "• We never republish scraped listings and we never send you to a "
    "middleman.\n"
    "• You never pay to apply. Anyone asking you for money is a scam.\n"
    "• Every post carries the closing date and how to apply.\n\n"
    "Follow for daily verified opportunities."
)
KEYWORDS = ("sa jobs, south africa jobs, learnership, internship, bursary, "
            "vacancies, graduate programme, mzansi careers, government jobs")


def fb():
    pid = os.getenv(f"FB_PAGE_ID_{NICHE}")
    tok = os.getenv(f"FB_PAGE_TOKEN_{NICHE}")
    if not (pid and tok):
        print("[FB] page not configured")
        return
    r = requests.post(f"{GRAPH}/{pid}", data={
        "name": NAME, "about": ABOUT, "description": DESCRIPTION,
        "access_token": tok}, timeout=60)
    print("[FB] name/about:", r.status_code, r.text[:400])
    if r.status_code != 200:
        r2 = requests.post(f"{GRAPH}/{pid}", data={
            "about": ABOUT, "description": DESCRIPTION,
            "access_token": tok}, timeout=60)
        print("[FB] about only:", r2.status_code, r2.text[:300])

    # profile picture — Graph accepts a raw upload on /picture
    with open(LOGO, "rb") as f:
        r = requests.post(f"{GRAPH}/{pid}/picture",
                          files={"source": f},
                          data={"access_token": tok}, timeout=180)
    print("[FB] picture:", r.status_code, r.text[:300])

    # cover — upload unpublished photo, then point the page cover at it
    with open(COVER, "rb") as f:
        r = requests.post(f"{GRAPH}/{pid}/photos", files={"source": f},
                          data={"published": "false", "access_token": tok},
                          timeout=180)
    print("[FB] cover upload:", r.status_code, r.text[:300])
    if r.status_code == 200:
        photo_id = r.json().get("id")
        r2 = requests.post(f"{GRAPH}/{pid}", data={
            "cover": photo_id, "access_token": tok}, timeout=60)
        print("[FB] cover set:", r2.status_code, r2.text[:300])


def youtube():
    from modules.uploader_youtube import _get_youtube_service
    yt = _get_youtube_service(NICHE)
    ch = yt.channels().list(part="brandingSettings,snippet",
                            mine=True).execute()["items"][0]
    bs = ch.get("brandingSettings", {})
    bs.setdefault("channel", {})
    bs["channel"]["title"] = NAME
    bs["channel"]["description"] = DESCRIPTION
    bs["channel"]["keywords"] = KEYWORDS
    try:
        r = yt.channels().update(part="brandingSettings",
                                 body={"id": ch["id"],
                                       "brandingSettings": bs}).execute()
        print("[YT] branding updated:",
              r["brandingSettings"]["channel"].get("title"))
    except Exception as e:
        print(f"[YT] branding failed: {e}")
    try:
        from googleapiclient.http import MediaFileUpload
        up = yt.channelBanners().insert(
            media_body=MediaFileUpload(COVER, resumable=False)).execute()
        url = up.get("url")
        bs.setdefault("image", {})["bannerExternalUrl"] = url
        yt.channels().update(part="brandingSettings",
                             body={"id": ch["id"],
                                   "brandingSettings": bs}).execute()
        print("[YT] banner set:", url)
    except Exception as e:
        print(f"[YT] banner failed: {e}")


if __name__ == "__main__":
    fb()
    youtube()

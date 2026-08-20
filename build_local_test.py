"""
Local-format test post for the SAGA of the NORTH page.

That page has 57,872 followers and its reels reach about 226 people — 0.4%
of its own audience. The hypothesis is that reach collapsed because the
content stopped being what those people followed for. This posts ONE piece
of South African, feel-good content in the same house style as Genesis News,
so we can compare it against the 226 baseline before deciding anything.

Every fact comes from Wikipedia's own summary and the photo is Creative
Commons with the photographer named — same verification rule as the rest of
the network.

    python build_local_test.py --dry-run
    python build_local_test.py            # posts to the page
"""
import argparse
import asyncio
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

import os  # noqa: E402
os.environ["PAGE_LOCK_OWNER"] = "build_local_test.py"   # owner-authorised test

import requests  # noqa: E402

NICHE = "blissful_moments"
OUT = Path("output/local_test")
UA = "GenesisNews/1.0 (mdlulipenuel@gmail.com)"

SUBJECT = "Blyde River Canyon"
COMMONS_FILE = "File:Blyde River Canyon Nature Reserve (ZA), Blyde River Canyon -- 2024 -- 3129.jpg"


def wiki_facts(title: str):
    r = requests.get(
        f"https://en.wikipedia.org/api/rest_v1/page/summary/{title.replace(' ', '_')}",
        headers={"User-Agent": UA}, timeout=45).json()
    extract = r.get("extract") or ""
    return extract, r.get("content_urls", {}).get("desktop", {}).get("page", "")


def commons_photo(query: str):
    r = requests.get("https://commons.wikimedia.org/w/api.php",
                     headers={"User-Agent": UA}, timeout=60, params={
                         "action": "query", "format": "json",
                         "generator": "search",
                         "gsrsearch": f"{query} filetype:bitmap",
                         "gsrlimit": 3, "gsrnamespace": 6,
                         "prop": "imageinfo",
                         "iiprop": "url|extmetadata", "iiurlwidth": 1800})
    for p in list(((r.json().get("query") or {}).get("pages") or {}).values()):
        ii = p["imageinfo"][0]
        em = ii.get("extmetadata", {})
        artist = " ".join(re.sub(r"<[^>]+>", "",
                                 em.get("Artist", {}).get("value", "")).split())
        lic = em.get("LicenseShortName", {}).get("value", "")
        url = ii.get("thumburl") or ii.get("url")
        if url:
            OUT.mkdir(parents=True, exist_ok=True)
            dest = OUT / "photo.jpg"
            img = requests.get(url, headers={"User-Agent": UA}, timeout=120)
            dest.write_bytes(img.content)
            return str(dest), f"photo: {artist[:40]} ({lic}, Wikimedia)"
    return None, ""


async def main(dry=False):
    extract, source_url = wiki_facts(SUBJECT)
    if not extract:
        print("[Local] no verified facts — refusing to post")
        return 1
    photo, credit = commons_photo(SUBJECT)
    if not photo:
        print("[Local] no licensed photo — refusing to post")
        return 1

    # only sentences Wikipedia actually states
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", extract)
                 if len(s.strip()) > 25][:3]
    print(f"[Local] {SUBJECT}: {len(sentences)} verified lines")
    for s in sentences:
        print("   -", s[:88])

    from modules.thumb_engine import make_reel_cover
    cover = make_reel_cover(OUT / "cover.jpg",
                            hook=SUBJECT,
                            kicker="Mzansi · Mpumalanga",
                            chip="Third largest on earth",
                            photo=photo, brand="mzansi", focus=0.5)

    # voiced reel over the photo, house style
    from modules.voice_generator import generate_voice
    from moviepy import (ImageClip, AudioFileClip, CompositeAudioClip,
                         CompositeVideoClip)
    narration = ("This is the Blyde River Canyon, in Mpumalanga. " +
                 " ".join(sentences) +
                 " Share this with someone who has never seen it.")
    v = await generate_voice(narration, OUT, "local_test", "short", "sa_pulse")
    audio = (v or {}).get("audio_path")
    dur = AudioFileClip(audio).duration if audio else 18.0

    base = ImageClip(cover).with_duration(dur + 0.6).resized((1080, 1920))
    clip = CompositeVideoClip([base], size=(1080, 1920))
    if audio:
        clip = clip.with_audio(CompositeAudioClip([AudioFileClip(audio)]))
    out = OUT / "reel.mp4"
    clip.write_videofile(str(out), fps=30, codec="libx264",
                         audio_codec="aac", logger=None)
    print(f"[Local] reel: {out} ({dur:.1f}s)")

    if dry:
        return 0

    caption = (f"🇿🇦 {SUBJECT.upper()} — MPUMALANGA\n\n"
               + "\n\n".join(sentences)
               + "\n\n🔁 Share this with someone who has never seen it.\n\n"
               + f"Source: Wikipedia · {credit}\n"
               + "#SouthAfrica #Mzansi #Mpumalanga #ProudlySouthAfrican")
    from modules.uploader_facebook import upload_to_facebook, post_comment
    fb = await upload_to_facebook(video_path=str(out),
                                  title=f"{SUBJECT} — Mpumalanga",
                                  description=caption, niche=NICHE,
                                  is_reel=True, thumbnail_path=cover)
    print(f"[Local] Facebook: {fb.get('status')} {fb.get('post_id')}")
    vid = fb.get("video_id") or fb.get("post_id")
    if vid and fb.get("status") == "uploaded":
        await post_comment(vid, "Which South African place should we show "
                                "next? Drop it below 👇🇿🇦", NICHE)
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    sys.exit(asyncio.run(main(ap.parse_args().dry_run)))

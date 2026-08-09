#!/usr/bin/env python
"""Publish SAGA OF THE NORTH episodes to the Genesis Hub blog as self-hosted video posts.

The Viking series lives on Facebook (no YouTube id to embed), so each episode is self-hosted: the
final.mp4 is transcoded to a small, web-optimised vertical clip (kept well under Cloudflare Pages'
~25 MB/file limit and fast to load), a poster frame is grabbed, and an SEO article is written around
the episode's real story + lesson. Posts merge into the same state.json/index as the rest of the hub.

  python blog/viking_blog.py            # publish every built episode not already on the blog
  python blog/viking_blog.py --all      # re-publish all (re-transcode)
"""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent          # blog/
REPO = ROOT.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(ROOT))

import imageio_ffmpeg
import generate_blog as gb
import viking_saga as saga

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
VIDEOS = gb.BUILD / "videos"
# The Viking Facebook page (blissful_moments) — where the "follow the saga" CTA points.
FB_PAGE_URL = "https://www.facebook.com/112465853843545"
KEYWORDS = ("viking motivation, norse mindset, saga of the north, discipline, "
            "self improvement, viking warrior, motivation")


def _built_episodes():
    """Newest final.mp4 per episode number (series naming only), in season order."""
    best = {}
    for f in REPO.glob("output/viking_ep*_*/final.mp4"):
        m = re.match(r"viking_ep(\d{2})_", f.parent.name)
        if not m:
            continue
        n = int(m.group(1))
        if n not in best or f.stat().st_mtime > best[n].stat().st_mtime:
            best[n] = f
    return sorted(best.items())


def _transcode(src: Path, out_mp4: Path, poster: Path, card: Path):
    """Small web clip + a vertical poster (for the player) + a 16:9 card thumb (for the grid/OG).

    The card matters: the video is 9:16, but the hub's grid cards are 16:9, so a raw vertical frame
    gets cropped to an ugly middle strip. The card image places the whole vertical frame centred on a
    dark themed background, so it reads cleanly in the grid and as the Facebook share image.
    Returns True on success.
    """
    VIDEOS.mkdir(parents=True, exist_ok=True)
    # 720x1280 max, H.264 CRF 28, faststart — a ~22s clip lands around 4-7 MB.
    v = subprocess.run([FFMPEG, "-y", "-i", str(src), "-vf", "scale=-2:1280",
                        "-c:v", "libx264", "-preset", "veryfast", "-crf", "28",
                        "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", str(out_mp4)],
                       capture_output=True)
    if v.returncode != 0 or not out_mp4.exists():
        print(f"[viking-blog] transcode failed: {v.stderr.decode()[-200:]}")
        return False
    # vertical poster for the inline player
    subprocess.run([FFMPEG, "-y", "-ss", "1", "-i", str(src), "-frames:v", "1",
                    "-vf", "scale=-2:1280", "-q:v", "3", str(poster)], capture_output=True)
    # 16:9 card: vertical frame centred on a dark navy (#1a1240) background
    subprocess.run([FFMPEG, "-y", "-ss", "1", "-i", str(src), "-frames:v", "1",
                    "-vf", "scale=-2:360,pad=640:360:(ow-iw)/2:0:color=0x1a1240",
                    "-q:v", "3", str(card)], capture_output=True)
    return True


def _article(ep, n):
    """A genuine SEO article built from the episode's own hook, story and lesson."""
    lesson_line = ep["lesson"].replace("\n", " ").strip()
    title = f"{ep['title'].title()}: {lesson_line.rstrip('.').title()}"
    hook = ep["hook"].rstrip(".")
    intro = (f"{hook.capitalize()}. This is Episode {n} of SAGA OF THE NORTH — a short Viking saga "
             f"with one hard lesson you can use today.")
    sections = [
        {"h": "What happens in this chapter", "p": ep["saga"]},
        {"h": "The lesson", "p": f"{lesson_line} It sounds simple, but it is the whole difference "
         f"between the people who talk about what they will do and the people who actually go and "
         f"do it. The North does not reward comfort. It rewards the ones who move."},
        {"h": "How to use it this week", "p": f"Pick the one thing you have been waiting to feel "
         f"ready for. You will not feel ready. Do it anyway — that is exactly what this episode is "
         f"about. Small, hard, repeated action is how a saga is actually built."},
    ]
    conclusion = (f"Watch Episode {n} below, then follow SAGA OF THE NORTH for the next chapter — "
                  f"the story runs in order and every episode carries the last one forward.")
    return {"title": title[:70], "meta": f"{hook}. A Viking saga lesson on {lesson_line.lower()}"[:155],
            "intro": intro, "sections": sections, "conclusion": conclusion}


def publish(force=False):
    eps = _built_episodes()
    if not eps:
        print("[viking-blog] no built episodes found.")
        return
    state = gb.load_state()
    posts = state.get("posts", [])
    by_slug = {p["slug"]: p for p in posts}

    published = 0
    for n, mp4 in eps:
        ep = saga.BY_EP.get(n)
        if not ep:
            continue
        slug = f"saga-of-the-north-ep-{n}-{ep['slug']}"
        web_mp4 = VIDEOS / f"viking_ep{n:02d}.mp4"
        poster = VIDEOS / f"viking_ep{n:02d}.jpg"
        card = VIDEOS / f"viking_ep{n:02d}_card.jpg"
        if slug in by_slug and web_mp4.exists() and card.exists() and not force:
            continue  # already on the blog
        print(f"[viking-blog] EP.{n} {ep['title']} -> transcoding...")
        if not _transcode(mp4, web_mp4, poster, card):
            continue
        a = _article(ep, n)
        t = {"slug": slug, "title": a["title"], "date": gb._today(), "niche": "viking",
             "channel": "SAGA OF THE NORTH", "channel_url": FB_PAGE_URL, "keywords": KEYWORDS,
             "self_hosted": True, "video": f"/videos/{web_mp4.name}",
             "poster": f"/videos/{poster.name}", "thumb": f"/videos/{card.name}"}
        gb.POSTS.mkdir(parents=True, exist_ok=True)
        (gb.POSTS / f"{slug}.html").write_text(gb._post_html(a, t), encoding="utf-8")
        # store the fields the index/card needs (poster + 16:9 card thumb + the rest)
        by_slug[slug] = {k: t[k] for k in ("slug", "title", "date", "video", "channel", "niche",
                                           "poster", "thumb", "self_hosted", "channel_url")}
        published += 1
        print(f"[viking-blog] wrote /posts/{slug}")

    # Viking episodes first (newest ep number), then the rest as they were.
    viking = sorted([p for p in by_slug.values() if p.get("niche") == "viking"],
                    key=lambda p: p["slug"], reverse=True)
    others = [p for p in posts if p.get("niche") != "viking"]
    state["posts"] = viking + others
    gb.rebuild_site(state["posts"])
    (ROOT / "state.json").write_text(json.dumps(state, indent=2))
    print(f"[viking-blog] DONE — {published} new episode post(s); site rebuilt.")


if __name__ == "__main__":
    publish(force="--all" in sys.argv)

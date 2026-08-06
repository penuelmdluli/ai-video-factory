#!/usr/bin/env python
"""Syndication Layer — the always-on monetization rail.

Takes ONE finished render and fans it across the rails that actually pay a ZA
creator (YouTube + Facebook), in the right format for each, plus extra free-reach
surfaces. Content-agnostic: Zuzu, war shorts, or any future channel can call it.

Rail strategy (from the research):
  - YouTube long-form (16:9)  -> mid-roll ad watch-time
  - YouTube Short   (9:16)    -> top-of-funnel discovery
  - Facebook video  (16:9)    -> in-stream higher-CPM tier ($1-4/1k)   <- the paying FB format
  - Facebook Reel   (9:16)    -> reach (optional; stagger to avoid de-dup)

Usage:
  python syndicate.py <video.mp4> --title "..." --desc "..." --yt kids_songs --fb blissful_moments
  python syndicate.py <video.mp4> ... --reframe-only     # just make the aspect ratios, don't post
"""
import sys, argparse, asyncio
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
from modules.reframe import make_aspects

async def syndicate(source, title, description, tags, yt_niche, fb_niche,
                    made_for_kids=None, want=("yt_long", "yt_short", "fb_video")):
    from modules.uploader_youtube import upload_to_youtube
    from modules.uploader_facebook import upload_to_facebook
    outdir = Path(source).parent / "syndicated"
    need = set()
    if {"yt_long", "fb_video"} & set(want): need.add("16x9")
    if {"yt_short", "fb_reel"} & set(want): need.add("9x16")
    if "fb_square" in want: need.add("1x1")
    print(f"[syn] reframing {Path(source).name} -> {sorted(need)}", flush=True)
    asp = make_aspects(source, outdir, aspects=tuple(need))
    res = {}
    if "yt_long" in want:
        res["yt_long"] = await upload_to_youtube(asp["16x9"], title, description, tags,
            niche=yt_niche, is_short=False, privacy="public", made_for_kids=made_for_kids)
        print("[syn] YT long:", res["yt_long"].get("url", res["yt_long"]), flush=True)
    if "yt_short" in want:
        st = (title[:80] + " #shorts")
        res["yt_short"] = await upload_to_youtube(asp["9x16"], st, description, tags,
            niche=yt_niche, is_short=True, privacy="public", made_for_kids=made_for_kids)
        print("[syn] YT short:", res["yt_short"].get("url", res["yt_short"]), flush=True)
    if "fb_video" in want:
        try:
            res["fb_video"] = await upload_to_facebook(asp["16x9"], title, description,
                niche=fb_niche, is_reel=False)
            print("[syn] FB video:", res["fb_video"].get("status", res["fb_video"]), flush=True)
        except Exception as e:
            print("[syn] FB video error:", e, flush=True)
    if "fb_reel" in want:
        try:
            res["fb_reel"] = await upload_to_facebook(asp["9x16"], title, description,
                niche=fb_niche, is_reel=True)
            print("[syn] FB reel:", res["fb_reel"].get("status", res["fb_reel"]), flush=True)
        except Exception as e:
            print("[syn] FB reel error:", e, flush=True)
    return res

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--title", default="")
    ap.add_argument("--desc", default="")
    ap.add_argument("--tags", default="")
    ap.add_argument("--yt", default="kids_songs", help="YouTube niche key")
    ap.add_argument("--fb", default="blissful_moments", help="Facebook niche key")
    ap.add_argument("--kids", action="store_true", help="flag made-for-kids")
    ap.add_argument("--reframe-only", action="store_true")
    a = ap.parse_args()
    if a.reframe_only:
        out = make_aspects(a.video, Path(a.video).parent / "syndicated")
        print("reframed:", out); return
    tags = [t.strip() for t in a.tags.split(",") if t.strip()] or ["video"]
    asyncio.run(syndicate(a.video, a.title, a.desc, tags, a.yt, a.fb,
                          made_for_kids=True if a.kids else None))

if __name__ == "__main__":
    main()

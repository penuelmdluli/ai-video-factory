#!/usr/bin/env python
"""$0 GRAPHIC reel — NO RunPod video, ANY channel. Builds a reel entirely from the local
animation toolkit (kinetic hook -> map/stat/bars/versus/timeline/flow/quote -> outro), driven
by a per-niche topic brain, with the FULL engagement pack (badge, progress bar, @handle
watermark, FOLLOW button, comment-bait) + a premium 9:16 cover, then posts to that niche's page.

The template engine picks the best-fit format from what real data the topic supplies (many top
templates, one engine). Cost ~ $0: local PIL/MoviePy render + free Kokoro voice; only spend is
the topic LLM (~1c). Designed to run on a schedule, forever, across channels.

  python make_graphic_reel.py                       # tech_news, build + post
  python make_graphic_reel.py --niche ai_money      # finance channel
  python make_graphic_reel.py --niche motivation    # Elevate You
  python make_graphic_reel.py --dry-run             # build only, no post
"""
import argparse
import asyncio
import subprocess
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

W, H, FPS = 1080, 1920, 30

# per-niche engagement + posting metadata
NICHE_META = {
    "tech_news":  dict(label="BREAKING", handle="TechPulseAfrica", follow=True,
                       hashtags=["Africa", "Geopolitics", "BreakingNews", "Reels", "AIgenerated"],
                       tag="\U0001F3AC AI-generated visualization",
                       comment="What do you think?"),
    "ai_money":   dict(label="MONEY", handle="SmartMoneyAI", follow=True,
                       hashtags=["Money", "Finance", "Investing", "SmartMoney", "Reels"],
                       tag="\U0001F4A1 Financial education",
                       comment="What would you do?"),
    "motivation": dict(label="MINDSET", handle="ElevateYou", follow=True,
                       hashtags=["Motivation", "Mindset", "Discipline", "Success", "Reels"],
                       tag="",
                       comment="Tag someone who needs this."),
}


def run(niche, dry_run=False):
    meta = NICHE_META.get(niche, NICHE_META["tech_news"])
    stamp = time.strftime("%Y%m%d_%H%M%S")
    out = ROOT / "output" / f"graphic_{niche}_{stamp}"; out.mkdir(parents=True, exist_ok=True)
    print(f"=== GRAPHIC REEL ($0, no RunPod) :: {niche} ===", flush=True)

    from channel_topics import get_topic, log_posted
    pkg = get_topic(niche)
    print(f"  TOPIC: {pkg.get('title')}", flush=True)

    from modules.thumbnail_pro import niche_style
    acc, eye, brand, kind = niche_style(niche)

    # beat-synced: the voiceover IS the video — each spoken line has a matching visual
    from modules.beats import build_beats
    from modules.synced_reel import make_synced_reel
    beats = build_beats(pkg, handle=brand or meta["handle"])
    print(f"  BEATS ({len(beats)}): " + " | ".join(
        (b.get("device", {}).get("type", "kw") if b.get("device") else
         ("hook" if b.get("hook") else "kw")) + ":" + (b.get("say", "")[:22]) for b in beats), flush=True)

    reel = out / "reel.mp4"
    r = make_synced_reel(beats, str(reel), size=(W, H), accent=acc, fps=FPS, breaking=True,
                         label=meta["label"], handle=meta["handle"], follow=meta["follow"],
                         comment_prompt=pkg.get("comment_prompt", meta["comment"]), niche=niche)
    if not r:
        raise SystemExit("synced reel render failed")
    reel = Path(r["path"])
    print(f"  built -> {reel}  ({r['duration']:.1f}s)", flush=True)
    print(f"  STANDALONE NARRATION: {r['narration']}", flush=True)

    # premium 9:16 cover from a frame of the reel
    cover = out / "cover.jpg"
    try:
        from modules.thumbnail_pro import make_pro_thumbnail
        import imageio_ffmpeg
        ff = imageio_ffmpeg.get_ffmpeg_exe()
        frame = out / "hero.png"
        subprocess.run([ff, "-y", "-ss", "1.5", "-i", str(reel), "-frames:v", "1", str(frame)], capture_output=True)
        make_pro_thumbnail(str(frame) if frame.exists() else "", pkg.get("title", ""), str(cover),
                           accent=acc, eyebrow=(pkg.get("lowerthird_label") or eye), brand=brand, kind=kind, size=(W, H))
    except Exception as e:
        print(f"  cover skipped ({e})", flush=True); cover = None

    if dry_run:
        print("  DRY-RUN — not posting.", flush=True)
        return str(reel)

    from modules.uploader_facebook import upload_to_facebook
    tag = ("\n\n" + meta["tag"]) if meta["tag"] else ""
    desc = pkg.get("caption", pkg.get("title", "")) + tag
    res = asyncio.run(upload_to_facebook(video_path=str(reel), title=pkg.get("title", ""), description=desc,
                                         niche=niche, hashtags=meta["hashtags"],
                                         is_reel=True, thumbnail_path=str(cover) if cover else None))
    print("  POST:", res, flush=True)
    if isinstance(res, dict) and res.get("status") == "uploaded":
        log_posted(niche, pkg)
        if niche == "tech_news":
            try:
                from news_topic_generator import log_posted as news_log
                news_log(pkg)
            except Exception:
                pass
        print("  logged (won't repeat)", flush=True)
    print("DONE", flush=True)
    return str(reel)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--niche", default="tech_news")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    run(a.niche, dry_run=a.dry_run)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("GRAPHIC_REEL ERROR:\n" + traceback.format_exc(), flush=True)

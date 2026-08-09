#!/usr/bin/env python
"""Post SAGA OF THE NORTH episodes to YouTube as Shorts, in season order.

Uses the repurposed Blissful Moments channel (youtube_token_blissful_moments.json — the YouTube twin
of the Viking Facebook page). Tracks uploaded episodes in logs/viking_youtube.json so it never
repeats, and always uploads the lowest-numbered episode not yet on YouTube.

  python upload_viking_youtube.py            # next episode in season order
  python upload_viking_youtube.py --count 3  # next 3
  python upload_viking_youtube.py --ep 5     # a specific episode
  python upload_viking_youtube.py --status   # what's built / uploaded / next
"""
import argparse
import asyncio
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import viking_saga as saga

NICHE = "blissful_moments"   # repurposed channel = the Viking channel on YouTube
LOG = ROOT / "logs" / "viking_youtube.json"
LOG.parent.mkdir(exist_ok=True)
HASHTAGS = ["Vikings", "Norse", "SagaOfTheNorth", "Motivation", "Shorts", "Viking", "Mindset"]


def _uploaded():
    try:
        return set(json.loads(LOG.read_text()))
    except Exception:
        return set()


def _mark(ep_num):
    s = _uploaded(); s.add(int(ep_num))
    LOG.write_text(json.dumps(sorted(s), indent=2))


def _built():
    """Newest final.mp4 per episode number (series naming only), in season order."""
    best = {}
    for f in ROOT.glob("output/viking_ep*_*/final.mp4"):
        m = re.match(r"viking_ep(\d{2})_", f.parent.name)
        if not m:
            continue
        n = int(m.group(1))
        if n not in best or f.stat().st_mtime > best[n].stat().st_mtime:
            best[n] = f
    return dict(sorted(best.items()))


def _title(n, ep):
    return f"SAGA OF THE NORTH — EP.{n} {ep['title']}"[:90]


def _description(n, ep):
    body = ep["caption"]
    tease = saga.next_tease(ep)
    if tease.startswith("NEXT"):
        body += f"\n\n▶ {tease.replace('NEXT  ', 'NEXT: ')} — subscribe so you don't miss it."
    else:
        body += "\n\n▶ Season 1 complete. Subscribe — Season 2 is coming."
    return body + "\n\n#" + " #".join(HASHTAGS)


def status():
    built = _built(); done = _uploaded()
    print(f"{saga.SERIES} — Season {saga.SEASON} (YouTube: {saga.EPISODES and len(saga.EPISODES)} written)")
    for ep in saga.EPISODES:
        n = ep["ep"]
        state = "not built" if n not in built else ("UPLOADED" if n in done else "ready")
        print(f"  EP.{n:>2} {ep['title']:<16} {state}")
    nxt = next((n for n in built if n not in done), None)
    print(f"\nnext up: {'EP.' + str(nxt) if nxt else 'nothing new to upload'}")


async def _upload_one(n, video, ep):
    from modules.uploader_youtube import upload_to_youtube
    srt = next((str(p) for p in [video.parent / "voiceover.srt", video.parent / "final.srt"]
                if p.exists()), None)
    res = await upload_to_youtube(
        video_path=str(video), title=_title(n, ep), description=_description(n, ep),
        tags=HASHTAGS, niche=NICHE, is_short=True, privacy="public", srt_path=srt)
    print("YOUTUBE:", res)
    if isinstance(res, dict) and res.get("video_id"):
        _mark(n)
        print(f"uploaded + logged: EP.{n} -> {res.get('url')}")
        return True
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ep", type=int, help="force a specific episode")
    ap.add_argument("--count", type=int, default=1, help="how many to upload this run")
    ap.add_argument("--status", action="store_true")
    args = ap.parse_args()

    if args.status:
        status(); return

    built = _built(); done = _uploaded()
    if args.ep:
        picks = [(args.ep, built.get(args.ep))] if args.ep in built else []
        if not picks:
            print(f"EP.{args.ep} is not built yet."); return
    else:
        picks = [(n, built[n]) for n in built if n not in done][:args.count]
    if not picks:
        print("every built episode is already on YouTube — build more with build_viking_batch.py")
        return

    for n, video in picks:
        ep = saga.BY_EP.get(n)
        print(f"\nuploading EP.{n} {ep['title'] if ep else ''}\n  {video}")
        try:
            asyncio.run(_upload_one(n, video, ep))
        except Exception as e:
            print(f"  EP.{n} upload FAILED: {e}")


if __name__ == "__main__":
    main()

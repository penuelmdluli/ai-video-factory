#!/usr/bin/env python
"""Post the next SAGA OF THE NORTH episode to the page (blissful_moments page ID, now the Viking
channel).

This is a SERIES, so order matters: it always posts the lowest-numbered episode that hasn't gone
out yet, never a random one from the pile. Posted episodes are tracked in logs/viking_posted.json.
Run 3x/day by the scheduler.

  python post_next_viking.py            # next episode in season order
  python post_next_viking.py --ep 5     # force a specific episode
  python post_next_viking.py --status   # what's built, what's posted, what's next
"""
import argparse
import asyncio
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

# We own the blissful_moments page (see config.LOCKED_PAGES). Declaring ownership
# before importing config/uploaders is what lets THIS script post there while
# every other pipeline is blocked.
os.environ["PAGE_LOCK_OWNER"] = "post_next_viking.py"
LOG = ROOT / "logs" / "viking_posted.json"
LOG.parent.mkdir(exist_ok=True)

import viking_saga as saga

DEFAULT_CAPTION = "SAGA OF THE NORTH ⚔️\U0001FA93  Legends of the North. Follow for the saga."
HASHTAGS = ["Vikings", "Norse", "SagaOfTheNorth", "Motivation", "Shorts", "Reels"]
FB_GRAPH = "https://graph.facebook.com/v24.0"


def _first_comment(post_id, text):
    """Seed the comment thread with the episode's question, posted AS the page.

    A first comment from the page is the single highest-leverage engagement nudge on Reels:
    Facebook surfaces it under the video and gives scrollers something to reply to. Our posts were
    getting ZERO comments with the prompt buried in the caption (see the Aug-2026 insights pull) —
    this drops it right where people tap. Pinning is UI-only in the Graph API, so we post the
    comment and best-effort attempt a pin, ignoring failure. Non-critical: never blocks the post.
    """
    import time
    import requests
    token = os.getenv("FB_PAGE_TOKEN_blissful_moments")
    if not (token and post_id and text):
        return None
    # A freshly published reel can reject a comment for a few seconds while it finishes processing,
    # so retry a couple of times before giving up. Never fatal — the post is already live.
    for attempt in range(3):
        try:
            r = requests.post(f"{FB_GRAPH}/{post_id}/comments",
                              data={"message": text, "access_token": token}, timeout=30)
            cid = r.json().get("id")
            if cid:
                print(f"  first comment posted: {cid}", flush=True)
                # Best-effort pin (UI-only on most objects; ignore any failure).
                try:
                    requests.post(f"{FB_GRAPH}/{cid}",
                                  data={"is_pinned": "true", "access_token": token}, timeout=15)
                except Exception:
                    pass
                return cid
            print(f"  first comment attempt {attempt + 1} failed: {r.status_code} {r.text[:140]}",
                  flush=True)
        except Exception as e:
            print(f"  first comment attempt {attempt + 1} error: {e}", flush=True)
        if attempt < 2:
            time.sleep(5)
    print("  first comment gave up (non-critical)", flush=True)
    return None


def _posted():
    try:
        return set(json.loads(LOG.read_text()))
    except Exception:
        return set()


def _mark(p):
    s = _posted()
    s.add(str(p))
    LOG.write_text(json.dumps(sorted(s), indent=2))


def _ep_of(path):
    """Episode number from an output dir like viking_ep05_shieldwall_20260808_120000.

    The zero-padding is what distinguishes a series build from the pre-series `viking_ep1_<stamp>`
    dirs, which were the old two-shot format and must not be posted as season 1.
    """
    m = re.match(r"viking_ep(\d{2})_", path.parent.name)
    return int(m.group(1)) if m else None


def _episodes_on_disk():
    """Built episodes as (ep_number, final.mp4), newest build per episode, in season order."""
    best = {}
    for f in ROOT.glob("output/viking_ep*_*/final.mp4"):
        n = _ep_of(f)
        if n is None:
            continue
        if n not in best or f.stat().st_mtime > best[n].stat().st_mtime:
            best[n] = f
    return sorted(best.items())


def _caption(n):
    ep = saga.BY_EP.get(n)
    if not ep:
        return DEFAULT_CAPTION
    tease = saga.next_tease(ep)
    body = ep["caption"]
    if tease.startswith("NEXT"):
        body += f"\n\n▶ {tease.replace('NEXT  ', 'NEXT: ')} — follow so you don't miss it."
    else:
        body += "\n\n▶ Season 1 complete. Follow — Season 2 is coming."
    return body


def status():
    built = _episodes_on_disk()
    done = _posted()
    print(f"{saga.SERIES} — Season {saga.SEASON} ({len(saga.EPISODES)} episodes written)", flush=True)
    for ep in saga.EPISODES:
        f = dict(built).get(ep["ep"])
        state = "not built" if not f else ("POSTED" if str(f) in done else "ready")
        print(f"  EP.{ep['ep']:>2} {ep['title']:<16} {state}", flush=True)
    nxt = next((n for n, f in built if str(f) not in done), None)
    print(f"\nnext up: {'EP.' + str(nxt) if nxt else 'nothing — run build_viking_batch.py'}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ep", type=int, help="force a specific episode number")
    ap.add_argument("--status", action="store_true", help="show build/post state and exit")
    args = ap.parse_args()

    if args.status:
        status()
        return

    built = _episodes_on_disk()
    done = _posted()
    if args.ep:
        pick = next(((n, f) for n, f in built if n == args.ep), None)
        if not pick:
            print(f"EP.{args.ep} is not built yet — "
                  f"run: python build_viking_batch.py --eps {args.ep}", flush=True)
            return
    else:
        pick = next(((n, f) for n, f in built if str(f) not in done), None)
    if not pick:
        print("every built episode has been posted — run build_viking_batch.py to make more",
              flush=True)
        return

    n, video = pick
    ep = saga.BY_EP.get(n)
    title = f"{saga.SERIES} — EP.{n}" + (f" {ep['title']}" if ep else "")
    cap = _caption(n) + "\n\n#" + " #".join(HASHTAGS)
    print(f"posting {title}\n  {video}", flush=True)

    from modules.uploader_facebook import upload_to_facebook
    res = asyncio.run(upload_to_facebook(
        video_path=str(video), title=title, description=cap, niche="blissful_moments",
        hashtags=HASHTAGS, is_reel=True))
    print("POST:", res, flush=True)
    if isinstance(res, dict) and res.get("status") == "uploaded":
        _mark(video)
        print(f"posted + logged: EP.{n}", flush=True)
        # Seed the comment thread with the episode's engagement question (the fix for our 0-comment
        # posts). Uses ep['comment'] — the per-episode bait that was previously unused.
        if ep and ep.get("comment"):
            _first_comment(res.get("post_id"), ep["comment"])


if __name__ == "__main__":
    main()

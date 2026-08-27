"""
Remove the duplicate card posts from Mzansi Careers, keeping every reel.

Careers published each opportunity twice - a photo card, then the same
caption again as a reel about a minute later. The code is fixed (one post per
job), but twenty pairs are already live and a feed that reads as doubled
undermines the one thing this page sells.

Safety, in order:

  1. A card is only removed when a reel carrying the SAME opening text is
     confirmed present. A job must never lose its only representation.
  2. Every post is fetched in full and written to data/deleted_posts.json
     BEFORE anything is deleted.
  3. --apply is required. Without it this prints the plan and touches nothing.

    python dedupe_careers_posts.py            # plan only
    python dedupe_careers_posts.py --apply
"""
import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv()
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
SAST = timezone(timedelta(hours=2))
GRAPH = "https://graph.facebook.com/v21.0"
NICHE = "motivation"
BACKUP = ROOT / "data" / "deleted_posts.json"
# How much of the caption must agree, and how close in time.
#
# The first plan matched on 40 characters and would have deleted FOUR real
# jobs. Every DPSA caption opens "JOB ALERT - DEPARTMENT", so forty characters
# only reached the department name: four different Forestry vacancies looked
# identical to each other, and were paired with a fifth unrelated Forestry
# reel posted six days later. The job TITLE is what distinguishes them, and it
# sits well past character forty.
#
# Time is the stronger signal anyway. A real duplicate is the same job posted
# twice by one run, about sixty seconds apart. Anything hours or days apart is
# two different vacancies, however similar the text looks.
MATCH_CHARS = 140
MAX_PAIR_GAP_MIN = 15     # a true card/reel pair goes out within a minute


def _creds():
    return (os.getenv("FB_PAGE_ID_" + NICHE, ""),
            os.getenv("FB_PAGE_TOKEN_" + NICHE)
            or os.getenv("FB_ACCESS_TOKEN_" + NICHE) or "")


def _head(msg):
    return " ".join((msg or "").split())[:MATCH_CHARS].strip()


async def plan(limit=100):
    pid, tok = _creds()
    if not (pid and tok):
        return [], "no credentials"
    async with httpx.AsyncClient(timeout=40) as cl:
        r = await cl.get(GRAPH + "/" + pid + "/posts",
                         params={"fields": "id,created_time,message,"
                                           "status_type",
                                 "limit": limit, "access_token": tok})
        posts = r.json().get("data", [])

    cards = [p for p in posts if p.get("status_type") == "added_photos"]
    reels = [p for p in posts if p.get("status_type") == "added_video"]

    def when(p):
        try:
            return datetime.fromisoformat(
                p["created_time"].replace("Z", "+00:00")).astimezone(SAST)
        except Exception:
            return None

    pairs, claimed = [], set()
    for c in cards:
        h = _head(c.get("message"))
        cw = when(c)
        if not h or cw is None:
            continue      # nothing safe to match on - leave it alone
        for v in reels:
            if v["id"] in claimed:
                continue          # one reel can only justify ONE deletion
            vw = when(v)
            if vw is None or _head(v.get("message")) != h:
                continue
            if abs((vw - cw).total_seconds()) / 60 > MAX_PAIR_GAP_MIN:
                continue          # too far apart to be the same run
            pairs.append((c, v))
            claimed.add(v["id"])
            break
    return pairs, ""


async def apply(pairs):
    pid, tok = _creds()
    log = []
    if BACKUP.exists():
        try:
            log = json.loads(BACKUP.read_text(encoding="utf-8"))
            if not isinstance(log, list):
                log = []
        except Exception:
            log = []

    done, failed = 0, 0
    async with httpx.AsyncClient(timeout=40) as cl:
        for card, reel in pairs:
            # full copy first - deletion is not reversible
            try:
                full = (await cl.get(GRAPH + "/" + card["id"],
                                     params={"fields": "id,message,"
                                                       "created_time,"
                                                       "permalink_url",
                                             "access_token": tok})).json()
            except Exception:
                full = card
            log.append({"deleted_at": datetime.now(SAST).isoformat(),
                        "reason": "duplicate card - the reel below carries "
                                  "the same job",
                        "kept_reel_id": reel["id"],
                        "post": full})
            BACKUP.parent.mkdir(exist_ok=True)
            BACKUP.write_text(json.dumps(log, indent=2, ensure_ascii=False),
                              encoding="utf-8")
            try:
                d = await cl.delete(GRAPH + "/" + card["id"],
                                    params={"access_token": tok})
                ok = d.status_code == 200
            except Exception:
                ok = False
            done += ok
            failed += (not ok)
            print(("  deleted " if ok else "  FAILED  ") + card["id"]
                  + "   kept reel " + reel["id"])
    return done, failed


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int, default=100)
    a = ap.parse_args()

    pairs, err = await plan(a.limit)
    if err:
        print("[Dedupe] " + err)
        return 1
    print(f"[Dedupe] {len(pairs)} card(s) have a matching reel and can go:")
    for c, v in pairs:
        print(f"  {c['created_time'][:16]}  card {c['id']}"
              f"  ->  keeps reel {v['id']}")
        print(f"      {_head(c.get('message'))}")
    if not pairs:
        print("  nothing to do")
        return 0
    if not a.apply:
        print("\nPLAN ONLY — rerun with --apply to delete")
        return 0

    done, failed = await apply(pairs)
    print(f"\n[Dedupe] deleted {done}, failed {failed}, "
          f"backed up to {BACKUP}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

"""
Engagement posts — light player-talk posts that keep the page conversational
AND keep us on pace for the weekly Facebook post target.

Owner spec (2026-08-17): "post image or pure text, comment after, that's it —
we need to always reach the weekly target, always check that."

Every run:
  1. counts this week's page posts via the Graph API
  2. compares against the weekly target's expected pace (default 53/week —
     Business Suite's weekly plan number, override FB_WEEKLY_POST_TARGET)
  3. if BEHIND pace, publishes 1-2 quick engagement posts:
       - PLAYER PHOTO: licensed photo of an in-form starter + rate/debate ask
       - PURE TEXT: a debate question built from live squads/fixtures
     each seeded with a follow-up comment (family-we-chat rule)
  4. if ON pace, does nothing — matchday days need no filler

Scheduled 3x daily. Usage: python build_engagement_post.py [--force]
"""
import asyncio
import json
import os
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from dotenv import load_dotenv
load_dotenv()

import requests

PAGE_ID = os.getenv("FB_PAGE_ID_sa_pulse", "")
TOKEN = os.getenv("FB_PAGE_TOKEN_sa_pulse", "")
TARGET = int(os.getenv("FB_WEEKLY_POST_TARGET", "53"))
GRAPH = "https://graph.facebook.com/v24.0"
STATE = Path("data/engagement_state.json")
MAX_PER_RUN = 2
BIG3 = ["chiefs", "pirates", "sundowns"]

TEXT_TEMPLATES = [
    "{p1} or {p2} — who starts in YOUR XI? 👇⚽",
    "Honest question, PSL family: is {p1} the most underrated player in the league right now? 👇",
    "Rate {club}'s season so far out of 10. No lies. 👇",
    "One January signing that fixes {club}. Go. 👇",
    "{p1} at his best vs {p2} at his best — who wins the league for you? 👇",
    "Fill in the blank: {club} will finish the season in position ___ 👇",
    "Unpopular opinion time: drop a {club} take you'll get attacked for 👇🔥",
]
COMMENT_SEEDS = [
    "We'll pin the best answer 👀",
    "Genesis News is reading every reply 👇",
    "Wrong answers only in THIS comment's replies 😂",
    "Tag a fan who needs to see this",
]


def _state() -> dict:
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except Exception:
        return {"club_idx": 0, "tpl_idx": 0}


def _save(s: dict):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(s, indent=2), encoding="utf-8")


def week_progress() -> tuple[int, int]:
    """(posts_this_week, expected_by_now) against the weekly target."""
    now = datetime.now()
    monday = (now - timedelta(days=now.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0)
    r = requests.get(f"{GRAPH}/{PAGE_ID}/published_posts",
                     params={"since": int(monday.timestamp()),
                             "limit": 100, "access_token": TOKEN},
                     timeout=30).json()
    count = len(r.get("data", []))
    week_frac = (now - monday).total_seconds() / (7 * 86400)
    expected = round(TARGET * week_frac)
    return count, expected


async def post_text(msg: str) -> str:
    r = requests.post(f"{GRAPH}/{PAGE_ID}/feed",
                      data={"message": msg, "access_token": TOKEN},
                      timeout=30).json()
    return r.get("id", "")


async def make_player_photo_post(club: str) -> bool:
    from modules.psl_squads import get_squad, recent_starts
    from modules.free_press_images import photos_for_player, download
    from modules.club_brand import CLUB_BRAND
    from matchday import _post_photo

    starts, _ = await recent_starts(club)
    squad = await get_squad(club)
    ranked = sorted(squad, key=lambda p: -starts.get(
        p["name"].split()[-1].lower(), 0))
    for p in ranked[:6]:
        hits = await photos_for_player(p["name"], 1)
        if not hits:
            continue
        path = await download(hits[0], Path("output/engagement") /
                              f"{p['name'].split()[-1]}.jpg")
        if not path:
            continue
        name = p["name"]
        cname = CLUB_BRAND.get(club, {}).get("name", club.title())
        caption = (f"{name}. {cname}. Rate his season out of 10 — "
                   f"and be honest 👇⚽\n\nphoto: {hits[0]['credit']}\n"
                   f"#PSL #BetwayPremiership #{cname.replace(' ', '')}")
        r = await _post_photo(str(path), caption,
                              random.choice(COMMENT_SEEDS))
        if r.get("status") == "uploaded":
            print(f"[Engage] player photo post: {name}")
            return True
    return False


async def make_text_post() -> bool:
    from modules.psl_squads import get_squad, recent_starts
    from modules.club_brand import CLUB_BRAND
    from modules.uploader_facebook import post_comment

    s = _state()
    club = BIG3[s["club_idx"] % len(BIG3)]
    tpl = TEXT_TEMPLATES[s["tpl_idx"] % len(TEXT_TEMPLATES)]
    s["club_idx"] += 1
    s["tpl_idx"] += 1
    _save(s)

    starts, _ = await recent_starts(club)
    squad = await get_squad(club)
    ranked = sorted(squad, key=lambda p: -starts.get(
        p["name"].split()[-1].lower(), 0))
    names = [p["name"] for p in ranked[:4]] or ["the keeper", "the striker"]
    cname = CLUB_BRAND.get(club, {}).get("name", club.title())
    msg = tpl.format(p1=names[0], p2=names[1] if len(names) > 1 else names[0],
                     club=cname)
    msg += "\n\n#PSL #BetwayPremiership"
    pid = await post_text(msg)
    if pid:
        print(f"[Engage] text post: {msg[:60]!r}")
        await post_comment(pid, random.choice(COMMENT_SEEDS), "sa_pulse")
        return True
    return False


async def main(force: bool = False):
    if not PAGE_ID or not TOKEN:
        print("[Engage] page not configured")
        return
    count, expected = week_progress()
    print(f"[Engage] week: {count} posted, {expected} expected "
          f"(target {TARGET}/week)")
    if count >= expected and not force:
        print("[Engage] on pace — nothing to do")
        return
    deficit = max(1, expected - count) if not force else 1
    todo = min(MAX_PER_RUN, deficit)
    made = 0
    for i in range(todo):
        kind = random.random() < 0.5
        try:
            if kind:
                s = _state()
                club = BIG3[s["club_idx"] % len(BIG3)]
                ok = await make_player_photo_post(club)
                if not ok:
                    ok = await make_text_post()
            else:
                ok = await make_text_post()
            made += 1 if ok else 0
        except Exception as e:
            print(f"[Engage] post failed: {str(e)[:120]}")
        await asyncio.sleep(5)
    print(f"[Engage] published {made} engagement post(s)")


if __name__ == "__main__":
    try:
        asyncio.run(main("--force" in sys.argv))
    except Exception as e:
        try:
            from modules.notify_whatsapp import notify_failure
            notify_failure("engagement",
                           f"ENGAGEMENT POST FAILED: {type(e).__name__}: {str(e)[:130]}")
        except Exception:
            pass
        raise

"""Cross-pipeline guards for pages that BOTH schedulers post to (owner 2026-10-13).

Genesis News (niche sa_pulse) is served by this repo (countdowns, matchday cards, engagement posts) and by the
traderadar-ai page engine (newsclips slots + game-day mode). The traderadar-ai side already checks the page's own
published posts before posting (quiet window), so it sees ours. This module gives our side the same rules:

  quiet_ok(niche, minutes)      False if the page published anything (not a cover/profile update) in the last N minutes
  story_taken(niche, title)     True if traderadar-ai's story lock already holds this story on that page today
  claim(niche, title, kind)     record our post in the same story lock so the other engine never repeats it
  gameday_owns(fid, part)       True when traderadar-ai's real-footage game-day mode covers that part of a fixture
                                ("prematch", "lineup", "live", "result"), so matchday.py must not post it twice

Never raises: a guard that cannot check lets the post through (a missed check must not silence a page).
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

TR_CONTENT = Path(r"C:\Users\PenuelM\Documents\traderadar-ai\content")
GAMEDAY_OWNED = TR_CONTENT / "pages" / "out" / "gameday_owned.json"
NICHE_PAGE = {"sa_pulse": "genesis_news", "genesis": "genesis_news", "tech_news": "tech_pulse_africa"}
GRAPH = "https://graph.facebook.com/v24.0"


def _page(niche: str) -> tuple[str, str]:
    return os.getenv(f"FB_PAGE_ID_{niche}", ""), os.getenv(f"FB_PAGE_TOKEN_{niche}", "")


def last_post_age_min(niche: str) -> float | None:
    pid, tok = _page(niche)
    if not pid or not tok:
        return None
    try:
        r = requests.get(f"{GRAPH}/{pid}/published_posts",
                         params={"fields": "created_time,attachments{type}", "limit": 5, "access_token": tok},
                         timeout=30).json()
        for p in r.get("data") or []:
            types = {a.get("type") for a in (p.get("attachments") or {}).get("data", [])}
            if types & {"profile_media", "cover_photo"}:
                continue
            t = datetime.strptime(p["created_time"], "%Y-%m-%dT%H:%M:%S%z")
            return (datetime.now(timezone.utc) - t).total_seconds() / 60
    except Exception as e:  # noqa: BLE001
        print(f"[Guard] quiet check failed (letting it through): {str(e)[:100]}")
    return None


def quiet_ok(niche: str, minutes: float) -> bool:
    age = last_post_age_min(niche)
    if age is not None and age < minutes:
        print(f"[Guard] {niche}: page posted {age:.0f} min ago (< {minutes:.0f}) - deferring")
        return False
    return True


def _storylock():
    p = str(TR_CONTENT / "newsclips")
    if p not in sys.path:
        sys.path.insert(0, p)
    import storylock  # noqa: PLC0415
    return storylock


def _today() -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=2)).strftime("%Y-%m-%d")  # SAST day


def story_taken(niche: str, title: str, url: str = "") -> bool:
    page = NICHE_PAGE.get(niche)
    if not page:
        return False
    try:
        L = _storylock()
        me = {"title": title, "url": url, "slug": ""}
        return any(c["page"] == page and L.same_story(me, c) for c in L._load().get(_today(), []))
    except Exception as e:  # noqa: BLE001
        print(f"[Guard] storylock read failed: {str(e)[:100]}")
        return False


def claim(niche: str, title: str, kind: str, url: str = "", slug: str = "") -> None:
    page = NICHE_PAGE.get(niche)
    if not page:
        return
    try:
        L = _storylock()
        L.claim(page, {"title": title, "url": url}, 10.0, _today(), slug=slug or kind, kind=f"aivf_{kind}")
    except Exception as e:  # noqa: BLE001
        print(f"[Guard] storylock claim failed: {str(e)[:100]}")


def gameday_owns(fixture_id: str, part: str) -> bool:
    try:
        d = json.loads(GAMEDAY_OWNED.read_text(encoding="utf-8"))
        return part in (d.get(str(fixture_id)) or {}).get("parts", [])
    except Exception:
        return False

"""
What people ASK us to post next.

Every careers post ends by asking which field to cover next. This reads the
replies, counts the fields people name, and hands that list to the feed so
the next posts are the ones the audience actually asked for.

Only category words are read — nothing else from a comment is stored or
published, and no comment text is ever reproduced in a post.
"""
import json
import os
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

import requests

from modules.careers_categories import CATEGORIES

STATE = Path(__file__).parent.parent / "data" / "careers_requests.json"
GRAPH = "https://graph.facebook.com/v24.0"
NICHE = "motivation"          # Mzansi Careers page
LOOKBACK_POSTS = 12


def _page():
    return os.getenv(f"FB_PAGE_ID_{NICHE}"), os.getenv(f"FB_PAGE_TOKEN_{NICHE}")


def collect(limit_posts: int = LOOKBACK_POSTS) -> dict:
    """Tally the fields people named in recent comments."""
    pid, tok = _page()
    if not (pid and tok):
        return {}
    tally = Counter()
    seen = 0
    try:
        posts = requests.get(f"{GRAPH}/{pid}/posts",
                             params={"fields": "id", "limit": limit_posts,
                                     "access_token": tok},
                             timeout=60).json().get("data", [])
        for p in posts:
            cs = requests.get(f"{GRAPH}/{p['id']}/comments",
                              params={"fields": "message", "limit": 50,
                                      "access_token": tok},
                              timeout=45).json().get("data", [])
            for c in cs:
                msg = (c.get("message") or "")
                seen += 1
                for key, _label, rx in CATEGORIES:
                    if rx.search(msg):
                        tally[key] += 1
    except Exception as e:
        print(f"[CareersRequests] could not read comments: {e}")
        return {}

    out = {"checked_at": datetime.now().isoformat(),
           "comments_read": seen, "tally": dict(tally)}
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(out, indent=2), encoding="utf-8")
    if tally:
        print("[CareersRequests] most requested: " + ", ".join(
            f"{k} x{v}" for k, v in tally.most_common(4)))
    return out


def requested(max_age_hours: int = 24) -> list[str]:
    """Categories people asked for, most wanted first. Refreshes if stale."""
    data = {}
    if STATE.exists():
        try:
            data = json.loads(STATE.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    stale = True
    if data.get("checked_at"):
        try:
            stale = (datetime.now() - datetime.fromisoformat(
                data["checked_at"])) > timedelta(hours=max_age_hours)
        except Exception:
            stale = True
    if stale:
        data = collect() or data
    tally = Counter(data.get("tally") or {})
    return [k for k, _ in tally.most_common(3)]


if __name__ == "__main__":
    collect()

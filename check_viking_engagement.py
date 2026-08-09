#!/usr/bin/env python
"""Track engagement on the live SAGA OF THE NORTH posts and report day-over-day movement.

First run saves a baseline snapshot (logs/viking_engagement_baseline.json). Every later run pulls
fresh numbers, diffs them against the baseline, and writes a human-readable report
(logs/viking_engagement_report.md) plus prints it. Auto-discovers Viking reels by caption keyword,
so new episodes are picked up with no edits.

  python check_viking_engagement.py            # snapshot + report (baseline on first run)
  python check_viking_engagement.py --reset    # overwrite the baseline with current numbers
"""
import argparse
import json
import os
import re
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv()

GRAPH = "https://graph.facebook.com/v24.0"
TOKEN = os.getenv("FB_PAGE_TOKEN_blissful_moments")
PAGE_ID = os.getenv("FB_PAGE_ID_blissful_moments") or "112465853843545"
BASELINE = ROOT / "logs" / "viking_engagement_baseline.json"
REPORT = ROOT / "logs" / "viking_engagement_report.md"
BASELINE.parent.mkdir(exist_ok=True)

# A reel counts as "Viking" if its caption hits one of these — covers the series episodes and the
# pre-series two-shots (THE OATH / THE PYRE / SAGA intro), and future episodes automatically.
KEYWORDS = ["saga of the north", "first light", "the forge", "the oath", "the storm",
            "shield wall", "betrayal", "the fall", "outnumbered", "pyre", "the return",
            "northmen", "viking"]


def _is_viking(caption: str) -> bool:
    c = (caption or "").lower()
    return any(k in c for k in KEYWORDS)


def _fetch():
    """Return {reel_id: {label, views, likes, comments}} for every live Viking reel."""
    out = {}
    url = f"{GRAPH}/{PAGE_ID}/video_reels"
    params = {"fields": "id,created_time,description,views,likes.summary(true),comments.summary(true)",
              "limit": 50, "access_token": TOKEN}
    for _ in range(5):  # paginate a little, tolerate hiccups
        r = requests.get(url, params=params, timeout=30)
        data = r.json()
        if "error" in data:
            print(f"[engagement] API error: {str(data['error'])[:160]}")
            break
        for v in data.get("data", []):
            cap = v.get("description", "")
            if not _is_viking(cap):
                continue
            label = re.sub(r"\s+", " ", cap).strip()[:40] or v["id"]
            out[v["id"]] = {
                "label": label,
                "views": v.get("views") or 0,
                "likes": v.get("likes", {}).get("summary", {}).get("total_count", 0),
                "comments": v.get("comments", {}).get("summary", {}).get("total_count", 0),
            }
        nxt = data.get("paging", {}).get("next")
        if not nxt:
            break
        url, params = nxt, {}
        time.sleep(1)
    return out


def _load_baseline():
    try:
        return json.loads(BASELINE.read_text())
    except Exception:
        return None


def _reply_stats_lines():
    """The OTHER half of the loop: auto-reply stats for the Viking page from community_manager.

    Pulls the 7-day community_stats for blissful_moments so the report shows both seeding (comments
    on our posts) AND the auto-reply bot (replies the page sent to real commenters). Fully
    best-effort — any import/DB problem just drops this section, never breaks the engagement report.
    """
    try:
        from modules.community_manager import get_reply_stats
        s = (get_reply_stats(7) or {}).get("blissful_moments")
        if not s:
            return ["", "## Auto-reply (7-day)", "No community-manager activity recorded yet for the "
                    "Viking page (it replies to real commenters, not the page's own seeds)."]
        return ["", "## Auto-reply (7-day)",
                f"- comments found: {s.get('total_comments', 0)}",
                f"- replies sent: {s.get('total_replies', 0)}",
                f"- negative flagged: {s.get('negative', 0)}  |  escalations: {s.get('escalations', 0)}",
                "", "Replies sent > 0 means real people are commenting and the bot is answering in "
                "the skald voice — the full seed→reply→reach loop is live."]
    except Exception as e:
        return ["", f"_(auto-reply stats unavailable: {str(e)[:80]})_"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true", help="overwrite baseline with current numbers")
    args = ap.parse_args()

    if not TOKEN:
        print("[engagement] FB_PAGE_TOKEN_blissful_moments not set — cannot pull.")
        return

    now = _fetch()
    if not now:
        print("[engagement] no Viking reels found (or API blocked).")
        return

    base = None if args.reset else _load_baseline()

    if base is None:
        BASELINE.write_text(json.dumps({"stamp": time.strftime("%Y-%m-%d %H:%M"), "posts": now},
                                       indent=2))
        print(f"[engagement] baseline saved: {len(now)} Viking reel(s) at {time.strftime('%H:%M')}")
        for pid, d in now.items():
            print(f"  {d['label']:42} views={d['views']} likes={d['likes']} comments={d['comments']}")
        return

    # Diff against baseline.
    b_posts = base.get("posts", {})
    lines = [f"# SAGA OF THE NORTH — engagement check",
             f"baseline: {base.get('stamp')}  |  now: {time.strftime('%Y-%m-%d %H:%M')}", "",
             "| Post | Views | Likes | Comments |",
             "|---|---|---|---|"]
    tv = tl = tc = 0
    for pid, d in sorted(now.items(), key=lambda kv: -kv[1]["views"]):
        bd = b_posts.get(pid, {"views": 0, "likes": 0, "comments": 0})
        dv = d["views"] - bd["views"]; dl = d["likes"] - bd["likes"]; dc = d["comments"] - bd["comments"]
        tv += dv; tl += dl; tc += dc
        lines.append(f"| {d['label']} | {d['views']} (+{dv}) | {d['likes']} (+{dl}) | "
                     f"{d['comments']} (+{dc}) |")
    lines += ["", f"**Totals since baseline:** +{tv} views, +{tl} likes, +{tc} comments.",
              "", "Reading it: comments climbing above the one seeded comment means real people are "
              "replying — the seeding worked. Flat comments but rising views means the prompt needs "
              "to be easier to answer (binary / one-word)."]
    lines += _reply_stats_lines()
    report = "\n".join(lines)
    REPORT.write_text(report, encoding="utf-8")
    # ascii-safe console echo
    print(report.encode("ascii", "ignore").decode())
    print(f"\n[engagement] report written -> {REPORT}")


if __name__ == "__main__":
    main()

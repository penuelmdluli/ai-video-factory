"""
What actually works, measured - and fed back into what we post next.

Until now the slot router rotated formats on fixed rules. It was never told
which ones the fans respond to, so a format that pulls 11 comments and a
format that pulls 1 got the same share of the week. The owner's read on
2026-08-27 was that the participation posts beat the news posts; the first
pull of real numbers agreed:

    WHO STARTS HERE? SHABALALA or DUBA      21 likes   11 comments
    news reel (Sources: Goal)                5 likes    3 comments
    Love and Peace                           1 like     0 comments

So this module measures every post, scores each format, and hands the router
weights. Nobody has to notice a trend and act on it.

Scoring reflects what this page is FOR. A comment is worth more than a like
because a comment is a person taking part; a share is worth most because it
puts us in front of someone who does not follow us yet. Likes are cheap.

Two guards against fooling ourselves:
  * a post younger than MIN_AGE_H is not scored at all - engagement arrives
    over hours, and a two-hour-old post always looks like a failure
  * a format needs MIN_POSTS before its score is trusted; below that it keeps
    a neutral weight so a single lucky post cannot take over the schedule
"""
import json
import os
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).parent.parent
DB = ROOT / "data" / "growth_analytics.db"
WEIGHTS = ROOT / "data" / "format_weights.json"
GRAPH = "https://graph.facebook.com/v21.0"
SAST = timezone(timedelta(hours=2))

MIN_AGE_H = 12      # below this a post has not finished earning engagement
MIN_POSTS = 3       # below this a format's average is noise
W_COMMENT, W_SHARE, W_LIKE = 3.0, 5.0, 1.0

# Format fingerprints, most specific first. These match what our own builders
# actually write, so a post can be scored without us having tagged it at
# publish time - which matters because the back catalogue was never tagged.
SIGNATURES = [
    ("fancall", re.compile(r"who starts here|one shirt, two names", re.I)),
    ("debate", re.compile(r"midfielders|defenders|forwards|keepers"
                          r".{0,40}(who starts|for one shirt)", re.I)),
    ("countdown", re.compile(r"\bdays? to go\b|\bkick-?off in\b|countdown", re.I)),
    ("lineup", re.compile(r"confirmed (xi|line-?up)|predicted (xi|line-?up)|"
                          r"team sheet", re.I)),
    ("result", re.compile(r"full[- ]time|final score|ft:", re.I)),
    ("prematch", re.compile(r"pre-?match|preview|head to head|winning record", re.I)),
    ("legend", re.compile(r"legend|on this day|remember when", re.I)),
    ("news", re.compile(r"sources?:|report:|according to", re.I)),
]


def classify(message: str) -> str:
    """Best guess at which format produced this post."""
    m = message or ""
    for name, rx in SIGNATURES:
        if rx.search(m):
            return name
    return "other"


def _conn():
    c = sqlite3.connect(str(DB), timeout=10)
    c.execute("""CREATE TABLE IF NOT EXISTS post_metrics (
        post_id TEXT, niche TEXT, content_type TEXT, message TEXT,
        created_at TEXT, reach INTEGER, impressions INTEGER,
        engagement INTEGER, likes INTEGER, comments INTEGER, shares INTEGER,
        engagement_rate REAL, collected_at TEXT)""")
    c.execute("""CREATE UNIQUE INDEX IF NOT EXISTS idx_pm_post
                 ON post_metrics(post_id)""")
    return c


async def collect(niche: str, limit: int = 100) -> int:
    """Pull engagement for recent posts and store it. Returns rows written."""
    pid = os.getenv("FB_PAGE_ID_" + niche, "")
    tok = (os.getenv("FB_PAGE_TOKEN_" + niche)
           or os.getenv("FB_ACCESS_TOKEN_" + niche) or "")
    if not (pid and tok):
        return 0

    fields = ("id,message,created_time,shares,"
              "comments.summary(true),likes.summary(true)")
    async with httpx.AsyncClient(timeout=40) as cl:
        r = await cl.get(GRAPH + "/" + pid + "/posts",
                         params={"fields": fields, "limit": limit,
                                 "access_token": tok})
        data = r.json()
    if "error" in data:
        print("[Intel] " + niche + ": " + str(data["error"].get("message")))
        return 0

    now = datetime.now(SAST).isoformat()
    rows = 0
    c = _conn()
    for p in data.get("data", []):
        msg = p.get("message") or ""
        likes = ((p.get("likes") or {}).get("summary") or {}).get("total_count", 0)
        comments = ((p.get("comments") or {}).get("summary") or {}).get("total_count", 0)
        shares = (p.get("shares") or {}).get("count", 0)
        eng = likes + comments + shares
        c.execute("""INSERT INTO post_metrics
            (post_id, niche, content_type, message, created_at, reach,
             impressions, engagement, likes, comments, shares,
             engagement_rate, collected_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(post_id) DO UPDATE SET
              likes=excluded.likes, comments=excluded.comments,
              shares=excluded.shares, engagement=excluded.engagement,
              collected_at=excluded.collected_at""",
                  (p["id"], niche, classify(msg), msg[:500],
                   p.get("created_time", ""), 0, 0, eng, likes, comments,
                   shares, 0.0, now))
        rows += 1
    c.commit()
    c.close()
    return rows


def _age_hours(created: str):
    try:
        when = datetime.fromisoformat(
            created.replace("Z", "+00:00")).astimezone(SAST)
        return (datetime.now(SAST) - when).total_seconds() / 3600
    except Exception:
        return None


def scores(niche: str, days: int = 30) -> dict:
    """{format: {posts, avg_score, comments, shares, likes}} - mature posts only."""
    c = _conn()
    cutoff = (datetime.now(SAST) - timedelta(days=days)).isoformat()
    rows = c.execute("""SELECT content_type, created_at, likes, comments, shares
                        FROM post_metrics WHERE niche=? AND created_at>=?""",
                     (niche, cutoff)).fetchall()
    c.close()

    agg = {}
    for fmt, created, likes, comments, shares in rows:
        age = _age_hours(created)
        if age is None or age < MIN_AGE_H:
            continue          # still earning - scoring it now would be unfair
        a = agg.setdefault(fmt, {"posts": 0, "likes": 0, "comments": 0,
                                 "shares": 0, "total": 0.0})
        a["posts"] += 1
        a["likes"] += likes
        a["comments"] += comments
        a["shares"] += shares
        a["total"] += (comments * W_COMMENT + shares * W_SHARE
                       + likes * W_LIKE)
    for a in agg.values():
        a["avg_score"] = round(a["total"] / a["posts"], 2) if a["posts"] else 0
    return agg


def weights(niche: str, days: int = 30) -> dict:
    """{format: multiplier} centred on 1.0, for the slot router to bias with.

    A format with too few mature posts gets exactly 1.0 - unproven is not the
    same as bad, and a new format must be allowed to earn its place rather
    than being starved on one weak sample.
    """
    sc = scores(niche, days)
    proven = {f: a for f, a in sc.items() if a["posts"] >= MIN_POSTS}
    if not proven:
        return {f: 1.0 for f in sc}
    mean = sum(a["avg_score"] for a in proven.values()) / len(proven)
    out = {}
    for f, a in sc.items():
        if f not in proven or mean <= 0:
            out[f] = 1.0
        else:
            # clamp: even a runaway winner never fully crowds the others out
            out[f] = round(min(2.0, max(0.4, a["avg_score"] / mean)), 3)
    return out


def save_weights(niche: str, days: int = 30) -> dict:
    w = weights(niche, days)
    payload = {}
    if WEIGHTS.exists():
        try:
            payload = json.loads(WEIGHTS.read_text(encoding="utf-8"))
        except Exception:
            payload = {}
    payload[niche] = {"at": datetime.now(SAST).isoformat(),
                      "weights": w, "detail": scores(niche, days)}
    WEIGHTS.parent.mkdir(exist_ok=True)
    WEIGHTS.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return w


def weight_for(niche: str, fmt: str) -> float:
    """What the router asks. Never raises, never blocks a build."""
    try:
        payload = json.loads(WEIGHTS.read_text(encoding="utf-8"))
        return float(payload.get(niche, {}).get("weights", {}).get(fmt, 1.0))
    except Exception:
        return 1.0


def fan_topics(niche: str, limit: int = 300) -> list:
    """What supporters keep raising, from their own comments.

    Engagement says which FORMAT works; this says what they want it to be
    ABOUT. Both are needed - the right format on a subject nobody cares about
    still lands flat.
    """
    c = sqlite3.connect(str(DB), timeout=10)
    try:
        rows = c.execute("""SELECT comment_text FROM replied_comments
                            WHERE niche=? ORDER BY replied_at DESC LIMIT ?""",
                         (niche, limit)).fetchall()
    except Exception:
        return []
    finally:
        c.close()

    stop = {"the", "and", "you", "for", "that", "this", "with", "they", "are",
            "was", "our", "his", "her", "not", "but", "all", "who", "why",
            "how", "can", "will", "must", "one", "get", "out", "now", "she",
            "him", "just", "like", "have", "from", "what", "them", "your"}
    tally = {}
    for (t,) in rows:
        for w in re.findall(r"[A-Za-z]{3,}", (t or "").lower()):
            if w in stop:
                continue
            tally[w] = tally.get(w, 0) + 1
    return sorted(tally.items(), key=lambda kv: -kv[1])[:15]

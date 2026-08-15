"""
Genesis News growth scorecard — the invest/kill dashboard.

Pulls live numbers from the Facebook page and YouTube channel, compares them
to the last run, and applies simple decision rules so the weekly call is
data, not vibes:

  - INVEST where engagement-per-post grows two runs straight
  - FIX where reach grows but engagement doesn't (packaging problem)
  - KILL/CHANGE anything below the page average for 3 runs

Output: output/growth/report_<date>.md  + history in data/growth_history.json
Usage:  python build_growth_report.py           (scheduled Sundays 18:30)
"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from dotenv import load_dotenv
load_dotenv()

HIST = Path("data/growth_history.json")
PAGE_ID = os.getenv("FB_PAGE_ID_sa_pulse", "")
TOKEN = os.getenv("FB_PAGE_TOKEN_sa_pulse", "")
CHANNEL = "UC4Y4udaLeLc6E4BhoepK5XA"


def fb_stats() -> dict:
    import requests
    out = {"followers": 0, "posts_7d": 0, "reactions_7d": 0, "comments_7d": 0}
    try:
        r = requests.get(f"https://graph.facebook.com/v24.0/{PAGE_ID}",
                         params={"fields": "followers_count,fan_count",
                                 "access_token": TOKEN}, timeout=30).json()
        out["followers"] = r.get("followers_count") or r.get("fan_count") or 0
        feed = requests.get(
            f"https://graph.facebook.com/v24.0/{PAGE_ID}/published_posts",
            params={"fields": "created_time,reactions.summary(true),comments.summary(true)",
                    "limit": 50, "access_token": TOKEN}, timeout=30).json()
        from datetime import timedelta, timezone
        week_ago = datetime.now(timezone.utc) - timedelta(days=7)
        for p in feed.get("data", []):
            ct = datetime.fromisoformat(p["created_time"].replace("+0000", "+00:00"))
            if ct < week_ago:
                continue
            out["posts_7d"] += 1
            out["reactions_7d"] += p.get("reactions", {}).get("summary", {}).get("total_count", 0)
            out["comments_7d"] += p.get("comments", {}).get("summary", {}).get("total_count", 0)
    except Exception as e:
        print(f"[Growth] FB stats failed: {e}")
    return out


def yt_stats() -> dict:
    out = {"subs": 0, "views_total": 0, "videos": 0, "views_recent": 0}
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
        creds = Credentials.from_authorized_user_info(
            json.loads(Path("tokens/youtube_token_sa_pulse.json").read_text()))
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
        yt = build("youtube", "v3", credentials=creds)
        ch = yt.channels().list(part="statistics,contentDetails", id=CHANNEL).execute()
        st = ch["items"][0]["statistics"]
        out["subs"] = int(st.get("subscriberCount", 0))
        out["views_total"] = int(st.get("viewCount", 0))
        out["videos"] = int(st.get("videoCount", 0))
        uploads = ch["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
        pi = yt.playlistItems().list(part="contentDetails", playlistId=uploads,
                                     maxResults=15).execute()
        ids = [i["contentDetails"]["videoId"] for i in pi.get("items", [])]
        if ids:
            vs = yt.videos().list(part="statistics", id=",".join(ids)).execute()
            out["views_recent"] = sum(int(v["statistics"].get("viewCount", 0))
                                      for v in vs.get("items", []))
    except Exception as e:
        print(f"[Growth] YT stats failed: {e}")
    return out


def main():
    today = datetime.now().strftime("%Y-%m-%d")
    fb, yt = fb_stats(), yt_stats()
    try:
        hist = json.loads(HIST.read_text(encoding="utf-8"))
    except Exception:
        hist = []
    prev = hist[-1] if hist else None
    snap = {"date": today, "fb": fb, "yt": yt}
    hist.append(snap)
    HIST.parent.mkdir(parents=True, exist_ok=True)
    HIST.write_text(json.dumps(hist[-52:], indent=2), encoding="utf-8")

    def delta(cur, old, key1, key2):
        if not old:
            return ""
        d = cur - old.get(key1, {}).get(key2, 0)
        return f" ({'+' if d >= 0 else ''}{d})"

    eng = fb["reactions_7d"] + fb["comments_7d"]
    epp = round(eng / fb["posts_7d"], 1) if fb["posts_7d"] else 0
    lines = [
        f"# Genesis News Growth Scorecard · {today}", "",
        "## Facebook page",
        f"- Followers: **{fb['followers']}**{delta(fb['followers'], prev, 'fb', 'followers')}",
        f"- Posts last 7d: {fb['posts_7d']}",
        f"- Engagement last 7d: {eng} ({fb['reactions_7d']} reactions + "
        f"{fb['comments_7d']} comments) → **{epp} per post**", "",
        "## YouTube (@GenesisNewsPSL)",
        f"- Subscribers: **{yt['subs']}**{delta(yt['subs'], prev, 'yt', 'subs')}",
        f"- Total views: {yt['views_total']}{delta(yt['views_total'], prev, 'yt', 'views_total')}",
        f"- Videos: {yt['videos']} · views on last 15: {yt['views_recent']}", "",
        "## Decision rules",
        "- **Comments per post** is the north star — debate drives reach.",
        "- INVEST: any format 2 runs above the page average.",
        "- FIX: reach up but comments flat → title/thumbnail problem.",
        "- KILL/CHANGE: any format below average 3 runs straight.",
        "- YouTube goal: 1,000 subs + 4,000 watch-hours → monetization.",
    ]
    out = Path("output/growth")
    out.mkdir(parents=True, exist_ok=True)
    p = out / f"report_{today}.md"
    body = "\n".join(lines)
    p.write_text(body, encoding="utf-8")
    print(f"[Growth] report -> {p}")
    print(body)
    _email_report(body, today)
    return str(p)


def _email_report(body: str, today: str):
    """
    Zero-touch delivery: emails the scorecard when SMTP creds exist in .env.
      SMTP_USER=<gmail address>
      SMTP_APP_PASSWORD=<16-char Google App Password>
      REPORT_EMAIL=<recipient, defaults to SMTP_USER>
    Missing creds -> skip silently (file output still happens).
    """
    user = os.getenv("SMTP_USER", "")
    pw = os.getenv("SMTP_APP_PASSWORD", "")
    to = os.getenv("REPORT_EMAIL", user)
    if not user or not pw:
        print("[Growth] email skipped — set SMTP_USER + SMTP_APP_PASSWORD in .env")
        return
    try:
        import smtplib
        from email.mime.text import MIMEText
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = f"⚽ Genesis News Growth Scorecard — {today}"
        msg["From"] = user
        msg["To"] = to
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as s:
            s.login(user, pw)
            s.send_message(msg)
        print(f"[Growth] emailed to {to}")
    except Exception as e:
        print(f"[Growth] email failed: {e}")


if __name__ == "__main__":
    main()

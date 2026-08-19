"""
Cadence check — did going to five reels a day help or dilute?

Pulls real numbers from both platforms and splits them at the moment the
schedule changed (19 Aug 2026), so the decision is made on data rather than
on the feeling that more posts must mean more reach.

    python build_perf_report.py
"""
import os
import sys
from datetime import datetime
from pathlib import Path
from statistics import median

sys.path.insert(0, str(Path(__file__).parent))
from dotenv import load_dotenv
load_dotenv()

import requests  # noqa: E402

SPLIT = "2026-08-19"          # the day the cadence went to 5/day
LOG = Path("logs/perf_report.txt")


def facebook():
    tok = os.getenv("FB_PAGE_TOKEN_sa_pulse")
    pid = os.getenv("FB_PAGE_ID_sa_pulse")
    r = requests.get(f"https://graph.facebook.com/v24.0/{pid}/video_reels",
                     params={"fields": "id,title,created_time,views,"
                                       "likes.summary(true)",
                             "limit": 40, "access_token": tok},
                     timeout=90).json()
    out = []
    for v in r.get("data", []):
        out.append({
            "when": v["created_time"][:10],
            "views": int(v.get("views") or 0),
            "likes": ((v.get("likes", {}).get("summary") or {})
                      .get("total_count") or 0),
            "title": (v.get("title") or "")[:44],
        })
    return out


def youtube():
    from modules.uploader_youtube import _get_youtube_service
    yt = _get_youtube_service("sa_pulse")
    up = (yt.channels().list(part="contentDetails", mine=True).execute()
          ["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"])
    ids = [i["contentDetails"]["videoId"] for i in
           yt.playlistItems().list(part="contentDetails", playlistId=up,
                                   maxResults=50).execute()["items"]]
    vs = yt.videos().list(part="snippet,statistics",
                          id=",".join(ids[:50])).execute()["items"]
    return [{"when": v["snippet"]["publishedAt"][:10],
             "views": int(v["statistics"].get("viewCount", 0)),
             "likes": int(v["statistics"].get("likeCount", 0)),
             "title": v["snippet"]["title"][:44]} for v in vs]


def split(rows):
    before = [r for r in rows if r["when"] < SPLIT]
    after = [r for r in rows if r["when"] >= SPLIT]
    return before, after


def summarise(name, rows, out):
    before, after = split(rows)
    out.append(f"\n{name}")
    for label, group in (("before 5/day", before), ("since 5/day", after)):
        if not group:
            out.append(f"  {label:12} no posts")
            continue
        v = [r["views"] for r in group]
        out.append(f"  {label:12} {len(group):>2} posts | "
                   f"median {int(median(v)):>5} views | "
                   f"best {max(v):>5} | total {sum(v):>6}")
    if before and after:
        mb = median([r["views"] for r in before])
        ma = median([r["views"] for r in after])
        verdict = ("HOLDING UP" if ma >= mb * 0.8 else
                   "DILUTING — fewer, stronger posts look better")
        out.append(f"  -> median moved {int(mb)} -> {int(ma)}   {verdict}")


def main():
    out = [f"CADENCE CHECK — {datetime.now():%Y-%m-%d %H:%M}",
           f"(split at {SPLIT}, when the schedule went to five reels a day)"]
    try:
        summarise("FACEBOOK REELS", facebook(), out)
    except Exception as e:
        out.append(f"\nFACEBOOK unavailable: {e}")
    try:
        summarise("YOUTUBE SHORTS", youtube(), out)
    except Exception as e:
        out.append(f"\nYOUTUBE unavailable: {e}")
    text = "\n".join(out)
    print(text)
    LOG.parent.mkdir(exist_ok=True)
    LOG.write_text(text, encoding="utf-8")
    try:
        from modules.notify_whatsapp import notify
        notify(text[:1200])
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())

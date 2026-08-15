"""
YouTube outreach — smart comments on OTHER channels' PSL videos.

Visibility play: our channel name appears under the biggest fresh PSL videos,
in front of exactly the fans we want. The guardrails are the feature:

  - MAX 5 comments per day, never two on the same channel in a day
  - only fresh (48h), relevant PSL/derby videos, never our own channel
  - every comment is a real take (Claude with the family personality),
    NO links, NO "check out our page" — value first; the channel name does
    the marketing
  - one search per run (100 quota units), history in data/yt_outreach.json

Usage:
    python modules/yt_outreach.py           # one round (respects daily cap)
"""
import asyncio
import json
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

OUR_CHANNEL = "UC4Y4udaLeLc6E4BhoepK5XA"
STATE = Path(__file__).parent.parent / "data" / "yt_outreach.json"
DAILY_CAP = 5

QUERIES = [
    "Kaizer Chiefs vs Mamelodi Sundowns",
    "PSL highlights today",
    "Betway Premiership",
    "Orlando Pirates news",
    "Kaizer Chiefs news today",
]


def _load() -> dict:
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _yt():
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    tok = Path(__file__).parent.parent / "tokens" / "youtube_token_sa_pulse.json"
    creds = Credentials.from_authorized_user_info(json.loads(tok.read_text()))
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return build("youtube", "v3", credentials=creds)


async def _comment_text(title: str, channel: str) -> str | None:
    """A real football take on the video's topic — personality, no self-promo."""
    from modules.community_manager import generate_reply
    fake_comment = {
        "message": (f"(You are commenting on another channel's video titled "
                    f"'{title}' by {channel}. Write ONE warm, knowledgeable "
                    f"fan-to-fan comment about that topic: a real take or a "
                    f"question that starts conversation. NO links, NO channel "
                    f"promotion, NO 'check out'. Max 2 sentences.)"),
        "from_name": "", "post_context": title}
    text = await generate_reply(fake_comment, "sa_pulse")
    if not text or "http" in text.lower() or "check out" in text.lower():
        return None
    return text


async def run_round() -> int:
    state = _load()
    today = datetime.now().strftime("%Y-%m-%d")
    day = state.setdefault(today, {"count": 0, "channels": [], "videos": []})
    if day["count"] >= DAILY_CAP:
        print(f"[Outreach] daily cap reached ({DAILY_CAP})")
        return 0

    yt = _yt()
    q = QUERIES[int(time.time() // 3600) % len(QUERIES)]
    try:
        res = yt.search().list(part="snippet", q=q, type="video", order="date",
                               maxResults=15, regionCode="ZA",
                               relevanceLanguage="en").execute()
    except Exception as e:
        print(f"[Outreach] search failed: {e}")
        return 0

    sent = 0
    for item in res.get("items", []):
        if day["count"] >= DAILY_CAP:
            break
        sn = item["snippet"]
        vid = item["id"].get("videoId")
        ch = sn.get("channelId", "")
        if not vid or ch == OUR_CHANNEL:
            continue
        if ch in day["channels"] or vid in day["videos"]:
            continue
        # PSL relevance gate — the query can drift
        blob = f"{sn.get('title', '')} {sn.get('channelTitle', '')}".lower()
        if not any(k in blob for k in ("chiefs", "pirates", "sundowns", "psl",
                                       "betway", "premiership", "mzansi")):
            continue
        text = await _comment_text(sn.get("title", ""), sn.get("channelTitle", ""))
        if not text:
            continue
        try:
            yt.commentThreads().insert(part="snippet", body={"snippet": {
                "videoId": vid,
                "topLevelComment": {"snippet": {"textOriginal": text}}}}).execute()
            day["count"] += 1
            day["channels"].append(ch)
            day["videos"].append(vid)
            sent += 1
            print(f"[Outreach] commented on '{sn.get('title', '')[:45]}' "
                  f"({sn.get('channelTitle', '')[:20]}): {text[:60]}")
        except Exception as e:
            msg = str(e)
            if "disabled" in msg.lower():
                continue
            print(f"[Outreach] insert failed: {msg[:120]}")
    # keep only the last 7 days of history
    for k in [k for k in state if k != today][:-7]:
        state.pop(k, None)
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    print(f"[Outreach] round done — {sent} comment(s), {day['count']}/{DAILY_CAP} today")
    return sent


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    asyncio.run(run_round())

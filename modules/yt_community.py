"""
YouTube community responder — nobody talks to Genesis News and gets silence.

Fetches comments on every video of the channel, replies to any top-level
comment we haven't answered (family-in-the-group-chat tone, via the same
Claude→Gemini→template chain as the Facebook manager), and remembers what it
has replied to in data/yt_replied.json.

Quota: uses playlistItems/commentThreads (1 unit each) + comments.insert
(50 units) — none of which touch the search quota that sweeps burn.

Usage:
    python modules/yt_community.py          # one round
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

CHANNEL = "UC4Y4udaLeLc6E4BhoepK5XA"
TOKEN = Path(__file__).parent.parent / "tokens" / "youtube_token_sa_pulse.json"
REPLIED = Path(__file__).parent.parent / "data" / "yt_replied.json"
MAX_REPLIES_PER_RUN = 20


def _yt():
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    creds = Credentials.from_authorized_user_info(
        json.loads(TOKEN.read_text(encoding="utf-8")))
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return build("youtube", "v3", credentials=creds)


def _load_replied() -> set:
    try:
        return set(json.loads(REPLIED.read_text(encoding="utf-8")))
    except Exception:
        return set()


def _save_replied(ids: set):
    REPLIED.parent.mkdir(parents=True, exist_ok=True)
    REPLIED.write_text(json.dumps(sorted(ids)), encoding="utf-8")


async def run_round() -> int:
    yt = _yt()
    replied = _load_replied()

    # our uploads
    ch = yt.channels().list(part="contentDetails", id=CHANNEL).execute()
    uploads = ch["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
    vids = []
    pi = yt.playlistItems().list(part="contentDetails", playlistId=uploads,
                                 maxResults=25).execute()
    vids = [i["contentDetails"]["videoId"] for i in pi.get("items", [])]

    from modules.community_manager import generate_reply, analyze_sentiment
    sent = 0
    for vid in vids:
        if sent >= MAX_REPLIES_PER_RUN:
            break
        try:
            threads = yt.commentThreads().list(
                part="snippet,replies", videoId=vid, maxResults=50,
                textFormat="plainText").execute().get("items", [])
        except Exception as e:
            if "disabled" in str(e).lower():
                continue
            print(f"[YTCommunity] threads failed for {vid}: {e}")
            continue
        for th in threads:
            if sent >= MAX_REPLIES_PER_RUN:
                break
            top = th["snippet"]["topLevelComment"]
            cid = top["id"]
            if cid in replied:
                continue
            sn = top["snippet"]
            if sn.get("authorChannelId", {}).get("value") == CHANNEL:
                continue                     # our own comment
            # already replied by us in-thread?
            ours = any(r["snippet"].get("authorChannelId", {}).get("value") == CHANNEL
                       for r in th.get("replies", {}).get("comments", []))
            if ours:
                replied.add(cid)
                continue
            comment = {"message": sn.get("textDisplay", ""),
                       "from_name": sn.get("authorDisplayName", ""),
                       "post_context": "PSL football video"}
            text = await generate_reply(comment, "sa_pulse")
            if not text:
                replied.add(cid)
                continue
            try:
                yt.comments().insert(part="snippet", body={"snippet": {
                    "parentId": cid, "textOriginal": text}}).execute()
                sent += 1
                replied.add(cid)
                print(f"[YTCommunity] replied to {sn.get('authorDisplayName','?')}: "
                      f"{text[:60]}")
            except Exception as e:
                print(f"[YTCommunity] reply failed: {e}")
    _save_replied(replied)
    print(f"[YTCommunity] round done — {sent} replies")
    return sent


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    asyncio.run(run_round())

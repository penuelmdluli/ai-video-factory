"""
Playlists — every upload lands in a series, on both platforms.

YouTube: videos are added to a named playlist ("Genesis News — PSL Reels" for
shorts, "Match Highlights & Shows" for long-form). Playlists are created once
and cached in data/playlists.json.

Facebook: reels are added to a page video playlist (series) via the
video_lists edge — best-effort, some page types don't expose it.

Usage:
    from modules.playlists import add_youtube, add_facebook
    add_youtube(video_id, shorts=True)
    add_facebook(video_id)
"""
import json
import os
from pathlib import Path

CACHE = Path(__file__).parent.parent / "data" / "playlists.json"
YT_SHORTS_TITLE = "Genesis News — PSL Reels"
YT_LONG_TITLE = "Match Previews, Highlights & Shows"
FB_LIST_TITLE = "Genesis News — PSL Reels"


def _cache() -> dict:
    try:
        return json.loads(CACHE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(c: dict):
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(c, indent=2), encoding="utf-8")


def _yt():
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    tok = Path(__file__).parent.parent / "tokens" / "youtube_token_sa_pulse.json"
    creds = Credentials.from_authorized_user_info(json.loads(tok.read_text()))
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return build("youtube", "v3", credentials=creds)


def add_youtube(video_id: str, shorts: bool = True) -> bool:
    """Add an uploaded video to the right channel playlist (created once)."""
    title = YT_SHORTS_TITLE if shorts else YT_LONG_TITLE
    key = f"yt:{title}"
    c = _cache()
    try:
        yt = _yt()
        pid = c.get(key)
        if not pid:
            r = yt.playlists().insert(part="snippet,status", body={
                "snippet": {"title": title,
                            "description": "Daily PSL news, live matchday "
                                           "coverage and analysis from Genesis News."},
                "status": {"privacyStatus": "public"}}).execute()
            pid = r["id"]
            c[key] = pid
            _save(c)
            print(f"[Playlists] created YouTube playlist: {title}")
        yt.playlistItems().insert(part="snippet", body={
            "snippet": {"playlistId": pid,
                        "resourceId": {"kind": "youtube#video",
                                       "videoId": video_id}}}).execute()
        print(f"[Playlists] YT {video_id} -> {title}")
        return True
    except Exception as e:
        print(f"[Playlists] YouTube failed: {str(e)[:120]}")
        return False


def add_facebook(video_id: str) -> bool:
    """Add a page video/reel to the page's Genesis playlist (best-effort)."""
    import requests
    page_id = os.getenv("FB_PAGE_ID_sa_pulse", "")
    token = os.getenv("FB_PAGE_TOKEN_sa_pulse", "")
    if not page_id or not token:
        return False
    c = _cache()
    try:
        pid = c.get("fb:list")
        if not pid:
            r = requests.post(
                f"https://graph.facebook.com/v24.0/{page_id}/video_lists",
                data={"title": FB_LIST_TITLE, "video_ids": json.dumps([video_id]),
                      "description": "Daily PSL news and matchday coverage.",
                      "access_token": token}, timeout=30)
            if r.status_code != 200:
                print(f"[Playlists] FB list create failed: {r.text[:120]}")
                return False
            pid = r.json().get("id")
            c["fb:list"] = pid
            _save(c)
            print(f"[Playlists] created FB playlist: {FB_LIST_TITLE}")
        r = requests.post(
            f"https://graph.facebook.com/v24.0/{pid}/videos",
            data={"video_ids": json.dumps([video_id]),
                  "access_token": token}, timeout=30)
        ok = r.status_code == 200
        print(f"[Playlists] FB {video_id} -> playlist: {'ok' if ok else r.text[:100]}")
        return ok
    except Exception as e:
        print(f"[Playlists] Facebook failed: {str(e)[:120]}")
        return False

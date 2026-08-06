"""Daily maintenance (runs after quota reset):
  1. Re-apply Pip's custom thumbnail + playlists (failed on the quota collision).
  2. Private the remaining war/news videos on the AlphaZone (deep_chill) channel,
     in quota-safe batches (cap per run) so it never breaks daily posting.
Idempotent: once everything's done it's a harmless no-op.
"""
import json, sys
from pathlib import Path
ROOT = Path(r"C:\Users\PenuelM\Documents\ai-video-factory")
sys.path.insert(0, str(ROOT))
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import config

SCOPES = getattr(config, "YOUTUBE_SCOPES",
                 ["https://www.googleapis.com/auth/youtube.upload",
                  "https://www.googleapis.com/auth/youtube"])
PER_RUN_PRIVATE = 60   # keep well under daily quota so posting still works

def svc(token):
    return build("youtube", "v3",
                 credentials=Credentials.from_authorized_user_file(str(ROOT / "tokens" / token), SCOPES))

# ── 1. Fix Pip ──
def fix_pip():
    vid = "8Rgg-neaA7E"
    thumb = ROOT / "output" / "zuzu" / "pip_50455_20260731_010459" / "thumb.jpg"
    try:
        yt = svc("youtube_token_kids_songs.json")
        if thumb.exists():
            yt.thumbnails().set(videoId=vid,
                media_body=MediaFileUpload(str(thumb), mimetype="image/jpeg")).execute()
            print("[maint] Pip thumbnail set")
        for pl in ["PLZa1ZtuM9pzc", "PLCV4FgxG3s4Y"]:
            try:
                yt.playlistItems().insert(part="snippet", body={"snippet": {"playlistId": pl,
                    "resourceId": {"kind": "youtube#video", "videoId": vid}}}).execute()
            except Exception:
                pass
        print("[maint] Pip playlists done")
        (ROOT / "maintenance" / "pip_fixed.flag").write_text("done")
    except Exception as e:
        print("[maint] pip fix err:", str(e)[:100])

# ── 2. Private remaining war videos ──
def clean_war():
    f = ROOT / "maintenance" / "war_ids.json"
    if not f.exists():
        return
    ids = json.load(open(f))
    try:
        yt = svc("youtube_token_deep_chill.json")
    except Exception as e:
        print("[maint] deep_chill token err:", str(e)[:80]); return
    done = 0; remaining = []
    for vid in ids:
        if done >= PER_RUN_PRIVATE:
            remaining.append(vid); continue
        try:
            v = yt.videos().list(part="status", id=vid).execute()["items"]
            if not v:
                continue
            st = dict(v[0]["status"])
            if st.get("privacyStatus") == "private":
                continue
            st["privacyStatus"] = "private"
            yt.videos().update(part="status", body={"id": vid, "status": st}).execute()
            done += 1
        except Exception as e:
            if "quota" in str(e).lower():
                remaining.append(vid); print("[maint] quota hit — stopping"); break
            remaining.append(vid)
    json.dump(remaining, open(f, "w"))
    print(f"[maint] privated {done} war videos this run; {len(remaining)} remain")

if __name__ == "__main__":
    if not (ROOT / "maintenance" / "pip_fixed.flag").exists():
        fix_pip()
    clean_war()
    print("[maint] DONE")

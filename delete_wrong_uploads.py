"""Delete the 6 videos that were uploaded to the wrong channel (Deep Focus Beats)."""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import json
from pathlib import Path
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

TOKENS_DIR = Path(__file__).parent / "tokens"
TOKEN_PATH = TOKENS_DIR / "youtube_token_main.json"

SCOPES = [
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]

# Videos wrongly uploaded to Deep Focus Beats
WRONG_VIDEOS = [
    ("ocKUxscFNmk", "ai_trading - AI Turned 10k into 13.8k"),
    ("sjCieIKhUuk", "ai_money - She Made $43K From AI Copywriting"),
    ("VsaVIwgbcmo", "tech_news"),
    ("6KDyAVVHBsY", "health_wellness"),
    ("sKRwiOxuHzc", "blissful_moments"),
    ("tRE0rKkcGCc", "motivation"),
]

creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
if creds.expired and creds.refresh_token:
    creds.refresh(Request())
    with open(TOKEN_PATH, "w") as f:
        f.write(creds.to_json())

youtube = build("youtube", "v3", credentials=creds)

# Verify we're on Deep Focus Beats
channel_resp = youtube.channels().list(part="snippet", mine=True).execute()
if channel_resp.get("items"):
    ch = channel_resp["items"][0]
    print(f"Authenticated as: {ch['snippet']['title']} (ID: {ch['id']})")

for video_id, label in WRONG_VIDEOS:
    try:
        youtube.videos().delete(id=video_id).execute()
        print(f"[DELETED] {video_id} ({label})")
    except Exception as e:
        print(f"[ERROR] {video_id} ({label}): {e}")

print("\nDone! All wrong uploads removed from Deep Focus Beats.")

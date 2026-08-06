"""Authenticate ONE YouTube brand channel. Opens browser for OAuth.

Usage: python auth_one_channel.py <niche>
Example: python auth_one_channel.py ai_trading
"""
import sys
import io
import json
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

ROOT_DIR = Path(__file__).parent
TOKENS_DIR = ROOT_DIR / "tokens"
CLIENT_SECRET_PATH = TOKENS_DIR / "youtube_client_secret.json"

SCOPES = [
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]

NICHE_CHANNELS = {
    "ai_trading": ("Beast Mode Academy", "UC4Y4udaLeLc6E4BhoepK5XA"),
    "ai_money": ("Smart Money AI", "UCOfKMxPVvraa6q1XEolvedg"),
    "tech_news": ("Tech Pulse Africa", "UCN56RIHQ5UNCI-o5OtHNAYw"),
    "motivation": ("Elevate You", "UCb6vhwP8oKjcqUBri0Zd_Ew"),
    "health_wellness": ("Herbal Organic Life", "UCs3Y2sZ0ImXQ9QEwR5gFHfw"),
    "blissful_moments": ("Blissful Moments", "UCPNgMBuOOUQ5-lvdm5miruQ"),
    "deep_chill": ("Deep Chill", "UCEBYlpBOjEOZBJ8EG999yWA"),
    "kids_songs": ("Zuzu & Friends", "UClg-hsIwpJk1yG3CUI3FMMg"),
}

niche = sys.argv[1] if len(sys.argv) > 1 else None
if not niche or niche not in NICHE_CHANNELS:
    print(f"Usage: python auth_one_channel.py <niche>")
    print(f"Valid niches: {', '.join(NICHE_CHANNELS.keys())}")
    sys.exit(1)

channel_name, channel_id = NICHE_CHANNELS[niche]

print(f"\n=== Authenticating: {channel_name} ({niche}) ===")
print(f"Expected Channel ID: {channel_id}")
print(f"\nBrowser will open. SELECT '{channel_name}' channel!\n")

flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET_PATH), SCOPES)
creds = flow.run_local_server(port=8765, open_browser=True)

# Save token
token_path = TOKENS_DIR / f"youtube_token_{niche}.json"
with open(token_path, "w") as f:
    f.write(creds.to_json())

# Verify
youtube = build("youtube", "v3", credentials=creds)
resp = youtube.channels().list(part="snippet", mine=True).execute()

if resp.get("items"):
    actual_name = resp["items"][0]["snippet"]["title"]
    actual_id = resp["items"][0]["id"]
    print(f"\nAuthenticated as: {actual_name} (ID: {actual_id})")
    if actual_id == channel_id:
        print(f"[OK] Correct! Token saved for {niche}.")
    else:
        print(f"[WARNING] Wrong channel! Expected {channel_name} ({channel_id})")
        print(f"          Got {actual_name} ({actual_id})")
        print(f"Token saved anyway — re-run if needed.")
else:
    print("Could not verify channel. Token saved.")

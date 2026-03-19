"""
YouTube OAuth Server — Per-channel authentication for brand channels.

Usage:
  python auth_youtube_server.py --niche ai_trading
  (Opens browser — user must select the correct brand channel)

  python auth_youtube_server.py --niche all
  (Runs OAuth for each niche one at a time)
"""
import sys
import io
import argparse
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
}

PORT = 8765


def auth_niche(niche: str) -> bool:
    """Run OAuth for a single niche/brand channel."""
    channel_name, channel_id = NICHE_CHANNELS[niche]

    print(f"\n{'='*60}")
    print(f"  Authenticating: {channel_name} ({niche})")
    print(f"  Expected Channel ID: {channel_id}")
    print(f"{'='*60}")
    print(f"\n  IMPORTANT: When the browser opens, click your Google account,")
    print(f"  then SELECT the '{channel_name}' channel (NOT your personal account).")
    print(f"  Look for the channel picker after signing in.\n")

    input(f"  Press Enter when ready to authenticate {channel_name}...")

    flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET_PATH), SCOPES)
    creds = flow.run_local_server(port=PORT, open_browser=True, prompt="consent")

    # Save token for this niche
    token_path = TOKENS_DIR / f"youtube_token_{niche}.json"
    with open(token_path, "w") as f:
        f.write(creds.to_json())

    # Verify which channel we authenticated as
    youtube = build("youtube", "v3", credentials=creds)
    resp = youtube.channels().list(part="snippet", mine=True).execute()

    if resp.get("items"):
        actual_name = resp["items"][0]["snippet"]["title"]
        actual_id = resp["items"][0]["id"]
        print(f"\n  Authenticated as: {actual_name} (ID: {actual_id})")

        if actual_id == channel_id:
            print(f"  [OK] Correct channel for {niche}!")
            return True
        else:
            print(f"  [WARNING] Expected {channel_name} ({channel_id})")
            print(f"            Got {actual_name} ({actual_id})")
            print(f"  Token saved anyway. Re-run if this is wrong.")
            return False
    else:
        print(f"  [WARNING] Could not verify channel. Token saved.")
        return False


def main():
    parser = argparse.ArgumentParser(description="YouTube per-channel OAuth")
    parser.add_argument("--niche", required=True, help="Niche name or 'all'")
    args = parser.parse_args()

    if args.niche == "all":
        results = {}
        for niche in NICHE_CHANNELS:
            ok = auth_niche(niche)
            results[niche] = ok
        print(f"\n{'='*60}")
        print("  Authentication Summary:")
        for niche, ok in results.items():
            name = NICHE_CHANNELS[niche][0]
            status = "OK" if ok else "WRONG CHANNEL"
            print(f"    {name:25s} [{status}]")
        print(f"{'='*60}")
    else:
        if args.niche not in NICHE_CHANNELS:
            print(f"[ERROR] Unknown niche: {args.niche}")
            print(f"  Valid: {', '.join(NICHE_CHANNELS.keys())}")
            sys.exit(1)
        auth_niche(args.niche)


if __name__ == "__main__":
    main()

"""
Manual YouTube OAuth — No PKCE, no state.
Step 1: python auth_youtube_manual.py --get-url
Step 2: Visit URL, capture code from redirect
Step 3: python auth_youtube_manual.py --exchange "CODE_HERE"
"""
import json
import sys
from pathlib import Path
from urllib.parse import urlencode
import requests

ROOT_DIR = Path(__file__).parent
TOKENS_DIR = ROOT_DIR / "tokens"
CLIENT_SECRET_PATH = TOKENS_DIR / "youtube_client_secret.json"

SCOPES = [
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]

REDIRECT_URI = "http://localhost"

# Load client secret
with open(CLIENT_SECRET_PATH) as f:
    data = json.load(f)
installed = data["installed"]
CLIENT_ID = installed["client_id"]
CLIENT_SECRET = installed["client_secret"]

NICHES = ["ai_trading", "ai_money", "tech_news", "motivation", "health_wellness", "blissful_moments"]


def get_url():
    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
    }
    url = "https://accounts.google.com/o/oauth2/auth?" + urlencode(params)
    print(f"\nVisit this URL:\n{url}\n")
    print("After auth, you'll be redirected to a failing localhost page.")
    print("Copy the 'code' parameter from the URL bar.")
    return url


def exchange(code: str):
    resp = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": REDIRECT_URI,
        },
    )

    if resp.status_code != 200:
        print(f"[ERROR] Token exchange failed: {resp.text}")
        return None

    token_data = resp.json()
    print(f"[OK] Got access token: {token_data['access_token'][:30]}...")
    print(f"[OK] Got refresh token: {'yes' if token_data.get('refresh_token') else 'no'}")

    # Save in google-auth format
    creds_data = {
        "token": token_data["access_token"],
        "refresh_token": token_data.get("refresh_token"),
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scopes": SCOPES,
    }

    # Save main token
    main_path = TOKENS_DIR / "youtube_token_main.json"
    with open(main_path, "w") as f:
        json.dump(creds_data, f, indent=2)
    print(f"[OK] Main token saved: {main_path}")

    # Copy to all niches
    for niche in NICHES:
        path = TOKENS_DIR / f"youtube_token_{niche}.json"
        with open(path, "w") as f:
            json.dump(creds_data, f, indent=2)
    print(f"[OK] Token copied for all {len(NICHES)} niches")

    return creds_data


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python auth_youtube_manual.py --get-url")
        print('  python auth_youtube_manual.py --exchange "CODE"')
        sys.exit(1)

    if sys.argv[1] == "--get-url":
        get_url()
    elif sys.argv[1] == "--exchange":
        if len(sys.argv) < 3:
            print("[ERROR] Provide the auth code")
            sys.exit(1)
        exchange(sys.argv[2])
    else:
        print(f"Unknown option: {sys.argv[1]}")

"""
One-time Gmail authorisation for the health check (read-only).

Reuses the existing desktop OAuth client in tokens/youtube_client_secret.json
and writes tokens/gmail_token.json. Scope is gmail.readonly — this token can
read mail and nothing else: it cannot send, delete, or modify.

    python auth_gmail.py            # opens a browser, then saves the token
    python auth_gmail.py --check    # verify an existing token still works

If it fails with "Gmail API has not been used in project ...", open the link
in that error and enable the Gmail API for the same Google Cloud project the
YouTube client belongs to, then run this again.
"""
import argparse
import sys
from pathlib import Path

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

ROOT = Path(__file__).parent
TOKEN_PATH = ROOT / "tokens" / "gmail_token.json"
CLIENT_SECRET_PATH = ROOT / "tokens" / "youtube_client_secret.json"
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def authorise():
    if not CLIENT_SECRET_PATH.exists():
        print(f"Missing OAuth client: {CLIENT_SECRET_PATH}")
        return 1
    flow = InstalledAppFlow.from_client_secrets_file(
        str(CLIENT_SECRET_PATH), SCOPES)
    # Desktop client is registered for http://localhost, so a loopback server
    # is the supported path; port 0 lets the OS pick a free one.
    creds = flow.run_local_server(port=0, prompt="consent")
    TOKEN_PATH.parent.mkdir(exist_ok=True)
    TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
    print(f"Saved {TOKEN_PATH}")
    return check()


def check():
    if not TOKEN_PATH.exists():
        print("No token yet — run: python auth_gmail.py")
        return 1
    creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    if not creds.valid and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
    try:
        svc = build("gmail", "v1", credentials=creds, cache_discovery=False)
        prof = svc.users().getProfile(userId="me").execute()
    except Exception as e:
        print(f"Token does not work: {str(e)[:300]}")
        return 1
    print(f"OK — {prof.get('emailAddress')} "
          f"({prof.get('messagesTotal')} messages readable)")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="verify the saved token instead of re-authorising")
    args = ap.parse_args()
    sys.exit(check() if args.check else authorise())
